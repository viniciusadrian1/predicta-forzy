"""Servico de RAG: indexacao da base de conhecimento e chat de troubleshooting.

A base de conhecimento e indexada sob demanda (lazy) na primeira interacao.
A resposta combina os trechos recuperados, o contexto em tempo real do ativo
e o LLM (ou o modo offline extrativo). Cada interacao e registrada em log
estruturado para fins de governanca.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.config import get_settings
from app.infra.vector_store.embeddings import HashingEmbedder
from app.infra.vector_store.store import create_vector_store
from app.modules.rag.knowledge_base import load_documents
from app.modules.rag.llm import LlmClient, stream_text
from app.modules.rag.prompts import SYSTEM_PROMPT, build_user_prompt
from app.modules.rag.retriever import RetrievedChunk, Retriever
from app.modules.rag.schemas import ChatRequest, ChatResponse, IngestResult, RagSource, RagStatus

logger = logging.getLogger("forzy.rag.service")

_HISTORY_LIMIT = 6


def _snippet(text: str, limit: int = 220) -> str:
    """Reduz um trecho a uma linha curta para exibir como fonte."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "..."


def _trim(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "..."


class RagService:
    """Orquestra recuperacao + geracao para o assistente de troubleshooting."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._embedder = HashingEmbedder(dim=settings.rag_embedding_dim)
        self._store = create_vector_store(
            settings.rag_vector_backend,
            chroma_host=settings.chroma_host,
            chroma_port=settings.chroma_port,
        )
        self._retriever = Retriever(self._embedder, self._store)
        api_key = (
            settings.openai_api_key
            if settings.llm_provider == "openai"
            else settings.anthropic_api_key
        )
        self._llm = LlmClient(
            provider=settings.llm_provider,
            api_key=api_key,
            model=settings.llm_model,
        )
        self._indexed = False
        self._document_count = 0
        self._lock = asyncio.Lock()

    # -- indexacao ----------------------------------------------------------

    def _reindex(self) -> None:
        documents = load_documents(self._settings.rag_documents_dir)
        chunks = self._retriever.index(
            documents, self._settings.rag_chunk_size, self._settings.rag_chunk_overlap
        )
        self._document_count = len(documents)
        self._indexed = True
        logger.info(
            "RAG: base indexada (%d documentos, %d chunks).",
            self._document_count,
            chunks,
        )

    async def _ensure_indexed(self) -> None:
        if self._indexed:
            return
        async with self._lock:
            if not self._indexed:
                self._reindex()

    async def ingest(self) -> IngestResult:
        """Forca a (re)ingestao da base de conhecimento."""
        async with self._lock:
            self._indexed = False
            self._reindex()
        return IngestResult(
            ingested=True,
            documents=self._document_count,
            chunks=self._retriever.chunk_count,
            vector_backend=self._settings.rag_vector_backend,
        )

    async def status(self) -> RagStatus:
        """Estado do indice de RAG e do provedor de LLM."""
        await self._ensure_indexed()
        return RagStatus(
            ready=self._retriever.chunk_count > 0,
            indexed_chunks=self._retriever.chunk_count,
            documents=self._document_count,
            vector_backend=self._settings.rag_vector_backend,
            llm_mode=self._llm.mode,
            embedding_dim=self._settings.rag_embedding_dim,
        )

    async def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Recupera trechos relevantes (sem gerar resposta). Usado pelo agente."""
        await self._ensure_indexed()
        return self._retriever.search(query, top_k or self._settings.rag_top_k)

    # -- chat ---------------------------------------------------------------

    def _sources(self, chunks: list[RetrievedChunk]) -> list[RagSource]:
        return [
            RagSource(
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                snippet=_snippet(chunk.text),
                score=chunk.score,
            )
            for chunk in chunks
        ]

    def _build_messages(
        self, request: ChatRequest, chunks: list[RetrievedChunk], asset_context: str | None
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": message.role, "content": message.content}
            for message in request.history[-_HISTORY_LIMIT:]
        ]
        messages.append(
            {"role": "user", "content": build_user_prompt(request.message, chunks, asset_context)}
        )
        return messages

    def _offline_answer(
        self, question: str, chunks: list[RetrievedChunk], asset_context: str | None
    ) -> str:
        """Compoe uma resposta extrativa a partir dos trechos recuperados."""
        parts: list[str] = []
        if chunks:
            parts.append("Com base na documentação técnica do Predicta:")
            for chunk in chunks[:2]:
                parts.append(f"\n[{chunk.document_title}]\n{_trim(chunk.text, 600)}")
        else:
            parts.append(
                "Não encontrei na base de conhecimento um trecho diretamente "
                "relacionado à sua pergunta. Tente reformular com termos mais "
                "específicos (ex.: vibração, rolamento, sobrecarga, temperatura)."
            )
        if asset_context:
            parts.append(f"\nSituação atual do ativo:\n{asset_context}")
        parts.append(
            "\nObservação: resposta gerada em modo offline (sem LLM), de forma "
            "extrativa a partir da documentação recuperada. Configure "
            "OPENAI_API_KEY para respostas em linguagem natural. Confirme "
            "sempre com a equipe de manutenção antes de qualquer intervenção."
        )
        return "\n".join(parts)

    async def _llm_answer(
        self, request: ChatRequest, chunks: list[RetrievedChunk], asset_context: str | None
    ) -> str:
        messages = self._build_messages(request, chunks, asset_context)
        try:
            parts = [token async for token in self._llm.stream(SYSTEM_PROMPT, messages)]
        except Exception as exc:  # pragma: no cover - depende de rede/credencial
            logger.warning("Falha na chamada ao LLM (%s); usando modo offline.", exc)
            return self._offline_answer(request.message, chunks, asset_context)
        text = "".join(parts).strip()
        return text or self._offline_answer(request.message, chunks, asset_context)

    async def answer(self, request: ChatRequest, asset_context: str | None) -> ChatResponse:
        """Responde uma pergunta (modo nao-streaming)."""
        await self._ensure_indexed()
        chunks = self._retriever.search(request.message, self._settings.rag_top_k)
        mode = self._llm.mode
        if mode != "offline":
            answer = await self._llm_answer(request, chunks, asset_context)
        else:
            answer = self._offline_answer(request.message, chunks, asset_context)
        self._log_chat(request, chunks, mode)
        return ChatResponse(
            answer=answer,
            mode=mode,
            sources=self._sources(chunks),
            asset_tag=request.asset_tag,
            used_asset_context=bool(asset_context),
        )

    async def stream(
        self, request: ChatRequest, asset_context: str | None
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        """Responde via streaming, emitindo eventos (sources, token, done)."""
        await self._ensure_indexed()
        chunks = self._retriever.search(request.message, self._settings.rag_top_k)
        mode = self._llm.mode

        yield (
            "sources",
            {
                "mode": mode,
                "asset_tag": request.asset_tag,
                "used_asset_context": bool(asset_context),
                "sources": [source.model_dump() for source in self._sources(chunks)],
            },
        )

        collected = ""
        if mode != "offline":
            try:
                messages = self._build_messages(request, chunks, asset_context)
                async for token in self._llm.stream(SYSTEM_PROMPT, messages):
                    collected += token
                    yield ("token", {"text": token})
            except Exception as exc:  # pragma: no cover - depende de rede/credencial
                logger.warning("Streaming do LLM falhou (%s); usando modo offline.", exc)

        if not collected.strip():
            offline = self._offline_answer(request.message, chunks, asset_context)
            async for token in stream_text(offline):
                collected += token
                yield ("token", {"text": token})

        self._log_chat(request, chunks, mode)
        yield ("done", {"answer": collected.strip(), "mode": mode})

    def _log_chat(self, request: ChatRequest, chunks: list[RetrievedChunk], mode: str) -> None:
        logger.info(
            "rag_chat mode=%s asset=%s sources=%d question=%s",
            mode,
            request.asset_tag or "-",
            len(chunks),
            _trim(request.message, 120),
            extra={"event": "rag_chat", "asset_tag": request.asset_tag},
        )


# Singleton compartilhado entre os endpoints do modulo de RAG.
rag_service = RagService()
