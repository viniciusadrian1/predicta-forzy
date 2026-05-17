"""Servico de consulta de telemetria."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.telemetry.repository import TelemetryRepository
from app.modules.telemetry.schemas import (
    LatestOut,
    LatestReading,
    TelemetryPoint,
    TelemetrySeriesOut,
)

DEFAULT_WINDOW = timedelta(hours=1)
MAX_LIMIT = 10_000


class TelemetryService:
    """Consulta de series temporais e de valores instantaneos."""

    def __init__(self, repository: TelemetryRepository) -> None:
        self._repo = repository

    async def query(
        self,
        asset_tag: str,
        variable: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> TelemetrySeriesOut:
        end = end or datetime.now(UTC)
        start = start or (end - DEFAULT_WINDOW)
        limit = min(max(limit, 1), MAX_LIMIT)
        rows = await self._repo.query_series(asset_tag, variable, start, end, limit)
        points = [
            TelemetryPoint(
                time=row["time"],
                variable=row["variable"],
                value=row["value"],
                unit=row["unit"] or "",
                quality=row["quality"] or 0,
            )
            for row in reversed(rows)
        ]
        return TelemetrySeriesOut(
            asset_tag=asset_tag,
            variable=variable,
            count=len(points),
            points=points,
        )

    async def latest(self, asset_tag: str) -> LatestOut:
        rows = await self._repo.latest(asset_tag)
        readings = [
            LatestReading(
                variable=row["variable"],
                value=row["value"],
                unit=row["unit"] or "",
                quality=row["quality"] or 0,
                time=row["time"],
            )
            for row in rows
        ]
        return LatestOut(asset_tag=asset_tag, readings=readings)
