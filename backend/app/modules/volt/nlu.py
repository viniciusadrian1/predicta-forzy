"""NLU do Volt: extracao de intencoes e entidades por regras deterministicas.

Entidades: codigo do ativo, tipo de sintoma (vibracao/ruido/temperatura),
nivel de urgencia. Intencoes: informar_ativo, relatar_sintoma, solicitar_status,
falar_humano. Abordagem hibrida (regras + modelo de diagnostico) conforme a
arquitetura minima do projeto.
"""

from __future__ import annotations

import re
import unicodedata

# Codigo de ativo: 2-4 letras + separador opcional + sufixo com ao menos um
# digito, aceitando letra intercalada (MTR-2291, MTR-F01, BMB001, MTR-001).
_ASSET_RE = re.compile(r"\b([A-Za-z]{2,4})[\s\-_]?([A-Za-z]?\d{1,4}[A-Za-z]?)\b")

_SYMPTOMS: dict[str, tuple[str, ...]] = {
    "vibracao": ("vibra", "tremend", "tremor", "balanc", "oscila"),
    "ruido": ("ruido", "barulho", "estalo", "zumbido", "chiado", "rangid", "batendo"),
    "temperatura": ("temperatura", "quente", "aquec", "esquent", "superaquec", "fervendo"),
}

_HUMAN_HINTS = (
    "falar com human",
    "falar com uma pessoa",
    "falar com alguem",
    "atendente",
    "suporte",
    "transfer",
    "pessoa de verdade",
    "quero um tecnico",
    "chamar alguem",
)

_URGENCY_HIGH = ("urgente", "parou", "parado", "emergencia", "grave", "fogo", "fumaca", "agora")

# Pistas de que a mensagem e uma duvida tecnica (consulta aos manuais/base RAG),
# e nao um codigo de ativo ou um sintoma do fluxo guiado.
_QUESTION_HINTS = (
    "como ",
    "o que ",
    "qual ",
    "quais ",
    "quando ",
    "onde ",
    "por que",
    "porque",
    "pra que",
    "para que",
    "posso ",
    "devo ",
    "poderia",
    "explica",
    "explique",
    "procedimento",
    "manual",
    "norma",
    "iso ",
    "torque",
    "especifica",
    "significa",
    "diferenca",
    "recomenda",
    "limite",
    "duvida",
)


def _norm(text: str) -> str:
    """Minusculas sem acento, para casar palavras-chave de forma robusta."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def extract_asset_code(text: str) -> str | None:
    """Extrai e normaliza o codigo do ativo (ex.: 'mtr 2291' -> 'MTR-2291')."""
    match = _ASSET_RE.search(text)
    if not match:
        return None
    return f"{match.group(1).upper()}-{match.group(2).upper()}"


def detect_symptom(text: str) -> str | None:
    """Identifica o tipo de sintoma relatado, se houver."""
    norm = _norm(text)
    for symptom, hints in _SYMPTOMS.items():
        if any(hint in norm for hint in hints):
            return symptom
    return None


def wants_human(text: str) -> bool:
    """Indica se o usuario pediu explicitamente para falar com uma pessoa."""
    norm = _norm(text)
    return any(hint in norm for hint in _HUMAN_HINTS)


def detect_urgency(text: str) -> str:
    """Nivel de urgencia percebido a partir do relato ('alta' ou 'normal')."""
    norm = _norm(text)
    return "alta" if any(word in norm for word in _URGENCY_HIGH) else "normal"


def is_question(text: str) -> bool:
    """Heuristica: a mensagem parece uma duvida tecnica (para consulta aos manuais)."""
    if "?" in text:
        return True
    norm = _norm(text)
    return any(hint in norm for hint in _QUESTION_HINTS)
