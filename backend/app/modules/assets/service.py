"""Regras de negocio do modulo de ativos."""

from __future__ import annotations

from app.modules.assets.models import Area, Asset, Plant
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import AreaIn, AssetIn, AssetUpdate, PlantIn


class AssetAlreadyExistsError(Exception):
    """Ja existe um ativo com a TAG informada."""


class AssetNotFoundError(Exception):
    """Nenhum ativo encontrado para a TAG informada."""


class PlantNotFoundError(Exception):
    """A planta referenciada nao existe."""


class AssetService:
    """Orquestra as operacoes do catalogo de ativos."""

    def __init__(self, repository: AssetRepository) -> None:
        self._repo = repository

    # ------------------------- Assets -------------------------
    async def list_assets(self) -> list[Asset]:
        return await self._repo.list_assets()

    async def get_asset(self, tag: str) -> Asset:
        asset = await self._repo.get_asset_by_tag(tag)
        if asset is None:
            raise AssetNotFoundError(tag)
        return asset

    async def create_asset(self, payload: AssetIn) -> Asset:
        if await self._repo.get_asset_by_tag(payload.tag) is not None:
            raise AssetAlreadyExistsError(payload.tag)
        return await self._repo.add_asset(Asset(**payload.model_dump()))

    async def update_asset(self, tag: str, payload: AssetUpdate) -> Asset:
        asset = await self.get_asset(tag)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(asset, field, value)
        return await self._repo.update_asset(asset)

    async def delete_asset(self, tag: str) -> None:
        await self._repo.delete_asset(await self.get_asset(tag))

    # --------------------- Plants / Areas ----------------------
    async def list_plants(self) -> list[Plant]:
        return await self._repo.list_plants()

    async def create_plant(self, payload: PlantIn) -> Plant:
        return await self._repo.add_plant(Plant(**payload.model_dump()))

    async def list_areas(self) -> list[Area]:
        return await self._repo.list_areas()

    async def create_area(self, payload: AreaIn) -> Area:
        if await self._repo.get_plant(payload.plant_id) is None:
            raise PlantNotFoundError(str(payload.plant_id))
        return await self._repo.add_area(Area(**payload.model_dump()))
