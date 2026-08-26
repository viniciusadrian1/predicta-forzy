FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Binario do Tesseract (OCR real de placas) + pacotes de idioma pt/en.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Extras opcionais de pip (ex.: PIP_EXTRAS="[rag]" habilita o backend ChromaDB).
ARG PIP_EXTRAS=""

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY start.sh ./
# Dataset real IO-Link (Forzy) importado no start como telemetria de MTR-F01/F02.
COPY data ./data

RUN pip install --no-cache-dir ".${PIP_EXTRAS}"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
