"""Testes do modulo de visao: parser de placas de identificacao."""

from app.modules.vision.plate_ocr import EXPECTED_FIELDS, parse_nameplate_text

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
