"""Endpoints de autenticacao e gestao de usuarios.

A Sprint 4 substitui o login mock por uma tabela de usuarios com hashing
argon2 e RBAC. Os usuarios de demonstracao em memoria sao mantidos como
fallback para ambientes em que a tabela ainda nao foi populada (ex.: testes
de unidade sem o seed).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_actor
from app.core.rbac import require_role
from app.core.security import create_access_token, verify_password
from app.infra.db.base import get_catalog_session
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import LoginIn, TokenOut, UserAccount, UserOut

router = APIRouter(tags=["auth"])

# Fallback de demonstracao: usuario -> (senha, papel). Usado apenas quando a
# tabela de usuarios ainda nao foi populada (ver app/scripts/seed.py).
_DEMO_USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin123", "admin"),
    "gestor": ("gestor123", "engineer"),  # perfil Gestor de Planta
    "engenheiro": ("eng123", "engineer"),  # alias historico
    "operador": ("operador123", "operator"),
    "auditor": ("auditor123", "auditor"),
    "viewer": ("viewer123", "viewer"),
}


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, session: AsyncSession = Depends(get_catalog_session)) -> TokenOut:
    """Autentica um usuario e devolve um token JWT de acesso.

    A verificacao usa a tabela de usuarios; se a conta nao existir nela,
    recai sobre os usuarios de demonstracao em memoria.
    """
    user = await UserRepository(session).get_by_username(payload.username)
    if (
        user is not None
        and user.is_active
        and verify_password(payload.password, user.password_hash)
    ):
        token = create_access_token(user.username, user.role)
        return TokenOut(access_token=token, username=user.username, role=user.role)

    credentials = _DEMO_USERS.get(payload.username)
    if credentials is not None and credentials[0] == payload.password:
        _, role = credentials
        token = create_access_token(payload.username, role)
        return TokenOut(access_token=token, username=payload.username, role=role)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas")


@router.get("/auth/me", response_model=UserOut)
async def me(
    actor: str = Depends(get_current_actor),
    session: AsyncSession = Depends(get_catalog_session),
) -> UserOut:
    """Devolve o usuario corrente, resolvido a partir do token Bearer."""
    user = await UserRepository(session).get_by_username(actor)
    if user is not None:
        return UserOut(username=user.username, role=user.role)
    role = _DEMO_USERS.get(actor, ("", "viewer"))[1]
    return UserOut(username=actor, role=role)


@router.get(
    "/users",
    response_model=list[UserAccount],
    dependencies=[Depends(require_role("admin"))],
)
async def list_users(
    session: AsyncSession = Depends(get_catalog_session),
) -> list[User]:
    """Lista as contas de usuario cadastradas (requer papel admin)."""
    return await UserRepository(session).list_all()
