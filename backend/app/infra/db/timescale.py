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

# Continuous aggregates: (nome da view, intervalo do bucket).
_CONTINUOUS_AGGREGATES = (
    ("telemetry_processed_1min", "1 minute"),
    ("telemetry_processed_5min", "5 minutes"),
    ("telemetry_processed_1hour", "1 hour"),
)


def _aggregate_sql(view_name: str, bucket: str) -> str:
    return (
        f"CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name} "
        "WITH (timescaledb.continuous) AS "
        f"SELECT time_bucket(INTERVAL '{bucket}', time) AS bucket, "
        "asset_tag, variable, "
        "avg(value) AS avg_value, min(value) AS min_value, "
        "max(value) AS max_value, count(*) AS sample_count "
        "FROM telemetry_processed "
        "GROUP BY bucket, asset_tag, variable "
        "WITH NO DATA"
    )


async def init_timeseries_schema(engine: AsyncEngine) -> None:
    """Cria, de forma idempotente, extensao, hypertables e continuous aggregates."""
    # Fase 1 (transacional): extensao + tabelas base + hypertables.
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        await conn.run_sync(timeseries_metadata.create_all)
        for table_name in ("telemetry_raw", "telemetry_processed"):
            await conn.execute(
                text(f"SELECT create_hypertable('{table_name}', 'time', " "if_not_exists => TRUE)")
            )
    logger.info("Hypertables telemetry_raw / telemetry_processed prontas")

    # Fase 2 (autocommit): continuous aggregates nao podem rodar em transacao.
    async with engine.connect() as raw_conn:
        conn = raw_conn.execution_options(isolation_level="AUTOCOMMIT")
        for view_name, bucket in _CONTINUOUS_AGGREGATES:
            try:
                await conn.execute(text(_aggregate_sql(view_name, bucket)))
                await conn.execute(
                    text(
                        f"SELECT add_continuous_aggregate_policy('{view_name}', "
                        "start_offset => NULL, end_offset => NULL, "
                        "schedule_interval => INTERVAL '1 minute', "
                        "if_not_exists => TRUE)"
                    )
                )
            except Exception as exc:  # noqa: BLE001 - aggregates sao otimizacao
                logger.warning("Continuous aggregate %s ignorado: %s", view_name, exc)
    logger.info("Continuous aggregates configurados")
