"""Endpoints REST do modulo de Machine Learning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_actor
from app.core.rbac import require_role
from app.infra.db.base import get_catalog_session, get_timeseries_session
from app.modules.ml.models import MlFeedback
from app.modules.ml.repository import MlFeedbackRepository
from app.modules.ml.schemas import (
    AnomalyPrediction,
    BaselinePrediction,
    FaultPrediction,
    FeedbackOut,
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


@router.post("/ml/fault/predict", response_model=FaultPrediction)
async def fault_predict(
    payload: PredictRequest,
    session: AsyncSession = Depends(get_timeseries_session),
) -> FaultPrediction:
    """Classifica o tipo de falha atual (modelo simulado, so na demo MTR-001)."""
    return await ml_service.predict_fault(session, payload.asset_tag)


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
    catalog: AsyncSession = Depends(get_catalog_session),
) -> FeedbackResponse:
    """Registra um reporte de predicao incorreta (loop de feedback persistido)."""
    await MlFeedbackRepository(catalog).create(
        MlFeedback(
            asset_tag=payload.asset_tag,
            model=payload.model,
            prediction=payload.prediction,
            is_correct=payload.is_correct,
            comment=payload.comment,
            actor=actor,
        )
    )
    return ml_service.record_feedback(payload, actor)


@router.get("/ml/feedback", response_model=list[FeedbackOut])
async def list_feedback(
    limit: int = Query(default=100, ge=1, le=500),
    asset_tag: str | None = Query(default=None),
    catalog: AsyncSession = Depends(get_catalog_session),
) -> list[MlFeedback]:
    """Lista os reportes de feedback recentes (governanca do modelo)."""
    return await MlFeedbackRepository(catalog).list_recent(limit, asset_tag)
