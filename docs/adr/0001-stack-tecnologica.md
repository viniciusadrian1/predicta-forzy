# ADR 0001 — Stack tecnológica

- **Status:** Aceito
- **Data:** 2026-05-16
- **Sprint:** 1

## Contexto

O Challenge Forzy exige uma plataforma de Digital Twin modular, demonstrável e
com qualidade de produção, integrando IoT, IA, visão computacional e RAG. É
preciso escolher uma stack que equilibre produtividade, maturidade do
ecossistema e baixo *vendor lock-in*.

## Decisão

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind | App Router, SSR, ecossistema maduro |
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2.0 | Async nativo, *type-safety*, OpenAPI automático |
| Catálogo | PostgreSQL 16 | Robustez, JSONB, padrão de mercado |
| Séries temporais | TimescaleDB | Compressão e *continuous aggregates* (ver ADR 0002) |
| IoT | `asyncua` (OPC-UA) | Open-source, assíncrono, padrão industrial |
| Orquestração | Docker Compose | Portabilidade — toda a stack sobe localmente |

ML, RAG e demais camadas seguem o stack definido no escopo do desafio e serão
detalhados em ADRs próprios nas Sprints 3 e 4.

## Consequências

- **Positivas:** alto *time-to-market*, *type-safety* ponta-a-ponta, documentação
  OpenAPI gratuita, comunidade ampla.
- **Negativas:** dois runtimes (Python + Node) aumentam a superfície de build.
- **Mitigação:** Docker Compose isola cada serviço; *feature flags* permitem
  ligar/desligar módulos individualmente.
