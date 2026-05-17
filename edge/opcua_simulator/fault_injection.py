"""Injecao de falhas no simulador do motor MTR-001.

Cobre os tres mecanismos de degradacao mais comuns em motores de inducao:

* ``BEARING_WEAR``  - desgaste progressivo de rolamento (vibracao crescente);
* ``UNBALANCE``     - desbalanceamento mecanico (componente 1x rpm);
* ``OVERLOAD``      - sobrecarga de processo (corrente e temperatura altas).

Mesmo em operacao normal ha um desgaste natural lentissimo, garantindo que o
ativo "envelheca" de forma realista ao longo do tempo.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models import Perturbation

# Desgaste natural de fundo: vida util de referencia ~240 dias de operacao.
NATURAL_WEAR_RATE = 1.0 / (3600.0 * 24.0 * 240.0)


class FaultMode(str, Enum):
    """Modos de falha suportados pelo simulador."""

    NONE = "NONE"
    BEARING_WEAR = "BEARING_WEAR"
    UNBALANCE = "UNBALANCE"
    OVERLOAD = "OVERLOAD"


@dataclass
class FaultInjector:
    """Converte o modo/severidade de falha em uma ``Perturbation`` por passo."""

    mode: FaultMode = FaultMode.NONE
    severity: float = 0.0  # 0.0 .. 1.0
    bearing_wear: float = 0.0  # 0.0 .. 1.0, acumulado e irreversivel
    _fault_elapsed_s: float = 0.0

    def configure(self, mode: FaultMode, severity: float) -> None:
        """Atualiza o modo de falha; zera o cronometro ao trocar de modo."""
        if mode is not self.mode:
            self._fault_elapsed_s = 0.0
        self.mode = mode
        self.severity = max(0.0, min(1.0, severity))

    def update(self, dt: float) -> Perturbation:
        """Avanca a falha em ``dt`` segundos e devolve a perturbacao resultante."""
        # Desgaste natural de fundo, sempre presente.
        self.bearing_wear = min(1.0, self.bearing_wear + NATURAL_WEAR_RATE * dt)

        if self.mode is FaultMode.BEARING_WEAR:
            # Desgaste acelerado; a severidade controla a taxa de progressao.
            rate = (0.3 + self.severity) / 150.0
            self.bearing_wear = min(1.0, self.bearing_wear + rate * dt)

        pert = self._bearing_perturbation()

        if self.mode is FaultMode.UNBALANCE:
            # Ganho constante na velocidade de vibracao (componente 1x rpm).
            pert.vib_velocity_gain *= 1.0 + 1.6 * self.severity
            pert.extra_vib_accel += 0.10 * self.severity
        elif self.mode is FaultMode.OVERLOAD:
            pert.load_multiplier *= 1.0 + 0.45 * self.severity
            pert.extra_current_a += 6.0 * self.severity
            pert.extra_temperature_c += 8.0 * self.severity

        if self.mode is not FaultMode.NONE:
            self._fault_elapsed_s += dt

        return pert

    def _bearing_perturbation(self) -> Perturbation:
        """Efeito do desgaste de rolamento acumulado.

        Rolamento desgastado eleva moderadamente a velocidade de vibracao e,
        de forma mais acentuada, a aceleracao (defeitos sao de alta frequencia).
        """
        w = self.bearing_wear
        return Perturbation(
            extra_vib_velocity=3.0 * w + 2.5 * w * w,
            extra_vib_accel=0.6 * w + 1.4 * w * w,
            extra_temperature_c=6.0 * w,
        )
