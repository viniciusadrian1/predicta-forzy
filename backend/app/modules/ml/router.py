"""Endpoints REST do modulo de Machine Learning."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_actor
from app.core.rbac import require_role
from app.infra.db.base import get_timeseries_session
from app.modules.ml.schemas import (
    AnomalyPrediction,
    BaselinePrediction,
    FeedbackRequest,
    FeedbackResponse,
    MlStatus,
    PredictRequest,
    RulEstimate,
)
from app.modules.ml.service import ml_service

router = APIRouter(tags=["ml"])


@router.get("/ml/status", response_model=MlStatus)
async def ml_status() -> MlStatus:
    """Estado dos modelos de ML em memoria."""
    return ml_service.status()


@router.post(
    "/ml/train",
    response_model=MlStatus,
    dependencies=[Depends(require_role("engineer"))],
)
async def ml_train(
    session: AsyncSession = Depends(get_timeseries_session),
) -> MlStatus:
    """Forca o retreino dos modelos a partir da telemetria recente."""
    await ml_service.train(session)
    return ml_service.status()


@router.post("/ml/baseline/predict", response_model=BaselinePrediction)
async def baseline_predict(
    payload: PredictRequest,
    session: AsyncSession = Depends(get_timeseries_session),
) -> BaselinePrediction:
    """Avalia o ponto de operacao do ativo (Isolation Forest)."""
    return await ml_service.predict_baseline(session, payload.asset_tag)


@router.post("/ml/anomaly/predict", response_model=AnomalyPrediction)
async def anomaly_predict(
    payload: PredictRequest,
    session: AsyncSession = Depends(get_timeseries_session),
) -> AnomalyPrediction:
    """Detecta anomalia de vibracao por erro de reconstrucao (autoencoder)."""
    return await ml_service.predict_anomaly(session, payload.asset_tag)


@router.get("/ml/rul/{tag}", response_model=RulEstimate)
async def rul_estimate(
    tag: str,
    session: AsyncSession = Depends(get_timeseries_session),
) -> RulEstimate:
    """Estima a vida util remanescente (RUL) do ativo."""
    return await ml_service.estimate_rul(session, tag)


@router.post("/ml/feedback", response_model=FeedbackResponse)
async def ml_feedback(
    payload: FeedbackRequest,
    actor: str = Depends(get_current_actor),
) -> FeedbackResponse:
    """Registra um reporte de predicao incorreta (loop de feedback)."""
    return ml_service.record_feedback(payload, actor)
