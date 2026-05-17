# Backend — Forzy Digital Twin

API / BFF em **FastAPI** (Python 3.11, assíncrono).

## Módulos

| Módulo | Responsabilidade | Sprint |
|---|---|---|
| `auth` | Autenticação (JWT) | 1 |
| `assets` | Cadastro de ativos, plantas e áreas | 1 |
| `telemetry` | Ingestão OPC-UA e consulta de séries temporais | 1 |
| `vision` | OCR de placas de identificação | 1–2 |
| `governance` | Auditoria e logging estruturado | 1 |
| `ml` | Baseline, anomalia e RUL | 3 |
| `rag` | Troubleshooting conversacional | 4 |
| `automation` | Workflows de RPA | 2 |

Cada módulo pode ser ligado/desligado por feature flag (`FEATURE_*` no `.env`).

## Camadas

```
app/
  core/      configuração, segurança, logging, dependências
  infra/     banco de dados, cliente OPC-UA, MQTT, vector store
  modules/   um pacote por domínio (router + service + repository + schemas)
  schemas/   schemas Pydantic compartilhados
  scripts/   utilitários (seed do banco)
```

## Desenvolvimento local

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Testes

```bash
pytest
```

## Migrations

O banco de **catálogo** (PostgreSQL) é versionado por Alembic. O banco de
**séries temporais** (TimescaleDB) tem o schema criado no startup da aplicação
(`app/infra/db/timescale.py`) — ver ADR 0002.

```bash
alembic revision --autogenerate -m "descricao"
alembic upgrade head
```
