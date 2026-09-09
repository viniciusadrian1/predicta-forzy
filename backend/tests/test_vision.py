"""Testes do modulo de visao: parser de placas de identificacao."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.modules.vision import plate_ocr
from app.modules.vision.plate_ocr import (
    EXPECTED_FIELDS,
    extract_nameplate,
    get_ocr_engine,
    parse_generic_fields,
    parse_nameplate_text,
    preprocess_image,
)

_NAMEPLATES: dict[str, str] = {
    "WEG": "\n".join(
        [
            "WEG MOTORES",
            "MOTOR DE INDUCAO TRIFASICO",
            "MOD W22 IR3 PREMIUM",
            "7,5 kW   10 CV",
            "220/380 V   25,4/14,7 A",
            "60 Hz   1755 RPM",
            "IP55   ISOL F",
            "FS 1.15   FP 0,83",
        ]
    ),
    "SIEMENS": "\n".join(
        [
            "SIEMENS",
            "MOTOR TRIFASICO DE INDUCAO",
            "TIPO 1LA7 130-4AA60",
            "5,5 kW   380 V",
            "11,8 A   60 Hz",
            "1745 RPM   IP55",
            "ISOL F   FS 1.15",
        ]
    ),
    "DUTCHI": "\n".join(
        [
            "DUTCHI MOTORS",
            "MOTOR ELETRICO TRIFASICO",
            "MOD DM1 132M",
            "7,5 kW   220 V",
            "26 A   60 Hz",
            "1760 RPM   IP55",
            "CL F   FP 0,82",
        ]
    ),
    "METALCORTE": "\n".join(
        [
            "METALCORTE",
            "MOTOR ELETRICO INDUSTRIAL",
            "MOD MC-100L4",
            "3,0 kW   220/380 V",
            "11,5/6,6 A   60 Hz",
            "1740 RPM   IP54",
            "ISOL B   FS 1,0",
        ]
    ),
}


def _coverage(text: str) -> float:
    fields = parse_nameplate_text(text)
    found = {field.field for field in fields}
    return len([key for key in EXPECTED_FIELDS if key in found]) / len(EXPECTED_FIELDS)


def test_parse_weg_nameplate():
    fields = {f.field: f.value for f in parse_nameplate_text(_NAMEPLATES["WEG"])}
    assert fields["manufacturer"] == "Weg"
    assert fields["power_kw"] == "7,5"
    assert fields["voltage_v"].startswith("220")
    assert fields["frequency_hz"] == "60"
    assert fields["nominal_rpm"] == "1755"
    assert fields["insulation_class"] == "F"


def test_all_nameplates_meet_coverage_target():
    # Criterio Sprint 2: >= 70% dos campos em ao menos 3 das 4 placas.
    good = sum(1 for text in _NAMEPLATES.values() if _coverage(text) >= 0.7)
    assert good >= 3


def test_parse_empty_text_returns_no_fields():
    assert parse_nameplate_text("") == []


def test_parse_converts_cv_to_kw():
    fields = {f.field: f.value for f in parse_nameplate_text("MOTOR 10 CV 220 V")}
    assert "power_kw" in fields


# --- Placa generica (equipamento que nao e motor) ---
_POULTRY = "\n".join(
    [
        "Tecno Poultry Equipment S.p.A",
        "Via L. da Vinci 15 - 35010",
        "Order X/3148",
        "Client GRANJA BAILON",
        "Machine",
        "NIAGARA",
        "Serial X/3148/5B",
        "Date 11/2015",
    ]
)


def test_generic_parser_extracts_non_motor_nameplate():
    fields = {f.field: f.value for f in parse_generic_fields(_POULTRY, base_confidence=0.8)}
    assert "Tecno Poultry Equipment" in (fields.get("manufacturer") or "")
    assert fields.get("model") == "NIAGARA"
    assert fields.get("serial_number") == "X/3148/5B"
    assert fields.get("manufacture_date") == "11/2015"


def test_generic_parser_does_not_invent_motor_fields():
    # A placa nao tem kW/V/A/RPM: nada de campos de motor inventados.
    motor = {f.field for f in parse_nameplate_text(_POULTRY)}
    assert "power_kw" not in motor
    assert "voltage_v" not in motor
    assert "nominal_rpm" not in motor


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 60), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_is_honest_without_engine(monkeypatch):
    # Sem motor de OCR: resultado vazio e sinalizado, NUNCA dados fabricados.
    monkeypatch.setattr(plate_ocr, "get_ocr_engine", lambda: None)
    result = extract_nameplate(_png())
    assert result.engine == "indisponivel"
    assert result.fields == []
    assert result.coverage == 0.0


# --- Caminho IMAGEM -> TEXTO -------------------------------------------------
# O resto do arquivo exercita so o parser, contra strings fixas. A metade que
# quebra na pratica (imagem -> texto) nao tinha teste nenhum: por isso um OCR
# devolvendo zero caracteres passava despercebido ate chegar na tela.

def _dir_amostras() -> Path:
    """Sobe a arvore ate achar assets/nameplates_samples.

    Caminho relativo fixo quebra conforme o teste roda do repo ou de dentro do
    container, onde o backend fica em /app.
    """
    for base in Path(__file__).resolve().parents:
        candidato = base / "assets" / "nameplates_samples"
        if candidato.is_dir():
            return candidato
    return Path(__file__).resolve().parents[2] / "assets" / "nameplates_samples"


_AMOSTRAS = _dir_amostras()


def _placas() -> list[Path]:
    return sorted(_AMOSTRAS.glob("placa_*.png"))


@pytest.mark.skipif(get_ocr_engine() is None, reason="tesseract ausente no ambiente")
def test_ocr_le_as_placas_reais_do_repositorio():
    """As placas versionadas precisam sair com todos os campos principais."""
    assert _placas(), f"nenhuma amostra em {_AMOSTRAS}"
    for caminho in _placas():
        resultado = extract_nameplate(caminho.read_bytes())
        assert resultado.raw_text.strip(), f"{caminho.name}: OCR nao leu nada"
        assert resultado.coverage >= 0.8, f"{caminho.name}: cobertura {resultado.coverage}"
        extraidos = {f.field: f.value for f in resultado.fields if f.value}
        for campo in ("manufacturer", "power_kw", "voltage_v", "nominal_rpm"):
            assert campo in extraidos, f"{caminho.name}: faltou {campo}"


@pytest.mark.skipif(get_ocr_engine() is None, reason="tesseract ausente no ambiente")
def test_fallback_psm6_resgata_placa_degradada():
    """Placa girada demais zera no modo padrao; o fallback ainda le algo.

    Trava a correcao do "cobertura 0%": o PSM 3 (layout de PAGINA) conclui que
    uma placa muito inclinada nao tem bloco de texto valido e devolve ZERO
    palavras. O PSM 6 entra como segunda tentativa. Vale como nao-regressao
    tambem: se alguem trocar o padrao por PSM 6, o teste acima e que cobra.
    """
    engine = get_ocr_engine()
    original = Image.open(_placas()[0])
    girada = original.rotate(12, expand=True, fillcolor=255)
    buffer = io.BytesIO()
    girada.convert("RGB").save(buffer, format="PNG")
    imagem = preprocess_image(buffer.getvalue())

    padrao, _ = engine._read(imagem, config="")
    com_fallback, _ = engine.read_text(imagem)

    assert not padrao.strip(), "amostra deixou de ser um caso de PSM 3 vazio"
    assert com_fallback.strip(), "o fallback PSM 6 nao resgatou a leitura"


def test_ip_tolera_ruido_de_ocr_e_normaliza_o_valor():
    """"1p55" numa placa gravada e IP55 — e precisa ser GRAVADO como IP55.

    Texto real vindo de uma foto de plaqueta metalica: o "I" sai como 1 e o
    "P" minusculo. A regex captura so os digitos para tolerar isso, entao o
    valor passa por um normalizador antes de virar campo do cadastro.
    """
    campos = {
        f.field: f.value
        for f in parse_nameplate_text("e 145 [ict B At soKliom 63 | 1p55]", 0.8)
    }
    assert campos.get("ip_rating") == "IP55"

    # Continua lendo a forma limpa...
    assert {f.field: f.value for f in parse_nameplate_text("IP55", 0.8)}["ip_rating"] == "IP55"
    # ...e nao confunde um ano com grau de protecao.
    assert "ip_rating" not in {f.field for f in parse_nameplate_text("NBR 1955", 0.8)}


def test_ruido_de_ocr_nao_vira_valor_de_campo():
    """Lixo de OCR num campo de texto e PIOR que campo vazio.

    A regex acha o rotulo ("FABRICANTE") e leva junto o que veio depois. Numa
    foto ruim isso produziu 'cria A ico ce velo ENTS INDUSTRIAL S.A: IO' como
    fabricante — e esse valor iria para a coluna do ativo. Quem revisa preenche
    o que falta, mas confia no que ja veio preenchido.
    """
    ruim = "FABRICANTE cria A ico ce velo ENTS INDUSTRIAL S.A: IO\ne cc O proce +"
    campos = {f.field for f in parse_generic_fields(ruim, 0.31)}
    assert "manufacturer" not in campos

    # E o gate nao pode ser cego: rotulo legitimo continua passando.
    bom = "FABRICANTE: WEG MOTORES\nMODELO: W22 IR3"
    extraidos = {f.field: f.value for f in parse_generic_fields(bom, 0.9)}
    assert extraidos.get("manufacturer") == "WEG MOTORES"
    assert extraidos.get("model") == "W22 IR3"
