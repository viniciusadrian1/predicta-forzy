"""Motor de diagnostico do Volt: sintoma + assinatura dos sensores -> falha.

Cruza o sintoma relatado com a ultima leitura dos sensores do ativo e devolve
uma falha nomeada com um nivel de confianca. Heuristica deterministica alinhada
aos limiares DIN ISO 10816 (vibracao) e aos limites termicos/eletricos do MVP;
quando ha um score de anomalia do modelo de ML, ele reforca a confianca.

O motor apenas LE dados de sensor - nunca aciona o equipamento (guardrail).
"""

from __future__ import annotations

from dataclasses import dataclass

# Limiares (espelho do avaliador de alertas / ISO 10816).
VEL_WARNING = 4.5
VEL_CRITICAL = 7.1
ACCEL_WARNING = 0.6
ACCEL_CRITICAL = 1.5
TEMP_WARNING = 80.0
TEMP_CRITICAL = 95.0


@dataclass(slots=True)
class Diagnosis:
    """Resultado do diagnostico automatico."""

    fault: str
    confidence: float  # 0..1
    evidence: str
    readings: dict[str, float]


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def diagnose(
    symptom: str,
    readings: dict[str, float],
    anomaly_score: float | None = None,
) -> Diagnosis:
    """Diagnostica a partir do sintoma e das leituras atuais dos sensores.

    Sem leituras, a confianca e baixa de proposito - forcando o handoff humano
    exigido pelos guardrails do projeto.
    """
    velocity = readings.get("Vibracao_Velocidade_RMS")
    accel = readings.get("Vibracao_Aceleracao_RMS")
    temperature = readings.get("Temperatura")
    current = readings.get("Corrente")

    if not readings:
        return Diagnosis(
            fault="Sem dados de sensor para diagnostico",
            confidence=0.2,
            evidence="Nao ha telemetria recente do ativo.",
            readings={},
        )

    # ---- Sintoma de temperatura ----
    if symptom == "temperatura" and temperature is not None:
        overloaded = current is not None and current >= 30.0
        if temperature >= TEMP_CRITICAL:
            fault = "Sobreaquecimento" + (" por sobrecarga" if overloaded else "")
            conf = 0.7 + min((temperature - TEMP_CRITICAL) / 40.0, 0.2)
            ev = f"Temperatura {temperature:.1f} C" + (
                f" com corrente {current:.1f} A (sobrecarga)" if overloaded else ""
            )
        elif temperature >= TEMP_WARNING:
            fault = "Aquecimento acima do normal"
            conf = 0.55
            ev = f"Temperatura {temperature:.1f} C, acima da faixa de operacao."
        else:
            fault = "Temperatura dentro do esperado"
            conf = 0.35
            ev = f"Temperatura {temperature:.1f} C, dentro da faixa normal."
        return Diagnosis(fault, _reinforce(conf, anomaly_score), ev, readings)

    # ---- Sintomas de vibracao / ruido (assinatura vibratoria) ----
    if symptom in ("vibracao", "ruido") and velocity is not None:
        accel_val = accel if accel is not None else 0.0
        # Aceleracao dominante -> defeito de rolamento (alta frequencia).
        if accel_val >= ACCEL_CRITICAL:
            fault = "Desgaste de rolamento"
            conf = 0.75 + min((accel_val - ACCEL_CRITICAL) / 3.0, 0.15)
            ev = f"Aceleracao {accel_val:.2f} g elevada (defeito de alta frequencia)."
        elif velocity >= VEL_CRITICAL:
            # Velocidade muito alta com aceleracao moderada -> desalinhamento.
            fault = "Desalinhamento do eixo"
            conf = 0.7 + min((velocity - VEL_CRITICAL) / 6.0, 0.18)
            ev = f"Velocidade {velocity:.2f} mm/s RMS (zona D, ISO 10816)."
        elif velocity >= VEL_WARNING or accel_val >= ACCEL_WARNING:
            fault = "Desbalanceamento ou folga mecanica"
            conf = 0.55
            ev = f"Velocidade {velocity:.2f} mm/s / aceleracao {accel_val:.2f} g (zona C)."
        else:
            fault = "Vibracao dentro do esperado"
            conf = 0.35
            ev = f"Velocidade {velocity:.2f} mm/s RMS, dentro da faixa aceitavel."
        return Diagnosis(fault, _reinforce(conf, anomaly_score), ev, readings)

    # ---- Sem assinatura correspondente ao sintoma ----
    return Diagnosis(
        fault="Sintoma sem confirmacao nos sensores",
        confidence=0.3,
        evidence="Os sensores disponiveis nao confirmam o sintoma relatado.",
        readings=readings,
    )


def _reinforce(confidence: float, anomaly_score: float | None) -> float:
    """Reforca (levemente) a confianca quando o modelo de ML tambem acusa anomalia."""
    if anomaly_score is not None and anomaly_score > 0:
        confidence += min(anomaly_score * 0.1, 0.1)
    return _clamp(confidence)
