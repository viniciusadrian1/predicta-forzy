# Forzy Digital Twin

Plataforma de **Digital Twin** para monitoramento em tempo real e manutenção
preditiva de motores elétricos industriais (220 V trifásicos). Desenvolvida para o
**Challenge FIAP × Forzy (Promon)**.

---

## O problema

A manutenção de ativos industriais costuma ser **corretiva** ou baseada em
calendário fixo. Isso gera paradas não planejadas, custo elevado de estoque de
peças e risco de falhas catastróficas. A Forzy precisa de uma solução que:

- capture dados dos motores em tempo real (tensão, corrente, temperatura,
  rotação e vibração);
- detecte desvios de comportamento **antes** da falha;
- estime o tempo restante de vida útil (RUL) dos componentes;
- ofereça apoio à decisão para a equipe de manutenção.

## A solução

Um **gêmeo digital** que integra IoT, IA e uma interface web navegável a partir
da planta baixa do ativo:

| Capacidade | Como |
|---|---|
| Aquisição de dados | Servidor/simulador OPC-UA → cliente assíncrono → TimescaleDB |
| Visualização | Next.js 14 — planta interativa, dashboards em tempo real |
| Cadastro de ativos | CRUD + OCR da placa de identificação |
| Detecção de anomalias | ML (Isolation Forest, LSTM autoencoder) |
| Manutenção preditiva | Estimativa de RUL |
| Troubleshooting | Chat com LLM + RAG sobre manuais técnicos |
| Governança | RBAC, auditoria, classificação de dados |

## Arquitetura

```mermaid
flowchart TD
    subgraph Apresentacao["Camada de Apresentacao"]
        FE["Next.js 14 + Tailwind + shadcn/ui<br/>Planta interativa - Dashboards - Chat"]
    end
    subgraph Aplicacao["Camada de Aplicacao"]
        API["FastAPI (BFF / API Gateway)<br/>auth - assets - telemetry - vision - ml - rag - governance"]
    end
    subgraph Dados["Persistencia"]
        PG[("PostgreSQL<br/>catalogo")]
        TS[("TimescaleDB<br/>series temporais")]
        CH[("ChromaDB<br/>embeddings RAG")]
    end
    subgraph Edge["Camada de Edge / IoT"]
        OPC["Simulador OPC-UA<br/>motor MTR-001"]
    end

    FE <-->|REST + SSE| API
    API --> PG
    API --> TS
    API --> CH
    OPC -->|OPC-UA subscription| API
```

Detalhes em [`docs/architecture.md`](docs/architecture.md) e nos
[ADRs](docs/adr/).

## Quickstart

Pré-requisitos: **Docker** + **Docker Compose v2**.

```bash
# 1. Entrar no diretorio do projeto
cd forzy-digital-twin

# 2. Criar o arquivo de ambiente
cp .env.example .env

# 3. Subir toda a stack
docker compose up -d --build

# 4. Aguardar os healthchecks (~1-2 min)
docker compose ps

# 5. Aplicar as migrations e o seed inicial
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# 6. Acessar:
#    Frontend ......... http://localhost:3001
#    API (Swagger) .... http://localhost:8000/docs
#    OPC-UA ........... opc.tcp://localhost:4840/forzy/server/
```

Após ~1 minuto, a tela `http://localhost:3001/asset/MTR-001` exibe o gráfico de
temperatura atualizando em tempo real.

## Estrutura

```
backend/    API FastAPI (auth, assets, telemetry, vision, ml, rag, governance)
frontend/   Aplicacao Next.js 14
edge/       Simulador OPC-UA + geradores de dados
ml/         Notebooks, pipelines e modelos
rag/        Ingestao e recuperacao para o chat
docs/       Arquitetura, ADRs, governanca, relatorios de sprint
assets/     Plantas, modelos 3D e amostras de placas
```

## Roadmap

| Sprint | Entrega | Status |
|---|---|---|
| 1 | Fundamentos: simulador, telemetria, cadastro, base de dados | concluída |
| 2 | Planta interativa, OCR de placas, telemetria completa | concluída |
| 3 | ML: baseline, anomalia, RUL e alertas | planejada |
| 4 | RAG conversacional, governança e deploy | planejada |

## Stack

Next.js 14 · FastAPI · PostgreSQL 16 · TimescaleDB · ChromaDB · `asyncua` ·
scikit-learn · PyTorch · LangChain · Docker Compose.

## Documentação

- [`docs/architecture.md`](docs/architecture.md) — visão C4 da arquitetura
- [`docs/adr/`](docs/adr/) — decisões arquiteturais (ADRs)
- [`docs/sprints/`](docs/sprints/) — relatórios executivos por sprint
- [`docs/governance/`](docs/governance/) — classificação de dados e controle de acesso

## Licença

Projeto acadêmico desenvolvido para o Challenge FIAP × Forzy/Promon.
