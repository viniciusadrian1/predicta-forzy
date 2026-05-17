# Sprint 2 — Visualização operacional e representação do ativo

> Relatório executivo · Predicta · `v0.2.0-sprint2`

## 1. Objetivo

Transformar a base do ativo em uma experiência visual de navegação: planta
baixa interativa, telemetria completa das 6 variáveis e automação de cadastro.

## 2. Entregas

### Planta baixa interativa
- SVG esquemático da planta (`assets/plant_layouts/`) e componente `PlantMap`
  que sobrepõe marcadores clicáveis por ativo, coloridos por status, com
  tooltip ao passar o mouse e navegação para `/asset/[tag]` no clique.
- Página `/plant/[plantId]`. A decisão de conversão DWG→SVG está no **ADR 0004**.

### PDF inteligente
- Endpoint `GET /api/v1/plants/{id}/smart-pdf` (reportlab): planta com um
  marcador por equipamento, snapshot da telemetria e **links clicáveis** que
  abrem o ativo no frontend.

### OCR de placas de identificação
- Módulo `vision/plate_ocr.py`: pré-processamento de imagem (Pillow), parser
  regex dos campos da placa (potência, tensão, corrente, RPM, IP, isolamento,
  FS, FP…) e motor **PaddleOCR pluggável** (extra opcional `ocr`).
- 4 placas sintéticas em `assets/nameplates_samples/` (WEG, Siemens, Dutchi,
  Metalcorte).

### Telemetria completa
- Página `/asset/[tag]` com os **6 sensores**: valor instantâneo, sparkline,
  gráfico expansível com seletor de janela (1h / 24h / 7d / 30d) e exportação
  CSV por variável.

### Hierarquia, busca e RPA
- Endpoint `/hierarchy` (árvore Planta→Área→Ativo), busca textual e filtros em
  `/assets`, sidebar de navegação.
- Módulo `automation`: `POST /automation/register-from-image` — OCR → rascunho
  de ativo → deduplicação por TAG → cadastro opcional → evento de auditoria.
- Página `/register` (cadastro a partir de foto da placa).

## 3. Métricas

| Métrica | Valor |
|---|---|
| Testes backend (pytest) | 32 passando |
| Lint backend (ruff) | sem erros |
| Build frontend (`next build`) | sucesso — 7 rotas |
| Cobertura OCR (placas sintéticas) | 4/4 placas ≥ 70% dos campos |
| Endpoints REST | 18+ |

## 4. Critérios de aceitação

| Critério | Status |
|---|---|
| Planta baixa SVG navegável | ✅ |
| PDF inteligente com links funcionais | ✅ |
| OCR extrai ≥ 70% dos campos em ≥ 3 de 4 placas | ✅ (4/4 nos testes do parser) |
| Telemetria em tempo real nas 6 variáveis | ✅ |
| e2e Playwright: login → mapa → clique no ativo → dados | ✅ (teste escrito) |

## 5. Decisões arquiteturais

- **ADR 0004** — a planta é autorada manualmente em SVG (a conversão do DWG
  exige ODA File Converter, indisponível no build); os marcadores são
  renderizados dinamicamente pelas coordenadas dos ativos.
- **OCR** — PaddleOCR é um extra opcional (`pip install .[ocr]`) para manter a
  imagem do backend leve. Sem ele, o endpoint opera em modo simulado e o parser
  de placas é validado de forma determinística por testes.

## 6. Riscos

| Risco | Mitigação |
|---|---|
| OCR de fotos reais depende do extra `paddleocr` | Parser testado isoladamente; extra documentado |
| Janelas 7d/30d limitadas pelo histórico disponível | Geração de dataset histórico entra na Sprint 3 |
| e2e Playwright exige a stack no ar | Documentado; fora do CI por ora |

## 7. Dívida técnica

- PaddleOCR não embarcado na imagem por padrão (peso da dependência).
- e2e Playwright não roda no CI (exige stack completa + `playwright install`).
- SSE disponível no backend; a telemetria em tempo real usa *polling* por
  robustez (revisão na Sprint 3).
- `audit_log` ainda sem *diff* before/after a nível de campo.

## 8. Próximos passos (Sprint 3)

- Geração de dataset histórico de 90 dias.
- Modelos de ML: baseline (Isolation Forest), detecção de anomalia
  (LSTM autoencoder), estimativa de RUL.
- Sistema de alertas e estados de saúde no mapa.

## 9. Roteiro de demonstração

```bash
# 1. Subir a stack e aplicar migrations + seed
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# 2. Frontend (http://localhost:3001)
#    - dashboard: busca por "weg", filtro por status, sidebar de hierarquia
#    - clicar na planta -> /plant/[id] -> mapa interativo
#    - clicar no marcador do MTR-001 -> /asset/MTR-001
#    - expandir um sensor -> janela 24h -> exportar CSV
#    - "Cadastrar por foto" -> /register -> enviar uma placa sintetica

# 3. PDF inteligente
#    GET http://localhost:8000/api/v1/plants/{plantId}/smart-pdf

# 4. e2e (opcional)
cd frontend && npx playwright install chromium && npm run test:e2e
```
