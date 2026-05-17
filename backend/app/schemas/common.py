"""Schemas Pydantic compartilhados entre os modulos."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Resposta do endpoint de healthcheck."""

    status: str
    project: str
    environment: str
    version: str


class MessageResponse(BaseModel):
    """Resposta generica com uma mensagem."""

    message: str
