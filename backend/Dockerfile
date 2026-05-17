FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Extras opcionais de pip (ex.: PIP_EXTRAS="[rag]" habilita o backend ChromaDB).
ARG PIP_EXTRAS=""

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir ".${PIP_EXTRAS}"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
