"""Modelo fisico simplificado do motor eletrico industrial MTR-001.

Copia do modelo do simulador OPC-UA (``edge/opcua_simulator/models.py``), trazida
para dentro do backend porque o diretorio ``edge/`` fica fora do contexto de build
da imagem. Usado pelo simulador de demo (``demo_sim``) quando nao ha OPC-UA real
(deploy publico no Render).

Motor de referencia: inducao trifasico 220 V, 4 polos, ~7,5 kW. As equacoes
priorizam comportamento qualitativo realista (nao um modelo de elementos
finitos): elevacao termica de primeira ordem, escorregamento proporcional a
carga e vibracao conforme as faixas da norma DIN ISO 10816/20816.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# --- Especificacoes nominais (placa do motor MTR-001) ---
NOMINAL_VOLTAGE_V = 220.0
NOMINAL_CURRENT_A = 25.0
NO_LOAD_CURRENT_A = 8.0
SYNCHRONOUS_RPM = 1800.0  # 4 polos @ 60 Hz
MAX_SLIP = 0.035  # ~1737 RPM em plena carga
AMBIENT_TEMP_C = 25.0
MAX_TEMP_RISE_C = 62.0  # elevacao em plena carga -> ~87 C
THERMAL_TAU_S = 180.0  # constante de tempo termica (sistema de 1a ordem)

# --- Vibracao em estado saudavel (mm/s e g) ---
BASE_VIB_VELOCITY_RMS = 1.4
BASE_VIB_ACCEL_RMS = 0.18


@dataclass(slots=True)
class SensorReading:
    """Leitura instantanea dos 6 sensores do motor."""

    voltage_v: float
    current_a: float
    temperature_c: float
    rotation_rpm: float
    vibration_velocity_rms: float
    vibration_acceleration_rms: float


@dataclass(slots=True)
class MotorModel:
    """Estado dinamico do motor, avancado por passos discretos via ``step``."""

    temperature_c: float = AMBIENT_TEMP_C
    _elapsed_s: float = 0.0
    _load_phase: float = 0.0

    def step(self, dt: float, load_setpoint: float) -> SensorReading:
        """Avanca o modelo em ``dt`` segundos e devolve a leitura dos sensores."""
        self._elapsed_s += dt
        self._load_phase += dt

        # Carga efetiva: setpoint + leve ondulacao operacional.
        wander = 0.04 * math.sin(self._load_phase / 37.0)
        load = _clamp(load_setpoint + wander, 0.0, 1.5)

        # Tensao: nominal com ruido gaussiano.
        voltage = NOMINAL_VOLTAGE_V + random.gauss(0.0, 1.8)

        # Corrente: interpolacao linear entre vazio e nominal.
        current = (
            NO_LOAD_CURRENT_A
            + load * (NOMINAL_CURRENT_A - NO_LOAD_CURRENT_A)
            + random.gauss(0.0, 0.25)
        )

        # Temperatura: modelo termico de primeira ordem (aproximacao exponencial).
        steady = AMBIENT_TEMP_C + MAX_TEMP_RISE_C * load**2
        self.temperature_c += (steady - self.temperature_c) * (dt / THERMAL_TAU_S)
        temperature = self.temperature_c + random.gauss(0.0, 0.15)

        # Rotacao: velocidade sincrona menos o escorregamento.
        slip = MAX_SLIP * load
        rotation = SYNCHRONOUS_RPM * (1.0 - slip) + random.gauss(0.0, 0.6)

        # Vibracao: base + carga (faixas da DIN ISO 10816/20816).
        vib_velocity = (BASE_VIB_VELOCITY_RMS + 0.35 * load) + abs(random.gauss(0.0, 0.06))
        vib_accel = BASE_VIB_ACCEL_RMS + 0.05 * load + abs(random.gauss(0.0, 0.012))

        return SensorReading(
            voltage_v=round(voltage, 3),
            current_a=round(max(current, 0.0), 3),
            temperature_c=round(temperature, 3),
            rotation_rpm=round(max(rotation, 0.0), 2),
            vibration_velocity_rms=round(max(vib_velocity, 0.0), 4),
            vibration_acceleration_rms=round(max(vib_accel, 0.0), 4),
        )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
