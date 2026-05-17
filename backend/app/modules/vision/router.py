"""Endpoints REST do modulo de visao computacional (OCR de placas).

Sprint 2: OCR real com pipeline pre-processamento -> motor -> parser
(ver ``app/modules/vision/plate_ocr.py`` e ADR 0003). O motor PaddleOCR e um
extra opcional; sem ele, o endpoint opera em modo simulado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.rbac import require_role
from app.modules.vision.plate_ocr import extract_nameplate
from app.modules.vision.schemas import NameplateExtractionOut, NameplateField

router = APIRouter(tags=["vision"])

_OCR_NOTE = "Campos extraidos por OCR (PaddleOCR) da imagem enviada."
_STUB_NOTE = (
    "Motor de OCR (PaddleOCR) nao instalado - exibindo dados de exemplo. "
    "Instale o extra com 'pip install .[ocr]' para habilitar o OCR real."
)


@router.post(
    "/assets/extract-from-image",
    response_model=NameplateExtractionOut,
    dependencies=[Depends(require_role("operator"))],
)
async def extract_from_image(
    file: UploadFile = File(...),
) -> NameplateExtractionOut:
    """Extrai os dados da placa de identificacao de um ativo a partir de uma imagem."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imagem vazia")
    try:
        result = extract_nameplate(content)
    except Exception as exc:  # imagem invalida ou corrompida
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nao foi possivel processar a imagem: {exc}",
        ) from exc

    return NameplateExtractionOut(
        filename=file.filename,
        size_bytes=len(content),
        engine=result.engine,
        raw_text=result.raw_text,
        coverage=result.coverage,
        fields=[
            NameplateField(
                field=field.field,
                label=field.label,
                value=field.value,
                confidence=field.confidence,
            )
            for field in result.fields
        ],
        note=_OCR_NOTE if result.engine == "paddleocr" else _STUB_NOTE,
    )
