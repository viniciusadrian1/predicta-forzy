# Governança de IA — Predicta

Documento de governança dos modelos de Machine Learning (Sprint 3).

## Princípios

1. **Apoio à decisão, não decisão autônoma** — os modelos sinalizam desvios; a
   intervenção de manutenção é sempre decidida por pessoas.
2. **Explicabilidade** — adotam-se modelos simples e auditáveis (Isolation
   Forest, autoencoder MLP, regressão linear) — ver ADR 0005.
3. **Supervisão humana** — toda predição relevante pode ser contestada.

## Limites de interpretação

| Modelo | O que indica | O que NÃO indica |
|---|---|---|
| Baseline (Isolation Forest) | Desvio do ponto de operação normal | A causa-raiz do desvio |
| Anomalia (autoencoder) | Comportamento de vibração incomum | O tipo de defeito |
| RUL | Tendência estatística até o limite ISO | Garantia da data de falha |

Os modelos do MVP são treinados com dados sintéticos / histórico curto. **Não
devem embasar decisão crítica** sem validação com dados reais rotulados.

## Rastreabilidade e logging

- Cada predição é registrada em log estruturado (evento `ml_prediction`):
  modelo, versão, ativo, score, decisão e timestamp.
- Cada alerta guarda o modelo e o score (`ml_score`).
- Os modelos são versionados (versão, `trained_at`, `n_samples` no meta).

## Loop de feedback

- Endpoint `POST /api/v1/ml/feedback` e botão **"Reportar predição incorreta"**
  na interface do ativo.
- Os reportes são registrados (evento `ml_feedback`) para revisão e retreino.

## Dados

- O treino usa apenas telemetria operacional — sem dado pessoal.
- Classificação detalhada em [`data-classification.md`](data-classification.md).

## Itens em aberto

- Métricas formais de qualidade (precisão / recall) com dados reais rotulados.
- Política de retreino e detecção de *drift* dos dados.
- Revisão humana periódica das predições reportadas como incorretas.
