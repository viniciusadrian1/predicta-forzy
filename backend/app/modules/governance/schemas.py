"""Schemas Pydantic do modulo de governanca."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    """Registro de auditoria exposto pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timestamp: datetime
    actor: str
    action: str
    resource_type: str
    resource_id: str | None
    method: str | None
    path: str | None
    status_code: int | None
    ip_address: str | None
