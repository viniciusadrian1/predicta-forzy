"""Middleware de auditoria: logging estruturado + registro em audit_log.

Toda requisicao gera um log JSON estruturado. Operacoes de escrita (POST,
PUT, PATCH, DELETE) bem-sucedidas geram tambem um registro append-only na
tabela ``audit_log``.
"""

from __future__ import annotations

import logging
import time
import uuid

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.security import decode_token
from app.infra.db.base import catalog_session_factory
from app.modules.governance.models import AuditLog

logger = logging.getLogger("forzy.governance.audit")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_settings = get_settings()


def _resolve_actor(authorization: str | None) -> str:
    """Resolve o usuario a partir do header Authorization Bearer."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return "anonymous"
    try:
        payload = decode_token(authorization.split(" ", 1)[1].strip())
    except jwt.PyJWTError:
        return "anonymous"
    return str(payload.get("sub", "anonymous"))


def _parse_resource(path: str) -> tuple[str, str | None]:
    """Deriva (tipo, id) do recurso a partir do caminho da requisicao."""
    prefix = _settings.api_v1_prefix
    trimmed = path[len(prefix) :] if path.startswith(prefix) else path
    parts = [segment for segment in trimmed.split("/") if segment]
    if not parts:
        return "root", None
    return parts[0], (parts[1] if len(parts) > 1 else None)


class AuditMiddleware(BaseHTTPMiddleware):
    """Loga toda requisicao e persiste auditoria das operacoes de escrita."""

    def __init__(self, app: ASGIApp, audit_enabled: bool = True) -> None:
        super().__init__(app)
        self._audit_enabled = audit_enabled

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid.uuid4().hex
        actor = _resolve_actor(request.headers.get("authorization"))
        started = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "actor": actor,
                "event": "http_request",
            },
        )

        if (
            self._audit_enabled
            and request.method in _MUTATING_METHODS
            and response.status_code < 500
        ):
            await self._record_audit(request, response, actor)

        return response

    async def _record_audit(self, request: Request, response: Response, actor: str) -> None:
        resource_type, resource_id = _parse_resource(request.url.path)
        client_host = request.client.host if request.client else None
        try:
            async with catalog_session_factory() as session:
                session.add(
                    AuditLog(
                        actor=actor,
                        action=request.method,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        ip_address=client_host,
                    )
                )
                await session.commit()
        except Exception:
            logger.exception("Falha ao registrar evento de auditoria")
