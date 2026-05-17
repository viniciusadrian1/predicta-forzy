"""Forzy Digital Twin - aplicacao FastAPI (API / BFF).

Cada modulo de dominio e exposto condicionalmente conforme as feature flags
``FEATURE_*``, garantindo a modularidade exigida pelo projeto.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infra.db.base import timeseries_engine
from app.infra.db.timescale import init_timeseries_schema
from app.modules.assets.router import router as assets_router
from app.modules.auth.router import router as auth_router
from app.modules.automation.router import router as automation_router
from app.modules.governance.middleware import AuditMiddleware
from app.modules.governance.router import router as governance_router
from app.modules.telemetry.ingestion import TelemetryIngestionService
from app.modules.telemetry.router import router as telemetry_router
from app.modules.vision.router import router as vision_router
from app.schemas.common import HealthResponse

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("forzy.main")

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Inicializa o schema de series temporais e a ingestao de telemetria."""
    for attempt in range(1, 6):
        try:
            await init_timeseries_schema(timeseries_engine)
            break
        except Exception as exc:
            logger.warning("Schema TimescaleDB indisponivel (tentativa %d/5): %s", attempt, exc)
            await asyncio.sleep(3.0)

    ingestion: TelemetryIngestionService | None = None
    if settings.feature_telemetry:
        ingestion = TelemetryIngestionService(settings)
        ingestion.start()

    yield

    if ingestion is not None:
        await ingestion.stop()


def create_app() -> FastAPI:
    """Constroi e configura a instancia FastAPI."""
    app = FastAPI(
        title=settings.project_name,
        version=APP_VERSION,
        description=(
            "Plataforma de Digital Twin para monitoramento e manutencao "
            "preditiva de motores eletricos industriais."
        ),
        lifespan=lifespan,
    )

    # AuditMiddleware fica interno; CORS, adicionado por ultimo, fica externo.
    app.add_middleware(AuditMiddleware, audit_enabled=settings.feature_governance)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_v1_prefix
    if settings.feature_auth:
        app.include_router(auth_router, prefix=prefix)
    if settings.feature_assets:
        app.include_router(assets_router, prefix=prefix)
    if settings.feature_automation:
        app.include_router(automation_router, prefix=prefix)
    if settings.feature_telemetry:
        app.include_router(telemetry_router, prefix=prefix)
    if settings.feature_vision:
        app.include_router(vision_router, prefix=prefix)
    if settings.feature_governance:
        app.include_router(governance_router, prefix=prefix)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            project=settings.project_name,
            environment=settings.environment,
            version=APP_VERSION,
        )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    logger.info("Aplicacao Forzy Digital Twin inicializada (v%s)", APP_VERSION)
    return app


app = create_app()
