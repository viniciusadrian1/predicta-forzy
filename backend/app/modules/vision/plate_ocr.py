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
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageChops, ImageFilter, ImageOps

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
# Raio do BoxBlur (janela de ~51px na imagem ja normalizada em 1600px) e quanto
# o pixel precisa estar abaixo da media local para contar como tinta. Medidos:
# janelas menores com margem maior liam melhor em foto degradada, mas
# CORROMPIAM valor em placa limpa (a corrente "11,5/6,6" virava "11,5/6,66") -
# e valor errado com confianca alta e pior que campo ausente.
_RAIO_LOCAL = 25
_MARGEM_TINTA = 10
# Abaixo disto a leitura e considerada fraca e vale uma segunda tentativa.
_COBERTURA_ACEITAVEL = 0.6
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


def preprocess_adaptativo(raw: bytes) -> Image.Image:
    """Binariza com limiar ADAPTATIVO — segunda tentativa para foto ruim.

    Cada pixel e comparado com a media da sua vizinhanca, nao com um valor unico
    do quadro. E o que salva a foto de iluminacao desigual (metade da placa na
    sombra, metade estourada), onde qualquer limiar global apaga um lado ou
    satura o outro — e onde o pipeline padrao chega a devolver ZERO campo.

    NAO e o padrao. Medido em banco balanceado (so 2 de 8 degradacoes sendo de
    iluminacao): 9 casos melhoram, 9 PIORAM, cobertura media praticamente igual
    (0,848 -> 0,862) e 28% mais lento. O ganho grande so aparece quando o banco
    e dominado por iluminacao desigual. Como segunda tentativa, fica o resgate
    sem as regressoes.

    O BoxBlur do PIL ja e a media local: sem dependencia nova (numpy nem e
    dependencia declarada deste backend).
    """
    base = preprocess_image(raw)
    media_local = base.filter(ImageFilter.BoxBlur(_RAIO_LOCAL))
    # (pixel - media_local + 128): tinta e quem ficou abaixo da media local.
    contraste = ImageChops.subtract(base, media_local, scale=1, offset=128)
    binaria = contraste.point(lambda p: 0 if p < 128 - _MARGEM_TINTA else 255, mode="L")
    # Mediana depois do limiar tira o salpico que a binarizacao cria no grao.
    return binaria.filter(ImageFilter.MedianFilter(3))


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
    ("power_kw", "Potência (kW)", re.compile(rf"({_NUM})\s*k\s*W", re.IGNORECASE)),
    (
        "voltage_v",
        "Tensão (V)",
        re.compile(rf"({_MULTI})\s*V(?:olts)?(?![A-Za-z])", re.IGNORECASE),
    ),
    (
        "nominal_current_a",
        "Corrente (A)",
        re.compile(rf"({_MULTI})\s*A(?:mp)?(?![A-Za-z])", re.IGNORECASE),
    ),
    ("frequency_hz", "Frequência (Hz)", re.compile(r"(\d{2})\s*Hz", re.IGNORECASE)),
    (
        "nominal_rpm",
        "Rotação (RPM)",
        re.compile(r"(\d{3,4})\s*(?:RPM|r/min|min-?1)", re.IGNORECASE),
    ),
    (
        "ip_rating",
        "Grau de proteção",
        # O "I" de IP sai como 1 ou l no OCR de placa gravada ("1p55"). A faixa
        # 2x-6x cobre os graus reais (IP21..IP68) e evita casar com um ano solto
        # como "1955". O valor e normalizado para "IP##" em _NORMALIZADORES.
        re.compile(r"\b[I1l][Pp]\s?([2-6]\d)\b"),
    ),
    (
        "insulation_class",
        "Classe de isolamento",
        re.compile(r"(?:ISOL\w*|CLASSE|CL\.?|INS\w*)\s*[:.]?\s*([BFH])\b", re.IGNORECASE),
    ),
    (
        "service_factor",
        "Fator de serviço",
        re.compile(
            r"(?:F\.?\s?S\.?|FATOR\s*DE\s*SERVI\w*|SERVICE\s*FACTOR)\s*[:.]?\s*"
            r"([01][.,]\d{1,2})",
            re.IGNORECASE,
        ),
    ),
    (
        "power_factor",
        "Fator de potência",
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


# Normalizacao do valor extraido. A regex de IP captura so os digitos (para
# tolerar o "1p55" que o OCR produz em placa gravada); o cadastro precisa
# receber "IP55", nao "55".
_NORMALIZADORES: dict[str, "Callable[[str], str]"] = {
    "ip_rating": lambda valor: f"IP{valor.strip()}",
}


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
            valor = match.group(1).strip()
            normalizar = _NORMALIZADORES.get(key)
            fields.append(
                ParsedField(key, label, normalizar(valor) if normalizar else valor, base_confidence)
            )

    # Potencia em CV/HP convertida para kW quando kW nao foi encontrado.
    if not any(f.field == "power_kw" for f in fields):
        cv = _POWER_CV.search(text)
        if cv:
            kw = float(cv.group(1).replace(",", ".")) * 0.7355
            fields.append(
                ParsedField(
                    "power_kw",
                    "Potência (kW)",
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
        "Número de série",
        re.compile(
            r"(?:SERIAL|S[ÉE]RIE|N[º°.]?\s*S[ÉE]RIE|SERIAL\s*(?:NO|N[º°]))"
            r"\s*[:.]?\s*\n?\s*([A-Za-z0-9][\w./\-]{2,40})",
            re.IGNORECASE,
        ),
    ),
    (
        "manufacture_date",
        "Data de fabricação",
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


# Campos de TEXTO livre (fabricante, modelo, serie) sao os que mais sofrem com
# ruido: a regex acha o rotulo ("FABRICANTE") e leva junto o lixo que veio
# depois. E o pior tipo de defeito neste sistema, porque o valor vai direto
# para uma coluna do ativo - "cria A ico ce velo ENTS INDUSTRIAL S.A: IO" como
# fabricante e pior do que campo vazio: um humano corrige o vazio, mas confia
# no que ja veio preenchido.
_CAMPOS_DE_TEXTO = frozenset({"manufacturer", "model", "serial_number"})


def _parece_ruido(valor: str) -> bool:
    """Heuristica de lixo de OCR para campo de texto curto.

    Nome de fabricante ou modelo e curto e denso. Leitura ruim vira uma cadeia
    longa de fragmentos de 1-2 letras, com muito simbolo solto no meio.
    """
    palavras = valor.split()
    if not palavras:
        return True
    # Placa nao tem fabricante com 5+ palavras.
    if len(palavras) > 4:
        return True
    # Muitos fragmentos minusculos = OCR picotando letra solta.
    fragmentos = sum(1 for palavra in palavras if len(palavra) <= 2)
    if fragmentos >= 2:
        return True
    # Densidade: pouca letra/digito no meio de simbolo e ruido.
    uteis = sum(1 for c in valor if c.isalnum() or c.isspace())
    if uteis / len(valor) < 0.75:
        return True
    return False


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
            if key in _CAMPOS_DE_TEXTO and _parece_ruido(value):
                # Melhor campo ausente do que valor inventado: quem revisa
                # preenche o que falta, mas nao desconfia do que ja veio.
                logger.debug("valor descartado por ruido em %s: %r", key, value)
                continue
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

    def _read(self, image: "Image.Image", config: str) -> tuple[str, float]:
        """Uma passada do tesseract, reconstruindo o texto por linha."""
        # Portugues + ingles; falha de idioma recai para o default do sistema.
        try:
            data = self._pt.image_to_data(
                image, lang="por+eng", config=config, output_type=self._pt.Output.DICT
            )
        except Exception:
            data = self._pt.image_to_data(
                image, config=config, output_type=self._pt.Output.DICT
            )

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

    def read_text(self, image: "Image.Image") -> tuple[str, float]:
        """Le a placa, com uma segunda tentativa quando a primeira vem vazia.

        O modo padrao (PSM 3, analise de layout de PAGINA) as vezes conclui que
        uma placa muito degradada - girada, desfocada - nao tem bloco de texto
        valido e devolve ZERO palavras, o que vira "cobertura 0%" na tela. Nesses
        casos o PSM 6 ("um unico bloco uniforme de texto"), que descreve melhor
        uma placa, ainda consegue ler.

        O PSM 6 entra so como SEGUNDA tentativa, nunca como padrao: medido sobre
        as placas de assets/nameplates_samples em variantes giradas e desfocadas,
        troca-lo por padrao resgata os casos vazios mas PIORA varios que hoje
        acertam. Como fallback, o caminho que ja funciona fica intacto.
        """
        text, mean = self._read(image, config="")
        if text.strip():
            return text, mean
        return self._read(image, config="--psm 6")


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

    engine_name = "tesseract" if isinstance(engine, TesseractEngine) else "paddleocr"

    def _tentar(imagem: Image.Image) -> ExtractionResult:
        text, mean_conf = engine.read_text(imagem)
        base = round(max(mean_conf, 0.3), 2)
        fields = merge_fields(
            parse_nameplate_text(text, base_confidence=base),
            parse_generic_fields(text, base_confidence=base),
        )
        return ExtractionResult(
            engine=engine_name, raw_text=text, fields=fields, coverage=_coverage(fields)
        )

    resultado = _tentar(image)
    if resultado.coverage >= _COBERTURA_ACEITAVEL:
        return resultado

    # Leitura fraca: pode ser iluminacao desigual. Uma segunda passada com
    # limiar adaptativo, ficando com a melhor das duas — assim o caminho que ja
    # funcionava nunca piora, e so a foto ruim paga o tempo extra.
    alternativa = _tentar(preprocess_adaptativo(raw))
    return alternativa if alternativa.coverage > resultado.coverage else resultado
