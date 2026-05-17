"""Infraestrutura de banco de dados: engines e sessoes assincronas.

O sistema usa duas bases distintas (ver ADR 0002):

* **catalogo** (PostgreSQL)        - ativos, plantas, auditoria; versionado
  por Alembic;
* **series temporais** (TimescaleDB) - telemetria dos sensores; schema criado
  de forma idempotente no startup da aplicacao.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

_settings = get_settings()


class CatalogBase(DeclarativeBase):
    """Base declarativa das tabelas do catalogo relacional."""


class UUIDMixin:
    """Mixin de chave primaria UUID."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Mixin de timestamps de criacao e atualizacao."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


catalog_engine = create_async_engine(_settings.catalog_database_url, echo=False, pool_pre_ping=True)
catalog_session_factory = async_sessionmaker(
    catalog_engine, expire_on_commit=False, class_=AsyncSession
)

timeseries_engine = create_async_engine(
    _settings.timeseries_database_url, echo=False, pool_pre_ping=True
)
timeseries_session_factory = async_sessionmaker(
    timeseries_engine, expire_on_commit=False, class_=AsyncSession
)


async def get_catalog_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI: sessao do banco de catalogo."""
    async with catalog_session_factory() as session:
        yield session


async def get_timeseries_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI: sessao do banco de series temporais."""
    async with timeseries_session_factory() as session:
        yield session
