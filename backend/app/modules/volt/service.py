"""Servico do chatbot de manutencao Volt (maquina de estados guiada).

Fluxo: identificar ativo -> coletar sintoma -> diagnosticar pelos sensores ->
abrir ordem de servico (confianca alta e ativo nao-critico) ou encaminhar a um
tecnico humano. Regra de ouro: uma pergunta por vez e confirmacao no fim.

Guardrails: o Volt apenas LE sensores (nunca aciona o equipamento); diagnostico
abaixo do limiar de confianca e sempre escalado a um humano; ativos criticos
exigem revisao humana mesmo com alta confianca; cada interacao e registrada em
log de auditoria; o nivel de detalhe segue o papel do usuario (RBAC).
"""

from __future__ import annotations

import logging
import re

from app.core.config import Settings
from app.core.rbac import has_required_role, rbac_enforced
from app.modules.assets.repository import AssetRepository
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.volt.diagnosis import diagnose
from app.modules.volt.models import WorkOrder
from app.modules.volt.nlu import (
    detect_symptom,
    detect_urgency,
    extract_asset_code,
    is_question,
    wants_human,
)
from app.modules.volt.repository import WorkOrderRepository
from app.modules.volt.schemas import (
    DiagnosisOut,
    HandoffSummary,
    VoltReply,
    VoltRequest,
    VoltSource,
    VoltStateModel,
    WorkOrderOut,
)

logger = logging.getLogger("forzy.volt")

BOT_NAME = "Volt"
SYMPTOM_CHIPS = ["Vibração", "Ruído", "Temperatura"]
# Chave (do detect_symptom) -> rótulo exibido/armazenado. A chave permanece sem
# acento (usada na lógica); o rótulo é o texto que o usuário vê.
_SYMPTOM_LABEL = {"vibracao": "vibração", "ruido": "ruído", "temperatura": "temperatura"}

GREETING = (
    "Olá! Sou o Volt, assistente de manutenção da Forzy. Eu identifico o ativo, "
    "leio os sensores e abro a ordem de serviço quando o diagnóstico é confiável — "
    "e também respondo dúvidas técnicas consultando os manuais. Casos delicados eu "
    "encaminho para um técnico humano. Para começar, me passe o código do ativo "
    "(Ex: MTR-2291) ou faça uma pergunta de manutenção."
)


def greeting_reply() -> VoltReply:
    """Mensagem inicial do Volt (capacidades ditas de cara - transparencia)."""
    return VoltReply(message=GREETING, state=VoltStateModel(step="aguardando_ativo"))


