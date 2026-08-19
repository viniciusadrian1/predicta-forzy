"""Schemas Pydantic do chatbot Volt."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Etapas da maquina de estados do atendimento.
VoltStep = Literal[
    "aguardando_ativo",
    "aguardando_sintoma",
    "concluido",
    "handoff",
]


class VoltStateModel(BaseModel):
    """Contexto do atendimento, mantido pelo cliente entre os turnos."""

    step: VoltStep = "aguardando_ativo"
    asset_tag: str | None = None
    asset_name: str | None = None
    symptom: str | None = None
    not_found_attempts: int = 0


class VoltRequest(BaseModel):
    """Uma mensagem do usuario + o estado atual do atendimento."""

    message: str = Field(default="", max_length=1000)
    state: VoltStateModel = Field(default_factory=VoltStateModel)


class DiagnosisOut(BaseModel):
    fault: str
    confidence: float
    evidence: str
    # Leituras dos sensores: expostas apenas para engenheiro/admin (RBAC).
    readings: dict[str, float] | None = None


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str
    asset_tag: str
    symptom: str
    fault: str
    confidence: float
    priority: str
    status: str
    opened_by: str
    created_at: datetime


class HandoffSummary(BaseModel):
    """Resumo estruturado entregue ao tecnico humano (sem repetir nada)."""

    asset_tag: str | None
    asset_name: str | None
    symptom: str | None
    diagnosis: str | None
    confidence: float | None
    actions_taken: str
    reason: str


class VoltReply(BaseModel):
    """Resposta de um turno do Volt."""

    message: str
    state: VoltStateModel
    quick_replies: list[str] = Field(default_factory=list)
    diagnosis: DiagnosisOut | None = None
    work_order: WorkOrderOut | None = None
    handoff: HandoffSummary | None = None
    done: bool = False
