"""Modelo ORM dos alertas operacionais."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import CatalogBase, UUIDMixin


class Alert(UUIDMixin, CatalogBase):
    """Alerta gerado por regra de limite ou por modelo de ML."""

    __tablename__ = "alerts"

    asset_tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # INFO / WARNING / CRITICAL
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    # THRESHOLD_EXCEEDED / BASELINE_DEVIATION / ANOMALY_DETECTED / RUL_WARNING
    alert_type: Mapped[str] = mapped_column(String(48), nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    ml_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ack_by: Mapped[str | None] = mapped_column(String(120))
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_comment: Mapped[str | None] = mapped_column(String(400))
