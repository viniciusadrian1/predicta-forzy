"""Schemas Pydantic do modulo de Machine Learning."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PredictRequest(BaseModel):
    asset_tag: str = "MTR-001"


class FeedbackOut(BaseModel):
    """Um reporte de feedback persistido (loop de melhoria)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_tag: str
    model: str
    prediction: str
    is_correct: bool
    comment: str | None
    actor: str
    created_at: datetime


class BaselinePrediction(BaseModel):
    """Resultado do modelo de baseline (Isolation Forest)."""

    ready: bool
    available: bool = False
    asset_tag: str | None = None
    score: float | None = None
    decision: str | None = None
    model_version: str | None = None


class AnomalyPrediction(BaseModel):
    """Resultado do detector de anomalias (autoencoder de reconstrucao)."""

    ready: bool
    available: bool = False
    asset_tag: str | None = None
    reconstruction_error: float | None = None
    threshold: float | None = None
    is_anomaly: bool | None = None
    model_version: str | None = None


class RulEstimate(BaseModel):
    """Estimativa de vida util remanescente (RUL)."""

    ready: bool
    available: bool = False
    asset_tag: str | None = None
    rul_days: float | None = None
    confidence_low_days: float | None = None
    confidence_high_days: float | None = None
    current_vibration: float | None = None
    trend_mm_s_per_day: float | None = None
    model_version: str | None = None
    note: str | None = None


class FaultPrediction(BaseModel):
    """Classificacao de TIPO de falha (modelo treinado em dado simulado).

    So disponivel no ativo de demonstracao (MTR-001): o classificador foi
    treinado no dado sintetico rotulado, cuja distribuicao casa com o simulador.
    Nos motores reais fica indisponivel ate haver falha real rotulada.
    """

    ready: bool
    available: bool = False
    asset_tag: str | None = None
    fault: str | None = None
    confidence: float | None = None
    simulated: bool = True
    note: str | None = None


class MlStatus(BaseModel):
    """Estado dos modelos de ML em memoria."""

    ready: bool
    model_version: str | None = None
    trained_at: datetime | None = None
    n_samples: int | None = None


class FeedbackRequest(BaseModel):
    """Reporte de predicao incorreta (loop de feedback - governanca de ML)."""

    asset_tag: str
    model: str
    prediction: str
    is_correct: bool
    comment: str | None = None


class FeedbackResponse(BaseModel):
    recorded: bool
    message: str
