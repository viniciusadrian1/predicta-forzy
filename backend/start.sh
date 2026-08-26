#!/bin/sh
# Start do backend no Render (free tier nao permite preDeployCommand): roda
# migracoes + seed (idempotentes) e sobe a API na porta do Render ($PORT).
# Usado so pelo dockerCommand do render.yaml; o compose local mantem o CMD padrao.
set -e

alembic upgrade head
python -m app.scripts.seed
# Telemetria real de MTR-F01/F02 (idempotente: nao reimporta se ja houver dado).
python -m app.scripts.import_history data/history_forzy_iolink.csv
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
