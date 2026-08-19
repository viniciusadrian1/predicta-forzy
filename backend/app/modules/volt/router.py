"""Endpoints REST do chatbot de manutencao Volt."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rbac import Principal, get_principal, require_role
from app.infra.db.base import get_catalog_session, get_timeseries_session
from app.modules.assets.repository import AssetRepository
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.volt.repository import WorkOrderRepository
from app.modules.volt.schemas import VoltReply, VoltRequest, WorkOrderOut
from app.modules.volt.service import VoltService, greeting_reply

router = APIRouter(tags=["volt"])


@router.get("/volt/greeting", response_model=VoltReply)
async def volt_greeting() -> VoltReply:
    """Mensagem inicial do Volt (capacidades ditas de cara)."""
    return greeting_reply()


@router.post("/volt/message", response_model=VoltReply)
async def volt_message(
    request: VoltRequest,
    principal: Principal = Depends(get_principal),
    catalog: AsyncSession = Depends(get_catalog_session),
    timeseries: AsyncSession = Depends(get_timeseries_session),
) -> VoltReply:
    """Processa um turno do atendimento guiado do Volt."""
    service = VoltService(
        assets=AssetRepository(catalog),
        telemetry=TelemetryRepository(timeseries),
        work_orders=WorkOrderRepository(catalog),
        settings=get_settings(),
        role=principal.role,
    )
    return await service.advance(request)


@router.get(
    "/volt/work-orders",
    response_model=list[WorkOrderOut],
    dependencies=[Depends(require_role("operator"))],
)
async def list_work_orders(
    tag: str | None = Query(default=None, description="Filtra por TAG do ativo"),
    limit: int = Query(default=100, ge=1, le=500),
    catalog: AsyncSession = Depends(get_catalog_session),
) -> list[WorkOrderOut]:
    """Lista as ordens de servico abertas pelo Volt (requer papel operator)."""
    orders = await WorkOrderRepository(catalog).list_orders(tag, limit)
    return [WorkOrderOut.model_validate(order) for order in orders]
