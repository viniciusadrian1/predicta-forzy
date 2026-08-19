"""Pipeline de OCR para placas de identificacao de equipamentos.

Etapas: pre-processamento da imagem -> OCR (Tesseract, ou PaddleOCR se o
extra ``ocr`` estiver instalado) -> parsing regex dos campos da placa.

IMPORTANTE: quando nenhum motor de OCR esta disponivel, o servico devolve
um resultado VAZIO e sinaliza a indisponibilidade - jamais inventa dados.
O parser reconhece tanto campos de motor (kW, V, A, RPM...) quanto campos
genericos de placa (fabricante, modelo, numero de serie, data).
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


# ----------------------- Parser generico de placa ------------------------
# Campos rotulados comuns a qualquer placa (nao so motores). O valor pode
# estar na mesma linha do rotulo ou na linha seguinte (\n opcional).
_GENERIC_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "manufacturer",
        "Fabricante",
        re.compile(
            r"(?:FABRICANTE|MANUFACTURER|FABRICANT)\s*[:.]?\s*\n?\s*"
            r"([A-Za-z][\w .,&/\-]{2,48})",
            re.IGNORECASE,
        ),
    ),
    (
        "model",
        "Modelo",
        re.compile(
            r"(?:MACHINE|M[ÁA]QUINA|MODELO|MODEL)\s*[:.]?\s*\n?\s*" r"([A-Za-z0-9][\w .\-/]{1,40})",
            re.IGNORECASE,
        ),
    ),
    (
        "serial_number",
        "Numero de serie",
        re.compile(
            r"(?:SERIAL|S[ÉE]RIE|N[º°.]?\s*S[ÉE]RIE|SERIAL\s*(?:NO|N[º°]))"
            r"\s*[:.]?\s*\n?\s*([A-Za-z0-9][\w./\-]{2,40})",
            re.IGNORECASE,
        ),
    ),
    (
        "manufacture_date",
        "Data de fabricacao",
        re.compile(
            r"(?:DATE|DATA)\s*[:.]?\s*\n?\s*(\d{1,2}[/.\-]\d{2,4}|\d{4})",
            re.IGNORECASE,
        ),
    ),
)

# Sufixos que denunciam um nome de empresa numa linha nao rotulada.
_COMPANY_HINT = re.compile(
    r"\b(S\.?p\.?A|S\.?A|LTDA|GMBH|INC|CO|EQUIPMENT|MOTORS?|MOTORES|IND[UÚ]STRIA|"
    r"EQUIPAMENTOS|TECHNOLOG|SISTEMAS)\b",
    re.IGNORECASE,
)


def parse_generic_fields(text: str, base_confidence: float) -> list[ParsedField]:
    """Extrai campos genericos de placa (fabricante, modelo, serie, data).

    Cobre equipamentos que nao sao motores. Se o fabricante nao vier rotulado,
    usa a primeira linha que se pareca com um nome de empresa (confianca menor).
    """
    fields: list[ParsedField] = []
    seen: set[str] = set()

    for key, label, pattern in _GENERIC_PATTERNS:
        match = pattern.search(text)
        if match:
            value = " ".join(match.group(1).split()).strip(" .,-")
            if value:
                fields.append(ParsedField(key, label, value, round(base_confidence - 0.05, 2)))
                seen.add(key)

    # Fabricante nao rotulado: 1a linha com cara de nome de empresa.
    if "manufacturer" not in seen:
        for line in (ln.strip() for ln in text.splitlines()):
            if 3 <= len(line) <= 48 and _COMPANY_HINT.search(line):
                fields.append(
                    ParsedField("manufacturer", "Fabricante", line, round(base_confidence - 0.2, 2))
                )
                break

    return fields


def merge_fields(*groups: list[ParsedField]) -> list[ParsedField]:
    """Combina grupos de campos, mantendo a primeira ocorrencia de cada chave."""
    out: list[ParsedField] = []
    seen: set[str] = set()
    for group in groups:
        for field in group:
            if field.field not in seen:
                out.append(field)
                seen.add(field.field)
    return out


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


class TesseractEngine:
    """Motor de OCR baseado no Tesseract (pytesseract + binario do sistema)."""

    def __init__(self) -> None:
        import pytesseract

        self._pt = pytesseract
        # Falha aqui (binario ausente) faz get_ocr_engine cair para None.
        pytesseract.get_tesseract_version()

    def read_text(self, image: Image.Image) -> tuple[str, float]:
        # Portugues + ingles; falha de idioma recai para o default do sistema.
        try:
            data = self._pt.image_to_data(image, lang="por+eng", output_type=self._pt.Output.DICT)
        except Exception:
            data = self._pt.image_to_data(image, output_type=self._pt.Output.DICT)

        # Reconstroi o texto por linha e coleta as confiancas dos tokens validos.
        lines: dict[tuple[int, int, int], list[str]] = {}
        confidences: list[float] = []
        for i, word in enumerate(data["text"]):
            token = word.strip()
            conf = float(data["conf"][i])
            if not token or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(token)
            confidences.append(conf / 100.0)

        text = "\n".join(" ".join(words) for words in lines.values())
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return text, mean


@lru_cache(maxsize=1)
def get_ocr_engine() -> TesseractEngine | PaddleOcrEngine | None:
    """Carrega o motor de OCR uma unica vez; ``None`` se nenhum disponivel."""
    try:
        return TesseractEngine()
    except Exception as exc:
        logger.info("Tesseract indisponivel (%s); tentando PaddleOCR", exc)
    try:
        return PaddleOcrEngine()
    except Exception as exc:
        logger.warning("Nenhum motor de OCR disponivel (%s)", exc)
        return None


def extract_nameplate(raw: bytes) -> ExtractionResult:
    """Executa o pipeline completo: pre-processa, faz OCR e parseia a placa.

    Sem motor de OCR disponivel, devolve um resultado vazio e honesto
    (engine ``indisponivel``) - nunca preenche com dados fabricados.
    """
    image = preprocess_image(raw)  # valida que os bytes sao uma imagem
    engine = get_ocr_engine()
    if engine is None:
        return ExtractionResult(engine="indisponivel", raw_text="", fields=[], coverage=0.0)

    text, mean_conf = engine.read_text(image)
    base = round(max(mean_conf, 0.3), 2)
    fields = merge_fields(
        parse_nameplate_text(text, base_confidence=base),
        parse_generic_fields(text, base_confidence=base),
    )
    engine_name = "tesseract" if isinstance(engine, TesseractEngine) else "paddleocr"
    return ExtractionResult(
        engine=engine_name, raw_text=text, fields=fields, coverage=_coverage(fields)
    )
