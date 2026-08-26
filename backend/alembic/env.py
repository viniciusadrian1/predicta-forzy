"""Ambiente Alembic para o banco de catalogo (engine assincrono)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.infra.db.base import CatalogBase
from app.modules.alerts import models as alerts_models  # noqa: F401
from app.modules.assets import models as assets_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.governance import models as governance_models  # noqa: F401
from app.modules.ml import models as ml_models  # noqa: F401
from app.modules.volt import models as volt_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_settings = get_settings()
target_metadata = CatalogBase.metadata


def _url() -> str:
    return _settings.catalog_database_url


def run_migrations_offline() -> None:
    """Gera SQL sem conectar ao banco."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine = async_engine_from_config(
        {"sqlalchemy.url": _url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    """Aplica as migrations conectando ao banco."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
