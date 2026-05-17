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


class DataAssetEntry(BaseModel):
    """Item do inventario de dados (data lineage)."""

    dataset: str
    origin: str
    classification: str
    storage: str
    retention: str
    notes: str


class DataLineageOut(BaseModel):
    """Catalogo de dados classificado, exposto pela API de governanca."""

    document: str
    classification_levels: list[str]
    datasets: list[DataAssetEntry]


class AccessRule(BaseModel):
    """Regra da matriz RBAC: papel minimo exigido para um recurso."""

    resource: str
    methods: list[str]
    min_role: str
    description: str


class AccessPolicyOut(BaseModel):
    """Politica de controle de acesso baseada em papeis (matriz RBAC)."""

    roles: list[str]
    rbac_enabled: bool
    rules: list[AccessRule]
