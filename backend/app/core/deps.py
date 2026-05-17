"""Dependencias compartilhadas entre os modulos da API."""

from __future__ import annotations

import jwt
from fastapi import Header

from app.core.security import decode_token


async def get_current_actor(authorization: str | None = Header(default=None)) -> str:
    """Extrai o usuario do token Bearer; devolve ``anonymous`` se ausente.

    Na Sprint 1 a autenticacao ainda nao e obrigatoria (login mock), mas o
    ator e sempre resolvido para alimentar o log de auditoria.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return "anonymous"
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return "anonymous"
    return str(payload.get("sub", "anonymous"))
