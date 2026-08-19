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

from app.core.config import Settings
from app.core.rbac import has_required_role
from app.modules.assets.repository import AssetRepository
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.volt.diagnosis import diagnose
from app.modules.volt.models import WorkOrder
from app.modules.volt.nlu import detect_symptom, detect_urgency, extract_asset_code, wants_human
from app.modules.volt.repository import WorkOrderRepository
from app.modules.volt.schemas import (
    DiagnosisOut,
    HandoffSummary,
    VoltReply,
    VoltRequest,
    VoltStateModel,
    WorkOrderOut,
)

logger = logging.getLogger("forzy.volt")

BOT_NAME = "Volt"
SYMPTOM_CHIPS = ["Vibracao", "Ruido", "Temperatura"]
_SYMPTOM_LABEL = {"vibracao": "vibracao", "ruido": "ruido", "temperatura": "temperatura"}

GREETING = (
    "Ola! Sou o Volt, assistente de manutencao da Forzy. Eu identifico o ativo, "
    "leio os sensores e abro a ordem de servico quando o diagnostico e confiavel "
    "- casos delicados eu encaminho para um tecnico humano. Para comecar, qual e "
    "o codigo do ativo? (Ex: MTR-2291)"
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
            return self._handoff(state, reason="Solicitacao explicita do tecnico.")

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
                message="Nao consegui identificar o codigo. Informe o codigo do "
                "ativo, por favor. (Ex: MTR-2291)",
                state=state,
            )

        asset = await self._assets.get_asset_by_tag(code)
        if asset is None:
            state.not_found_attempts += 1
            # 2a falha na conferencia -> handoff (rota de fuga humana).
            if state.not_found_attempts >= 2:
                state.asset_tag = code
                return self._handoff(state, reason=f"Ativo {code} nao localizado apos conferencia.")
            return VoltReply(
                message=f"Nao encontrei o ativo {code} no sistema. Pode conferir o "
                "codigo na etiqueta do equipamento? Se preferir, posso te "
                "transferir agora para o suporte da manutencao.",
                state=state,
                quick_replies=["Falar com humano"],
            )

        state.asset_tag = asset.tag
        state.asset_name = asset.name or asset.tag
        state.not_found_attempts = 0
        state.step = "aguardando_sintoma"
        return VoltReply(
            message=f"Ativo localizado: {state.asset_name}. Qual sintoma voce esta "
            "observando - vibracao, ruido ou temperatura?",
            state=state,
            quick_replies=SYMPTOM_CHIPS,
        )

    async def _handle_symptom(self, state: VoltStateModel, message: str) -> VoltReply:
        symptom = detect_symptom(message)
        if symptom is None:
            return VoltReply(
                message="Qual desses sintomas melhor descreve o problema: vibracao, "
                "ruido ou temperatura?",
                state=state,
                quick_replies=SYMPTOM_CHIPS,
            )

        state.symptom = _SYMPTOM_LABEL[symptom]
        assert state.asset_tag is not None

        # Le os sensores do ativo (somente leitura) e diagnostica.
        latest = await self._telemetry.latest(state.asset_tag)
        readings = {row["variable"]: float(row["value"]) for row in latest}
        dx = diagnose(symptom, readings)

        # Ativo critico: sempre revisao humana, mesmo com alta confianca.
        if state.asset_tag in self._critical:
            return self._handoff(
                state,
                reason="Ativo classificado como critico para a producao.",
                diagnosis=dx.fault,
                confidence=dx.confidence,
            )

        # Confianca abaixo do limiar: escala para um humano.
        if dx.confidence < self._settings.volt_confidence_threshold:
            return self._handoff(
                state,
                reason=f"Confianca do diagnostico abaixo de "
                f"{int(self._settings.volt_confidence_threshold * 100)}%.",
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
            message=f"Diagnostico automatico: {dx.fault.lower()}, com "
            f"{int(dx.confidence * 100)}% de confianca. Ja abri a ordem de servico "
            f"{number} com prioridade {priority}. A equipe deve chegar em ate 30 minutos.",
            state=state,
            diagnosis=diagnosis_out,
            work_order=WorkOrderOut.model_validate(order),
            done=True,
        )

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
            actions_taken="Nenhuma ordem de servico aberta ainda.",
            reason=reason,
        )
        return VoltReply(
            message="Vou te transferir para um tecnico da manutencao com o resumo do "
            "atendimento - voce nao precisa repetir nada. Motivo: " + reason.lower(),
            state=state,
            handoff=summary,
            done=True,
        )

    def _restart(self, state: VoltStateModel, message: str) -> VoltReply:
        """Apos concluir/encaminhar, um novo codigo reinicia o atendimento."""
        fresh = VoltStateModel(step="aguardando_ativo")
        if message and extract_asset_code(message):
            return VoltReply.model_validate(
                {
                    **greeting_reply().model_dump(),
                    "message": "Vamos la, novo atendimento.",
                    "state": fresh,
                }
            )
        return VoltReply(
            message="Atendimento encerrado. Para registrar outro ativo, informe o "
            "codigo. (Ex: MTR-2291)",
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
