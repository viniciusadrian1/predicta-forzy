# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [0.2.0] — Sprint 2 — Visualização operacional e representação do ativo

### Added

- **Planta baixa interativa** — SVG da planta + componente `PlantMap` com
  marcadores de ativo clicáveis, coloridos por status e com tooltip.
- **PDF inteligente** — `GET /plants/{id}/smart-pdf` (reportlab) com snapshot da
  telemetria e links clicáveis para os ativos.
- **OCR de placas** — módulo `vision/plate_ocr.py` (pré-processamento + parser
  regex + motor PaddleOCR opcional) e 4 placas sintéticas de exemplo.
- **Telemetria completa** — página do ativo com os 6 sensores, sparkline,
  janelas temporais (1h/24h/7d/30d) e exportação CSV.
- **Hierarquia e busca** — endpoint `/hierarchy`, busca/filtros em `/assets` e
  sidebar de navegação Planta→Área→Ativo.
- **RPA** — módulo `automation` com `POST /automation/register-from-image`
  (OCR → rascunho → deduplicação → cadastro) e página `/register`.
- ADR 0004 (representação da planta) e testes e2e Playwright.

### Changed

- Telemetria em tempo real para as 6 variáveis (antes só temperatura).

## [0.1.0] — Sprint 1 — Fundamentos do ativo e da base de dados

### Added

**Infraestrutura**

- Bootstrap do repositório: estrutura de pastas, `.gitignore`, `.editorconfig`,
  `.gitattributes`, `pre-commit` (ruff, black, mypy, eslint, prettier).
- `docker-compose.yml` com a stack completa: PostgreSQL, TimescaleDB, Redis,
  ChromaDB, Mosquitto, simulador OPC-UA, backend e frontend.
- Workflows de CI (GitHub Actions) para backend, frontend e ML.

**Edge / IoT**

- Simulador OPC-UA do motor MTR-001 com modelos físicos (térmico, elétrico e de
  vibração) e injeção de falhas (desgaste de rolamento, desbalanceamento e
  sobrecarga).

**Backend (FastAPI)**

- Módulo `assets`: CRUD de ativos, plantas e áreas.
- Módulo `telemetry`: cliente OPC-UA com *subscription*, pipeline raw→processed,
  consulta REST histórica e streaming SSE.
- Módulo `vision`: *stub* do endpoint de OCR de placas de identificação.
- Módulo `auth`: login mock com emissão de token JWT.
- Módulo `governance`: middleware de auditoria e logging estruturado em JSON.
- Banco de catálogo versionado por Alembic; *hypertables* TimescaleDB com
  *continuous aggregates*.
- Seed inicial: planta, área e o motor de referência MTR-001.

**Frontend (Next.js 14)**

- Tela de login, dashboard de ativos e página de detalhe do ativo com
  telemetria em tempo real (gráfico de temperatura).

**Documentação**

- ADRs 0001 (stack tecnológica), 0002 (modelo de séries temporais) e 0003
  (estratégia de OCR).
- `docs/architecture.md` (modelo C4) e `docs/governance/data-classification.md`.

### Tests

- Suíte `pytest` cobrindo os módulos `assets` e `telemetry`.
