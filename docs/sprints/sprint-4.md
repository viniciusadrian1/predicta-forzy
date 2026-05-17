# Sprint 4 — Assistente conversacional, governança e deploy

> Relatório executivo · Predicta · `v0.4.0-sprint4`

## 1. Objetivo

Encerrar o MVP: um **assistente de troubleshooting** (chat com RAG sobre a
documentação técnica), a **governança final** com RBAC e linhagem de dados, e
os **artefatos de implantação**. A aplicação passa a se chamar **Predicta**.

## 2. Entregas

### Rebranding

- A plataforma passa a se chamar **Predicta** (a empresa-cliente do desafio
  continua sendo a Forzy). Atualização em código, interface e documentação.

### Assistente de troubleshooting (RAG)

- Módulo `rag`: base de conhecimento, fragmentação, embeddings, recuperação,
  prompts, cliente de LLM e serviço de orquestração.
- **Base de conhecimento:** corpus markdown curado (manual do MTR-001, guia de
  vibração ISO 10816, troubleshooting de falhas, plano de manutenção), embalado
  na imagem; documentos externos opcionais (`.md`, `.txt`, `.pdf`).
- **Embeddings** determinísticos por *hashing* e **vector store** em processo,
  com adaptador ChromaDB para produção (ver ADR 0006).
- **Chat com degradação graciosa:** usa a API Anthropic em *streaming* quando
  há `ANTHROPIC_API_KEY`; sem ela, opera em modo offline extrativo.
- O agente injeta no contexto a **telemetria, os alertas e o RUL** do ativo.
- Endpoints `GET /rag/status`, `POST /rag/ingest`, `POST /rag/chat` e
  `POST /rag/chat/stream` (SSE).

### Frontend

- Página `/chat` — assistente em tela cheia, com indicadores do índice de RAG.
- **Widget de chat flutuante** na página do ativo, com o contexto pré-carregado.
- Streaming token a token; respostas citam as fontes da documentação.

### Governança e RBAC (ver ADR 0007)

- **RBAC** com hierarquia `viewer < operator < engineer < admin`; dependency
  `require_role` aplicada aos endpoints sensíveis.
- **Tabela de usuários** (`users`, migration `0003`) com hashing argon2; o login
  passa a validar contra o banco. Quatro contas no *seed*.
- Endpoints de governança: `/governance/access-policy` (matriz RBAC) e
  `/governance/data-lineage` (inventário de dados classificado). `/audit`
  restrito a `admin`.
- `docs/governance/access-control.md` — matriz de acesso.

### Deploy

- `docker-compose.prod.yml` — stack de produção (frontend compilado, backend com
  ChromaDB, limites de recursos).
- `deploy/k8s/` — manifests Kubernetes (namespace, config, segredos, bancos,
  backend com Job de migração, frontend, ingress).
- `deploy/deploy.sh` — script de build e deploy; `deploy/README.md`.

## 3. Métricas

| Métrica | Valor |
|---|---|
| Testes backend (pytest) | 60 passando |
| Lint backend (ruff) | sem erros |
| Build frontend (`next build`) | sucesso — 9 rotas |
| Documentos no corpus de RAG | 4 (curado) + PDFs externos |
| Novos endpoints REST | `rag` (4), `governance` (2), `users` (1) |
| ADRs acumulados | 7 |

## 4. Critérios de aceitação

| Critério | Status |
|---|---|
| Chat de troubleshooting com RAG sobre os manuais | ✅ |
| Respostas fundamentadas, com citação das fontes | ✅ |
| Funciona com e sem chave de LLM (modo offline) | ✅ |
| Agente usa telemetria, alertas e RUL do ativo | ✅ |
| RBAC com papéis e endpoints sensíveis protegidos | ✅ |
| Usuários persistidos com hashing argon2 | ✅ |
| Artefatos de deploy (Compose de produção + Kubernetes) | ✅ |

## 5. Decisões arquiteturais

- **ADR 0006** — RAG com embeddings por *hashing* e vector store em processo
  (ChromaDB como caminho de produção); LLM com degradação graciosa para um modo
  offline extrativo.
- **ADR 0007** — RBAC com hierarquia de papéis, tabela de usuários com argon2 e
  endpoints de governança (matriz de acesso e linhagem de dados).

## 6. Riscos

| Risco | Mitigação |
|---|---|
| Embeddings por *hashing* são léxicos, não semânticos | Corpus curado + bigramas; evolução para modelo semântico |
| Resposta de LLM pode alucinar | Prompt restrito ao contexto; citação de fontes; supervisão humana |
| RBAC cobre um subconjunto dos endpoints | Subconjunto sensível documentado em `access-control.md` |
| Segredos de exemplo nos manifests | `deploy/README.md` orienta o uso de um cofre de segredos |

## 7. Dívida técnica

- Embeddings semânticos e ChromaDB como backend padrão.
- *Diff* before/after por campo no `audit_log`.
- *Refresh* de token com rotação; federação de identidade (OIDC).
- Reranking e ingestão incremental de novos manuais no RAG.

## 8. Conclusão e evolução

O Predicta encerra o MVP com o ciclo completo de um gêmeo digital: aquisição de
telemetria (OPC-UA), visualização navegável pela planta, IA para anomalia e
RUL, alertas e, agora, um assistente conversacional e a governança. A evolução
natural inclui dados reais rotulados, embeddings semânticos, escalabilidade
horizontal dos *workers* e integração com o ERP/CMMS de manutenção.

## 9. Roteiro de demonstração

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# Frontend (http://localhost:3001)
#  - login: admin / admin123
#  - /chat -> perguntar "o que indica desgaste de rolamento?"
#  - /asset/MTR-001 -> widget de chat flutuante (canto inferior direito)
#  - injetar falha BEARING_WEAR no simulador e perguntar a saude do ativo

# API
#  GET  /api/v1/rag/status
#  POST /api/v1/rag/chat              {"message": "...", "asset_tag": "MTR-001"}
#  GET  /api/v1/governance/access-policy
```

O roteiro completo está em [`docs/demo-scenario.md`](../demo-scenario.md).
