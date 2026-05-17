"""RBAC - controle de acesso baseado em papeis.

Hierarquia de papeis (do menor para o maior privilegio):

    viewer < operator < engineer < admin

Cada papel herda as permissoes dos papeis inferiores. Endpoints sensiveis
declaram o papel minimo exigido via a dependency ``require_role``.

A verificacao e configuravel por ``RBAC_ENABLED`` (ligada por padrao). A
matriz completa de acesso esta em ``docs/governance/access-control.md``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.core.security import decode_token

logger = logging.getLogger("forzy.rbac")

# Papeis ordenados por nivel de privilegio crescente.
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "operator": 1,
    "engineer": 2,
    "admin": 3,
}
DEFAULT_ROLE = "viewer"
ANONYMOUS = "anonymous"


@dataclass(frozen=True)
class Principal:
    """Usuario autenticado (ou anonimo) resolvido a partir do token JWT."""

    username: str
    role: str

    @property
    def level(self) -> int:
        """Nivel numerico do papel na hierarquia."""
        return ROLE_HIERARCHY.get(self.role, 0)

    @property
    def is_authenticated(self) -> bool:
        return self.username != ANONYMOUS


def has_required_role(role: str, minimum: str) -> bool:
    """Indica se ``role`` satisfaz o papel minimo ``minimum``."""
    return ROLE_HIERARCHY.get(role, -1) >= ROLE_HIERARCHY.get(minimum, 99)


def resolve_principal(authorization: str | None) -> Principal:
    """Resolve o ``Principal`` a partir do header ``Authorization: Bearer``.

    Requisicoes sem token (ou com token invalido) sao tratadas como o
    usuario anonimo, que recebe o papel ``viewer`` (somente leitura).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return Principal(ANONYMOUS, DEFAULT_ROLE)
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return Principal(ANONYMOUS, DEFAULT_ROLE)
    username = str(payload.get("sub", ANONYMOUS))
    role = str(payload.get("role", DEFAULT_ROLE))
    if role not in ROLE_HIERARCHY:
        role = DEFAULT_ROLE
    return Principal(username, role)


def rbac_enforced() -> bool:
    """Indica se a verificacao de papel deve ser aplicada."""
    return get_settings().rbac_enabled


async def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Dependency: usuario corrente resolvido do token Bearer."""
    return resolve_principal(authorization)


def require_role(minimum: str) -> Callable[..., Awaitable[Principal]]:
    """Fabrica de dependency que exige o papel minimo ``minimum``.

    Uso::

        @router.get("/audit", dependencies=[Depends(require_role("admin"))])
    """

    async def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not rbac_enforced():
            return principal
        if not has_required_role(principal.role, minimum):
            logger.warning(
                "rbac_denied actor=%s role=%s required=%s",
                principal.username,
                principal.role,
                minimum,
                extra={"event": "rbac_denied", "actor": principal.username},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: requer o papel '{minimum}' ou superior.",
            )
        return principal

    return _dependency
