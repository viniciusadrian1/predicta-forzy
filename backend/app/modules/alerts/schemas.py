"""Schemas Pydantic do modulo de alertas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    """Alerta exposto pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_tag: str
    severity: str
    alert_type: str
    message: str
    ml_score: float | None
    created_at: datetime
    acknowledged: bool
    ack_by: str | None
    ack_at: datetime | None
    ack_comment: str | None


class AlertAck(BaseModel):
    """Payload de reconhecimento (ack) de um alerta."""

    comment: str | None = None
