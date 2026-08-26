#!/bin/sh
# Start do backend (Render / Railway / VPS): espera o banco, roda migracoes +
# seed (idempotentes) e sobe a API na porta do host ($PORT).
# Usado pelo dockerCommand/command; o compose local mantem o CMD padrao.
set -e

# Espera os bancos ficarem acessiveis antes de migrar. Cobre a rede privada do
# Railway (*.railway.internal demora alguns segundos a resolver) e o caso de o
# Postgres iniciar depois do backend (compose/VPS).
python - <<'PY'
import os, socket, time, sys
targets = {
    (os.getenv("POSTGRES_HOST", "localhost"), int(os.getenv("POSTGRES_PORT", "5432"))),
    (os.getenv("TIMESCALE_HOST", "localhost"), int(os.getenv("TIMESCALE_PORT", "5432"))),
}
for host, port in targets:
    for _ in range(30):  # ~60s por banco
        try:
            socket.create_connection((host, port), 2).close()
            print(f"banco ok: {host}:{port}")
            break
        except OSError as exc:
            print(f"aguardando banco {host}:{port} ({exc})")
            time.sleep(2)
    else:
        sys.exit(f"banco {host}:{port} nao respondeu a tempo")
PY

alembic upgrade head
python -m app.scripts.seed
# Telemetria real de MTR-F01/F02 (idempotente: nao reimporta se ja houver dado).
python -m app.scripts.import_history data/history_forzy_iolink.csv
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
