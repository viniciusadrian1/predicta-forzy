# RAG — Base de conhecimento

Esta pasta reúne os **documentos de origem** usados pelo assistente de
troubleshooting (RAG) do Predicta.

## Estrutura

```
rag/
  documents/   Documentos de origem (PDFs, datasheets) ingeridos pelo backend
  ingestion/   Reservado para scripts de ingestao offline
  retrieval/   Reservado para experimentos de recuperacao
  prompts/     Reservado para versionamento de prompts
```

## Como a base é montada

O motor de RAG vive no backend, em `backend/app/modules/rag/`. A base de
conhecimento tem duas origens:

1. **Corpus curado** — arquivos markdown em `backend/app/modules/rag/corpus/`,
   empacotados na imagem do backend. Garantem que o assistente funcione em
   qualquer ambiente, sem montagem de volumes. Cobrem:
   - manual de operação do motor MTR-001;
   - guia de vibração (DIN ISO 10816/20816);
   - troubleshooting de falhas comuns;
   - plano de manutenção.

2. **Documentos externos** — arquivos em `rag/documents/` (`.md`, `.txt`,
   `.pdf`). O `docker-compose.yml` monta esta pasta no backend em
   `/rag/documents` (`RAG_DOCUMENTS_DIR`); PDFs são extraídos com `pypdf`.

Para adicionar um documento à base, basta colocá-lo em `rag/documents/` e
reindexar com `POST /api/v1/rag/ingest` (ou reiniciar o backend).

A estratégia de embeddings e de vector store está descrita no
[ADR 0006](../docs/adr/0006-estrategia-rag.md).
