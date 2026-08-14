"""Testes da ingestao dos sensores fisicos Forzy (API HTTP externa)."""

from app.modules.telemetry.external import extract_readings, parse_targets


def test_parse_targets():
    targets = parse_targets("MTR-F01:/get_s1,MTR-F02:/get_s2")
    assert targets == [("MTR-F01", "/get_s1"), ("MTR-F02", "/get_s2")]


def test_parse_targets_ignores_malformed_entries():
    assert parse_targets("sem-endpoint, :/x, MTR-F01:/get_s1,") == [("MTR-F01", "/get_s1")]


def test_extract_readings_maps_forzy_payload():
    payload = {"dados1": {"Velocidade": 0.06, "Aceleração": 0.0, "Temperatura": 33}}
    readings = extract_readings(payload)
    assert readings == {
        "Vibracao_Velocidade_RMS": 0.06,
        "Vibracao_Aceleracao_RMS": 0.0,
        "Temperatura": 33.0,
    }


def test_extract_readings_tolerates_unaccented_and_unknown_fields():
    payload = {"dados2": {"Aceleracao": 0.5, "Pressao": 10, "Temperatura": "34"}}
    readings = extract_readings(payload)
    assert readings == {"Vibracao_Aceleracao_RMS": 0.5, "Temperatura": 34.0}


def test_extract_readings_handles_garbage():
    assert extract_readings(None) == {}
    assert extract_readings({}) == {}
    assert extract_readings({"dados1": "nao-e-dict"}) == {}
    assert extract_readings({"dados1": {"Velocidade": "x"}}) == {}
