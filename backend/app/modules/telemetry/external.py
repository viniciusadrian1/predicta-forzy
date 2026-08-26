"""Ingestao dos sensores fisicos da Forzy via API HTTP externa.

A Forzy expoe endpoints (/get_s1, /get_s2) com a ultima medicao dos sensores
acoplados ao motor real, no formato::

    {"dados1": {"Velocidade": 0.06, "Aceleração": 0.0, "Temperatura": 33}}

Este poller consulta os endpoints periodicamente, converte cada leitura para
as variaveis canonicas da plataforma e a injeta no mesmo pipeline da
telemetria OPC-UA (TimescaleDB + broadcaster SSE). Quando o motor esta
desligado a API repete a ultima medicao - leituras identicas consecutivas
sao ignoradas para nao poluir as series com uma linha reta.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.infra.db.base import timeseries_session_factory
from app.infra.opcua_client.client import TelemetrySample
from app.modules.telemetry.processing import QUALITY_GOOD, process_sample
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.telemetry.stream import broadcaster

logger = logging.getLogger("forzy.telemetry.external")

# Campo da API Forzy -> (variavel canonica da plataforma, unidade).
VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "Velocidade": ("Vibracao_Velocidade_RMS", "mm/s"),
    "Aceleração": ("Vibracao_Aceleracao_RMS", "g"),
    "Aceleracao": ("Vibracao_Aceleracao_RMS", "g"),  # tolera payload sem acento
    "Temperatura": ("Temperatura", "C"),
}


def parse_targets(mapping: str) -> list[tuple[str, str]]:
    """Converte "TAG:/get_s1,TAG2:/get_s2" em pares (tag, endpoint)."""
    targets: list[tuple[str, str]] = []
    for entry in mapping.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        tag, path = entry.split(":", 1)
        if tag.strip() and path.strip():
            targets.append((tag.strip(), path.strip()))
    return targets


def extract_readings(payload: object) -> dict[str, float]:
    """Extrai {variavel_canonica: valor} do corpo devolvido pela API Forzy.

    O corpo tem um unico envelope ("dados1"/"dados2"); campos desconhecidos
    sao ignorados.
    """
    if not isinstance(payload, dict) or not payload:
        return {}
    inner = next(iter(payload.values()))
    if not isinstance(inner, dict):
        return {}
    readings: dict[str, float] = {}
    for field, value in inner.items():
        mapped = VARIABLE_MAP.get(str(field))
        if mapped is None:
            continue
        try:
            readings[mapped[0]] = float(value)
        except (TypeError, ValueError):
            continue
    return readings


class ExternalSensorsService:
    """Poller dos sensores fisicos: HTTP -> pipeline de telemetria."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.external_sensors_base_url.rstrip("/")
        self._targets = parse_targets(settings.external_sensors_map)
        self._interval = max(settings.external_sensors_poll_seconds, 5.0)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        # Ultima leitura por TAG - para deduplicar quando o motor esta parado.
        self._last: dict[str, dict[str, float]] = {}

    def start(self) -> None:
        if self._task is None and self._base_url and self._targets:
            self._running = True
            self._task = asyncio.create_task(self._run_forever())
            logger.info(
                "Ingestao de sensores externos iniciada (%d endpoint(s), %.0fs)",
                len(self._targets),
                self._interval,
            )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_forever(self) -> None:
        while self._running:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # tunel externo pode oscilar
                logger.warning("Sensores externos indisponiveis: %s", exc)
            await asyncio.sleep(self._interval)

    async def poll_once(self) -> int:
        """Consulta todos os endpoints; devolve o numero de amostras gravadas."""
        written = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for tag, path in self._targets:
                try:
                    response = await client.get(f"{self._base_url}{path}")
                    response.raise_for_status()
                    readings = extract_readings(response.json())
                except Exception as exc:
                    logger.warning("Falha ao consultar %s (%s): %s", path, tag, exc)
                    continue
                if not readings:
                    continue
                # Motor desligado: a API repete a ultima medicao - ignora.
                if readings == self._last.get(tag):
                    continue
                self._last[tag] = readings
                written += await self._ingest(tag, readings)
        return written

    async def _ingest(self, tag: str, readings: dict[str, float]) -> int:
        now = datetime.now(UTC)
        # Passa pelo MESMO pipeline do OPC-UA: grava o dado bruto (lineage) e
        # valida a faixa via process_sample (marca QUALITY_OUT_OF_RANGE quando
        # a leitura fisica esta fora do esperado) - nada entra como GOOD as cegas.
        raw = [
            TelemetrySample(
                asset_tag=tag,
                variable=variable,
                value=value,
                timestamp=now,
                quality=QUALITY_GOOD,
                source="forzy-http",
            )
            for variable, value in readings.items()
        ]
        processed = [process_sample(sample) for sample in raw]
        async with timeseries_session_factory() as session:
            repository = TelemetryRepository(session)
            for raw_sample, sample in zip(raw, processed, strict=True):
                await repository.add_raw(raw_sample)
                await repository.add_processed(sample)
            await session.commit()
        for sample in processed:
            await broadcaster.publish(sample.as_event())
        logger.info(
            "Sensores externos: %d leitura(s) do ativo %s",
            len(processed),
            tag,
            extra={"event": "external_ingest", "asset_tag": tag},
        )
        return len(processed)
