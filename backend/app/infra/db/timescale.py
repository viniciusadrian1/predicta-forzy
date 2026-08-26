"""Schema do banco de series temporais (TimescaleDB).

As tabelas de telemetria sao *hypertables*. O DDL especifico do TimescaleDB
(``create_hypertable``, continuous aggregates) nao e versionado por Alembic
- ver ADR 0002 - mas criado de forma idempotente no startup da aplicacao.
"""

from __future__ import annotations

import logging

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    text,
)
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("forzy.infra.timescale")

timeseries_metadata = MetaData()

# Dado bruto, exatamente como recebido do OPC-UA.
telemetry_raw = Table(
    "telemetry_raw",
    timeseries_metadata,
    Column("time", DateTime(timezone=True), nullable=False, index=True),
    Column("asset_tag", String(64), nullable=False),
    Column("variable", String(64), nullable=False),
    Column("value", Float),
    Column("quality", Integer),
    Column("source", String(128)),
)

# Dado processado: convertido para unidades SI e validado.
telemetry_processed = Table(
    "telemetry_processed",
    timeseries_metadata,
    Column("time", DateTime(timezone=True), nullable=False, index=True),
    Column("asset_tag", String(64), nullable=False),
    Column("variable", String(64), nullable=False),
    Column("value", Float),
    Column("unit", String(16)),
    Column("quality", Integer),
)

# Continuous aggregates herdados (hoje removidos - ver init_timeseries_schema).
_LEGACY_AGGREGATES = (
    "telemetry_processed_1min",
    "telemetry_processed_5min",
    "telemetry_processed_1hour",
)

# Retencao alinhada a politica de governanca/LGPD: bruto 30 dias, processado 1 ano.
_RETENTION = (
    ("telemetry_raw", "30 days"),
    ("telemetry_processed", "365 days"),
)


async def init_timeseries_schema(engine: AsyncEngine) -> None:
    """Cria, de forma idempotente, extensao, hypertables e politicas de retencao."""
    # Fase 1 (transacional): extensao + tabelas base + hypertables.
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        await conn.run_sync(timeseries_metadata.create_all)
        for table_name in ("telemetry_raw", "telemetry_processed"):
            await conn.execute(
                text(f"SELECT create_hypertable('{table_name}', 'time', " "if_not_exists => TRUE)")
            )
    logger.info("Hypertables telemetry_raw / telemetry_processed prontas")

    # Fase 2: remove continuous aggregates legados (nao utilizados - reagregavam
    # a hypertable inteira sem consumidor) e aplica a retencao alinhada a politica
    # de governanca. Cada instrucao em sua propria transacao para que uma falha
    # nao derrube as demais.
    for view_name in _LEGACY_AGGREGATES:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name} CASCADE"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Nao foi possivel remover o aggregate %s: %s", view_name, exc)
    for table_name, keep in _RETENTION:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        f"SELECT add_retention_policy('{table_name}', "
                        f"INTERVAL '{keep}', if_not_exists => TRUE)"
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Retencao de %s ignorada: %s", table_name, exc)
    logger.info("Aggregates legados removidos; politicas de retencao aplicadas")
