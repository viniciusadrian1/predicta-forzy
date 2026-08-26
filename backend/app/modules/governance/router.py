"""Endpoints REST do modulo de governanca: auditoria, data lineage e RBAC."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rbac import AUDIT_ROLES, LINEAGE_ROLES, require_any_role
from app.infra.db.base import get_catalog_session
from app.modules.governance.models import AuditLog, TagAuditEvent
from app.modules.governance.policy import (
    ACCESS_RULES,
    CLASSIFICATION_LEVELS,
    DATA_INVENTORY,
    ROLES,
)
from app.modules.governance.repository import AuditRepository, TagAuditRepository
from app.modules.governance.schemas import (
    AccessPolicyOut,
    AuditEntryOut,
    DataLineageOut,
    TagAuditEventOut,
)

router = APIRouter(tags=["governance"])


@router.get(
    "/audit",
    response_model=list[AuditEntryOut],
    dependencies=[Depends(require_any_role(AUDIT_ROLES))],
)
async def list_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_catalog_session),
) -> list[AuditLog]:
    """Lista os registros de auditoria mais recentes (requer papel admin)."""
    return await AuditRepository(session).list_recent(limit)


@router.get(
    "/governance/tag-audit",
    response_model=list[TagAuditEventOut],
    dependencies=[Depends(require_any_role(AUDIT_ROLES))],
)
async def tag_audit(
    tag: str | None = Query(default=None, description="Filtra por TAG do ativo"),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_catalog_session),
) -> list[TagAuditEvent]:
    """Trilha de associacao/movimentacao de TAG na planta (auditor ou admin)."""
    return await TagAuditRepository(session).list_recent(limit, tag)


@router.get(
    "/governance/data-lineage",
    response_model=DataLineageOut,
    dependencies=[Depends(require_any_role(LINEAGE_ROLES))],
)
async def data_lineage() -> DataLineageOut:
    """Catalogo de dados classificado (data lineage) - requer papel engineer."""
    return DataLineageOut(
        document="docs/governance/data-classification.md",
        classification_levels=CLASSIFICATION_LEVELS,
        datasets=DATA_INVENTORY,
    )


@router.get("/governance/access-policy", response_model=AccessPolicyOut)
async def access_policy() -> AccessPolicyOut:
    """Matriz de controle de acesso baseada em papeis (RBAC)."""
    return AccessPolicyOut(
        roles=ROLES,
        rbac_enabled=get_settings().rbac_enabled,
        rules=ACCESS_RULES,
    )
