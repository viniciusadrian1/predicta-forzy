"""Schemas Pydantic do modulo de ativos (validacao de entrada e saida)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --------------------------- Plant ---------------------------
class PlantIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=32)
    location: str | None = Field(default=None, max_length=200)


class PlantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    location: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------- Area ----------------------------
class AreaIn(BaseModel):
    plant_id: UUID
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=32)


class AreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plant_id: UUID
    name: str
    code: str
    created_at: datetime
    updated_at: datetime


# --------------------------- Asset ---------------------------
class AssetBase(BaseModel):
    asset_type: str = "motor"
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    power_kw: float | None = None
    voltage_v: float | None = None
    nominal_current_a: float | None = None
    nominal_rpm: int | None = None
    connection_type: str | None = None
    insulation_class: str | None = None
    ip_rating: str | None = None
    weight_kg: float | None = None
    manufacture_date: date | None = None
    plant_id: UUID | None = None
    area_id: UUID | None = None
    position_x: float | None = None
    position_y: float | None = None
    datasheet_url: str | None = None
    status: str = "unknown"

    # Rastreabilidade do cadastro (governanca).
    data_origin: str = "humano"
    registration_photo_at: datetime | None = None
    ocr_engine_version: str | None = None
    ocr_confidence: float | None = None
    validated_by: str | None = None
    validated_at: datetime | None = None
    image_source: str | None = None
    visual_condition: str | None = None
    # Limiares por ativo (contrato de metricas). Nulos = limiares globais ISO.
    vib_warning: float | None = None
    vib_critical: float | None = None
    temp_warning: float | None = None
    temp_critical: float | None = None


class AssetIn(AssetBase):
    """Payload de criacao de ativo."""

    tag: str = Field(min_length=1, max_length=64)


class AssetUpdate(BaseModel):
    """Payload de atualizacao parcial (PATCH) - todos os campos opcionais."""

    asset_type: str | None = None
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    power_kw: float | None = None
    voltage_v: float | None = None
    nominal_current_a: float | None = None
    nominal_rpm: int | None = None
    connection_type: str | None = None
    insulation_class: str | None = None
    ip_rating: str | None = None
    weight_kg: float | None = None
    manufacture_date: date | None = None
    plant_id: UUID | None = None
    area_id: UUID | None = None
    position_x: float | None = None
    position_y: float | None = None
    datasheet_url: str | None = None
    status: str | None = None
    # Validacao humana do cadastro + limiares por ativo (governanca).
    validated_by: str | None = None
    image_source: str | None = None
    visual_condition: str | None = None
    vib_warning: float | None = None
    vib_critical: float | None = None
    temp_warning: float | None = None
    temp_critical: float | None = None


class AssetOut(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tag: str
    created_at: datetime
    updated_at: datetime


# ------------------------ Hierarquia ------------------------
class HierarchyAsset(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tag: str
    name: str | None
    asset_type: str
    status: str


class HierarchyArea(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    assets: list[HierarchyAsset]


class HierarchyPlant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    areas: list[HierarchyArea]
