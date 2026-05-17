"""Endpoints REST do modulo de visao computacional (OCR de placas).

Sprint 1: stub que devolve dados mockados no formato final esperado.
Sprint 2: implementacao real com PaddleOCR (ver ADR 0003).
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.modules.vision.schemas import NameplateExtractionOut, NameplateField

router = APIRouter(tags=["vision"])

# Campos mockados (placa tipica de motor WEG) - substituidos por OCR na Sprint 2.
_MOCK_FIELDS: list[NameplateField] = [
    NameplateField(field="manufacturer", label="Fabricante", value="WEG", confidence=0.94),
    NameplateField(field="model", label="Modelo", value="W22 IR3 Premium", confidence=0.89),
    NameplateField(field="power_kw", label="Potencia (kW)", value="7.5", confidence=0.92),
    NameplateField(field="voltage_v", label="Tensao (V)", value="220/380", confidence=0.90),
    NameplateField(
        field="nominal_current_a",
        label="Corrente nominal (A)",
        value="25.4/14.7",
        confidence=0.86,
    ),
    NameplateField(field="frequency_hz", label="Frequencia (Hz)", value="60", confidence=0.95),
    NameplateField(field="nominal_rpm", label="Rotacao (RPM)", value="1755", confidence=0.88),
    NameplateField(field="ip_rating", label="Grau de protecao", value="IP55", confidence=0.91),
    NameplateField(
        field="insulation_class",
        label="Classe de isolamento",
        value="F",
        confidence=0.84,
    ),
    NameplateField(
        field="service_factor",
        label="Fator de servico",
        value="1.15",
        confidence=0.80,
    ),
]


@router.post("/assets/extract-from-image", response_model=NameplateExtractionOut)
async def extract_from_image(
    file: UploadFile = File(...),
) -> NameplateExtractionOut:
    """Extrai os dados da placa de identificacao de um ativo a partir de uma imagem."""
    content = await file.read()
    return NameplateExtractionOut(
        filename=file.filename,
        size_bytes=len(content),
        engine="stub",
        fields=list(_MOCK_FIELDS),
        note=(
            "Resposta simulada da Sprint 1. O OCR real (PaddleOCR) sera "
            "implementado na Sprint 2 - ver docs/adr/0003-ocr-strategy.md."
        ),
    )
