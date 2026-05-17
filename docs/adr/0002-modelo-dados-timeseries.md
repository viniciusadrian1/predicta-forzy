# ADR 0002 — Modelo de dados de séries temporais

- **Status:** Aceito
- **Data:** 2026-05-16
- **Sprint:** 1

## Contexto

Os sensores do motor publicam leituras a cada segundo (6 variáveis a 1 Hz). Em
90 dias de histórico isso representa dezenas de milhões de registros. Um banco
relacional comum degrada em consultas por janela temporal e não oferece
compressão nativa.

## Decisão

1. **TimescaleDB** (extensão do PostgreSQL) para a telemetria, com as tabelas
   `telemetry_raw` e `telemetry_processed` convertidas em *hypertables*.
2. **Dois bancos separados:** catálogo (PostgreSQL puro) e séries temporais
   (TimescaleDB), conforme a arquitetura de referência do desafio. Isola o
   perfil de carga OLTP do perfil de série temporal.
3. **Continuous aggregates** de 1 min / 5 min / 1 h sobre `telemetry_processed`.
4. O DDL específico do TimescaleDB (`create_hypertable`, *continuous
   aggregates*) **não** é versionado por Alembic — o Alembic gerencia apenas o
   catálogo. O schema de séries temporais é criado de forma idempotente no
   startup da aplicação (`app/infra/db/timescale.py`).

## Alternativas consideradas

- **InfluxDB:** ótimo para séries temporais, mas adiciona um segundo dialeto de
  consulta (Flux) e mais um serviço. Descartado para manter um único SQL.
- **Tabela única no PostgreSQL:** simples, mas sem compressão nem *continuous
  aggregates*; não escala para o histórico de 90 dias.
- **Instância única do TimescaleDB para tudo:** viável, mas a arquitetura do
  desafio define os bancos separados.

## Consequências

- **Positivas:** consultas por janela rápidas; retenção e compressão nativas.
- **Negativas:** o DDL de *hypertable* fora do Alembic exige disciplina; o
  backend mantém duas conexões de banco.
- **Política de retenção:** dado bruto 30 dias, processado 1 ano — a ser
  implementada via políticas do TimescaleDB nas Sprints 3/4.
