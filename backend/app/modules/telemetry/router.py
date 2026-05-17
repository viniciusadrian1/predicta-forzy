"""Endpoints REST + SSE do modulo de telemetria."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import get_timeseries_session
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.telemetry.schemas import LatestOut, TelemetrySeriesOut
from app.modules.telemetry.service import TelemetryService
from app.modules.telemetry.stream import broadcaster

router = APIRouter(tags=["telemetry"])

_SSE_KEEPALIVE_S = 15.0


async def get_telemetry_service(
    session: AsyncSession = Depends(get_timeseries_session),
) -> TelemetryService:
    """Dependency: servico de telemetria com a sessao de series temporais."""
    return TelemetryService(TelemetryRepository(session))


@router.get("/telemetry", response_model=TelemetrySeriesOut)
async def query_telemetry(
    tag: str = Query(..., description="TAG do ativo"),
    variable: str | None = Query(default=None, description="Variavel; vazio = todas"),
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=1000, ge=1, le=10_000),
    service: TelemetryService = Depends(get_telemetry_service),
) -> TelemetrySeriesOut:
    """Consulta historica de uma serie temporal."""
    return await service.query(tag, variable, start, end, limit)


@router.get("/telemetry/{tag}/latest", response_model=LatestOut)
async def latest_telemetry(
    tag: str, service: TelemetryService = Depends(get_telemetry_service)
) -> LatestOut:
    """Snapshot com a ultima leitura de cada variavel do ativo."""
    return await service.latest(tag)


@router.get("/telemetry/stream")
async def stream_telemetry(
    tag: str | None = Query(default=None, description="Filtra por TAG do ativo"),
) -> StreamingResponse:
    """Stream SSE com os eventos de telemetria em tempo real."""

    async def event_generator() -> AsyncGenerator[str, None]:
        queue = broadcaster.subscribe()
        try:
            yield ": conexao estabelecida\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_S)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if tag and event.get("asset_tag") != tag:
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/telemetry/{tag}/export")
async def export_telemetry_csv(
    tag: str,
    variable: str | None = Query(default=None),
    service: TelemetryService = Depends(get_telemetry_service),
) -> Response:
    """Exporta a serie temporal do ativo em formato CSV."""
    series = await service.query(tag, variable, limit=10_000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["time", "asset_tag", "variable", "value", "unit", "quality"])
    for point in series.points:
        writer.writerow(
            [
                point.time.isoformat(),
                series.asset_tag,
                point.variable,
                point.value,
                point.unit,
                point.quality,
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="telemetria-{tag}.csv"'},
    )
