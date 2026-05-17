"""Endpoints REST do modulo de ativos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import get_catalog_session
from app.modules.assets.models import Area, Asset, Plant
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import (
    AreaIn,
    AreaOut,
    AssetIn,
    AssetOut,
    AssetUpdate,
    PlantIn,
    PlantOut,
)
from app.modules.assets.service import (
    AssetAlreadyExistsError,
    AssetNotFoundError,
    AssetService,
    PlantNotFoundError,
)

router = APIRouter(tags=["assets"])


async def get_asset_service(
    session: AsyncSession = Depends(get_catalog_session),
) -> AssetService:
    """Dependency: instancia o servico de ativos com a sessao do catalogo."""
    return AssetService(AssetRepository(session))


# ----------------------------- Assets -----------------------------
@router.get("/assets", response_model=list[AssetOut])
async def list_assets(
    service: AssetService = Depends(get_asset_service),
) -> list[Asset]:
    return await service.list_assets()


@router.post("/assets", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetIn, service: AssetService = Depends(get_asset_service)
) -> Asset:
    try:
        return await service.create_asset(payload)
    except AssetAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ja existe um ativo com a TAG '{exc}'",
        ) from exc


@router.get("/assets/{tag}", response_model=AssetOut)
async def get_asset(tag: str, service: AssetService = Depends(get_asset_service)) -> Asset:
    try:
        return await service.get_asset(tag)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' nao encontrado",
        ) from exc


@router.patch("/assets/{tag}", response_model=AssetOut)
async def update_asset(
    tag: str,
    payload: AssetUpdate,
    service: AssetService = Depends(get_asset_service),
) -> Asset:
    try:
        return await service.update_asset(tag, payload)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' nao encontrado",
        ) from exc


@router.delete("/assets/{tag}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(tag: str, service: AssetService = Depends(get_asset_service)) -> None:
    try:
        await service.delete_asset(tag)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' nao encontrado",
        ) from exc


# ----------------------------- Plants -----------------------------
@router.get("/plants", response_model=list[PlantOut])
async def list_plants(
    service: AssetService = Depends(get_asset_service),
) -> list[Plant]:
    return await service.list_plants()


@router.post("/plants", response_model=PlantOut, status_code=status.HTTP_201_CREATED)
async def create_plant(
    payload: PlantIn, service: AssetService = Depends(get_asset_service)
) -> Plant:
    return await service.create_plant(payload)


# ------------------------------ Areas -----------------------------
@router.get("/areas", response_model=list[AreaOut])
async def list_areas(
    service: AssetService = Depends(get_asset_service),
) -> list[Area]:
    return await service.list_areas()


@router.post("/areas", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
async def create_area(payload: AreaIn, service: AssetService = Depends(get_asset_service)) -> Area:
    try:
        return await service.create_area(payload)
    except PlantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planta '{exc}' nao encontrada",
        ) from exc
