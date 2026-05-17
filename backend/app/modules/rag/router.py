"""Endpoints REST + SSE do modulo de RAG / chat de troubleshooting."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rbac import require_role
from app.infra.db.base import get_catalog_session, get_timeseries_session
from app.modules.alerts.repository import AlertRepository
from app.modules.ml.service import ml_service
from app.modules.rag.schemas import ChatRequest, ChatResponse, IngestResult, RagStatus
from app.modules.rag.service import rag_service
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.telemetry.service import TelemetryService

logger = logging.getLogger("forzy.rag.router")

router = APIRouter(tags=["rag"])


async def _build_asset_context(
    asset_tag: str | None, catalog: AsyncSession, timeseries: AsyncSession
) -> str | None:
    """Monta um bloco de contexto com telemetria, alertas e RUL do ativo.

    O assistente de troubleshooting usa esse contexto para fundamentar a
    resposta nos dados em tempo real, alem da documentacao tecnica.
    """
    if not asset_tag:
        return None

    settings = get_settings()
    lines = [f"Ativo: {asset_tag}"]

    try:
        latest = await TelemetryService(TelemetryRepository(timeseries)).latest(asset_tag)
        readings = getattr(latest, "readings", [])
        if readings:
            snapshot = "; ".join(
                f"{reading.variable}={reading.value} {reading.unit}" for reading in readings
            )
            lines.append(f"Leituras atuais: {snapshot}")
    except Exception as exc:  # pragma: no cover - telemetria pode estar vazia
        logger.debug("Contexto do ativo: telemetria indisponivel (%s)", exc)

    try:
        alerts = await AlertRepository(catalog).list_alerts(
            asset_tag=asset_tag, only_active=True, limit=5
        )
        if alerts:
            joined = "; ".join(f"{alert.severity}: {alert.message}" for alert in alerts)
            lines.append(f"Alertas ativos: {joined}")
        else:
            lines.append("Alertas ativos: nenhum")
    except Exception as exc:  # pragma: no cover - tabela pode nao existir
        logger.debug("Contexto do ativo: alertas indisponiveis (%s)", exc)

    if settings.feature_ml:
        try:
            rul = await ml_service.estimate_rul(timeseries, asset_tag)
            if rul.available and rul.rul_days is not None:
                lines.append(f"RUL estimado: {rul.rul_days} dias ({rul.note})")
            elif rul.note:
                lines.append(f"RUL: {rul.note}")
        except Exception as exc:  # pragma: no cover - depende de historico
            logger.debug("Contexto do ativo: RUL indisponivel (%s)", exc)

    return "\n".join(lines)


@router.get("/rag/status", response_model=RagStatus)
async def rag_status() -> RagStatus:
    """Estado do indice de RAG e do provedor de LLM."""
    return await rag_service.status()


@router.post(
    "/rag/ingest",
    response_model=IngestResult,
    dependencies=[Depends(require_role("engineer"))],
)
async def rag_ingest() -> IngestResult:
    """Reindexa a base de conhecimento (requer papel engineer ou superior)."""
    return await rag_service.ingest()


@router.post("/rag/chat", response_model=ChatResponse)
async def rag_chat(
    request: ChatRequest,
    catalog: AsyncSession = Depends(get_catalog_session),
    timeseries: AsyncSession = Depends(get_timeseries_session),
) -> ChatResponse:
    """Responde uma pergunta de troubleshooting (modo nao-streaming)."""
    asset_context = await _build_asset_context(request.asset_tag, catalog, timeseries)
    return await rag_service.answer(request, asset_context)


@router.post("/rag/chat/stream")
async def rag_chat_stream(
    request: ChatRequest,
    catalog: AsyncSession = Depends(get_catalog_session),
    timeseries: AsyncSession = Depends(get_timeseries_session),
) -> StreamingResponse:
    """Responde via SSE, emitindo os eventos ``sources``, ``token`` e ``done``."""
    asset_context = await _build_asset_context(request.asset_tag, catalog, timeseries)

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event_name, data in rag_service.stream(request, asset_context):
            yield f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
