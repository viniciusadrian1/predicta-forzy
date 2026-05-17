"""Recuperacao de trechos relevantes da base de conhecimento."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.infra.vector_store.embeddings import HashingEmbedder
from app.infra.vector_store.store import VectorRecord, VectorStore
from app.modules.rag.chunking import chunk_text
from app.modules.rag.knowledge_base import Document

logger = logging.getLogger("forzy.rag.retriever")


@dataclass
class RetrievedChunk:
    """Trecho recuperado, com a pontuacao de similaridade."""

    text: str
    document_id: str
    document_title: str
    score: float


class Retriever:
    """Indexa documentos e recupera os trechos mais similares a uma consulta."""

    def __init__(self, embedder: HashingEmbedder, store: VectorStore) -> None:
        self._embedder = embedder
        self._store = store
        self._document_count = 0

    def index(self, documents: list[Document], chunk_size: int, overlap: int) -> int:
        """(Re)constroi o indice a partir dos documentos; devolve o nº de chunks."""
        self._store.clear()
        records: list[VectorRecord] = []
        for document in documents:
            for position, chunk in enumerate(chunk_text(document.text, chunk_size, overlap)):
                records.append(
                    VectorRecord(
                        id=f"{document.id}::{position}",
                        text=chunk,
                        embedding=self._embedder.embed(chunk),
                        metadata={
                            "document_id": document.id,
                            "document_title": document.title,
                            "source": document.source,
                        },
                    )
                )
        self._store.add(records)
        self._document_count = len(documents)
        logger.info(
            "RAG: %d chunk(s) indexado(s) de %d documento(s).",
            len(records),
            len(documents),
        )
        return len(records)

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        """Recupera os ``top_k`` trechos mais relevantes para a consulta."""
        embedding = self._embedder.embed(query)
        results: list[RetrievedChunk] = []
        for hit in self._store.search(embedding, top_k):
            if hit.score <= 0.0:
                continue  # descarta trechos sem qualquer sobreposicao
            results.append(
                RetrievedChunk(
                    text=hit.record.text,
                    document_id=hit.record.metadata.get("document_id", hit.record.id),
                    document_title=hit.record.metadata.get("document_title", "Documento"),
                    score=round(hit.score, 4),
                )
            )
        return results

    @property
    def chunk_count(self) -> int:
        return self._store.count()

    @property
    def document_count(self) -> int:
        return self._document_count
