"""Modelo ORM de usuario (autenticacao e RBAC).

A Sprint 4 substitui o login mock por uma tabela de usuarios persistida,
com senha protegida por hashing argon2 (ver ``core/security.py``).
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import CatalogBase, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, CatalogBase):
    """Conta de usuario, com papel usado pelo controle de acesso (RBAC)."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    full_name: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
