"""Endpoints REST do modulo de visao computacional (OCR de placas).

Pipeline: pre-processamento -> motor de OCR (Tesseract) -> parser
(ver ``app/modules/vision/plate_ocr.py`` e ADR 0003). Sem motor de OCR
disponivel, o endpoint devolve um resultado vazio e honesto - nunca dados
fabricados.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.rbac import require_role
from app.modules.vision.plate_ocr import extract_nameplate
from app.modules.vision.schemas import NameplateExtractionOut, NameplateField

router = APIRouter(tags=["vision"])

_UNAVAILABLE_NOTE = (
    "OCR indisponível no servidor (Tesseract não instalado). Nenhum dado foi "
    "extraído - preencha os campos manualmente."
)
_EMPTY_NOTE = (
    "Nenhum campo reconhecido na imagem. Verifique a nitidez/enquadramento da "
    "placa ou preencha os campos manualmente."
)


def _note_for(engine: str, has_fields: bool) -> str:
    if engine == "indisponivel":
        return _UNAVAILABLE_NOTE
    if not has_fields:
        return _EMPTY_NOTE
    return f"Campos extraídos por OCR ({engine}) da imagem enviada. Revise antes de usar."


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
            detail=f"Não foi possível processar a imagem: {exc}",
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
        note=_note_for(result.engine, bool(result.fields)),
    )
