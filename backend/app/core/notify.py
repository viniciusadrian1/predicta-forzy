"""Aviso de plantao por Telegram.

O handoff do Volt so existia dentro da conversa: a tela dizia que ia chamar um
humano e ninguem era chamado. Aqui a escalada sai do chat e vira mensagem no
grupo de plantao.

A API do Telegram e um POST comum - nao vale uma dependencia so para isso, e o
``httpx`` ja e dependencia do projeto (o webhook de alertas usa o mesmo).
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("forzy.notify")

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
# Curto de proposito: do outro lado ha um tecnico esperando a resposta no chat.
_TIMEOUT_S = 4.0


def _sem_token(texto: str) -> str:
    """Remove o token de qualquer texto que va para o log.

    O token viaja no CAMINHO da URL da API do Telegram, entao ele escapa por
    qualquer coisa que registre a URL. A porta principal era o log de nivel
    INFO do httpx (fechada em core/logging.py); esta e a segunda barreira, para
    o caso de uma excecao de rede trazer a URL na propria mensagem.
    """
    token = get_settings().telegram_bot_token
    return texto.replace(token, "<token oculto>") if token else texto


async def enviar_telegram(texto: str) -> bool:
    """Manda uma mensagem ao grupo de plantao; devolve se ela saiu.

    Sem token ou sem chat configurado, nao faz nada e devolve ``False`` - o
    recurso e opcional e o sistema roda igual sem ele.

    Nunca levanta excecao: um aviso que falha nao pode derrubar exatamente o
    atendimento que ele estava tentando anunciar.
    """
    settings = get_settings()
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return False

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resposta = await client.post(
                _TELEGRAM_URL.format(token=token),
                json={"chat_id": chat_id, "text": texto, "parse_mode": "HTML"},
            )
    except Exception as exc:  # noqa: BLE001 - rede fora nao derruba o atendimento
        logger.warning("Falha ao avisar no Telegram: %s", _sem_token(str(exc)))
        return False

    if resposta.status_code != 200:
        # O corpo do erro diz o que arrumar: "chat not found" e chat_id errado
        # ou ninguem deu /start no bot; "unauthorized" e token errado.
        logger.warning(
            "Telegram recusou o aviso (%s): %s",
            resposta.status_code,
            _sem_token(resposta.text[:200]),
        )
        return False
    return True
