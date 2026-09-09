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
    Index,
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
    # A consulta mais quente do sistema e "ultima leitura de cada variavel
    # deste ativo", refeita por toda tela a cada poucos segundos. Sem indice
    # por asset_tag ela varria o historico inteiro: 2.291 ms no motor de
    # demonstracao (1,9 milhao de linhas) contra 2,8 ms com o indice.
    Index(
        "ix_telemetry_processed_asset_var_time",
        "asset_tag",
        "variable",
        text("time DESC"),
    ),
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
    """Cria o schema de telemetria. Usa TimescaleDB quando disponivel
    (hypertables + retencao); sem a extensao (ex.: Postgres gerenciado do
    Render), cai para Postgres simples - as tabelas continuam funcionando como
    tabelas comuns, so sem particionamento/compressao/retencao automatica.
    """
    # Fase 0: tabelas base - sempre criadas (funcionam em Postgres puro).
    async with engine.begin() as conn:
        await conn.run_sync(timeseries_metadata.create_all)
    logger.info("Tabelas telemetry_raw / telemetry_processed prontas")

    # `create_all` nao altera tabela existente: bancos ja criados precisam do
    # indice explicitamente. IF NOT EXISTS torna a chamada idempotente.
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_telemetry_processed_asset_var_time "
                    "ON telemetry_processed (asset_tag, variable, time DESC)"
                )
            )
    except Exception as exc:  # noqa: BLE001 - indice ausente degrada, nao quebra
        logger.warning("Indice de telemetria nao criado: %s", exc)

    # Fase 1: extensao TimescaleDB (opcional). Sem ela, segue em modo Postgres.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("TimescaleDB indisponivel (%s) - modo Postgres simples.", exc)
        return

    # Fase 2: hypertables (so com Timescale).
    for table_name in ("telemetry_raw", "telemetry_processed"):
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"SELECT create_hypertable('{table_name}', 'time', if_not_exists => TRUE)")
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Hypertable %s ignorada: %s", table_name, exc)
    logger.info("Hypertables prontas")

    # Fase 3: remove continuous aggregates legados e aplica a retencao (Timescale).
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
