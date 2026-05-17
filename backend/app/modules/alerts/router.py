"""Endpoints REST do modulo de alertas."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_actor
from app.core.rbac import require_role
from app.infra.db.base import get_catalog_session
from app.modules.alerts.models import Alert
from app.modules.alerts.repository import AlertRepository
from app.modules.alerts.schemas import AlertAck, AlertOut
from app.modules.alerts.service import AlertNotFoundError, AlertService

router = APIRouter(tags=["alerts"])


async def get_alert_service(
    session: AsyncSession = Depends(get_catalog_session),
) -> AlertService:
    return AlertService(AlertRepository(session))


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    tag: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    only_active: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    service: AlertService = Depends(get_alert_service),
) -> list[Alert]:
    """Lista os alertas, com filtros opcionais por ativo e severidade."""
    return await service.list_alerts(tag, severity, only_active, limit)


@router.post(
    "/alerts/{alert_id}/ack",
    response_model=AlertOut,
    dependencies=[Depends(require_role("operator"))],
)
async def acknowledge_alert(
    alert_id: UUID,
    payload: AlertAck,
    actor: str = Depends(get_current_actor),
    service: AlertService = Depends(get_alert_service),
) -> Alert:
    """Reconhece (ack) um alerta, com comentario opcional."""
    try:
        return await service.acknowledge(alert_id, actor, payload.comment)
    except AlertNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alerta nao encontrado"
        ) from exc
