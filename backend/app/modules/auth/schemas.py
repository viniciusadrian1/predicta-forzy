"""Schemas Pydantic do modulo de autenticacao."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserOut(BaseModel):
    username: str
    role: str


class UserAccount(BaseModel):
    """Conta de usuario exposta pela API de governanca (sem o hash da senha)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: str
    full_name: str | None
    is_active: bool
    created_at: datetime
