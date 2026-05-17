"""Fixtures de teste: aplicacao FastAPI com bancos SQLite em memoria."""

import os

# Configurado antes de importar a aplicacao: desliga a escrita de auditoria
# (que usa o banco real) para isolar os testes.
os.environ.setdefault("FEATURE_GOVERNANCE", "false")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.infra.db.base import (  # noqa: E402
    CatalogBase,
    get_catalog_session,
    get_timeseries_session,
)
from app.infra.db.timescale import timeseries_metadata  # noqa: E402
from app.main import app  # noqa: E402


def _memory_engine():
    """Cria um engine SQLite em memoria compartilhado (StaticPool)."""
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest_asyncio.fixture
async def catalog_sessionmaker():
    engine = _memory_engine()
    async with engine.begin() as conn:
        await conn.run_sync(CatalogBase.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest_asyncio.fixture
async def timeseries_sessionmaker():
    engine = _memory_engine()
    async with engine.begin() as conn:
        await conn.run_sync(timeseries_metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    catalog_sessionmaker, timeseries_sessionmaker
) -> AsyncGenerator[AsyncClient, None]:
    async def override_catalog():
        async with catalog_sessionmaker() as session:
            yield session

    async def override_timeseries():
        async with timeseries_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_catalog_session] = override_catalog
    app.dependency_overrides[get_timeseries_session] = override_timeseries
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