class VoltService:
    """Orquestra um turno do atendimento do Volt."""

    def __init__(
        self,
        assets: AssetRepository,
        telemetry: TelemetryRepository,
        work_orders: WorkOrderRepository,
        settings: Settings,
        role: str,
    ) -> None:
        self._assets = assets
        self._telemetry = telemetry
        self._orders = work_orders
        self._settings = settings
        self._role = role
        self._critical = {
            t.strip() for t in settings.volt_critical_asset_tags.split(",") if t.strip()
        }

    # ------------------------------------------------------------------
    async def advance(self, request: VoltRequest) -> VoltReply:
        """Processa a mensagem do usuario e devolve o proximo turno."""
        message = request.message.strip()
        state = request.state.model_copy(deep=True)

        # Pedido explicito de humano, em qualquer etapa (guardrail / handoff).
        if message and wants_human(message) and state.step not in ("handoff", "concluido"):
            return self._handoff(state, reason="Solicitação explícita do técnico.")

        # Duvida tecnica (nem codigo, nem sintoma): consulta os manuais (RAG) sem
        # perder o estado do atendimento guiado - assistente unificado.
        if message and self._is_knowledge_query(message):
            reply = await self._answer_knowledge(state, message)
            self._audit(reply)
            return reply

        if state.step in ("concluido", "handoff"):
            reply = self._restart(state, message)
        elif state.step == "aguardando_ativo":
            reply = await self._handle_asset(state, message)
        elif state.step == "aguardando_sintoma":
            reply = await self._handle_symptom(state, message)
        else:  # estado desconhecido -> reinicia com seguranca
            reply = greeting_reply()

        self._audit(reply)
        return reply

    # ------------------------------ etapas ------------------------------
    async def _handle_asset(self, state: VoltStateModel, message: str) -> VoltReply:
        code = extract_asset_code(message)
        if code is None:
            return VoltReply(
                message="Não consegui identificar o código. Informe o código do "
                "ativo, por favor. (Ex: MTR-2291)",
                state=state,
            )

        asset = await self._assets.get_asset_by_tag(code)
        if asset is None:
            state.not_found_attempts += 1
            # 2a falha na conferência -> handoff (rota de fuga humana).
            if state.not_found_attempts >= 2:
                state.asset_tag = code
                return self._handoff(state, reason=f"Ativo {code} não localizado após conferência.")
            return VoltReply(
                message=f"Não encontrei o ativo {code} no sistema. Pode conferir o "
                "código na etiqueta do equipamento? Se preferir, posso te "
                "transferir agora para o suporte da manutenção.",
                state=state,
                quick_replies=["Falar com humano"],
            )

        state.asset_tag = asset.tag
        state.asset_name = asset.name or asset.tag
        state.not_found_attempts = 0
        state.step = "aguardando_sintoma"
        return VoltReply(
            message=f"Ativo localizado: {state.asset_name}. Qual sintoma você está "
            "observando — vibração, ruído ou temperatura?",
            state=state,
            quick_replies=SYMPTOM_CHIPS,
        )

    async def _handle_symptom(self, state: VoltStateModel, message: str) -> VoltReply:
        symptom = detect_symptom(message)
        if symptom is None:
            return VoltReply(
                message="Qual desses sintomas melhor descreve o problema: vibração, "
                "ruído ou temperatura?",
                state=state,
                quick_replies=SYMPTOM_CHIPS,
            )

        state.symptom = _SYMPTOM_LABEL[symptom]
        assert state.asset_tag is not None

        # Le os sensores do ativo (somente leitura) e diagnostica.
        latest = await self._telemetry.latest(state.asset_tag)
        readings = {row["variable"]: float(row["value"]) for row in latest}
        dx = diagnose(symptom, readings)

        # Ativo crítico: sempre revisão humana, mesmo com alta confiança.
        if state.asset_tag in self._critical:
            return self._handoff(
                state,
                reason="Ativo classificado como crítico para a produção.",
                diagnosis=dx.fault,
                confidence=dx.confidence,
            )

        # Confiança abaixo do limiar: escala para um humano.
        if dx.confidence < self._settings.volt_confidence_threshold:
            return self._handoff(
                state,
                reason=f"Confiança do diagnóstico abaixo de "
                f"{int(self._settings.volt_confidence_threshold * 100)}%.",
                diagnosis=dx.fault,
                confidence=dx.confidence,
            )

        # Guardrail RBAC: abrir uma OS é uma escrita — exige papel operator+.
        # (Só bloqueia com o RBAC ativo; com RBAC desligado, mantém o fluxo.)
        if rbac_enforced() and not has_required_role(self._role, "operator"):
            return self._handoff(
                state,
                reason="Abertura de ordem de serviço requer um operador.",
                diagnosis=dx.fault,
                confidence=dx.confidence,
            )

        # Confianca alta: abre a ordem de servico com prioridade automatica.
        priority = self._priority(dx.confidence, dx.fault, detect_urgency(message))
        number = await self._orders.next_number(state.asset_tag)
        order = await self._orders.create(
            WorkOrder(
                number=number,
                asset_tag=state.asset_tag,
                symptom=state.symptom,
                fault=dx.fault,
                confidence=round(dx.confidence, 2),
                priority=priority,
                opened_by=f"volt/{self._role}",
            )
        )
        state.step = "concluido"

        # RBAC: leituras dos sensores so para engenheiro/admin.
        detailed = has_required_role(self._role, "engineer")
        diagnosis_out = DiagnosisOut(
            fault=dx.fault,
            confidence=round(dx.confidence, 2),
            evidence=dx.evidence,
            readings=dx.readings if detailed else None,
        )
        return VoltReply(
            message=f"Diagnóstico automático: {dx.fault.lower()}, com "
            f"{int(dx.confidence * 100)}% de confiança. Já abri a ordem de serviço "
            f"{number} com prioridade {priority}. A equipe deve chegar em até 30 minutos.",
            state=state,
            diagnosis=diagnosis_out,
            work_order=WorkOrderOut.model_validate(order),
            done=True,
        )

    # -------------------------- base de manuais --------------------------
    @staticmethod
    def _is_knowledge_query(message: str) -> bool:
        """Dúvida técnica: uma pergunta que não é sintoma nem apenas um código.

        Uma pergunta vira consulta aos manuais mesmo quando o regex de código
        casa um trecho espúrio da frase ("operar com 30 A" -> COM-30); só segue
        o fluxo guiado quando a mensagem é essencialmente o próprio código do
        ativo (ex.: "MTR-001?").
        """
        if detect_symptom(message) is not None or not is_question(message):
            return False
        code = extract_asset_code(message)
        if code is not None:
            alnum_msg = re.sub(r"[^a-z0-9]", "", message.lower())
            alnum_code = re.sub(r"[^a-z0-9]", "", code.lower())
            if alnum_msg == alnum_code:  # a mensagem é só o código do ativo
                return False
        return True

    async def _answer_knowledge(self, state: VoltStateModel, message: str) -> VoltReply:
        """Responde uma duvida tecnica pela base de manuais (RAG), citando as fontes."""
        if not self._settings.feature_rag:
            return VoltReply(
                message="A base técnica de manuais não está habilitada neste ambiente. "
                "Posso diagnosticar um ativo pelos sensores — me passe o código. (Ex: MTR-2291)",
                state=state,
            )

        # Import local: evita acoplar o Volt ao RAG no import e respeita o feature flag.
        from app.modules.rag.schemas import ChatRequest
        from app.modules.rag.service import rag_service

        resolved_tag, asset_context = await self._asset_context(state, message)
        try:
            response = await rag_service.answer(
                ChatRequest(message=message[:2000], asset_tag=resolved_tag or state.asset_tag),
                asset_context,
            )
        except Exception:
            logger.exception("Volt: falha ao consultar a base de conhecimento")
            return VoltReply(
                message="Não consegui consultar os manuais agora. Tente de novo em "
                "instantes, ou me passe o código do ativo para eu diagnosticar pelos sensores.",
                state=state,
            )

        sources = [
            VoltSource(document_title=source.document_title, snippet=source.snippet)
            for source in response.sources[:3]
        ]
        return VoltReply(message=response.answer, state=state, sources=sources)

    async def _asset_context(
        self, state: VoltStateModel, message: str
    ) -> tuple[str | None, str | None]:
        """Contexto do ativo (placa + leituras) para fundamentar a resposta.

        Usa o ativo em atendimento ou, se a pergunta citar um codigo, esse ativo -
        assim 'me fala do MTR-001' ja chega ao LLM com os dados de placa e as
        leituras atuais, mesmo sem um manual especifico recuperado.
        Devolve (tag_resolvida, contexto).
        """
        tag = state.asset_tag or extract_asset_code(message)
        if not tag:
            return None, None
        asset = await self._assets.get_asset_by_tag(tag)
        if asset is None:
            return None, None
        lines = [f"Ativo: {asset.tag} — {asset.name}" if asset.name else f"Ativo: {asset.tag}"]
        specs = [
            ("Fabricante", asset.manufacturer),
            ("Modelo", asset.model),
            ("Potência", f"{asset.power_kw} kW" if asset.power_kw else None),
            ("Tensão", f"{asset.voltage_v} V" if asset.voltage_v else None),
            ("Corrente nominal", f"{asset.nominal_current_a} A" if asset.nominal_current_a else None),
            ("Rotação nominal", f"{asset.nominal_rpm} rpm" if asset.nominal_rpm else None),
            ("Classe de isolamento", asset.insulation_class),
            ("Grau de proteção", asset.ip_rating),
        ]
        specs_txt = "; ".join(f"{key}: {value}" for key, value in specs if value)
        if specs_txt:
            lines.append(f"Dados de placa: {specs_txt}")
        latest = await self._telemetry.latest(asset.tag)
        if latest:
            snapshot = "; ".join(f"{row['variable']}={row['value']}" for row in latest)
            lines.append(f"Leituras atuais: {snapshot}")
        return asset.tag, "\n".join(lines)

    # ------------------------------ apoio ------------------------------
    def _handoff(
        self,
        state: VoltStateModel,
        reason: str,
        diagnosis: str | None = None,
        confidence: float | None = None,
    ) -> VoltReply:
        state.step = "handoff"
        summary = HandoffSummary(
            asset_tag=state.asset_tag,
            asset_name=state.asset_name,
            symptom=state.symptom,
            diagnosis=diagnosis,
            confidence=round(confidence, 2) if confidence is not None else None,
            actions_taken="Nenhuma ordem de serviço aberta ainda.",
            reason=reason,
        )
        return VoltReply(
            message="Vou te transferir para um técnico da manutenção com o resumo do "
            "atendimento — você não precisa repetir nada. Motivo: " + reason.lower(),
            state=state,
            handoff=summary,
            done=True,
        )

    def _restart(self, state: VoltStateModel, message: str) -> VoltReply:
        """Após concluir/encaminhar, um novo código reinicia o atendimento."""
        fresh = VoltStateModel(step="aguardando_ativo")
        if message and extract_asset_code(message):
            return VoltReply.model_validate(
                {
                    **greeting_reply().model_dump(),
                    "message": "Vamos lá, novo atendimento.",
                    "state": fresh,
                }
            )
        return VoltReply(
            message="Atendimento encerrado. Para registrar outro ativo, informe o "
            "código. (Ex: MTR-2291)",
            state=fresh,
        )

    @staticmethod
    def _priority(confidence: float, fault: str, urgency: str) -> str:
        severe = any(k in fault.lower() for k in ("rolamento", "desalinhamento", "sobreaquec"))
        if urgency == "alta" or confidence >= 0.75 or severe:
            return "alta"
        if confidence >= 0.6:
            return "media"
        return "baixa"

    def _audit(self, reply: VoltReply) -> None:
        """Registra a interacao em log estruturado (rastreabilidade / guardrail)."""
        logger.info(
            "volt_interaction step=%s asset=%s symptom=%s decision=%s",
            reply.state.step,
            reply.state.asset_tag or "-",
            reply.state.symptom or "-",
            "os_aberta" if reply.work_order else "handoff" if reply.handoff else "dialogo",
            extra={
                "event": "volt_interaction",
                "actor": self._role,
                "asset_tag": reply.state.asset_tag,
            },
        )
