"""Schemas Pydantic do modulo de visao computacional."""

from __future__ import annotations

from pydantic import BaseModel


class NameplateField(BaseModel):
    """Um campo extraido da placa de identificacao, com confianca."""

    field: str
    label: str
    value: str | None
    confidence: float


class NameplateExtractionOut(BaseModel):
    """Resultado da extracao OCR de uma placa de identificacao."""

    filename: str | None
    size_bytes: int
    engine: str
    raw_text: str
    coverage: float
    fields: list[NameplateField]
    note: str
