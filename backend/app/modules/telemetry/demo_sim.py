"""Simulador de telemetria para a demo publica (Render), onde nao ha OPC-UA.

Grava telemetria com timestamp=agora para os 3 motores, mantendo os cards
"AO VIVO" e os graficos preenchidos:

* **MTR-001**: modelo fisico do motor WEG (dado *simulado* - nao ha dataset real).
* **MTR-F01 / MTR-F02**: *replay* do dataset real IO-Link da Forzy em loop. Os
  valores sao reais (do sensor); apenas o timestamp e reposicionado para agora,
  ja que a captura original tem ~4h de maio/2026 e nao cai nas janelas da UI.

Ativado por ``DEMO_SIMULATOR=true``. No ambiente local (docker-compose) o
simulador OPC-UA real cobre o MTR-001, entao esta tarefa fica desligada.

Passa pelo MESMO pipeline do OPC-UA/externo (dado bruto + processado + SSE),
entao nada entra como "bom" sem validar a faixa fisica em ``process_sample``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from datetime import UTC, datetime

from app.core.config import Settings
from app.infra.db.base import timeseries_session_factory
from app.infra.opcua_client.client import TelemetrySample
from app.modules.telemetry.motor_model import MotorModel
from app.modules.telemetry.processing import QUALITY_GOOD, process_sample
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.telemetry.stream import broadcaster

logger = logging.getLogger("forzy.telemetry.demosim")

# Variaveis do modelo fisico do MTR-001 (6 sensores).
_MTR001_VARIABLES = (
    "Tensao",
    "Corrente",
    "Temperatura",
    "Rotacao",
    "Vibracao_Velocidade_RMS",
    "Vibracao_Aceleracao_RMS",
)

# (indice da coluna no CSV real, variavel canonica) por motor fisico.
_REPLAY_COLUMNS: dict[str, list[tuple[int, str]]] = {
    "MTR-F01": [(3, "Vibracao_Velocidade_RMS"), (4, "Vibracao_Aceleracao_RMS"), (5, "Temperatura")],
    "MTR-F02": [(6, "Vibracao_Velocidade_RMS"), (7, "Vibracao_Aceleracao_RMS"), (8, "Temperatura")],
}


def load_replay_frames(path: str) -> list[dict[str, dict[str, float]]]:
    """Le o CSV real -> lista de frames ``[{tag: {variavel: valor}}]``.

    Devolve lista vazia se o arquivo nao existir (a demo segue so com o MTR-001).
    """
    import csv

    if not path or not os.path.exists(path):
        return []
    frames: list[dict[str, dict[str, float]]] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle, delimiter=";"))[3:]  # pula 3 cabecalhos
    for row in rows:
        if not row or not row[0].strip():
            continue
        frame: dict[str, dict[str, float]] = {}
        for tag, columns in _REPLAY_COLUMNS.items():
            readings: dict[str, float] = {}
            for index, variable in columns:
                try:
                    readings[variable] = round(float(row[index].replace(",", ".")), 4)
                except (IndexError, ValueError):
                    continue
            if readings:
                frame[tag] = readings
        if frame:
            frames.append(frame)
    return frames


class DemoSimulatorService:
    """Gera telemetria recente para a demo publica (substitui o OPC-UA)."""

    def __init__(self, settings: Settings) -> None:
        self._interval = max(settings.demo_simulator_interval_seconds, 2.0)
        self._load = settings.demo_simulator_load
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._model = MotorModel()
        self._frames = load_replay_frames(settings.demo_history_csv)
        self._idx = 0

    def start(self) -> None:
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run_forever())
            logger.info(
                "Simulador de demo iniciado (%.0fs; MTR-001 fisico + replay real de %d frames)",
                self._interval,
                len(self._frames),
            )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_forever(self) -> None:
        while self._running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - um passo ruim nao derruba a tarefa
                logger.warning("Simulador de demo falhou num passo: %s", exc)
            await asyncio.sleep(self._interval)

    async def tick(self) -> int:
        """Gera e grava uma leitura por motor com timestamp=agora."""
        now = datetime.now(UTC)
        raw: list[TelemetrySample] = []

        # MTR-001: modelo fisico (simulado).
        reading = self._model.step(self._interval, self._load)
        values = {
            "Tensao": reading.voltage_v,
            "Corrente": reading.current_a,
            "Temperatura": reading.temperature_c,
            "Rotacao": reading.rotation_rpm,
            "Vibracao_Velocidade_RMS": reading.vibration_velocity_rms,
            "Vibracao_Aceleracao_RMS": reading.vibration_acceleration_rms,
        }
        for variable in _MTR001_VARIABLES:
            raw.append(
                TelemetrySample(
                    asset_tag="MTR-001",
                    variable=variable,
                    value=values[variable],
                    timestamp=now,
                    quality=QUALITY_GOOD,
                    source="demo-sim",
                )
            )

        # MTR-F01 / MTR-F02: replay do dado real, re-datado para agora.
        if self._frames:
            frame = self._frames[self._idx % len(self._frames)]
            self._idx += 1
            for tag, readings in frame.items():
                for variable, value in readings.items():
                    raw.append(
                        TelemetrySample(
                            asset_tag=tag,
                            variable=variable,
                            value=value,
                            timestamp=now,
                            quality=QUALITY_GOOD,
                            source="demo-replay",
                        )
                    )

        processed = [process_sample(sample) for sample in raw]
        async with timeseries_session_factory() as session:
            repository = TelemetryRepository(session)
            for raw_sample, sample in zip(raw, processed, strict=True):
                await repository.add_raw(raw_sample)
                await repository.add_processed(sample)
            await session.commit()
        for sample in processed:
            await broadcaster.publish(sample.as_event())
        return len(processed)
