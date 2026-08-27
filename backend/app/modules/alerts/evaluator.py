"""Avaliador periodico de alertas: regras de limite + modelos de ML.

Executa como uma task em background, avaliando o ativo a cada 30 s, o que
atende ao criterio de detectar uma falha injetada em menos de 60 segundos.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infra.db.base import catalog_session_factory, timeseries_session_factory
from app.modules.alerts.models import Alert
from app.modules.alerts.repository import AlertRepository
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.ml.service import ml_service
from app.modules.telemetry.repository import TelemetryRepository

logger = logging.getLogger("forzy.alerts.evaluator")

EVALUATION_INTERVAL_S = 30.0
MONITORED_ASSET_TAG = "MTR-001"

# Limites operacionais globais (DIN ISO 10816/20816) - usados quando o ativo
# nao tem limiares proprios (contrato de metricas por percentil / por motor).
VIB_WARNING = 4.5
VIB_CRITICAL = 7.1
TEMP_WARNING = 95.0
TEMP_CRITICAL = 105.0
RUL_WARNING_DAYS = 45.0
RUL_CRITICAL_DAYS = 15.0
# Janela de deduplicacao: nao recria o mesmo tipo de alerta nesse intervalo.
DEDUP_MINUTES = 15
# ponytail: aceleracao minima esperada quando ha vibracao relevante - abaixo
# disso com velocidade alta indica divergencia (falha de sensor). Calibrar.
ACCEL_DIVERGENCE_MIN = 0.02

# (severidade, tipo, mensagem, score)
Candidate = tuple[str, str, str, float | None]


class AlertsEvaluator:
    """Avalia regras e modelos periodicamente e gera alertas."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running = False
        # Ciclos consecutivos de anomalia de ML por ativo (gate do alerta advisory).
        self._anomaly_streak: dict[str, int] = {}

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
        # 'physical' = condicao MEDIDA neste ciclo (circuit breaker + limiares).
        # E o que define o status/badge do ativo. Os alertas de ML sao advisory:
        # entram na lista de alertas, mas NAO prendem o badge em critico.
        physical: list[Candidate] = []

        # Limiares por ativo (contrato de metricas); nulos -> globais ISO.
        async with catalog_session_factory() as cat_session:
            asset = await AssetRepository(cat_session).get_asset_by_tag(asset_tag)
        thresholds = self._thresholds(asset)

        async with timeseries_session_factory() as ts_session:
            repo_ts = TelemetryRepository(ts_session)
            latest = await repo_ts.latest(asset_tag)
            readings = {row["variable"]: row["value"] for row in latest}
            qualities = {row["variable"]: row["quality"] for row in latest}
            recent = {
                variable: await repo_ts.recent_values(asset_tag, variable, 2)
                for variable in ("Vibracao_Velocidade_RMS", "Temperatura")
            }

            # Circuit Breaker: se o dado nao e confiavel, suspende o disparo
            # automatico e retem a decisao para revisao humana.
            breaker = self._circuit_breaker(readings, qualities, recent)
            if breaker is not None:
                physical.append(
                    (
                        "WARNING",
                        "CIRCUIT_BREAKER",
                        f"Alerta automático suspenso para revisão humana — {breaker}.",
                        None,
                    )
                )
            else:
                physical += self._threshold_rules(readings, recent, thresholds)
                # Anomalia de ML vira alerta CONSULTIVO (INFO): entra na lista de
                # alertas mas NAO prende o badge (_sync_asset_status usa so
                # 'physical'). Gate conservador (erro alto por 2 ciclos) evita o
                # falso-positivo que motivou desligar o ML no dado de demo.
                candidates += await self._ml_advisory(ts_session, asset_tag)

        # Todos (fisicos + ML) viram alertas; so os fisicos definem o status.
        candidates = physical + candidates

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
                await self._notify(alert)
            await self._sync_asset_status(asset_tag, cat_session, physical)
        return created

    async def _ml_advisory(self, session: AsyncSession, asset_tag: str) -> list[Candidate]:
        """Anomalia de ML como alerta CONSULTIVO (INFO), com gate de 2 ciclos.

        Usa so modelos ja carregados/prontos (``train_if_missing=False``) para nao
        disparar treino dentro do laco de 30s. Falha de ML nunca quebra a avaliacao.
        """
        try:
            pred = await ml_service.predict_anomaly(session, asset_tag, train_if_missing=False)
        except Exception:
            logger.warning("ML advisory falhou (%s)", asset_tag, exc_info=True)
            self._anomaly_streak.pop(asset_tag, None)
            return []
        threshold = pred.threshold
        error = pred.reconstruction_error
        # Gate mais duro que o is_anomaly cru: erro > 1.5x o limiar de treino.
        strong = bool(
            pred.available and pred.is_anomaly and threshold and error and error > 1.5 * threshold
        )
        if not strong:
            self._anomaly_streak[asset_tag] = 0
            return []
        streak = self._anomaly_streak.get(asset_tag, 0) + 1
        self._anomaly_streak[asset_tag] = streak
        if streak < 2:
            return []
        return [
            (
                "INFO",
                "ANOMALY_DETECTED",
                f"Consultivo: modelo de anomalia acusou vibração atípica "
                f"(erro {error:.4f}, limiar {threshold:.4f}).",
                error,
            )
        ]

    async def _notify(self, alert: Alert) -> None:
        """Entrega o alerta a um canal externo (webhook), se configurado.

        Fecha o loop da manutencao preditiva: um alerta >= WARNING chega a quem
        precisa agir sem depender de alguem com a UI aberta. A deduplicacao do
        avaliador ja evita spam; falhas de rede nunca derrubam a avaliacao.
        """
        url = get_settings().alert_webhook_url
        if not url or alert.severity not in ("WARNING", "CRITICAL"):
            return
        payload = {
            "asset_tag": alert.asset_tag,
            "severity": alert.severity,
            "type": alert.alert_type,
            "message": alert.message,
            "score": alert.ml_score,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:  # noqa: BLE001 - webhook nao pode quebrar o avaliador
            logger.warning("Falha ao notificar alerta via webhook: %s", exc)

    @staticmethod
    def _thresholds(asset: Asset | None) -> dict[str, float]:
        """Limiares do ativo (contrato por percentil) ou globais ISO se nulos."""
        return {
            "vib_warning": (
                asset.vib_warning if asset and asset.vib_warning is not None else VIB_WARNING
            ),
            "vib_critical": (
                asset.vib_critical if asset and asset.vib_critical is not None else VIB_CRITICAL
            ),
            "temp_warning": (
                asset.temp_warning if asset and asset.temp_warning is not None else TEMP_WARNING
            ),
            "temp_critical": (
                asset.temp_critical if asset and asset.temp_critical is not None else TEMP_CRITICAL
            ),
        }

    @staticmethod
    def _circuit_breaker(
        readings: dict[str, Any],
        qualities: dict[str, Any],
        recent: dict[str, list[dict[str, Any]]],
    ) -> str | None:
        """Motivo para suspender o alerta automatico, ou None se o dado e confiavel."""
        gap_limit = get_settings().circuit_breaker_gap_seconds
        vib_recent = recent.get("Vibracao_Velocidade_RMS", [])
        # 1. Intervalo entre as duas ultimas leituras alem do esperado.
        if len(vib_recent) >= 2:
            gap = abs((vib_recent[0]["time"] - vib_recent[1]["time"]).total_seconds())
            if gap > gap_limit:
                return f"intervalo de {gap:.0f}s entre leituras (possível falha de comunicação)"
        # 2. Qualidade comprometida (dado fora de faixa ou inconsistente).
        if any(quality not in (None, 0) for quality in qualities.values()):
            return "leitura fora de faixa ou inconsistente (qualidade comprometida)"
        # 3. Velocidade e aceleracao divergindo (normalmente correlacionadas).
        velocity = readings.get("Vibracao_Velocidade_RMS")
        accel = readings.get("Vibracao_Aceleracao_RMS")
        if (
            velocity is not None
            and accel is not None
            and velocity > 1.0
            and accel < ACCEL_DIVERGENCE_MIN
        ):
            return "velocidade elevada sem aceleração correspondente (possível falha do sensor)"
        return None

    def _threshold_rules(
        self,
        readings: dict[str, Any],
        recent: dict[str, list[dict[str, Any]]],
        thresholds: dict[str, float],
    ) -> list[Candidate]:
        """Regras de limite por faixa (Normal / Atenção / Crítico) por ativo."""
        out: list[Candidate] = []
        vibration = readings.get("Vibracao_Velocidade_RMS")
        if vibration is not None:
            out += self._band_rule(
                "Vibração",
                vibration,
                "mm/s",
                thresholds["vib_warning"],
                thresholds["vib_critical"],
                [row["value"] for row in recent.get("Vibracao_Velocidade_RMS", [])],
            )
        temperature = readings.get("Temperatura")
        if temperature is not None:
            out += self._band_rule(
                "Temperatura",
                temperature,
                "°C",
                thresholds["temp_warning"],
                thresholds["temp_critical"],
                [row["value"] for row in recent.get("Temperatura", [])],
            )
        return out

    @staticmethod
    def _band_rule(
        label: str,
        value: float,
        unit: str,
        warn: float,
        crit: float,
        recent_values: list[float],
    ) -> list[Candidate]:
        """Uma variavel -> faixa Atenção/Crítico, com anomalia por 2 leituras."""
        if value > crit:
            # Anomalia so confirmada com >= 2 leituras consecutivas acima do critico.
            consecutive = sum(1 for reading in recent_values[:2] if reading > crit)
            if consecutive >= 2:
                return [
                    (
                        "CRITICAL",
                        "THRESHOLD_EXCEEDED",
                        f"Crítico: {label} em {value:.1f} {unit} — acima do limite "
                        f"{crit:.1f} por 2 leituras consecutivas.",
                        None,
                    )
                ]
            return [
                (
                    "WARNING",
                    "THRESHOLD_APPROACHING",
                    f"Atenção: {label} em {value:.1f} {unit} — acima do limite {crit:.1f}, "
                    "aguardando confirmação (2ª leitura).",
                    None,
                )
            ]
        if value > warn:
            return [
                (
                    "WARNING",
                    "THRESHOLD_APPROACHING",
                    f"Atenção: {label} em {value:.1f} {unit} — aproximando-se do limite "
                    f"crítico de {crit:.1f} {unit}.",
                    None,
                )
            ]
        return []

    async def _sync_asset_status(
        self, asset_tag: str, session: AsyncSession, physical: list[Candidate]
    ) -> None:
        """Status do ativo = condicao fisica MEDIDA neste ciclo.

        Antes usava os alertas historicos nao-reconhecidos: um unico pico
        antigo prendia o badge em 'critico' para sempre. Agora reflete a
        leitura atual (limiares + circuit breaker); os alertas de ML nao
        entram no badge (sao advisory na aba de saude do ativo).
        """
        severities = {candidate[0] for candidate in physical}
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
