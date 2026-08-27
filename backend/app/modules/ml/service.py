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
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import catalog_session_factory
from app.infra.db.timescale import telemetry_processed
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.ml.schemas import (
    AnomalyPrediction,
    BaselinePrediction,
    FaultPrediction,
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
# Limite de vibracao para fim de vida (DIN ISO 10816/20816, zona D). Fallback
# quando o ativo nao tem limiar proprio; o RUL prefere asset.vib_critical.
VIBRATION_FAILURE_THRESHOLD = 7.1
# Dado do fabricante: intervalo de inspecao de rolamento do plano de manutencao
# (avaliacao SEMESTRAL). Serve de TETO para o "momento de parada" - a
# recomendacao nunca ultrapassa a inspecao preventiva recomendada.
MANUFACTURER_INSPECTION_DAYS = 180.0
WINDOW_SIZE = 16
MIN_TRAINING_SAMPLES = 80
# Modelos PRONTOS (treinados offline no dado real da Forzy e versionados no
# repositorio). Se existe <tag>.joblib aqui, o serving carrega em vez de
# retreinar na hora. Sem artefato, cai no retreino sob demanda (fallback).
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
# Classificador de TIPO de falha: treinado em dado SIMULADO rotulado. So serve o
# ativo de demonstracao (a distribuicao casa com o simulador); nos motores reais
# fica indisponivel ate haver falha real rotulada.
FAULT_CLASSIFIER_PATH = ARTIFACTS_DIR / "fault_classifier.joblib"
FAULT_DEMO_TAG = "MTR-001"
FAULT_FEATURE_WINDOW = 15


def build_fault_features(
    vel: pd.Series, accel: pd.Series, temp: pd.Series
) -> pd.DataFrame:
    """Features do classificador de falha (vibracao + temperatura apenas).

    Fonte unica reusada no treino offline e no serving, garantindo paridade de
    features. Ordem das colunas fixa (o artefato guarda a lista e o serving
    reindexa por ela).
    """
    feats = pd.DataFrame(index=vel.index)
    for name, series in (("vel", vel), ("accel", accel), ("temp", temp)):
        feats[name] = series
        feats[f"{name}_mean"] = series.rolling(FAULT_FEATURE_WINDOW, min_periods=1).mean()
        feats[f"{name}_std"] = (
            series.rolling(FAULT_FEATURE_WINDOW, min_periods=1).std().fillna(0.0)
        )
    feats["vel_roc"] = vel.diff().abs().fillna(0.0)
    return feats.fillna(0.0)


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


def fit_bundle(wide: pd.DataFrame, available: list[str]) -> ModelBundle:
    """Treina o conjunto de modelos de UM ativo (parte CPU-bound, sklearn).

    Isolada em nivel de modulo para ser reusada tanto pelo treino sob demanda
    (via ``asyncio.to_thread``) quanto pelo script offline que gera os modelos
    PRONTOS a partir do dado real. Roda fora do event loop para nao travar a API.
    """
    features = wide[available].to_numpy(dtype=float)
    # Modelos enxutos: cabem na memoria/CPU do free tier (512MB / 0.1 vCPU).
    baseline = IsolationForest(n_estimators=60, contamination=0.03, random_state=42)
    baseline.fit(features)

    # Autoencoder de vibracao: so quando ha o sinal de velocidade de vibracao.
    autoencoder: Any = None
    threshold = 0.0
    if VIBRATION_VARIABLE in wide.columns:
        windows = _make_windows(wide[VIBRATION_VARIABLE].to_numpy(dtype=float), WINDOW_SIZE)
        if len(windows) >= MIN_TRAINING_SAMPLES:
            autoencoder = MLPRegressor(hidden_layer_sizes=(8, 4, 8), max_iter=200, random_state=42)
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


class MlService:
    """Treina (sob demanda, POR ATIVO) e serve os modelos de ML."""

    def __init__(self) -> None:
        # Um modelo por ativo: evita aplicar o modelo do MTR-001 a outros motores.
        self._bundles: dict[str, ModelBundle] = {}
        # Lock por ativo: serializa o treino do mesmo motor (evita o avaliador de
        # alertas e uma requisicao HTTP dispararem o mesmo treino em paralelo).
        self._locks: dict[str, asyncio.Lock] = {}
        # Classificador de falha (carregado uma vez, sob demanda).
        self._fault_clf: dict[str, Any] | None = None
        self._fault_clf_loaded = False

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
        self, session: AsyncSession, asset_tag: str, max_rows: int = 5000
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
        bundle = await asyncio.to_thread(fit_bundle, wide, available)
        self._bundles[asset_tag] = bundle
        logger.info(
            "ML: modelos treinados asset=%s (%d amostras, features=%s, versao %s)",
            asset_tag,
            bundle.n_samples,
            ",".join(available),
            bundle.version,
        )
        return True

    def _load_shipped(self, asset_tag: str) -> bool:
        """Carrega o modelo PRONTO do ativo (treinado offline), se existir.

        Prioridade sobre o retreino: se ha um artefato versionado no repo, ele
        e a fonte da verdade. Qualquer falha ao desserializar (ex.: versao de
        sklearn incompativel) cai no fallback de retreino, sem derrubar a API.
        """
        path = ARTIFACTS_DIR / f"{asset_tag}.joblib"
        if not path.exists():
            return False
        try:
            self._bundles[asset_tag] = joblib.load(path)
            logger.info(
                "ML: modelo pronto carregado asset=%s versao=%s",
                asset_tag,
                self._bundles[asset_tag].version,
            )
            return True
        except Exception:
            logger.exception("ML: falha ao carregar modelo pronto de %s; vai retreinar", asset_tag)
            return False

    async def _ensure(
        self, session: AsyncSession, asset_tag: str, *, train_if_missing: bool = True
    ) -> None:
        if asset_tag in self._bundles:
            return
        # Serializa por ativo e re-checa: so um treino/carga por motor de cada vez.
        lock = self._locks.setdefault(asset_tag, asyncio.Lock())
        async with lock:
            if asset_tag in self._bundles:
                return
            # 1) modelo pronto (offline) tem prioridade; 2) senao, retreina.
            if self._load_shipped(asset_tag):
                return
            if train_if_missing:
                await self.train(session, asset_tag)

    async def predict_baseline(
        self, session: AsyncSession, asset_tag: str, *, train_if_missing: bool = True
    ) -> BaselinePrediction:
        await self._ensure(session, asset_tag, train_if_missing=train_if_missing)
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

    async def predict_anomaly(
        self, session: AsyncSession, asset_tag: str, *, train_if_missing: bool = True
    ) -> AnomalyPrediction:
        await self._ensure(session, asset_tag, train_if_missing=train_if_missing)
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

    async def _fetch_asset(
        self, asset_tag: str, catalog_session: AsyncSession | None
    ) -> Asset | None:
        """Busca o ativo usando a sessao injetada (testavel) ou a factory global."""
        if catalog_session is not None:
            return await AssetRepository(catalog_session).get_asset_by_tag(asset_tag)
        async with catalog_session_factory() as cat_session:
            return await AssetRepository(cat_session).get_asset_by_tag(asset_tag)

    async def estimate_rul(
        self,
        session: AsyncSession,
        asset_tag: str,
        *,
        train_if_missing: bool = True,
        catalog_session: AsyncSession | None = None,
    ) -> RulEstimate:
        await self._ensure(session, asset_tag, train_if_missing=train_if_missing)
        bundle = self._bundles.get(asset_tag)
        version = bundle.version if bundle else None

        # Dado do FABRICANTE: limiar de vibracao POR MOTOR (contrato de metricas
        # / placa) e o intervalo de inspecao preventiva. O momento de parada
        # combina a tendencia (historico) com esses limites do fabricante.
        asset = await self._fetch_asset(asset_tag, catalog_session)
        failure_threshold = (
            asset.vib_critical
            if asset and asset.vib_critical is not None
            else VIBRATION_FAILURE_THRESHOLD
        )
        ceiling = MANUFACTURER_INSPECTION_DAYS

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
            # Sem degradacao mensuravel: o momento de parada passa a ser a
            # inspecao preventiva do fabricante (nao "vida infinita").
            return RulEstimate(
                ready=True,
                available=True,
                asset_tag=asset_tag,
                rul_days=round(ceiling, 1),
                current_vibration=round(current, 4),
                trend_mm_s_per_day=round(slope_per_day, 5),
                model_version=version,
                note=(
                    "Sem degradacao mensuravel; parada recomendada pela inspecao "
                    f"semestral de rolamento do fabricante ({ceiling:.0f} dias)."
                ),
            )

        remaining = max(failure_threshold - current, 0.0)
        rul_vibration = remaining / slope_per_day
        # Momento de parada = min(condicao por vibracao, inspecao do fabricante).
        rul_days = min(rul_vibration, ceiling)
        slope_fast = slope_per_day + 2.0 * slope_se_day
        slope_slow = max(slope_per_day - 2.0 * slope_se_day, 0.0005)
        basis = (
            f"tendencia de vibracao ate {failure_threshold:.1f} mm/s"
            if rul_vibration <= ceiling
            else f"inspecao semestral do fabricante ({ceiling:.0f} dias)"
        )
        return RulEstimate(
            ready=True,
            available=True,
            asset_tag=asset_tag,
            rul_days=round(rul_days, 1),
            confidence_low_days=round(min(remaining / slope_fast, ceiling), 1),
            confidence_high_days=round(min(remaining / slope_slow, ceiling), 1),
            current_vibration=round(current, 4),
            trend_mm_s_per_day=round(slope_per_day, 5),
            model_version=version,
            note=f"Momento de parada por {basis} (limiar do motor + plano do fabricante).",
        )

    def _load_fault_classifier(self) -> dict[str, Any] | None:
        """Carrega o classificador de falha do artefato (uma vez)."""
        if self._fault_clf_loaded:
            return self._fault_clf
        self._fault_clf_loaded = True
        if not FAULT_CLASSIFIER_PATH.exists():
            return None
        try:
            self._fault_clf = joblib.load(FAULT_CLASSIFIER_PATH)
            logger.info("ML: classificador de falha carregado (simulado)")
        except Exception:
            logger.exception("ML: falha ao carregar classificador de falha")
            self._fault_clf = None
        return self._fault_clf

    async def predict_fault(self, session: AsyncSession, asset_tag: str) -> FaultPrediction:
        """Classifica o TIPO de falha atual (so no ativo de demonstracao)."""
        if asset_tag != FAULT_DEMO_TAG:
            return FaultPrediction(
                ready=self.ready,
                available=False,
                asset_tag=asset_tag,
                note="Classificacao de falha (simulada) so no ativo de demonstracao.",
            )
        clf = self._load_fault_classifier()
        if clf is None:
            return FaultPrediction(ready=self.ready, available=False, asset_tag=asset_tag)
        wide = await self._fetch_wide(session, asset_tag, minutes=30)
        needed = ("Vibracao_Velocidade_RMS", "Vibracao_Aceleracao_RMS", "Temperatura")
        if wide.empty or not all(column in wide.columns for column in needed):
            return FaultPrediction(ready=True, available=False, asset_tag=asset_tag)
        feats = build_fault_features(
            wide["Vibracao_Velocidade_RMS"],
            wide["Vibracao_Aceleracao_RMS"],
            wide["Temperatura"],
        ).reindex(columns=clf["features"], fill_value=0.0)
        latest = feats.to_numpy(dtype=float)[-1:]
        model = clf["model"]
        fault = str(model.predict(latest)[0])
        confidence = float(np.max(model.predict_proba(latest)))
        logger.info(
            "ml_prediction model=fault asset=%s fault=%s conf=%.3f",
            asset_tag,
            fault,
            confidence,
            extra={"event": "ml_prediction", "asset_tag": asset_tag},
        )
        return FaultPrediction(
            ready=True,
            available=True,
            asset_tag=asset_tag,
            fault=fault,
            confidence=round(confidence, 3),
            simulated=True,
            note="Treinado em dado simulado (motor de demonstracao).",
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
