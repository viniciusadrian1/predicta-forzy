"""Agente do Volt: um assistente unico, orientado por ferramentas (function
calling da OpenAI).

Em vez de um roteador de palavras-chave escolhendo entre um fluxo fixo e o RAG,
o LLM e o cerebro: ele decide quando buscar os dados do ativo, consultar os
manuais, diagnosticar ou abrir uma ordem de servico - tudo numa conversa so.

Os guardrails vivem DENTRO das ferramentas: ``abrir_ordem_servico`` respeita
RBAC + confianca minima + ativo critico e pode recusar (encaminhando a um
humano); nada aciona equipamento (somente leitura); cada chamada e auditada.

Requer provider ``openai`` (a chave). Sem chave, o ``VoltService`` cai no fluxo
de regras deterministico.
"""

from __future__ import annotations

import json
import logging

from app.core.config import Settings
from app.core.rbac import has_required_role, rbac_enforced
from app.modules.assets.repository import AssetRepository
from app.modules.rag.llm import LlmClient
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.volt.diagnosis import diagnose
from app.modules.volt.models import WorkOrder
from app.modules.volt.repository import WorkOrderRepository
from app.modules.volt.schemas import (
    DiagnosisOut,
    HandoffSummary,
    VoltReply,
    VoltSource,
    VoltStateModel,
    WorkOrderOut,
)

logger = logging.getLogger("forzy.volt.agent")

_MAX_STEPS = 5  # teto de rodadas de ferramenta por turno (custo/latencia)
_HISTORY_LIMIT = 8
_SYMPTOM_ALIASES = {"vibração": "vibracao", "ruído": "ruido"}

AGENT_SYSTEM_PROMPT = (
    "Você é o Volt, assistente de manutenção do Predicta — um gêmeo digital de "
    "motores elétricos industriais. Você é UM assistente só e conversa em "
    "português do Brasil, de forma objetiva, técnica e prestativa.\n\n"
    "Você tem FERRAMENTAS para agir; use-as em vez de adivinhar:\n"
    "- dados_do_ativo(tag): placa, status e leituras atuais de um motor.\n"
    "- buscar_manuais(consulta): trechos dos manuais e da base técnica (motores "
    "WEG, vibração ISO, manutenção, plataforma).\n"
    "- diagnosticar(tag, sintoma): falha provável a partir do sintoma + sensores.\n"
    "- abrir_ordem_servico(...): abre uma OS (só após diagnosticar).\n"
    "- escalar_humano(motivo): encaminha a um técnico humano.\n\n"
    "Como agir:\n"
    "- Pergunta sobre um motor específico → chame dados_do_ativo.\n"
    "- Dúvida técnica / de manual / de como a plataforma funciona → buscar_manuais.\n"
    "- Relato de sintoma (vibração, ruído, temperatura) → diagnosticar; se o "
    "diagnóstico for confiável, ofereça abrir a OS.\n"
    "- Perguntas mistas → use mais de uma ferramenta e junte as respostas.\n\n"
    "Regras (guardrails):\n"
    "- Baseie-se nos dados retornados pelas ferramentas. NÃO invente valores, "
    "normas ou números de peça; se não tiver o dado, diga o que sabe em termos "
    "gerais e oriente onde confirmar.\n"
    "- Você apenas LÊ sensores; nunca aciona equipamento.\n"
    "- A intervenção de manutenção é sempre decidida e validada por uma pessoa. "
    "Se abrir_ordem_servico recusar (ativo crítico, baixa confiança ou permissão), "
    "explique que o caso foi encaminhado a um humano.\n"
    "- Evite responder só 'não sei': ajude no possível e aponte o próximo passo."
)

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "dados_do_ativo",
            "description": "Dados de placa, status e leituras atuais de um motor "
            "(ativo). Use quando o usuario perguntar sobre um motor especifico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "codigo do ativo, ex.: MTR-001"}
                },
                "required": ["tag"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_manuais",
            "description": "Busca trechos nos manuais tecnicos e na base de "
            "conhecimento (motores WEG, vibracao ISO 10816, manutencao, "
            "plataforma Predicta). Use para duvidas tecnicas e de procedimento.",
            "parameters": {
                "type": "object",
                "properties": {"consulta": {"type": "string"}},
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnosticar",
            "description": "Diagnostica uma falha provavel a partir do sintoma e "
            "das leituras atuais do motor. Devolve falha e nivel de confianca.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "sintoma": {
                        "type": "string",
                        "enum": ["vibracao", "ruido", "temperatura"],
                    },
                },
                "required": ["tag", "sintoma"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_ordem_servico",
            "description": "Abre uma ordem de servico para o ativo. Use apenas "
            "APOS diagnosticar. A abertura respeita guardrails (papel do usuario, "
            "confianca minima, ativo critico) e pode ser recusada, exigindo "
            "revisao humana.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "sintoma": {"type": "string"},
                    "diagnostico": {"type": "string"},
                    "confianca": {"type": "number", "description": "0 a 1"},
                },
                "required": ["tag", "sintoma", "diagnostico", "confianca"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalar_humano",
            "description": "Encaminha o atendimento a um tecnico humano com um "
            "resumo. Use quando o usuario pedir ou quando o caso exigir.",
            "parameters": {
                "type": "object",
                "properties": {"motivo": {"type": "string"}},
                "required": ["motivo"],
            },
        },
    },
]


