"""Testes do modulo de visao: parser de placas de identificacao."""

import io

from PIL import Image

from app.modules.vision import plate_ocr
from app.modules.vision.plate_ocr import (
    EXPECTED_FIELDS,
    extract_nameplate,
    parse_generic_fields,
    parse_nameplate_text,
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
