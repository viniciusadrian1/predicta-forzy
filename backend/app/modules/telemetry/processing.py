"""Pipeline de processamento da telemetria: validacao e normalizacao.

Recebe o dado bruto do OPC-UA, anexa a unidade canonica, valida a faixa
operacional e ajusta o codigo de qualidade. As faixas estao alinhadas ao
sensor de vibracao Pepperl+Fuchs VIM32 e ao motor de referencia MTR-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.infra.opcua_client.client import TelemetrySample

# Codigos de qualidade (inspirados no StatusCode OPC-UA).
QUALITY_GOOD = 0
QUALITY_OUT_OF_RANGE = 1


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """Metadados de uma variavel de telemetria."""

    unit: str
    min_valid: float
    max_valid: float
    label: str


VARIABLE_SPECS: dict[str, VariableSpec] = {
    "Tensao": VariableSpec("V", 0.0, 500.0, "Tensao"),
    "Corrente": VariableSpec("A", 0.0, 200.0, "Corrente"),
    "Temperatura": VariableSpec("C", -40.0, 200.0, "Temperatura"),
    "Rotacao": VariableSpec("RPM", 0.0, 5000.0, "Rotacao"),
    "Vibracao_Velocidade_RMS": VariableSpec("mm/s", 0.0, 128.0, "Vibracao - velocidade RMS"),
    "Vibracao_Aceleracao_RMS": VariableSpec("g", 0.0, 10.0, "Vibracao - aceleracao RMS"),
}


@dataclass(slots=True)
class ProcessedSample:
    """Amostra de telemetria apos validacao e normalizacao."""

    time: datetime
    asset_tag: str
    variable: str
    value: float
    unit: str
    quality: int

    def as_event(self) -> dict[str, object]:
        """Serializa a amostra para envio via SSE."""
        return {
            "asset_tag": self.asset_tag,
            "variable": self.variable,
            "value": self.value,
            "unit": self.unit,
            "quality": self.quality,
            "time": self.time.isoformat(),
        }


def process_sample(sample: TelemetrySample) -> ProcessedSample:
    """Valida a leitura, anexa a unidade canonica e ajusta a qualidade."""
    spec = VARIABLE_SPECS.get(sample.variable)
    quality = sample.quality
    unit = ""
    if spec is not None:
        unit = spec.unit
        if not spec.min_valid <= sample.value <= spec.max_valid:
            quality = max(quality, QUALITY_OUT_OF_RANGE)
    return ProcessedSample(
        time=sample.timestamp,
        asset_tag=sample.asset_tag,
        variable=sample.variable,
        value=round(sample.value, 4),
        unit=unit,
        quality=quality,
    )
