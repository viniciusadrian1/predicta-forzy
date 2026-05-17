"""Endpoints REST do modulo de automacao (RPA)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_actor
from app.core.rbac import require_role
from app.infra.db.base import get_catalog_session
from app.modules.assets.repository import AssetRepository
from app.modules.automation.schemas import RpaRegisterResult
from app.modules.automation.service import RpaService

router = APIRouter(tags=["automation"])


@router.post(
    "/automation/register-from-image",
    response_model=RpaRegisterResult,
    dependencies=[Depends(require_role("operator"))],
)
async def register_from_image(
    file: UploadFile = File(...),
    tag: str | None = Form(default=None),
    auto_create: bool = Form(default=False),
    actor: str = Depends(get_current_actor),
    session: AsyncSession = Depends(get_catalog_session),
) -> RpaRegisterResult:
    """Fluxo de RPA: OCR da placa, rascunho, deduplicacao e cadastro opcional."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imagem vazia")
    try:
        service = RpaService(AssetRepository(session))
        return await service.register_from_image(content, tag, auto_create, actor)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha no processamento da imagem: {exc}",
        ) from exc
