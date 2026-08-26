"""Testes do cliente de LLM (provider OpenAI/Anthropic + modo offline)."""

import app.modules.rag.llm as llm
from app.modules.rag.llm import LlmClient


def test_mode_resolves_by_provider_and_key():
    assert LlmClient(provider="openai", api_key="x", model="gpt-4o-mini").mode == "openai"
    assert LlmClient(provider="anthropic", api_key="y", model="m").mode == "anthropic"
    # Sem chave -> offline, qualquer provider.
    assert LlmClient(provider="openai", api_key="", model="m").mode == "offline"
    assert LlmClient(provider="anthropic", api_key="", model="m").mode == "offline"


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeClient:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def stream(self, *_, **__):
        return _FakeResp(self._lines)


async def test_stream_openai_parses_sse_deltas(monkeypatch):
    lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',  # sem content -> ignora
        'data: {"choices":[{"delta":{"content":"Verifique"}}]}',
        'data: {"choices":[{"delta":{"content":" a vibracao"}}]}',
        "data: [DONE]",
        "ping",  # linha nao-data -> ignora
    ]
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda *a, **k: _FakeClient(lines))
    client = LlmClient(provider="openai", api_key="sk-test", model="gpt-4o-mini")
    tokens = [tok async for tok in client.stream("SYS", [{"role": "user", "content": "?"}])]
    assert tokens == ["Verifique", " a vibracao"]
