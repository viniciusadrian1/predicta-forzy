# ADR 0006 — Estratégia de RAG e do assistente conversacional

- **Status:** Aceito
- **Data:** 2026-05-17
- **Sprint:** 4

## Contexto

A Sprint 4 exige um **assistente de troubleshooting** — chat com LLM e RAG
(*Retrieval-Augmented Generation*) sobre os manuais técnicos, com acesso à
telemetria, aos alertas e ao RUL do ativo.

Restrições do MVP:

- a imagem do backend deve permanecer leve e implantável;
- o sistema precisa **funcionar na demonstração mesmo sem uma chave de LLM**
  (o avaliador pode não ter credenciais);
- a recuperação deve ser **reprodutível** e testável, sem download de modelos;
- o ChromaDB já consta da arquitetura como vector store.

## Decisão

| Componente | Escolha |
|---|---|
| Base de conhecimento | Corpus markdown curado, empacotado no módulo `rag/corpus/` + documentos externos opcionais (`.md`, `.txt`, `.pdf`) |
| Fragmentação | Chunker consciente de parágrafos, com sobreposição |
| Embeddings | `HashingEmbedder` determinístico (*hashing trick*, tokens + bigramas) |
| Vector store | `InMemoryVectorStore` (padrão) · `ChromaVectorStore` (produção) |
| LLM | API Anthropic (streaming) quando há chave; **modo offline extrativo** sem chave |
| Entrega | SSE — eventos `sources`, `token`, `done` |

- **Embeddings por hashing em vez de modelo semântico:** não exige download de
  pesos, é totalmente offline, leve e reprodutível. O corpus curado e o uso de
  bigramas compensam a natureza léxica. Produção → modelo semântico (ONNX).
- **Vector store em processo por padrão:** o corpus do desafio é pequeno e de
  nó único; o índice em memória elimina uma dependência de rede e garante
  reprodutibilidade nos testes. O `ChromaVectorStore` (extra `[rag]`,
  `RAG_VECTOR_BACKEND=chroma`) é o caminho de produção — usado no
  `docker-compose.prod.yml` e nos manifests Kubernetes.
- **Degradação graciosa do LLM:** sem `ANTHROPIC_API_KEY`, o assistente compõe
  uma resposta **extrativa** a partir dos trechos recuperados. O campo `mode`
  (`anthropic` | `offline`) deixa o comportamento explícito na interface.
- **Agente com contexto:** quando a pergunta indica um ativo, o serviço injeta
  no prompt a telemetria atual, os alertas ativos e a estimativa de RUL.

## Consequências

- **Positivas:** roda em qualquer ambiente (testes, CI, demo) sem credenciais
  nem GPU; reprodutível; honesto quanto ao modo de operação.
- **Negativas:** o embedding por hashing é léxico, não semântico — sinônimos sem
  sobreposição de termos não casam. Mitigado pelo corpus curado e pelos bigramas.
- **Evolução:** embeddings semânticos (sentence-transformers / ONNX) e ChromaDB
  como backend padrão; reranking; ingestão incremental de novos manuais.
