"""Testes do modulo de RAG / chat de troubleshooting."""

from app.infra.vector_store.embeddings import HashingEmbedder, cosine_similarity, tokenize
from app.infra.vector_store.store import InMemoryVectorStore
from app.modules.rag.chunking import chunk_text
from app.modules.rag.knowledge_base import load_documents
from app.modules.rag.retriever import Retriever


def test_chunk_text_respects_size_and_overlaps():
    text = "\n\n".join(
        f"Paragrafo {index} com conteudo tecnico sobre motores e vibracao." for index in range(40)
    )
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(chunk) <= 200 * 2 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_embedder_is_deterministic():
    embedder = HashingEmbedder(dim=256)
    first = embedder.embed("vibracao do rolamento do motor")
    second = embedder.embed("vibracao do rolamento do motor")
    assert first == second


def test_embedder_ranks_related_text_higher():
    embedder = HashingEmbedder(dim=256)
    base = embedder.embed("vibracao do rolamento do motor")
    related = embedder.embed("o rolamento do motor apresenta vibracao elevada")
    unrelated = embedder.embed("politica de retencao de logs de auditoria")
    assert cosine_similarity(base, related) > cosine_similarity(base, unrelated)


def test_tokenize_removes_accents_and_stopwords():
    tokens = tokenize("A vibracao do MOTOR e a Temperatura")
    assert "vibracao" in tokens
    assert "motor" in tokens
    assert "temperatura" in tokens
    assert "de" not in tokens


def test_knowledge_base_loads_packaged_corpus():
    documents = load_documents(None)
    assert len(documents) >= 4
    assert all(document.text.strip() for document in documents)


def test_retriever_finds_relevant_chunk():
    retriever = Retriever(HashingEmbedder(dim=256), InMemoryVectorStore())
    indexed = retriever.index(load_documents(None), chunk_size=600, overlap=100)
    assert indexed > 0
    hits = retriever.search("limite de vibracao zona ISO 10816", top_k=3)
    assert hits
    assert "vibrac" in hits[0].text.lower()


async def test_rag_status(client):
    response = await client.get("/api/v1/rag/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["indexed_chunks"] > 0
    assert body["llm_mode"] in {"offline", "anthropic"}


async def test_rag_chat_returns_answer_and_sources(client):
    response = await client.post(
        "/api/v1/rag/chat",
        json={"message": "Qual o limite de vibracao do motor MTR-001?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].strip()
    assert body["mode"] in {"offline", "anthropic"}
    assert len(body["sources"]) >= 1
    assert body["used_asset_context"] is False


async def test_rag_chat_uses_asset_context(client):
    response = await client.post(
        "/api/v1/rag/chat",
        json={"message": "Como esta a saude do ativo?", "asset_tag": "MTR-001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["asset_tag"] == "MTR-001"
    assert body["used_asset_context"] is True


async def test_rag_ingest(client):
    response = await client.post("/api/v1/rag/ingest")
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] is True
    assert body["chunks"] > 0
