"""Modelo ORM de ordem de servico aberta pelo chatbot Volt."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import CatalogBase, UUIDMixin


class WorkOrder(UUIDMixin, CatalogBase):
    """Ordem de servico (OS) gerada a partir de um diagnostico do Volt."""

    __tablename__ = "work_orders"

    number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    asset_tag: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    symptom: Mapped[str] = mapped_column(String(32), nullable=False)
    fault: Mapped[str] = mapped_column(String(160), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)  # baixa/media/alta
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="aberta")
    opened_by: Mapped[str] = mapped_column(String(120), nullable=False, default="volt")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
