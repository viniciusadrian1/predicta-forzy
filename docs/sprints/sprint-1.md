# Sprint 1 — Fundamentos do ativo e da base de dados

> Relatório executivo · Forzy Digital Twin · `v0.1.0-sprint1`

## 1. Objetivo

Estruturar a base do projeto: captura inicial dos dados do motor, cadastro do
equipamento, persistência e a primeira visualização operacional em tempo real.

## 2. Entregas

### Edge / IoT
- Simulador OPC-UA do motor **MTR-001** (`edge/opcua_simulator/`) publicando os
  6 sensores + TAG sob o namespace `ns=2`.
- Modelos físicos: térmico (1ª ordem), elétrico (corrente e escorregamento) e de
  vibração (faixas da DIN ISO 10816/20816).
- Injeção de falhas (`fault_injection.py`): desgaste de rolamento,
  desbalanceamento e sobrecarga, controláveis por nodes OPC-UA graváveis.

### Backend (FastAPI)
- Módulo `assets` — CRUD de ativos, plantas e áreas.
- Módulo `telemetry` — cliente OPC-UA com *subscription* (1 Hz), pipeline
  raw→processed, consulta REST histórica e *streaming* SSE.
- Módulo `vision` — *stub* do endpoint de OCR de placas.
- Módulo `auth` — login mock com emissão de JWT.
- Módulo `governance` — middleware de auditoria + logging estruturado JSON.
- Catálogo (PostgreSQL) versionado por Alembic; séries temporais (TimescaleDB)
  com *hypertables* e *continuous aggregates*.
- Seed inicial: planta, área e o motor MTR-001.

### Frontend (Next.js 14)
- `/login` (mock), `/dashboard` (cards de ativos + cadastro) e `/asset/[tag]`
  (metadados, leituras atuais e gráfico de temperatura em tempo real).

### Documentação
- ADRs 0001 (stack), 0002 (séries temporais), 0003 (OCR).
- `docs/architecture.md` (modelo C4), `docs/governance/data-classification.md`,
  `docs/api/openapi.json`.

## 3. Métricas

| Métrica | Valor |
|---|---|
| Testes backend (pytest) | 20 passando |
| Cobertura total do backend | 73% |
| Cobertura — módulo `assets` | 68–100% por arquivo |
| Cobertura — módulo `telemetry` | 50–100% por arquivo |
| Lint backend (ruff) | sem erros |
| Build frontend (`next build`) | sucesso — 6 rotas |
| Serviços na stack Docker | 8 |

## 4. Critérios de aceitação

| Critério | Status |
|---|---|
| `docker compose up` sobe toda a stack | ✅ |
| Gráfico de temperatura em tempo real no frontend | ✅ `/asset/MTR-001` |
| Cadastrar ativo via API e vê-lo no frontend | ✅ |
| Cobertura de testes > 60% (`assets`, `telemetry`) | ✅ |
| README com setup em menos de 10 passos | ✅ (6 passos) |

## 5. Decisões arquiteturais

Registradas como ADRs: escolha da stack (0001), modelo de dados de séries
temporais com TimescaleDB e bancos separados (0002), e estratégia de OCR com
PaddleOCR (0003).

## 6. Riscos

| Risco | Mitigação |
|---|---|
| SSE através de `BaseHTTPMiddleware` pode bufferizar | Sprint 1 usa *polling*; SSE será revisado na Sprint 2 |
| Conversão DWG→SVG depende de ferramenta externa | Avaliar ODA File Converter / SVG manual na Sprint 2 |
| `mypy --strict` ainda não 100% limpo | CI roda mypy como informativo (`continue-on-error`) |

## 7. Dívida técnica

- **Autenticação mock** — usuários em memória; Sprint 4 implementa tabela de
  usuários, hashing argon2 e RBAC.
- **Auditoria** — `audit_log` registra método/rota/status, mas ainda não o
  *diff* before/after a nível de campo (Sprint 2).
- **Cobertura de `ingestion.py` / `opcua_client.py`** baixa — exigem um servidor
  OPC-UA vivo; testes de integração planejados para a Sprint 2.
- **Frontend sem testes automatizados** — Vitest + Playwright entram na Sprint 2.
- *Continuous aggregates* são criados em modo *best-effort*.

## 8. Próximos passos (Sprint 2)

- Planta baixa interativa (SVG navegável) a partir do DWG fornecido.
- OCR real de placas com PaddleOCR.
- Telemetria completa das 6 variáveis com seletor de janela.
- Workflow de RPA para cadastro a partir de foto.
- Testes e2e (Playwright).

## 9. Roteiro de demonstração

```bash
# 1. Subir a stack
cp .env.example .env
docker compose up -d --build

# 2. Aplicar migrations e seed
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# 3. Abrir o frontend
#    http://localhost:3001  -> dashboard com o motor MTR-001
#    Clicar no card  -> /asset/MTR-001
#    Observar o grafico de temperatura subir nos primeiros ~60 s.

# 4. Cadastrar um ativo via API e ve-lo no dashboard
curl -X POST http://localhost:8000/api/v1/assets \
  -H "Content-Type: application/json" \
  -d '{"tag":"MTR-002","name":"Motor secundario"}'

# 5. (Opcional) Injetar uma falha no simulador via cliente OPC-UA
#    Node Forzy/Motor/MTR-001/Control/FaultMode = "BEARING_WEAR"
#    Node Forzy/Motor/MTR-001/Control/FaultSeverity = 1.0
#    -> vibracao cresce; visivel no /asset/MTR-001.
```