class VoltAgent:
    """Orquestra um turno do Volt via function calling, reaproveitando os
    servicos existentes (ativos, telemetria, diagnostico, ordens de servico)."""

    def __init__(
        self,
        *,
        assets: AssetRepository,
        telemetry: TelemetryRepository,
        work_orders: WorkOrderRepository,
        settings: Settings,
        role: str,
        llm: LlmClient,
    ) -> None:
        self._assets = assets
        self._telemetry = telemetry
        self._orders = work_orders
        self._settings = settings
        self._role = role
        self._llm = llm
        self._critical = {
            t.strip() for t in settings.volt_critical_asset_tags.split(",") if t.strip()
        }
        # Acumuladores do turno (para montar a VoltReply).
        self._sources: list[VoltSource] = []
        self._diagnosis: DiagnosisOut | None = None
        self._work_order: WorkOrderOut | None = None
        self._handoff: HandoffSummary | None = None

    async def run(
        self, message: str, state: VoltStateModel, history: list[dict[str, str]]
    ) -> VoltReply:
        """Processa um turno: o LLM decide as ferramentas e responde."""
        self._state = state
        messages: list[dict] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        messages += self._history_messages(history)
        messages.append({"role": "user", "content": message})

        final_text = ""
        for _ in range(_MAX_STEPS):
            assistant = await self._llm.complete_with_tools(messages, TOOLS)
            tool_calls = assistant.get("tool_calls")
            if not tool_calls:
                final_text = (assistant.get("content") or "").strip()
                break
            messages.append(assistant)  # turno do assistente com as chamadas
            for call in tool_calls:
                name = call.get("function", {}).get("name", "")
                try:
                    args = json.loads(call.get("function", {}).get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await self._execute(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        else:
            final_text = final_text or (
                "Preciso de mais informações para concluir. Pode detalhar?"
            )

        return VoltReply(
            message=final_text or "Certo.",
            state=self._state,
            diagnosis=self._diagnosis,
            work_order=self._work_order,
            handoff=self._handoff,
            sources=self._sources,
            done=bool(self._work_order or self._handoff),
        )

    # ------------------------------------------------------------------
    def _history_messages(self, history: list[dict[str, str]]) -> list[dict]:
        """Converte o historico do front (role bot/user) para o formato do LLM."""
        out: list[dict] = []
        for item in history[-_HISTORY_LIMIT:]:
            role = "assistant" if item.get("role") in ("bot", "assistant") else "user"
            content = (item.get("content") or item.get("text") or "").strip()
            if content:
                out.append({"role": role, "content": content})
        return out

    async def _execute(self, name: str, args: dict) -> dict:
        """Executa uma ferramenta e devolve um resultado serializavel."""
        logger.info(
            "volt_tool name=%s args=%s",
            name,
            args,
            extra={"event": "volt_tool", "actor": self._role},
        )
        try:
            if name == "dados_do_ativo":
                return await self._t_dados_do_ativo(str(args.get("tag", "")))
            if name == "buscar_manuais":
                return await self._t_buscar_manuais(str(args.get("consulta", "")))
            if name == "diagnosticar":
                return await self._t_diagnosticar(
                    str(args.get("tag", "")), str(args.get("sintoma", ""))
                )
            if name == "abrir_ordem_servico":
                return await self._t_abrir_os(args)
            if name == "escalar_humano":
                return self._t_escalar(str(args.get("motivo", "")))
        except Exception:  # noqa: BLE001 - uma ferramenta nao pode derrubar o turno
            logger.exception("Falha na ferramenta %s", name)
            return {"erro": "falha ao executar a ferramenta; tente outra abordagem"}
        return {"erro": f"ferramenta desconhecida: {name}"}

    async def _t_dados_do_ativo(self, tag: str) -> dict:
        asset = await self._assets.get_asset_by_tag(tag) if tag else None
        if asset is None:
            return {"encontrado": False, "tag": tag}
        self._state.asset_tag = asset.tag
        self._state.asset_name = asset.name or asset.tag
        latest = await self._telemetry.latest(asset.tag)
        return {
            "encontrado": True,
            "tag": asset.tag,
            "nome": asset.name,
            "status": asset.status,
            "placa": {
                "fabricante": asset.manufacturer,
                "modelo": asset.model,
                "potencia_kw": asset.power_kw,
                "tensao_v": asset.voltage_v,
                "corrente_nominal_a": asset.nominal_current_a,
                "rotacao_nominal_rpm": asset.nominal_rpm,
                "classe_isolamento": asset.insulation_class,
                "grau_protecao": asset.ip_rating,
            },
            "leituras_atuais": {row["variable"]: row["value"] for row in latest},
        }

    async def _t_buscar_manuais(self, consulta: str) -> dict:
        from app.modules.rag.service import rag_service

        chunks = await rag_service.retrieve(consulta)
        trechos = []
        for chunk in chunks:
            self._sources.append(
                VoltSource(
                    document_title=chunk.document_title,
                    snippet=_snippet(chunk.text),
                )
            )
            trechos.append(
                {"fonte": chunk.document_title, "trecho": _trim(chunk.text, 700)}
            )
        # Dedup das fontes por titulo (mantendo a ordem).
        seen: set[str] = set()
        self._sources = [
            s for s in self._sources if not (s.document_title in seen or seen.add(s.document_title))
        ]
        return {"trechos": trechos} if trechos else {"trechos": [], "aviso": "nada encontrado"}

    async def _t_diagnosticar(self, tag: str, sintoma: str) -> dict:
        sintoma = _SYMPTOM_ALIASES.get(sintoma.lower(), sintoma.lower())
        asset = await self._assets.get_asset_by_tag(tag) if tag else None
        if asset is None:
            return {"erro": f"ativo {tag} nao encontrado"}
        self._state.asset_tag = asset.tag
        self._state.asset_name = asset.name or asset.tag
        self._state.symptom = sintoma
        latest = await self._telemetry.latest(asset.tag)
        readings = {row["variable"]: float(row["value"]) for row in latest}
        dx = diagnose(sintoma, readings)
        detailed = has_required_role(self._role, "engineer")
        self._diagnosis = DiagnosisOut(
            fault=dx.fault,
            confidence=round(dx.confidence, 2),
            evidence=dx.evidence,
            readings=dx.readings if detailed else None,
        )
        return {
            "falha": dx.fault,
            "confianca": round(dx.confidence, 2),
            "evidencia": dx.evidence,
            "ativo_critico": asset.tag in self._critical,
        }

    async def _t_abrir_os(self, args: dict) -> dict:
        tag = str(args.get("tag", ""))
        sintoma = str(args.get("sintoma", "")) or (self._state.symptom or "")
        diagnostico = str(args.get("diagnostico", ""))
        try:
            confianca = float(args.get("confianca", 0.0))
        except (TypeError, ValueError):
            confianca = 0.0

        # --- Guardrails ---
        if tag in self._critical:
            self._set_handoff(tag, sintoma, diagnostico, confianca, "ativo crítico")
            return {"aberta": False, "encaminhado_humano": True, "motivo": "ativo critico"}
        if confianca < self._settings.volt_confidence_threshold:
            self._set_handoff(tag, sintoma, diagnostico, confianca, "confiança abaixo do mínimo")
            return {
                "aberta": False,
                "encaminhado_humano": True,
                "motivo": f"confianca {confianca:.2f} abaixo do minimo",
            }
        if rbac_enforced() and not has_required_role(self._role, "operator"):
            self._set_handoff(tag, sintoma, diagnostico, confianca, "requer papel de operador")
            return {"aberta": False, "encaminhado_humano": True, "motivo": "requer operador"}

        # --- Abre a OS ---
        asset = await self._assets.get_asset_by_tag(tag)
        if asset is None:
            return {"aberta": False, "motivo": f"ativo {tag} nao encontrado"}
        number = await self._orders.next_number(tag)
        priority = _priority(confianca, diagnostico)
        order = await self._orders.create(
            WorkOrder(
                number=number,
                asset_tag=tag,
                symptom=sintoma or "-",
                fault=diagnostico or "-",
                confidence=round(confianca, 2),
                priority=priority,
                opened_by=f"volt/{self._role}",
            )
        )
        self._work_order = WorkOrderOut.model_validate(order)
        self._state.step = "concluido"
        return {"aberta": True, "numero": number, "prioridade": priority}

    def _t_escalar(self, motivo: str) -> dict:
        self._set_handoff(
            self._state.asset_tag,
            self._state.symptom,
            self._diagnosis.fault if self._diagnosis else None,
            self._diagnosis.confidence if self._diagnosis else None,
            motivo or "solicitação de atendimento humano",
        )
        return {"encaminhado_humano": True, "motivo": motivo}

    def _set_handoff(
        self,
        tag: str | None,
        sintoma: str | None,
        diagnostico: str | None,
        confianca: float | None,
        motivo: str,
    ) -> None:
        self._handoff = HandoffSummary(
            asset_tag=tag,
            asset_name=self._state.asset_name,
            symptom=sintoma,
            diagnosis=diagnostico,
            confidence=round(confianca, 2) if confianca is not None else None,
            actions_taken="Nenhuma ordem de serviço aberta.",
            reason=motivo,
        )
        self._state.step = "handoff"


def _priority(confidence: float, fault: str) -> str:
    severe = any(k in fault.lower() for k in ("rolamento", "desalinhamento", "sobreaquec"))
    if confidence >= 0.75 or severe:
        return "alta"
    if confidence >= 0.6:
        return "media"
    return "baixa"


def _snippet(text: str, limit: int = 220) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "..."


def _trim(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "..."
