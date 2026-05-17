"""Vector store do RAG: indice em memoria + adaptador ChromaDB opcional.

O MVP usa, por padrao, um indice vetorial em processo (``InMemoryVectorStore``):
zero dependencias externas, reproduzivel e suficiente para o corpus pequeno
do desafio. O ``ChromaVectorStore`` integra o ChromaDB provisionado na stack
e e selecionado por ``RAG_VECTOR_BACKEND=chroma`` (ver ADR 0006).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from app.infra.vector_store.embeddings import cosine_similarity

logger = logging.getLogger("forzy.vector_store")

_COLLECTION = "predicta_rag"


@dataclass
class VectorRecord:
    """Documento indexado: texto, embedding e metadados de origem."""

    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SearchHit:
    """Resultado de uma busca por similaridade."""

    record: VectorRecord
    score: float


class VectorStore(Protocol):
    """Contrato comum dos backends de vector store."""

    def add(self, records: list[VectorRecord]) -> None: ...

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchHit]: ...

    def clear(self) -> None: ...

    def count(self) -> int: ...


class InMemoryVectorStore:
    """Indice vetorial em processo com busca por cosseno (forca bruta)."""

    def __init__(self) -> None:
        self._records: list[VectorRecord] = []

    def add(self, records: list[VectorRecord]) -> None:
        self._records.extend(records)

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchHit]:
        hits = [
            SearchHit(record=record, score=cosine_similarity(query_embedding, record.embedding))
            for record in self._records
        ]
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def clear(self) -> None:
        self._records.clear()

    def count(self) -> int:
        return len(self._records)


class ChromaVectorStore:
    """Adaptador para o ChromaDB (extra opcional ``[rag]``).

    Os embeddings sao calculados pela aplicacao (``HashingEmbedder``) e
    apenas persistidos/consultados no ChromaDB, que opera com metrica de
    cosseno.
    """

    def __init__(self, host: str, port: int) -> None:
        import chromadb  # import tardio: dependencia opcional

        self._client = chromadb.HttpClient(host=host, port=port)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def add(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        self._collection.add(
            ids=[record.id for record in records],
            embeddings=[record.embedding for record in records],
            documents=[record.text for record in records],
            metadatas=[record.metadata or {"source": "?"} for record in records],
        )

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchHit]:
        result = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[SearchHit] = []
        for identifier, text, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):
            hits.append(
                SearchHit(
                    record=VectorRecord(
                        id=identifier, text=text, embedding=[], metadata=dict(metadata or {})
                    ),
                    score=1.0 - float(distance),  # distancia de cosseno -> similaridade
                )
            )
        return hits

    def clear(self) -> None:
        self._client.delete_collection(_COLLECTION)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def count(self) -> int:
        return int(self._collection.count())


def create_vector_store(backend: str, *, chroma_host: str, chroma_port: int) -> VectorStore:
    """Fabrica o vector store conforme a configuracao, com fallback seguro."""
    if backend == "chroma":
        try:
            store = ChromaVectorStore(chroma_host, chroma_port)
            logger.info("Vector store: ChromaDB em %s:%d", chroma_host, chroma_port)
            return store
        except Exception as exc:  # pragma: no cover - depende de infra externa
            logger.warning("ChromaDB indisponivel (%s); usando indice em memoria.", exc)
    return InMemoryVectorStore()
