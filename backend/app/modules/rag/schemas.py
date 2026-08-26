"""Schemas Pydantic do modulo de RAG / chat de troubleshooting."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Mensagem de uma conversa (historico enviado pelo cliente)."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Requisicao de chat: pergunta + contexto opcional do ativo."""

    message: str = Field(min_length=1, max_length=2000)
    asset_tag: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class RagSource(BaseModel):
    """Trecho da base de conhecimento usado para fundamentar a resposta."""

    document_id: str
    document_title: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    """Resposta do assistente, com as fontes citadas."""

    answer: str
    mode: Literal["openai", "anthropic", "offline"]
    sources: list[RagSource]
    asset_tag: str | None = None
    used_asset_context: bool = False


class RagStatus(BaseModel):
    """Estado do indice de RAG e do provedor de LLM."""

    ready: bool
    indexed_chunks: int = 0
    documents: int = 0
    vector_backend: str = "memory"
    llm_mode: Literal["openai", "anthropic", "offline"] = "offline"
    embedding_dim: int = 0


class IngestResult(BaseModel):
    """Resultado de uma (re)ingestao da base de conhecimento."""

    ingested: bool
    documents: int
    chunks: int
    vector_backend: str
