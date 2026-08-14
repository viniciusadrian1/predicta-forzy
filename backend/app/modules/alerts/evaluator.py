"""Avaliador periodico de alertas: regras de limite + modelos de ML.

Executa como uma task em background, avaliando o ativo a cada 30 s, o que
atende ao criterio de detectar uma falha injetada em menos de 60 segundos.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infra.db.base import catalog_session_factory, timeseries_session_factory
from app.modules.alerts.models import Alert
from app.modules.alerts.repository import AlertRepository
from app.modules.assets.models import Asset
from app.modules.ml.service import ml_service
from app.modules.telemetry.repository import TelemetryRepository

logger = logging.getLogger("forzy.alerts.evaluator")

EVALUATION_INTERVAL_S = 30.0
MONITORED_ASSET_TAG = "MTR-001"

# Limites operacionais (DIN ISO 10816/20816 para vibracao).
VIB_WARNING = 4.5
VIB_CRITICAL = 7.1
TEMP_WARNING = 95.0
TEMP_CRITICAL = 105.0
RUL_WARNING_DAYS = 45.0
RUL_CRITICAL_DAYS = 15.0
# Janela de deduplicacao: nao recria o mesmo tipo de alerta nesse intervalo.
DEDUP_MINUTES = 15

# (severidade, tipo, mensagem, score)
Candidate = tuple[str, str, str, float | None]


class AlertsEvaluator:
    """Avalia regras e modelos periodicamente e gera alertas."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run_forever())
            logger.info("Avaliador de alertas iniciado")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_forever(self) -> None:
        # Lista de ativos monitorados vem da configuracao (inclui os sensores
        # fisicos Forzy, alem do simulador).
        tags = [
            tag.strip() for tag in get_settings().monitored_asset_tags.split(",") if tag.strip()
        ] or [MONITORED_ASSET_TAG]
        while self._running:
            for tag in tags:
                try:
                    await self.evaluate(tag)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Falha na avaliacao de alertas (%s)", tag)
            await asyncio.sleep(EVALUATION_INTERVAL_S)

    async def evaluate(self, asset_tag: str) -> list[Alert]:
        """Avalia um ativo (regras + ML) e cria os alertas necessarios."""
        candidates: list[Candidate] = []

        async with timeseries_session_factory() as ts_session:
            latest = await TelemetryRepository(ts_session).latest(asset_tag)
            readings = {row["variable"]: row["value"] for row in latest}
            candidates += self._threshold_rules(readings)

            baseline = await ml_service.predict_baseline(ts_session, asset_tag)
            if baseline.available and baseline.decision == "anomalo":
                candidates.append(
                    (
                        "WARNING",
                        "BASELINE_DEVIATION",
                        "Desvio do baseline de operacao detectado pelo modelo",
                        baseline.score,
                    )
                )
            anomaly = await ml_service.predict_anomaly(ts_session, asset_tag)
            if anomaly.available and anomaly.is_anomaly:
                candidates.append(
                    (
                        "WARNING",
                        "ANOMALY_DETECTED",
                        "Anomalia de vibracao detectada (autoencoder)",
                        anomaly.reconstruction_error,
                    )
                )
            rul = await ml_service.estimate_rul(ts_session, asset_tag)
            if rul.available and rul.rul_days is not None and rul.rul_days < RUL_WARNING_DAYS:
                severity = "CRITICAL" if rul.rul_days < RUL_CRITICAL_DAYS else "WARNING"
                candidates.append(
                    (
                        severity,
                        "RUL_WARNING",
                        f"RUL estimado em {rul.rul_days:.0f} dias - planejar manutencao",
                        None,
                    )
                )

        created: list[Alert] = []
        async with catalog_session_factory() as cat_session:
            repo = AlertRepository(cat_session)
            for severity, alert_type, message, score in candidates:
                if await repo.has_recent_unacked(asset_tag, alert_type, DEDUP_MINUTES):
                    continue
                alert = await repo.create(
                    Alert(
                        asset_tag=asset_tag,
                        severity=severity,
                        alert_type=alert_type,
                        message=message,
                        ml_score=score,
                    )
                )
                created.append(alert)
                logger.warning(
                    "alerta gerado: %s/%s - %s",
                    severity,
                    alert_type,
                    message,
                    extra={"event": "alert_created", "asset_tag": asset_tag},
                )
            await self._sync_asset_status(asset_tag, cat_session, repo)
        return created

    def _threshold_rules(self, readings: dict[str, Any]) -> list[Candidate]:
        """Regras determinísticas de limite sobre a ultima leitura."""
        out: list[Candidate] = []
        vibration = readings.get("Vibracao_Velocidade_RMS")
        if vibration is not None:
            if vibration > VIB_CRITICAL:
                out.append(
                    (
                        "CRITICAL",
                        "THRESHOLD_EXCEEDED",
                        f"Vibracao critica: {vibration:.2f} mm/s",
                        None,
                    )
                )
            elif vibration > VIB_WARNING:
                out.append(
                    (
                        "WARNING",
                        "THRESHOLD_EXCEEDED",
                        f"Vibracao elevada: {vibration:.2f} mm/s",
                        None,
                    )
                )
        temperature = readings.get("Temperatura")
        if temperature is not None:
            if temperature > TEMP_CRITICAL:
                out.append(
                    (
                        "CRITICAL",
                        "THRESHOLD_EXCEEDED",
                        f"Temperatura critica: {temperature:.1f} C",
                        None,
                    )
                )
            elif temperature > TEMP_WARNING:
                out.append(
                    (
                        "WARNING",
                        "THRESHOLD_EXCEEDED",
                        f"Temperatura elevada: {temperature:.1f} C",
                        None,
                    )
                )
        return out

    async def _sync_asset_status(
        self, asset_tag: str, session: AsyncSession, repo: AlertRepository
    ) -> None:
        """Sincroniza o status do ativo com a severidade dos alertas ativos."""
        severities = await repo.active_severities(asset_tag)
        if "CRITICAL" in severities:
            status = "critical"
        elif "WARNING" in severities:
            status = "warning"
        else:
            status = "ok"
        await session.execute(update(Asset).where(Asset.tag == asset_tag).values(status=status))
        await session.commit()


# Singleton compartilhado com o ciclo de vida da aplicacao.
alerts_evaluator = AlertsEvaluator()
