"""Endpoints de autenticacao.

Sprint 1: login mock com usuarios em memoria. A Sprint 4 substitui por uma
tabela de usuarios, hashing argon2 (ver ``core/security.py``) e RBAC completo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_actor
from app.core.security import create_access_token
from app.modules.auth.schemas import LoginIn, TokenOut, UserOut

router = APIRouter(tags=["auth"])

# MOCK Sprint 1: usuarios de demonstracao (usuario -> senha, papel).
_DEMO_USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin123", "admin"),
    "engenheiro": ("eng123", "engineer"),
    "operador": ("operador123", "operator"),
    "viewer": ("viewer123", "viewer"),
}


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn) -> TokenOut:
    """Autentica um usuario e devolve um token JWT de acesso."""
    credentials = _DEMO_USERS.get(payload.username)
    if credentials is None or credentials[0] != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais invalidas",
        )
    _, role = credentials
    token = create_access_token(payload.username, role)
    return TokenOut(
        access_token=token,
        token_type="bearer",
        username=payload.username,
        role=role,
    )


@router.get("/auth/me", response_model=UserOut)
async def me(actor: str = Depends(get_current_actor)) -> UserOut:
    """Devolve o usuario corrente, resolvido a partir do token Bearer."""
    role = _DEMO_USERS.get(actor, ("", "viewer"))[1]
    return UserOut(username=actor, role=role)
