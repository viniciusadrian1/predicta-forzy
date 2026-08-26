"""Predicta - aplicacao FastAPI (API / BFF).

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
from fastapi.responses import JSONResponse, RedirectResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.infra.db.base import (
    catalog_session_factory,
    timeseries_engine,
    timeseries_session_factory,
)
from app.infra.db.timescale import init_timeseries_schema
from app.modules.alerts.evaluator import alerts_evaluator
from app.modules.alerts.router import router as alerts_router
from app.modules.assets.router import router as assets_router
from app.modules.auth.router import router as auth_router
from app.modules.automation.router import router as automation_router
from app.modules.governance.middleware import AuditMiddleware
from app.modules.governance.router import router as governance_router
from app.modules.ml.router import router as ml_router
from app.modules.rag.router import router as rag_router
from app.modules.telemetry.demo_sim import DemoSimulatorService
from app.modules.telemetry.external import ExternalSensorsService
from app.modules.telemetry.ingestion import TelemetryIngestionService
from app.modules.telemetry.router import router as telemetry_router
from app.modules.vision.router import router as vision_router
from app.modules.volt.router import router as volt_router
from app.schemas.common import HealthResponse

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("forzy.main")

APP_VERSION = "0.4.0"

_DEFAULT_JWT_SECRET = "dev-only-secret-change-me-in-production-min32b"


def _assert_production_secure(cfg: Settings) -> None:
    """Aborta o boot fora de desenvolvimento se a configuração estiver insegura.

    Todo o RBAC confia no claim ``role`` do JWT: com o segredo default (que está
    versionado) qualquer um forja um token admin. Em ``development``/``test``/
    ``local`` a checagem não interfere; em produção ela recusa o boot.
    """
    if cfg.environment.lower() in ("development", "dev", "test", "local"):
        return
    problems: list[str] = []
    if cfg.jwt_secret_key == _DEFAULT_JWT_SECRET or len(cfg.jwt_secret_key) < 32:
        problems.append("JWT_SECRET_KEY inseguro (default ou com menos de 32 caracteres)")
    if not cfg.rbac_enabled:
        problems.append("RBAC_ENABLED desligado")
    if problems:
        message = (
            f"Configuração insegura para o ambiente '{cfg.environment}': "
            f"{'; '.join(problems)}. Defina um JWT_SECRET_KEY forte e habilite o RBAC."
        )
        logger.critical(message)
        raise RuntimeError(message)


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
    external: ExternalSensorsService | None = None
    demo_sim: DemoSimulatorService | None = None
    if settings.feature_telemetry:
        if settings.demo_simulator:
            # Deploy publico (sem OPC-UA): o simulador de demo e a fonte de dados.
            demo_sim = DemoSimulatorService(settings)
            demo_sim.start()
        else:
            ingestion = TelemetryIngestionService(settings)
            ingestion.start()
        # Sensores fisicos Forzy (API HTTP): ativos apenas com URL configurada.
        if settings.external_sensors_base_url:
            external = ExternalSensorsService(settings)
            external.start()
    if settings.feature_alerts:
        alerts_evaluator.start()

    yield

    if ingestion is not None:
        await ingestion.stop()
    if external is not None:
        await external.stop()
    if demo_sim is not None:
        await demo_sim.stop()
    if settings.feature_alerts:
        await alerts_evaluator.stop()


def create_app() -> FastAPI:
    """Constroi e configura a instancia FastAPI."""
    _assert_production_secure(settings)
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
    if settings.feature_ml:
        app.include_router(ml_router, prefix=prefix)
    if settings.feature_alerts:
        app.include_router(alerts_router, prefix=prefix)
    if settings.feature_rag:
        app.include_router(rag_router, prefix=prefix)
    if settings.feature_volt:
        app.include_router(volt_router, prefix=prefix)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        # Liveness: o processo esta de pe (nao checa dependencias).
        return HealthResponse(
            status="ok",
            project=settings.project_name,
            environment=settings.environment,
            version=APP_VERSION,
        )

    @app.get("/health/ready", tags=["system"])
    async def health_ready() -> JSONResponse:
        # Readiness: so responde pronto se os bancos respondem (SELECT 1).
        checks: dict[str, str] = {}
        ready = True
        for name, factory in (
            ("catalog", catalog_session_factory),
            ("timeseries", timeseries_session_factory),
        ):
            try:
                async with factory() as session:
                    await session.execute(text("SELECT 1"))
                checks[name] = "ok"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Readiness: %s indisponivel (%s)", name, exc)
                checks[name] = "error"
                ready = False
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"ready": ready, "checks": checks},
        )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    logger.info("Aplicacao Predicta inicializada (v%s)", APP_VERSION)
    return app


app = create_app()
