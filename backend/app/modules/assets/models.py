"""Modelos ORM do catalogo de ativos: plantas, areas e ativos."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import CatalogBase, TimestampMixin, UUIDMixin


class Plant(UUIDMixin, TimestampMixin, CatalogBase):
    """Planta industrial - raiz da hierarquia de ativos."""

    __tablename__ = "plants"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))

    areas: Mapped[list[Area]] = relationship(back_populates="plant", cascade="all, delete-orphan")
    assets: Mapped[list[Asset]] = relationship(back_populates="plant")


class Area(UUIDMixin, TimestampMixin, CatalogBase):
    """Area / setor dentro de uma planta."""

    __tablename__ = "areas"

    plant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)

    plant: Mapped[Plant] = relationship(back_populates="areas")
    assets: Mapped[list[Asset]] = relationship(back_populates="area")


class Asset(UUIDMixin, TimestampMixin, CatalogBase):
    """Ativo monitorado (ex.: motor eletrico industrial)."""

    __tablename__ = "assets"

    tag: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    asset_type: Mapped[str] = mapped_column(String(48), nullable=False, default="motor")
    name: Mapped[str | None] = mapped_column(String(160))
    manufacturer: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    serial_number: Mapped[str | None] = mapped_column(String(80))

    # Dados de placa (preenchidos por cadastro manual ou OCR).
    power_kw: Mapped[float | None] = mapped_column(Float)
    voltage_v: Mapped[float | None] = mapped_column(Float)
    nominal_current_a: Mapped[float | None] = mapped_column(Float)
    nominal_rpm: Mapped[int | None] = mapped_column(Integer)
    connection_type: Mapped[str | None] = mapped_column(String(32))
    insulation_class: Mapped[str | None] = mapped_column(String(16))
    ip_rating: Mapped[str | None] = mapped_column(String(16))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    manufacture_date: Mapped[date | None] = mapped_column(Date)

    # Localizacao na hierarquia e na planta baixa.
    plant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plants.id", ondelete="SET NULL"))
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("areas.id", ondelete="SET NULL"))
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)

    datasheet_url: Mapped[str | None] = mapped_column(String(300))
    # Status operacional: unknown / ok / warning / critical.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    # --- Rastreabilidade do cadastro (governanca) ---
    # Origem do dado do cadastro: humano / ia_gerado / importacao.
    data_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="humano")
    registration_photo_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ocr_engine_version: Mapped[str | None] = mapped_column(String(48))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    validated_by: Mapped[str | None] = mapped_column(String(120))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image_source: Mapped[str | None] = mapped_column(String(48))
    visual_condition: Mapped[str | None] = mapped_column(String(300))

    # --- Limiares por ativo (contrato de metricas por percentil / por motor) ---
    # Nulos = usa os limiares globais ISO 10816 do avaliador.
    vib_warning: Mapped[float | None] = mapped_column(Float)
    vib_critical: Mapped[float | None] = mapped_column(Float)
    temp_warning: Mapped[float | None] = mapped_column(Float)
    temp_critical: Mapped[float | None] = mapped_column(Float)

    plant: Mapped[Plant | None] = relationship(back_populates="assets")
    area: Mapped[Area | None] = relationship(back_populates="assets")
