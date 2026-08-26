"""Servico de Machine Learning: treino sob demanda e serving dos modelos.

Modelos (ver ADR 0005):
- baseline: Isolation Forest sobre o vetor multivariavel dos 6 sensores;
- anomalia: autoencoder MLP de reconstrucao sobre janelas de vibracao;
- RUL: regressao linear da tendencia de vibracao ate o limite DIN ISO 10816.

Os modelos sao treinados sob demanda a partir da telemetria do TimescaleDB e
mantidos em memoria, com versionamento. Cada predicao e registrada em log
estruturado (governanca de ML).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.timescale import telemetry_processed
from app.modules.ml.schemas import (
    AnomalyPrediction,
    BaselinePrediction,
    FeedbackRequest,
    FeedbackResponse,
    MlStatus,
    RulEstimate,
)

logger = logging.getLogger("forzy.ml.service")

SENSOR_ORDER = (
    "Tensao",
    "Corrente",
    "Temperatura",
    "Rotacao",
    "Vibracao_Velocidade_RMS",
    "Vibracao_Aceleracao_RMS",
)
VIBRATION_VARIABLE = "Vibracao_Velocidade_RMS"
# Limite de vibracao para fim de vida (DIN ISO 10816/20816, zona D).
VIBRATION_FAILURE_THRESHOLD = 7.1
WINDOW_SIZE = 16
MIN_TRAINING_SAMPLES = 80


def _make_windows(values: np.ndarray, size: int) -> np.ndarray:
    """Fatia o vetor em janelas deslizantes de comprimento ``size``."""
    if len(values) < size:
        return np.empty((0, size))
    return np.array([values[i : i + size] for i in range(len(values) - size + 1)])


@dataclass
class ModelBundle:
    """Conjunto de modelos treinados de UM ativo, com metadados de versao."""

    version: str
    trained_at: datetime
    n_samples: int
    baseline: Any
    # Features realmente usadas (o ativo pode nao ter os 6 sensores - ex.: os
    # motores fisicos Forzy so tem vibracao + temperatura).
    features: tuple[str, ...] = ()
    autoencoder: Any = None
    anomaly_threshold: float = 0.0


class MlService:
    """Treina (sob demanda, POR ATIVO) e serve os modelos de ML."""

    def __init__(self) -> None:
        # Um modelo por ativo: evita aplicar o modelo do MTR-001 a outros motores.
        self._bundles: dict[str, ModelBundle] = {}
        # Lock por ativo: serializa o treino do mesmo motor (evita o avaliador de
        # alertas e uma requisicao HTTP dispararem o mesmo treino em paralelo).
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def ready(self) -> bool:
        return bool(self._bundles)

    def status(self) -> MlStatus:
        if not self._bundles:
            return MlStatus(ready=False)
        latest = max(self._bundles.values(), key=lambda bundle: bundle.trained_at)
        return MlStatus(
            ready=True,
            model_version=latest.version,
            trained_at=latest.trained_at,
            n_samples=latest.n_samples,
        )

    async def _fetch_wide(
        self, session: AsyncSession, asset_tag: str, minutes: int
    ) -> pd.DataFrame:
        """Carrega a telemetria recente em formato wide (uma coluna por sensor)."""
        start = datetime.now(UTC) - timedelta(minutes=minutes)
        stmt = (
            select(
                telemetry_processed.c.time,
                telemetry_processed.c.variable,
                telemetry_processed.c.value,
            )
            .where(
                telemetry_processed.c.asset_tag == asset_tag,
                telemetry_processed.c.time >= start,
            )
            .order_by(telemetry_processed.c.time)
        )
        result = await session.execute(stmt)
        rows = [dict(row) for row in result.mappings().all()]
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        frame["time"] = pd.to_datetime(frame["time"]).dt.floor("s")
        wide = frame.pivot_table(index="time", columns="variable", values="value", aggfunc="mean")
        present = [column for column in SENSOR_ORDER if column in wide.columns]
        return wide.dropna(subset=present)

    async def _fetch_history(
        self, session: AsyncSession, asset_tag: str, max_rows: int = 60000
    ) -> pd.DataFrame:
        """Historico do ativo em formato wide (por contagem, sem filtro de tempo).

        Usado no TREINO: pega as ultimas ``max_rows`` leituras independentemente
        da data, o que permite treinar tambem com o dado real importado (que e de
        meses atras) - nao so com a janela recente do simulador.
        """
        stmt = (
            select(
                telemetry_processed.c.time,
                telemetry_processed.c.variable,
                telemetry_processed.c.value,
            )
            .where(telemetry_processed.c.asset_tag == asset_tag)
            .order_by(telemetry_processed.c.time.desc())
            .limit(max_rows)
        )
        result = await session.execute(stmt)
        rows = [dict(row) for row in result.mappings().all()]
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        frame["time"] = pd.to_datetime(frame["time"]).dt.floor("s")
        wide = frame.pivot_table(index="time", columns="variable", values="value", aggfunc="mean")
        wide = wide.sort_index()
        present = [column for column in SENSOR_ORDER if column in wide.columns]
        return wide.dropna(subset=present)

    def _fit_bundle(self, wide: pd.DataFrame, available: list[str]) -> ModelBundle:
        """Parte CPU-bound do treino (sklearn). Roda via ``asyncio.to_thread``
        para NAO bloquear o event loop do uvicorn - no free tier (1 worker) o
        ``.fit()`` sincrono travava toda a API enquanto treinava.
        """
        features = wide[available].to_numpy(dtype=float)
        baseline = IsolationForest(n_estimators=120, contamination=0.03, random_state=42)
        baseline.fit(features)

        # Autoencoder de vibracao: so quando ha o sinal de velocidade de vibracao.
        autoencoder: Any = None
        threshold = 0.0
        if VIBRATION_VARIABLE in wide.columns:
            windows = _make_windows(wide[VIBRATION_VARIABLE].to_numpy(dtype=float), WINDOW_SIZE)
            if len(windows) >= MIN_TRAINING_SAMPLES:
                autoencoder = MLPRegressor(
                    hidden_layer_sizes=(8, 4, 8), max_iter=500, random_state=42
                )
                autoencoder.fit(windows, windows)
                errors = np.mean((windows - autoencoder.predict(windows)) ** 2, axis=1)
                threshold = float(np.percentile(errors, 99))

        return ModelBundle(
            version=datetime.now(UTC).strftime("v%Y%m%d%H%M%S"),
            trained_at=datetime.now(UTC),
            n_samples=int(len(wide)),
            baseline=baseline,
            features=tuple(available),
            autoencoder=autoencoder,
            anomaly_threshold=threshold,
        )

    async def train(self, session: AsyncSession, asset_tag: str = "MTR-001") -> bool:
        """Treina os modelos DESTE ativo com as variaveis que ele realmente tem."""
        wide = await self._fetch_history(session, asset_tag)
        available = [column for column in SENSOR_ORDER if column in wide.columns]
        if len(wide) < MIN_TRAINING_SAMPLES or not available:
            logger.warning(
                "ML: dados insuficientes para treino de %s (%d amostras, %d features)",
                asset_tag,
                len(wide),
                len(available),
            )
            return False

        # sklearn (CPU-bound) fora do event loop -> a API continua respondendo.
        bundle = await asyncio.to_thread(self._fit_bundle, wide, available)
        self._bundles[asset_tag] = bundle
        logger.info(
            "ML: modelos treinados asset=%s (%d amostras, features=%s, versao %s)",
            asset_tag,
            bundle.n_samples,
            ",".join(available),
            bundle.version,
        )
        return True

    async def _ensure(self, session: AsyncSession, asset_tag: str) -> None:
        if asset_tag in self._bundles:
            return
        # Serializa por ativo e re-checa: so um treino por motor de cada vez.
        lock = self._locks.setdefault(asset_tag, asyncio.Lock())
        async with lock:
            if asset_tag not in self._bundles:
                await self.train(session, asset_tag)

    async def predict_baseline(self, session: AsyncSession, asset_tag: str) -> BaselinePrediction:
        await self._ensure(session, asset_tag)
        bundle = self._bundles.get(asset_tag)
        if bundle is None:
            return BaselinePrediction(ready=self.ready, available=False, asset_tag=asset_tag)
        wide = await self._fetch_wide(session, asset_tag, minutes=10)
        if wide.empty or not all(c in wide.columns for c in bundle.features):
            return BaselinePrediction(ready=True, available=False, asset_tag=asset_tag)
        latest = wide[list(bundle.features)].to_numpy(dtype=float)[-1:]
        score = float(bundle.baseline.score_samples(latest)[0])
        is_normal = int(bundle.baseline.predict(latest)[0]) == 1
        logger.info(
            "ml_prediction model=baseline asset=%s decision=%s score=%.4f",
            asset_tag,
            "normal" if is_normal else "anomalo",
            score,
            extra={"event": "ml_prediction", "asset_tag": asset_tag},
        )
        return BaselinePrediction(
            ready=True,
            available=True,
            asset_tag=asset_tag,
            score=round(score, 4),
            decision="normal" if is_normal else "anomalo",
            model_version=bundle.version,
        )

    async def predict_anomaly(self, session: AsyncSession, asset_tag: str) -> AnomalyPrediction:
        await self._ensure(session, asset_tag)
        bundle = self._bundles.get(asset_tag)
        if bundle is None or bundle.autoencoder is None:
            return AnomalyPrediction(ready=self.ready, available=False, asset_tag=asset_tag)
        wide = await self._fetch_wide(session, asset_tag, minutes=30)
        if wide.empty or VIBRATION_VARIABLE not in wide.columns:
            return AnomalyPrediction(ready=True, available=False, asset_tag=asset_tag)
        vibration = wide[VIBRATION_VARIABLE].to_numpy(dtype=float)
        if len(vibration) < WINDOW_SIZE:
            return AnomalyPrediction(ready=True, available=False, asset_tag=asset_tag)
        window = vibration[-WINDOW_SIZE:].reshape(1, -1)
        reconstruction = bundle.autoencoder.predict(window)
        error = float(np.mean((window - reconstruction) ** 2))
        is_anomaly = error > bundle.anomaly_threshold
        logger.info(
            "ml_prediction model=anomaly asset=%s anomaly=%s error=%.5f",
            asset_tag,
            is_anomaly,
            error,
            extra={"event": "ml_prediction", "asset_tag": asset_tag},
        )
        return AnomalyPrediction(
            ready=True,
            available=True,
            asset_tag=asset_tag,
            reconstruction_error=round(error, 5),
            threshold=round(bundle.anomaly_threshold, 5),
            is_anomaly=is_anomaly,
            model_version=bundle.version,
        )

    async def estimate_rul(self, session: AsyncSession, asset_tag: str) -> RulEstimate:
        await self._ensure(session, asset_tag)
        bundle = self._bundles.get(asset_tag)
        version = bundle.version if bundle else None
        wide = await self._fetch_wide(session, asset_tag, minutes=240)
        if wide.empty or VIBRATION_VARIABLE not in wide.columns or len(wide) < 30:
            return RulEstimate(
                ready=True,
                available=False,
                asset_tag=asset_tag,
                note="Historico insuficiente para estimar o RUL.",
            )
        series = wide[VIBRATION_VARIABLE]
        origin = series.index[0]
        seconds = np.array([(ts - origin).total_seconds() for ts in series.index]).reshape(-1, 1)
        values = series.to_numpy(dtype=float)
        regression = LinearRegression().fit(seconds, values)
        slope_per_day = float(regression.coef_[0]) * 86400.0
        current = float(values[-1])

        # Erro-padrao da inclinacao para o intervalo de confianca.
        residuals = values - regression.predict(seconds)
        flat = seconds.flatten()
        sxx = float(np.sum((flat - flat.mean()) ** 2))
        resid_var = float(np.sum(residuals**2)) / max(len(flat) - 2, 1)
        slope_se_day = (np.sqrt(resid_var / sxx) * 86400.0) if sxx > 0 else 0.0

        if slope_per_day <= 0.002:
            return RulEstimate(
                ready=True,
                available=True,
                asset_tag=asset_tag,
                rul_days=None,
                current_vibration=round(current, 4),
                trend_mm_s_per_day=round(slope_per_day, 5),
                model_version=version,
                note="Sem tendencia de degradacao mensuravel - vida util longa.",
            )

        remaining = max(VIBRATION_FAILURE_THRESHOLD - current, 0.0)
        rul_days = remaining / slope_per_day
        slope_fast = slope_per_day + 2.0 * slope_se_day
        slope_slow = max(slope_per_day - 2.0 * slope_se_day, 0.0005)
        return RulEstimate(
            ready=True,
            available=True,
            asset_tag=asset_tag,
            rul_days=round(rul_days, 1),
            confidence_low_days=round(remaining / slope_fast, 1),
            confidence_high_days=round(remaining / slope_slow, 1),
            current_vibration=round(current, 4),
            trend_mm_s_per_day=round(slope_per_day, 5),
            model_version=version,
            note="Estimativa por tendencia de vibracao ate o limite ISO 10816.",
        )

    def record_feedback(self, feedback: FeedbackRequest, actor: str) -> FeedbackResponse:
        """Registra o feedback de uma predicao (loop de melhoria)."""
        logger.info(
            "ml_feedback model=%s asset=%s correct=%s actor=%s comment=%s",
            feedback.model,
            feedback.asset_tag,
            feedback.is_correct,
            actor,
            feedback.comment or "-",
            extra={"event": "ml_feedback", "asset_tag": feedback.asset_tag},
        )
        return FeedbackResponse(
            recorded=True, message="Feedback registrado. Obrigado pela contribuicao."
        )


# Singleton compartilhado entre os endpoints e o avaliador de alertas.
ml_service = MlService()
