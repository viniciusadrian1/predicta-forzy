"""Servico de ingestao de telemetria via OPC-UA.

Liga o cliente OPC-UA ao pipeline de processamento, persistencia e streaming:
cada amostra recebida e validada, gravada nas hypertables ``telemetry_raw`` e
``telemetry_processed`` e publicada para os assinantes SSE.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.infra.db.base import timeseries_session_factory
from app.infra.opcua_client.client import OpcuaIngestionClient, TelemetrySample
from app.modules.telemetry.processing import process_sample
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.telemetry.stream import broadcaster

logger = logging.getLogger("forzy.telemetry.ingestion")

# Sprint 1: um unico motor monitorado.
MONITORED_ASSET_TAG = "MTR-001"


class TelemetryIngestionService:
    """Coordena a captura OPC-UA, o processamento e a persistencia."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpcuaIngestionClient(
            endpoint=settings.opcua_endpoint,
            namespace_uri=settings.opcua_namespace_uri,
            publishing_interval_ms=settings.opcua_publishing_interval_ms,
            asset_tag=MONITORED_ASSET_TAG,
            on_sample=self._handle_sample,
        )

    async def _handle_sample(self, sample: TelemetrySample) -> None:
        """Callback da subscription: processa, persiste e publica a amostra."""
        try:
            processed = process_sample(sample)
            async with timeseries_session_factory() as session:
                repository = TelemetryRepository(session)
                await repository.add_raw(sample)
                await repository.add_processed(processed)
                await session.commit()
            await broadcaster.publish(processed.as_event())
        except Exception:
            # Uma falha pontual nao deve derrubar a subscription OPC-UA.
            logger.exception("Falha ao processar amostra de telemetria")

    def start(self) -> None:
        self._client.start()
        logger.info("Ingestao de telemetria iniciada (ativo %s)", MONITORED_ASSET_TAG)

    async def stop(self) -> None:
        await self._client.stop()
        logger.info("Ingestao de telemetria encerrada")
