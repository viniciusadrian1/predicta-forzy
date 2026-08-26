"""Acesso ao banco de series temporais (TimescaleDB) da telemetria."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.timescale import telemetry_processed, telemetry_raw
from app.infra.opcua_client.client import TelemetrySample
from app.modules.telemetry.processing import ProcessedSample


class TelemetryRepository:
    """Persistencia e consulta das hypertables de telemetria."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_raw(self, sample: TelemetrySample) -> None:
        """Insere o dado bruto (sem commit - controlado pelo chamador)."""
        await self._session.execute(
            insert(telemetry_raw).values(
                time=sample.timestamp,
                asset_tag=sample.asset_tag,
                variable=sample.variable,
                value=sample.value,
                quality=sample.quality,
                source=sample.source,
            )
        )

    async def add_processed(self, processed: ProcessedSample) -> None:
        """Insere o dado processado (sem commit - controlado pelo chamador)."""
        await self._session.execute(
            insert(telemetry_processed).values(
                time=processed.time,
                asset_tag=processed.asset_tag,
                variable=processed.variable,
                value=processed.value,
                unit=processed.unit,
                quality=processed.quality,
            )
        )

    async def query_series(
        self,
        asset_tag: str,
        variable: str | None,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        stmt = select(
            telemetry_processed.c.time,
            telemetry_processed.c.variable,
            telemetry_processed.c.value,
            telemetry_processed.c.unit,
            telemetry_processed.c.quality,
        ).where(
            telemetry_processed.c.asset_tag == asset_tag,
            telemetry_processed.c.time >= start,
            telemetry_processed.c.time <= end,
        )
        if variable is not None:
            stmt = stmt.where(telemetry_processed.c.variable == variable)
        stmt = stmt.order_by(telemetry_processed.c.time.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def recent_values(
        self, asset_tag: str, variable: str, limit: int
    ) -> list[dict[str, Any]]:
        """Ultimas ``limit`` leituras de uma variavel (mais recentes primeiro)."""
        stmt = (
            select(
                telemetry_processed.c.time,
                telemetry_processed.c.value,
                telemetry_processed.c.quality,
            )
            .where(
                telemetry_processed.c.asset_tag == asset_tag,
                telemetry_processed.c.variable == variable,
            )
            .order_by(telemetry_processed.c.time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def latest(self, asset_tag: str) -> list[dict[str, Any]]:
        """Ultima leitura de cada variavel do ativo (via window function)."""
        ranked = (
            select(
                telemetry_processed.c.time,
                telemetry_processed.c.variable,
                telemetry_processed.c.value,
                telemetry_processed.c.unit,
                telemetry_processed.c.quality,
                func.row_number()
                .over(
                    partition_by=telemetry_processed.c.variable,
                    order_by=telemetry_processed.c.time.desc(),
                )
                .label("rn"),
            )
            .where(telemetry_processed.c.asset_tag == asset_tag)
            .subquery()
        )
        stmt = select(
            ranked.c.time,
            ranked.c.variable,
            ranked.c.value,
            ranked.c.unit,
            ranked.c.quality,
        ).where(ranked.c.rn == 1)
        result = await self._session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]
