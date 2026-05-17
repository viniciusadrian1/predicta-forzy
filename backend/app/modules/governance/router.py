"""Endpoints REST do modulo de governanca."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import get_catalog_session
from app.modules.governance.models import AuditLog
from app.modules.governance.repository import AuditRepository
from app.modules.governance.schemas import AuditEntryOut

router = APIRouter(tags=["governance"])


@router.get("/audit", response_model=list[AuditEntryOut])
async def list_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_catalog_session),
) -> list[AuditLog]:
    """Lista os registros de auditoria mais recentes."""
    return await AuditRepository(session).list_recent(limit)
