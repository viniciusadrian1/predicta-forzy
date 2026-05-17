"""Utilitarios de seguranca: hashing de senha (argon2) e tokens JWT."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import get_settings

_settings = get_settings()
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Gera o hash argon2 de uma senha."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verifica uma senha contra o hash armazenado."""
    try:
        return _hasher.verify(hashed, password)
    except Argon2Error:
        return False


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    """Emite um JWT de acesso para ``subject`` com o papel ``role``."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=expires_minutes or _settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _settings.jwt_secret_key, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decodifica e valida um JWT. Lanca ``jwt.PyJWTError`` se invalido."""
    return jwt.decode(token, _settings.jwt_secret_key, algorithms=[_settings.jwt_algorithm])
