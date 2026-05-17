"""Cliente de LLM do assistente, com degradacao graciosa.

Quando ``ANTHROPIC_API_KEY`` esta configurada, o assistente usa a API de
mensagens da Anthropic em modo *streaming*. Sem a chave, opera em modo
*offline*: a resposta e composta de forma extrativa a partir dos trechos
recuperados (ver ``RagService``). Assim o chat funciona na demo mesmo sem
credenciais de LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator

import httpx

logger = logging.getLogger("forzy.rag.llm")

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_TOKENS = 1024
_STREAM_WORD_RE = re.compile(r"\S+\s*")


class LlmClient:
    """Encapsula a chamada ao provedor de LLM (Anthropic) em modo streaming."""

    def __init__(self, *, provider: str, api_key: str, model: str) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model = model

    @property
    def mode(self) -> str:
        """Modo efetivo: ``anthropic`` se houver credencial, senao ``offline``."""
        if self._provider == "anthropic" and self._api_key:
            return "anthropic"
        return "offline"

    async def stream_anthropic(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Faz streaming da resposta da API Anthropic, token a token."""
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "system": system,
            "messages": messages,
            "stream": True,
        }
        async with (
            httpx.AsyncClient(timeout=60.0) as client,
            client.stream("POST", _ANTHROPIC_URL, headers=headers, json=payload) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[len("data:") :].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "content_block_delta":
                    text = event.get("delta", {}).get("text", "")
                    if text:
                        yield text


async def stream_text(text: str, delay: float = 0.012) -> AsyncIterator[str]:
    """Emite um texto pronto palavra a palavra, simulando um streaming."""
    words = _STREAM_WORD_RE.findall(text) or [text]
    for word in words:
        yield word
        await asyncio.sleep(delay)
