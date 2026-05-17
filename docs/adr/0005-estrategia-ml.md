# ADR 0005 — Estratégia de Machine Learning

- **Status:** Aceito
- **Data:** 2026-05-17
- **Sprint:** 3

## Contexto

A Sprint 3 exige três capacidades de IA: **baseline de operação**, **detecção
de anomalia** e estimativa de **RUL** (vida útil remanescente). O escopo sugere
Isolation Forest, um LSTM autoencoder em PyTorch e uma regressão para o RUL.

Restrições do MVP: a imagem do backend deve permanecer leve e implantável; os
modelos precisam treinar rápido e ser explicáveis; e o sensor de vibração real
(Pepperl+Fuchs VIM32) entrega *process data* — valores RMS — e não a forma de
onda bruta de 8 kHz.

## Decisão

| Modelo | Algoritmo | Biblioteca |
|---|---|---|
| Baseline de operação | Isolation Forest | scikit-learn |
| Detecção de anomalia | Autoencoder de reconstrução (MLP) sobre janelas de vibração | scikit-learn |
| Estimativa de RUL | Regressão linear da tendência de vibração até o limite DIN ISO 10816 | scikit-learn |

- **scikit-learn em vez de PyTorch:** footprint pequeno, treino em segundos,
  modelos explicáveis, sem dependência pesada na imagem. O LSTM autoencoder em
  PyTorch fica registrado como **evolução futura** (extra opcional `ml`).
- **Dados em nível de RMS:** as features espectrais são extraídas da *série
  temporal* de valores RMS (FFT da janela), coerente com o que o sensor real
  entrega — não de uma forma de onda bruta de 8 kHz.
- **Treino e serving:** o backend treina os modelos sob demanda a partir da
  telemetria do TimescaleDB e os mantém em memória, com versionamento e meta.
  Os pipelines em `ml/` são o caminho offline e reprodutível (dataset sintético
  de 90 dias + notebooks).

## Consequências

- **Positivas:** leve, rápido, explicável, reprodutível e testável.
- **Negativas:** o autoencoder MLP não modela dependência temporal longa como um
  LSTM — aceitável para o MVP, dado o sinal de RMS.
- **Evolução:** LSTM autoencoder (PyTorch) treinado offline a partir de formas
  de onda de vibração de 8 kHz, quando o gateway as disponibilizar.
