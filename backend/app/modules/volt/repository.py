"""Acesso a dados das ordens de servico (OS) do Volt."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.volt.models import WorkOrder


class WorkOrderRepository:
    """Persistencia e consulta das ordens de servico."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_number(self, asset_tag: str) -> str:
        """Gera o proximo numero de OS do ativo (ex.: MTR-2291-OS047)."""
        count = await self._session.scalar(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.asset_tag == asset_tag)
        )
        return f"{asset_tag}-OS{(int(count or 0) + 1):03d}"

    async def create(self, order: WorkOrder) -> WorkOrder:
        self._session.add(order)
        await self._session.commit()
        await self._session.refresh(order)
        return order

    async def list_orders(self, asset_tag: str | None = None, limit: int = 100) -> list[WorkOrder]:
        stmt = select(WorkOrder)
        if asset_tag:
            stmt = stmt.where(WorkOrder.asset_tag == asset_tag)
        stmt = stmt.order_by(WorkOrder.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
