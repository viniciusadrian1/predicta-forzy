"""Gerador de dataset historico sintetico de telemetria (90 dias).

Reutiliza os modelos fisicos do simulador OPC-UA para produzir 90 dias de
telemetria em resolucao de 1 minuto, cobrindo operacao normal, degradacao
progressiva de rolamento, janelas de sobrecarga, desbalanceamento e spikes
pontuais.

Saida: ml/data/raw/telemetry_history.csv (formato wide, com coluna 'label').

Executar:  python edge/data_generator/generate_dataset.py
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Reutiliza os modelos fisicos do simulador OPC-UA.
_SIMULATOR_DIR = Path(__file__).resolve().parents[1] / "opcua_simulator"
sys.path.insert(0, str(_SIMULATOR_DIR))

from fault_injection import FaultInjector, FaultMode  # noqa: E402
from models import MotorModel  # noqa: E402

STEP_SECONDS = 60
DAYS = 90
TOTAL_STEPS = DAYS * 24 * 60
ASSET_TAG = "MTR-001"
OUTPUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "ml"
    / "data"
    / "raw"
    / "telemetry_history.csv"
)


def _schedule(step: int) -> tuple[float, FaultMode, float, float, str]:
    """Devolve (load, modo_falha, severidade, desgaste_rolamento, label)."""
    day = step / 1440.0
    minute_of_day = step % 1440

    # Carga: variacao dia/noite + ruido operacional.
    base_load = 0.82 if 6 * 60 <= minute_of_day < 22 * 60 else 0.62
    load = base_load + random.uniform(-0.04, 0.04)

    # Desgaste de rolamento: lento ate o dia 60, acelerado a partir dai.
    if day < 60:
        bearing_wear = 0.12 * (day / 60.0)
    else:
        bearing_wear = min(0.97, 0.12 + 0.85 * ((day - 60) / 30.0))

    # Janelas de sobrecarga (~4,8 h cada).
    for start in (12.0, 41.0, 73.0):
        if start <= day < start + 0.2:
            return load, FaultMode.OVERLOAD, 0.8, bearing_wear, "overload"

    # Janelas de desbalanceamento (~8 h cada).
    for start in (27.0, 55.0):
        if start <= day < start + 0.34:
            return load, FaultMode.UNBALANCE, 0.6, bearing_wear, "unbalance"

    label = "bearing_wear" if day >= 68 else "normal"
    return load, FaultMode.NONE, 0.0, bearing_wear, label


def generate() -> Path:
    """Gera o dataset historico e devolve o caminho do CSV."""
    model = MotorModel()
    injector = FaultInjector()
    start = datetime.now(UTC) - timedelta(days=DAYS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "time",
                "asset_tag",
                "voltage_v",
                "current_a",
                "temperature_c",
                "rotation_rpm",
                "vibration_velocity_rms",
                "vibration_acceleration_rms",
                "label",
            ]
        )
        for step in range(TOTAL_STEPS):
            load, mode, severity, bearing_wear, label = _schedule(step)
            injector.bearing_wear = bearing_wear
            injector.configure(mode, severity)
            perturbation = injector.update(STEP_SECONDS)
            reading = model.step(STEP_SECONDS, load, perturbation)
            timestamp = start + timedelta(seconds=step * STEP_SECONDS)

            values = [
                reading.voltage_v,
                reading.current_a,
                reading.temperature_c,
                reading.rotation_rpm,
                reading.vibration_velocity_rms,
                reading.vibration_acceleration_rms,
            ]
            # Spikes pontuais (~0,2% dos passos).
            if random.random() < 0.002:
                index = random.randint(0, 5)
                values[index] = round(values[index] * random.uniform(1.4, 2.2), 4)
                label = "spike"

            writer.writerow([timestamp.isoformat(), ASSET_TAG, *values, label])

    return OUTPUT_PATH


def main() -> None:
    random.seed(42)
    path = generate()
    print(f"Dataset gerado: {path} ({TOTAL_STEPS} registros, {DAYS} dias)")


if __name__ == "__main__":
    main()
