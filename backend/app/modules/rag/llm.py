"""Cliente de LLM do assistente, com degradacao graciosa.

Com a chave do provedor configurado (``OPENAI_API_KEY`` para ``openai`` ou
``ANTHROPIC_API_KEY`` para ``anthropic``), o assistente gera a resposta em modo
*streaming*. Sem a chave, opera em modo *offline*: a resposta e composta de
forma extrativa a partir dos trechos recuperados (ver ``RagService``). Assim o
chat funciona na demo mesmo sem credenciais de LLM.
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
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MAX_TOKENS = 1024
_STREAM_WORD_RE = re.compile(r"\S+\s*")


class LlmClient:
    """Encapsula a chamada ao provedor de LLM (OpenAI/Anthropic) em streaming."""

    def __init__(self, *, provider: str, api_key: str, model: str) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model = model

    @property
    def mode(self) -> str:
        """Modo efetivo: o provider (``openai``/``anthropic``) se houver
        credencial, senao ``offline``."""
        if self._api_key and self._provider in ("openai", "anthropic"):
            return self._provider
        return "offline"

    def stream(self, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Despacha o streaming para o provider configurado."""
        if self._provider == "openai":
            return self.stream_openai(system, messages)
        return self.stream_anthropic(system, messages)

    async def stream_openai(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Faz streaming da resposta da API OpenAI (chat completions), token a token."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            # OpenAI espera o system dentro do array de mensagens.
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
        }
        async with (
            httpx.AsyncClient(timeout=60.0) as client,
            client.stream("POST", _OPENAI_URL, headers=headers, json=payload) as response,
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
                choices = event.get("choices") or [{}]
                text = choices[0].get("delta", {}).get("content") or ""
                if text:
                    yield text

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
