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
    """Conjunto de modelos treinados, com metadados de versao."""

    version: str
    trained_at: datetime
    n_samples: int
    baseline: Any
    autoencoder: Any = None
    anomaly_threshold: float = 0.0


class MlService:
    """Treina (sob demanda) e serve os modelos de ML."""

    def __init__(self) -> None:
        self._bundle: ModelBundle | None = None

    @property
    def ready(self) -> bool:
        return self._bundle is not None

    def status(self) -> MlStatus:
        if self._bundle is None:
            return MlStatus(ready=False)
        return MlStatus(
            ready=True,
            model_version=self._bundle.version,
            trained_at=self._bundle.trained_at,
            n_samples=self._bundle.n_samples,
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

    async def train(self, session: AsyncSession, asset_tag: str = "MTR-001") -> bool:
        """Treina os modelos a partir da telemetria recente; devolve sucesso."""
        wide = await self._fetch_wide(session, asset_tag, minutes=240)
        if len(wide) < MIN_TRAINING_SAMPLES or not all(
            column in wide.columns for column in SENSOR_ORDER
        ):
            logger.warning("ML: dados insuficientes para treino (%d amostras)", len(wide))
            return False

        features = wide[list(SENSOR_ORDER)].to_numpy(dtype=float)
        baseline = IsolationForest(n_estimators=120, contamination=0.03, random_state=42)
        baseline.fit(features)

        autoencoder: Any = None
        threshold = 0.0
        windows = _make_windows(wide[VIBRATION_VARIABLE].to_numpy(dtype=float), WINDOW_SIZE)
        if len(windows) >= MIN_TRAINING_SAMPLES:
            autoencoder = MLPRegressor(hidden_layer_sizes=(8, 4, 8), max_iter=500, random_state=42)
            autoencoder.fit(windows, windows)
            errors = np.mean((windows - autoencoder.predict(windows)) ** 2, axis=1)
            threshold = float(np.percentile(errors, 99))

        self._bundle = ModelBundle(
            version=datetime.now(UTC).strftime("v%Y%m%d%H%M%S"),
            trained_at=datetime.now(UTC),
            n_samples=int(len(wide)),
            baseline=baseline,
            autoencoder=autoencoder,
            anomaly_threshold=threshold,
        )
        logger.info(
            "ML: modelos treinados (%d amostras, versao %s)",
            self._bundle.n_samples,
            self._bundle.version,
        )
        return True

    async def _ensure(self, session: AsyncSession) -> None:
        if self._bundle is None:
            await self.train(session)

    async def predict_baseline(self, session: AsyncSession, asset_tag: str) -> BaselinePrediction:
        await self._ensure(session)
        if self._bundle is None:
            return BaselinePrediction(ready=False)
        wide = await self._fetch_wide(session, asset_tag, minutes=10)
        if wide.empty or not all(c in wide.columns for c in SENSOR_ORDER):
            return BaselinePrediction(ready=True, available=False, asset_tag=asset_tag)
        latest = wide[list(SENSOR_ORDER)].to_numpy(dtype=float)[-1:]
        score = float(self._bundle.baseline.score_samples(latest)[0])
        is_normal = int(self._bundle.baseline.predict(latest)[0]) == 1
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
            model_version=self._bundle.version,
        )

    async def predict_anomaly(self, session: AsyncSession, asset_tag: str) -> AnomalyPrediction:
        await self._ensure(session)
        if self._bundle is None or self._bundle.autoencoder is None:
            return AnomalyPrediction(ready=self._bundle is not None, available=False)
        wide = await self._fetch_wide(session, asset_tag, minutes=30)
        if wide.empty or VIBRATION_VARIABLE not in wide.columns:
            return AnomalyPrediction(ready=True, available=False, asset_tag=asset_tag)
        vibration = wide[VIBRATION_VARIABLE].to_numpy(dtype=float)
        if len(vibration) < WINDOW_SIZE:
            return AnomalyPrediction(ready=True, available=False, asset_tag=asset_tag)
        window = vibration[-WINDOW_SIZE:].reshape(1, -1)
        reconstruction = self._bundle.autoencoder.predict(window)
        error = float(np.mean((window - reconstruction) ** 2))
        is_anomaly = error > self._bundle.anomaly_threshold
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
            threshold=round(self._bundle.anomaly_threshold, 5),
            is_anomaly=is_anomaly,
            model_version=self._bundle.version,
        )

    async def estimate_rul(self, session: AsyncSession, asset_tag: str) -> RulEstimate:
        await self._ensure(session)
        version = self._bundle.version if self._bundle else None
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
