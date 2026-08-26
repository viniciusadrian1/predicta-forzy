"""Modelos ORM da governanca: log de auditoria e trilha de TAG na planta."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import CatalogBase, UUIDMixin


class AuditLog(UUIDMixin, CatalogBase):
    """Registro append-only de uma acao relevante no sistema."""

    __tablename__ = "audit_log"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="anonymous")
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120))
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(300))
    status_code: Mapped[int | None] = mapped_column(Integer)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))


class TagAuditEvent(UUIDMixin, CatalogBase):
    """Trilha imutavel de associacao / movimentacao / edicao de TAG na planta.

    Espelha o 'Dicionario de Rastreabilidade de Navegacao' da governanca: cada
    evento carrega quem, quando, o que mudou (coordenadas), a linhagem e um hash
    de integridade (SHA-256) que detecta adulteracao retroativa do registro.
    """

    __tablename__ = "tag_audit_event"

    # ACAO: associacao / movimentacao / desvinculacao / edicao.
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    user_id: Mapped[str] = mapped_column(String(120), nullable=False, default="anonymous")
    user_role: Mapped[str] = mapped_column(String(24), nullable=False, default="viewer")
    tag_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    equipment_id: Mapped[str | None] = mapped_column(String(120))
    map_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1.0")
    coords_before: Mapped[dict | None] = mapped_column(JSON)
    coords_after: Mapped[dict | None] = mapped_column(JSON)
    # Linhagem: humano / ia_gerado / importacao.
    data_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="humano")
    confidence_score: Mapped[float | None] = mapped_column(Float)
    # Status de validacao: pendente / validado / rejeitado.
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="validado")
    validated_by: Mapped[str | None] = mapped_column(String(120))
    integrity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
