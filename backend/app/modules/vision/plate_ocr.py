"""Pipeline de OCR para placas de identificacao de motores.

Etapas: pre-processamento da imagem -> OCR (motor pluggavel) -> parsing
regex dos campos tipicos de placa. O motor padrao e o PaddleOCR (extra
opcional ``ocr``); quando ausente, o servico opera em modo simulado e o
parser permanece totalmente funcional e testavel.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger("forzy.vision.ocr")


@dataclass(slots=True)
class ParsedField:
    """Um campo extraido da placa, com grau de confianca."""

    field: str
    label: str
    value: str | None
    confidence: float


@dataclass(slots=True)
class ExtractionResult:
    """Resultado completo da extracao de uma placa."""

    engine: str
    raw_text: str
    fields: list[ParsedField]
    coverage: float


# --------------------------- Pre-processamento ---------------------------
def preprocess_image(raw: bytes) -> Image.Image:
    """Normaliza a imagem da placa para melhorar a leitura por OCR.

    Aplica correcao de orientacao, escala de cinza, realce de contraste,
    nitidez e upscale de textos pequenos.
    """
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    longest = max(image.size)
    if longest < 1600:
        scale = 1600 / longest
        image = image.resize((round(image.width * scale), round(image.height * scale)))
    return image


# ------------------------------- Parser ----------------------------------
_KNOWN_MANUFACTURERS = (
    "WEG",
    "SIEMENS",
    "DUTCHI",
    "METALCORTE",
    "ABB",
    "TECO",
    "BALDOR",
)
_NUM = r"\d+(?:[.,]\d+)?"
_MULTI = rf"{_NUM}(?:\s*/\s*{_NUM})*"

# (chave, rotulo, padrao) para cada campo tipico de placa de motor.
_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("power_kw", "Potencia (kW)", re.compile(rf"({_NUM})\s*k\s*W", re.IGNORECASE)),
    (
        "voltage_v",
        "Tensao (V)",
        re.compile(rf"({_MULTI})\s*V(?:olts)?(?![A-Za-z])", re.IGNORECASE),
    ),
    (
        "nominal_current_a",
        "Corrente (A)",
        re.compile(rf"({_MULTI})\s*A(?:mp)?(?![A-Za-z])", re.IGNORECASE),
    ),
    ("frequency_hz", "Frequencia (Hz)", re.compile(r"(\d{2})\s*Hz", re.IGNORECASE)),
    (
        "nominal_rpm",
        "Rotacao (RPM)",
        re.compile(r"(\d{3,4})\s*(?:RPM|r/min|min-?1)", re.IGNORECASE),
    ),
    ("ip_rating", "Grau de protecao", re.compile(r"(IP\s?\d{2})", re.IGNORECASE)),
    (
        "insulation_class",
        "Classe de isolamento",
        re.compile(r"(?:ISOL\w*|CLASSE|CL\.?|INS\w*)\s*[:.]?\s*([BFH])\b", re.IGNORECASE),
    ),
    (
        "service_factor",
        "Fator de servico",
        re.compile(
            r"(?:F\.?\s?S\.?|FATOR\s*DE\s*SERVI\w*|SERVICE\s*FACTOR)\s*[:.]?\s*"
            r"([01][.,]\d{1,2})",
            re.IGNORECASE,
        ),
    ),
    (
        "power_factor",
        "Fator de potencia",
        re.compile(
            r"(?:F\.?\s?P\.?|COS\s*[O0]?|POWER\s*FACTOR)\s*[:.]?\s*(0[.,]\d{1,2})",
            re.IGNORECASE,
        ),
    ),
)
_POWER_CV = re.compile(rf"({_NUM})\s*(?:CV|HP)", re.IGNORECASE)
_MODEL = re.compile(
    r"(?:MOD(?:ELO)?|TYPE|TIPO)\.?\s*:?\s*([A-Z0-9][A-Z0-9 \-/]{2,30})", re.IGNORECASE
)

# Campos considerados no calculo de cobertura.
EXPECTED_FIELDS = (
    "manufacturer",
    "model",
    "power_kw",
    "voltage_v",
    "nominal_current_a",
    "frequency_hz",
    "nominal_rpm",
    "ip_rating",
    "insulation_class",
)


def parse_nameplate_text(text: str, base_confidence: float = 0.9) -> list[ParsedField]:
    """Extrai os campos tipicos de uma placa de motor a partir do texto OCR."""
    fields: list[ParsedField] = []
    upper = text.upper()

    for name in _KNOWN_MANUFACTURERS:
        if name in upper:
            fields.append(ParsedField("manufacturer", "Fabricante", name.title(), base_confidence))
            break

    model = _MODEL.search(text)
    if model:
        fields.append(
            ParsedField("model", "Modelo", model.group(1).strip(), round(base_confidence - 0.1, 2))
        )

    for key, label, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            fields.append(ParsedField(key, label, match.group(1).strip(), base_confidence))

    # Potencia em CV/HP convertida para kW quando kW nao foi encontrado.
    if not any(f.field == "power_kw" for f in fields):
        cv = _POWER_CV.search(text)
        if cv:
            kw = float(cv.group(1).replace(",", ".")) * 0.7355
            fields.append(
                ParsedField(
                    "power_kw",
                    "Potencia (kW)",
                    f"{kw:.1f}".replace(".", ","),
                    round(base_confidence - 0.15, 2),
                )
            )
    return fields


def _coverage(fields: list[ParsedField]) -> float:
    found = {f.field for f in fields}
    hits = sum(1 for key in EXPECTED_FIELDS if key in found)
    return round(hits / len(EXPECTED_FIELDS), 2)


# --------------------------- Motor de OCR --------------------------------
class PaddleOcrEngine:
    """Motor de OCR baseado em PaddleOCR (extra opcional ``ocr``)."""

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

    def read_text(self, image: Image.Image) -> tuple[str, float]:
        import numpy as np

        result = self._ocr.ocr(np.array(image), cls=True)
        lines: list[str] = []
        confidences: list[float] = []
        for page in result or []:
            for entry in page or []:
                text, conf = entry[1]
                lines.append(str(text))
                confidences.append(float(conf))
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return "\n".join(lines), mean


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOcrEngine | None:
    """Carrega o motor de OCR uma unica vez; devolve ``None`` se indisponivel."""
    try:
        return PaddleOcrEngine()
    except Exception as exc:  # paddleocr ausente ou falha ao baixar modelo
        logger.warning("OCR PaddleOCR indisponivel (%s); modo simulado ativo", exc)
        return None


# Campos simulados (placa WEG tipica) usados quando o motor de OCR esta ausente.
_STUB_FIELDS: tuple[ParsedField, ...] = (
    ParsedField("manufacturer", "Fabricante", "WEG", 0.0),
    ParsedField("model", "Modelo", "W22 IR3 Premium", 0.0),
    ParsedField("power_kw", "Potencia (kW)", "7,5", 0.0),
    ParsedField("voltage_v", "Tensao (V)", "220/380", 0.0),
    ParsedField("nominal_current_a", "Corrente (A)", "25,4/14,7", 0.0),
    ParsedField("frequency_hz", "Frequencia (Hz)", "60", 0.0),
    ParsedField("nominal_rpm", "Rotacao (RPM)", "1755", 0.0),
    ParsedField("ip_rating", "Grau de protecao", "IP55", 0.0),
    ParsedField("insulation_class", "Classe de isolamento", "F", 0.0),
)


def extract_nameplate(raw: bytes) -> ExtractionResult:
    """Executa o pipeline completo: pre-processa, faz OCR e parseia a placa."""
    image = preprocess_image(raw)  # valida que os bytes sao uma imagem
    engine = get_ocr_engine()
    if engine is None:
        return ExtractionResult(engine="stub", raw_text="", fields=list(_STUB_FIELDS), coverage=0.0)
    text, mean_conf = engine.read_text(image)
    fields = parse_nameplate_text(text, base_confidence=round(max(mean_conf, 0.5), 2))
    return ExtractionResult(
        engine="paddleocr", raw_text=text, fields=fields, coverage=_coverage(fields)
    )
