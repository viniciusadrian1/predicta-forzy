"""Schemas Pydantic do modulo de automacao (RPA)."""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.vision.schemas import NameplateField


class AssetDraft(BaseModel):
    """Rascunho de ativo pre-preenchido a partir do OCR da placa."""

    tag: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    power_kw: float | None = None
    voltage_v: float | None = None
    nominal_current_a: float | None = None
    nominal_rpm: int | None = None
    ip_rating: str | None = None
    insulation_class: str | None = None


class RpaRegisterResult(BaseModel):
    """Resultado do fluxo de RPA de cadastro a partir de foto."""

    ocr_engine: str
    ocr_coverage: float
    # Texto CRU do OCR. Sem ele, "cobertura 0%" e um beco sem saida: nao da
    # para saber se o motor nao leu nada ou se leu e o parser nao casou.
    raw_text: str = ""
    fields: list[NameplateField]
    draft: AssetDraft
    duplicate: bool
    created: bool
    message: str
