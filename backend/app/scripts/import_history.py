"""Importa o dataset real IO-Link (History_*.csv da Forzy) como telemetria.

Converte as leituras dos dois motores (Porta 1 / Porta 2) para as variaveis
canonicas da plataforma e as insere em ``telemetry_processed``, permitindo
reproduzir a EDA e o contrato de metricas com dado real dentro do Predicta.

Uso::

    python -m app.scripts.import_history data/history_forzy_iolink.csv
    python -m app.scripts.import_history <csv> MTR-F01,MTR-F02   # remapear

Layout do CSV (delimitado por ';', 3 linhas de cabecalho):
    col 0 = timestamp ISO
    col 3,4,5 = Motor 1 (Velocidade, Aceleracao, Temperatura)
    col 6,7,8 = Motor 2 (Velocidade, Aceleracao, Temperatura)
"""

from __future__ import annotations

import asyncio
import csv
import sys
from datetime import datetime
from typing import Any

from sqlalchemy import insert

from app.infra.db.base import timeseries_session_factory
from app.infra.db.timescale import telemetry_processed

# (indice da coluna, variavel canonica, unidade) para cada motor do dataset.
MOTOR_COLUMNS: dict[str, list[tuple[int, str, str]]] = {
    "MTR-F01": [
        (3, "Vibracao_Velocidade_RMS", "mm/s"),
        (4, "Vibracao_Aceleracao_RMS", "g"),
        (5, "Temperatura", "C"),
    ],
    "MTR-F02": [
        (6, "Vibracao_Velocidade_RMS", "mm/s"),
        (7, "Vibracao_Aceleracao_RMS", "g"),
        (8, "Temperatura", "C"),
    ],
}


def parse_row(
    row: list[str], motors: dict[str, list[tuple[int, str, str]]]
) -> list[dict[str, Any]]:
    """Converte uma linha de dados do CSV em amostras canonicas (pura, testavel)."""
    if not row or not row[0].strip():
        return []
    try:
        time = datetime.fromisoformat(row[0].strip())
    except ValueError:
        return []
    samples: list[dict[str, Any]] = []
    for tag, columns in motors.items():
        for index, variable, unit in columns:
            try:
                value = float(row[index].replace(",", "."))
            except (IndexError, ValueError):
                continue
            samples.append(
                {
                    "time": time,
                    "asset_tag": tag,
                    "variable": variable,
                    "value": round(value, 4),
                    "unit": unit,
                    "quality": 0,
                }
            )
    return samples


def _data_rows(path: str) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    return rows[3:]  # pula as 3 linhas de cabecalho


async def import_history(path: str, motors: dict[str, list[tuple[int, str, str]]]) -> int:
    """Le o CSV e insere as amostras em lotes; devolve o total importado."""
    batch: list[dict[str, Any]] = []
    total = 0
    async with timeseries_session_factory() as session:
        for row in _data_rows(path):
            batch.extend(parse_row(row, motors))
            if len(batch) >= 1000:
                await session.execute(insert(telemetry_processed), batch)
                total += len(batch)
                batch = []
        if batch:
            await session.execute(insert(telemetry_processed), batch)
            total += len(batch)
        await session.commit()
    return total


def _motors_from_args(argv: list[str]) -> dict[str, list[tuple[int, str, str]]]:
    if len(argv) > 2:
        tag1, tag2 = (t.strip() for t in argv[2].split(","))
        return {tag1: MOTOR_COLUMNS["MTR-F01"], tag2: MOTOR_COLUMNS["MTR-F02"]}
    return MOTOR_COLUMNS


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: python -m app.scripts.import_history <csv> [TAG_M1,TAG_M2]")
        raise SystemExit(1)
    total = asyncio.run(import_history(sys.argv[1], _motors_from_args(sys.argv)))
    print(f"Importadas {total} amostras de {sys.argv[1]}")


if __name__ == "__main__":
    main()
