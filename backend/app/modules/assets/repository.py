"""Acesso a dados do catalogo de ativos, plantas e areas."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.assets.models import Area, Asset, Plant


class AssetRepository:
    """Operacoes de persistencia para ativos, plantas e areas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------- Assets -------------------------
    async def list_assets(self) -> list[Asset]:
        result = await self._session.execute(select(Asset).order_by(Asset.tag))
        return list(result.scalars().all())

    async def get_asset_by_tag(self, tag: str) -> Asset | None:
        result = await self._session.execute(select(Asset).where(Asset.tag == tag))
        return result.scalar_one_or_none()

    async def add_asset(self, asset: Asset) -> Asset:
        self._session.add(asset)
        await self._session.commit()
        await self._session.refresh(asset)
        return asset

    async def update_asset(self, asset: Asset) -> Asset:
        await self._session.commit()
        await self._session.refresh(asset)
        return asset

    async def delete_asset(self, asset: Asset) -> None:
        await self._session.delete(asset)
        await self._session.commit()

    # ------------------------- Plants -------------------------
    async def list_plants(self) -> list[Plant]:
        result = await self._session.execute(select(Plant).order_by(Plant.code))
        return list(result.scalars().all())

    async def get_plant(self, plant_id: UUID) -> Plant | None:
        return await self._session.get(Plant, plant_id)

    async def add_plant(self, plant: Plant) -> Plant:
        self._session.add(plant)
        await self._session.commit()
        await self._session.refresh(plant)
        return plant

    # ------------------------- Areas --------------------------
    async def list_areas(self) -> list[Area]:
        result = await self._session.execute(select(Area).order_by(Area.code))
        return list(result.scalars().all())

    async def add_area(self, area: Area) -> Area:
        self._session.add(area)
        await self._session.commit()
        await self._session.refresh(area)
        return area

    # ----------------------- Busca / hierarquia -----------------------
    async def search_assets(
        self,
        search: str | None = None,
        status: str | None = None,
        asset_type: str | None = None,
        plant_id: UUID | None = None,
    ) -> list[Asset]:
        stmt = select(Asset)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                Asset.tag.ilike(like)
                | Asset.name.ilike(like)
                | Asset.manufacturer.ilike(like)
                | Asset.model.ilike(like)
            )
        if status:
            stmt = stmt.where(Asset.status == status)
        if asset_type:
            stmt = stmt.where(Asset.asset_type == asset_type)
        if plant_id:
            stmt = stmt.where(Asset.plant_id == plant_id)
        result = await self._session.execute(stmt.order_by(Asset.tag))
        return list(result.scalars().all())

    async def list_hierarchy(self) -> list[Plant]:
        result = await self._session.execute(
            select(Plant)
            .options(selectinload(Plant.areas).selectinload(Area.assets))
            .order_by(Plant.code)
        )
        return list(result.scalars().all())
