"""Modelo ORM do feedback de predicoes de ML (loop de melhoria / governanca)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import CatalogBase, UUIDMixin


class MlFeedback(UUIDMixin, CatalogBase):
    """Reporte de um operador sobre uma predicao (feedback loop persistido).

    Antes o feedback era apenas logado; persistir permite auditar, medir a
    taxa de acerto por modelo e curar o dataset de retreino.
    """

    __tablename__ = "ml_feedback"

    asset_tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(48), nullable=False)
    prediction: Mapped[str] = mapped_column(String(120), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(400))
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="anonymous")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
