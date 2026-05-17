# Sprint 3 — Inteligência operacional e apoio à decisão

> Relatório executivo · Forzy Digital Twin · `v0.3.0-sprint3`

## 1. Objetivo

Adicionar capacidade analítica para detectar desvios, gerar alertas e apoiar a
decisão de manutenção, com três modelos de IA, um sistema de alertas e
governança de ML.

## 2. Entregas

### Dataset histórico
- `edge/data_generator/generate_dataset.py` — 90 dias de telemetria sintética
  (129.600 registros, resolução de 1 min), com operação normal, degradação
  progressiva de rolamento, sobrecargas, desbalanceamento e spikes.

### Modelos de ML (ver ADR 0005)
- **Baseline** — Isolation Forest sobre o vetor multivariável dos 6 sensores.
- **Anomalia** — autoencoder de reconstrução (MLP) sobre janelas de vibração;
  limiar no percentil 99 do erro.
- **RUL** — regressão linear da tendência de vibração até o limite ISO 10816.
- Pipelines em `ml/pipelines/` produzem artefatos versionados (`*_v{N}.pkl` +
  `meta.json`); o backend treina sob demanda a partir do TimescaleDB e serve
  via `POST /ml/baseline/predict`, `POST /ml/anomaly/predict`, `GET /ml/rul/{tag}`.

### Sistema de alertas
- Tabela `alerts` + migration `0002`; módulo `alerts` com avaliador periódico
  (30 s) que combina regras de limite + modelos de ML.
- Tipos: `THRESHOLD_EXCEEDED`, `BASELINE_DEVIATION`, `ANOMALY_DETECTED`,
  `RUL_WARNING`; severidades INFO / WARNING / CRITICAL.
- O status do ativo é sincronizado com a severidade — os badges do mapa
  refletem o estado em tempo real.
- Endpoints `GET /alerts` e `POST /alerts/{id}/ack` (com comentário).

### Frontend
- Página `/alerts` com filtros e reconhecimento.
- Seção "Saúde do ativo" em `/asset/[tag]`: baseline, anomalia, RUL com gauge,
  e timeline de alertas recentes.
- Notificações *toast* em tempo real para novos alertas.
- Botão "Reportar predição incorreta" (loop de feedback).

### Governança de ML
- `docs/governance/ai-ethics.md`; logging estruturado de cada predição
  (`ml_prediction`) e do feedback (`ml_feedback`).

## 3. Métricas

| Métrica | Valor |
|---|---|
| Testes backend (pytest) | 41 passando |
| Lint backend (ruff) | sem erros |
| Build frontend (`next build`) | sucesso — 8 rotas |
| Dataset histórico | 129.600 registros (90 dias) |
| Modelos treinados e versionados | 3 (baseline, anomalia, RUL) |

## 4. Critérios de aceitação

| Critério | Status |
|---|---|
| Dataset histórico de 90 dias gerado | ✅ |
| 3 modelos treinados, versionados e servidos via API | ✅ |
| Alertas em tempo real visíveis no frontend | ✅ |
| Falha injetada detectada em < 60 s | ✅ (avaliador a cada 30 s + regras de limite) |
| Notebooks executáveis end-to-end | ✅ (4 notebooks em `ml/notebooks/`) |

## 5. Decisões arquiteturais

- **ADR 0005** — modelos scikit-learn (Isolation Forest, autoencoder MLP,
  regressão linear) em vez de PyTorch: footprint leve, treino rápido,
  explicabilidade; LSTM autoencoder registrado como evolução.
- **Avaliador in-process** — o avaliador de alertas roda como task assíncrona
  no backend (a cada 30 s), evitando um serviço Celery/ARQ dedicado no MVP.

## 6. Riscos

| Risco | Mitigação |
|---|---|
| Modelos treinados com dados sintéticos | Validação com dados reais rotulados na evolução; ver ai-ethics.md |
| Avaliador in-process não escala horizontalmente | Externalizável para ARQ/Celery quando necessário |
| RUL sensível à janela de tendência | Intervalo de confiança exposto; supervisão humana |

## 7. Dívida técnica

- Sem métricas formais de qualidade dos modelos (precisão/recall) — exige dados
  reais rotulados.
- Sem detecção de *drift* nem política de retreino automático.
- LSTM autoencoder (PyTorch) não implementado — extra opcional futuro.

## 8. Próximos passos (Sprint 4)

- RAG conversacional (LangChain + ChromaDB) sobre os manuais e o datasheet.
- Agente de troubleshooting com acesso a telemetria, alertas e RUL.
- Governança final: RBAC completo, data lineage, deploy.

## 9. Roteiro de demonstração

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head     # aplica a tabela alerts

# 1. Gerar o dataset historico e treinar os modelos offline
python edge/data_generator/generate_dataset.py
python ml/pipelines/train_baseline.py

# 2. No frontend (http://localhost:3001)
#    - /asset/MTR-001 -> secao "Saude do ativo" (baseline, anomalia, RUL)
#    - /alerts -> lista de alertas, filtros e ack

# 3. Injetar uma falha no simulador (cliente OPC-UA):
#    Forzy/Motor/MTR-001/Control/FaultMode = "BEARING_WEAR"
#    Forzy/Motor/MTR-001/Control/FaultSeverity = 1.0
#    -> em ~30-60 s surge um alerta de vibracao e o badge do mapa fica vermelho.
```
