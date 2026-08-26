"""Endpoints REST do modulo de ativos."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Principal, require_role
from app.infra.db.base import get_catalog_session, get_timeseries_session
from app.modules.assets.models import Area, Asset, Plant
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import (
    AreaIn,
    AreaOut,
    AssetIn,
    AssetOut,
    AssetUpdate,
    HierarchyPlant,
    PlantIn,
    PlantOut,
)
from app.modules.assets.service import (
    AssetAlreadyExistsError,
    AssetNotFoundError,
    AssetService,
    PlantNotFoundError,
)
from app.core.config import get_settings
from app.modules.assets.smart_pdf import build_plant_pdf
from app.modules.telemetry.repository import TelemetryRepository

router = APIRouter(tags=["assets"])


async def get_asset_service(
    session: AsyncSession = Depends(get_catalog_session),
) -> AssetService:
    """Dependency: instancia o servico de ativos com a sessao do catalogo."""
    return AssetService(AssetRepository(session))


# ----------------------------- Assets -----------------------------
@router.get("/assets", response_model=list[AssetOut])
async def list_assets(
    search: str | None = Query(
        default=None, description="Busca por TAG, nome, fabricante ou modelo"
    ),
    status_filter: str | None = Query(default=None, alias="status"),
    asset_type: str | None = Query(default=None),
    plant_id: UUID | None = Query(default=None),
    service: AssetService = Depends(get_asset_service),
) -> list[Asset]:
    """Lista os ativos, com busca textual e filtros opcionais."""
    if any((search, status_filter, asset_type, plant_id)):
        return await service.search_assets(search, status_filter, asset_type, plant_id)
    return await service.list_assets()


@router.get("/hierarchy", response_model=list[HierarchyPlant])
async def get_hierarchy(
    service: AssetService = Depends(get_asset_service),
) -> list[Plant]:
    """Devolve a arvore Planta -> Area -> Ativo."""
    return await service.get_hierarchy()


@router.post(
    "/assets",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("operator"))],
)
async def create_asset(
    payload: AssetIn, service: AssetService = Depends(get_asset_service)
) -> Asset:
    try:
        return await service.create_asset(payload)
    except AssetAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um ativo com a TAG '{exc}'",
        ) from exc


@router.get("/assets/{tag}", response_model=AssetOut)
async def get_asset(tag: str, service: AssetService = Depends(get_asset_service)) -> Asset:
    try:
        return await service.get_asset(tag)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' não encontrado",
        ) from exc


@router.patch("/assets/{tag}", response_model=AssetOut)
async def update_asset(
    tag: str,
    payload: AssetUpdate,
    principal: Principal = Depends(require_role("operator")),
    service: AssetService = Depends(get_asset_service),
) -> Asset:
    try:
        return await service.update_asset(tag, payload, principal.username, principal.role)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' não encontrado",
        ) from exc


@router.post("/assets/{tag}/validate", response_model=AssetOut)
async def validate_asset(
    tag: str,
    principal: Principal = Depends(require_role("engineer")),
    service: AssetService = Depends(get_asset_service),
) -> Asset:
    """Valida manualmente um cadastro (perfil Gestor de Planta ou Admin)."""
    try:
        return await service.validate_asset(tag, principal.username)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' não encontrado",
        ) from exc


@router.delete(
    "/assets/{tag}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("engineer"))],
)
async def delete_asset(tag: str, service: AssetService = Depends(get_asset_service)) -> Response:
    # 204 nao tem corpo: devolvemos Response explicito (sem response_model)
    # para compatibilidade com as versoes recentes do FastAPI.
    try:
        await service.delete_asset(tag)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ativo '{tag}' não encontrado",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------- Plants -----------------------------
@router.get("/plants", response_model=list[PlantOut])
async def list_plants(
    service: AssetService = Depends(get_asset_service),
) -> list[Plant]:
    return await service.list_plants()


@router.post(
    "/plants",
    response_model=PlantOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("operator"))],
)
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


@router.post(
    "/areas",
    response_model=AreaOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("operator"))],
)
async def create_area(payload: AreaIn, service: AssetService = Depends(get_asset_service)) -> Area:
    try:
        return await service.create_area(payload)
    except PlantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planta '{exc}' não encontrada",
        ) from exc


@router.get("/plants/{plant_id}/smart-pdf")
async def plant_smart_pdf(
    plant_id: UUID,
    catalog: AsyncSession = Depends(get_catalog_session),
    timeseries: AsyncSession = Depends(get_timeseries_session),
) -> Response:
    """Gera o PDF interativo da planta com o snapshot da telemetria."""
    asset_repo = AssetRepository(catalog)
    plant = await asset_repo.get_plant(plant_id)
    if plant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planta não encontrada")
    plant_assets = await asset_repo.search_assets(plant_id=plant_id)
    telemetry_repo = TelemetryRepository(timeseries)
    latest_by_tag = {asset.tag: await telemetry_repo.latest(asset.tag) for asset in plant_assets}
    pdf_bytes = build_plant_pdf(
        plant, plant_assets, latest_by_tag, get_settings().resolved_frontend_base_url
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="planta-{plant.code}.pdf"'},
    )
