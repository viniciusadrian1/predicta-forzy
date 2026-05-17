"""Schemas Pydantic do modulo de Machine Learning."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PredictRequest(BaseModel):
    asset_tag: str = "MTR-001"


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
