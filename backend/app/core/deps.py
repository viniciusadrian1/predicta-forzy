"""Dependencias compartilhadas entre os modulos da API."""

from __future__ import annotations

from fastapi import Header

from app.core.rbac import resolve_principal


async def get_current_actor(authorization: str | None = Header(default=None)) -> str:
    """Extrai o usuario do token Bearer; devolve ``anonymous`` se ausente.

    Delega em ``resolve_principal`` em vez de decodificar o token por conta
    propria. Antes eram duas copias da mesma logica, e as duas engoliam token
    invalido virando "anonymous" - o que fazia ``/auth/me`` responder 200
    {"username": "anonymous"} para uma sessao expirada, justamente o endpoint
    que o cliente usa para descobrir que a sessao morreu. De quebra, uma acao
    feita com token expirado entrava na trilha de auditoria como "anonymous"
    em vez de ser recusada.

    Credencial ausente segue anonima (leitura publica); credencial apresentada
    e invalida agora levanta 401, vindo de ``resolve_principal``.
    """
    return resolve_principal(authorization).username
