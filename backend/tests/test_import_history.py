"""Testes do importador do dataset real IO-Link (parsing puro)."""

from app.scripts.import_history import MOTOR_COLUMNS, parse_row


def test_parse_row_maps_both_motors():
    row = ["2026-05-19T11:46:10.921", "bytes1", "bytes2", "0.04", "0", "27", "6.5", "0.1", "45"]
    samples = parse_row(row, MOTOR_COLUMNS)
    assert len(samples) == 6
    by = {(s["asset_tag"], s["variable"]): s["value"] for s in samples}
    assert by[("MTR-F01", "Vibracao_Velocidade_RMS")] == 0.04
    assert by[("MTR-F01", "Temperatura")] == 27
    assert by[("MTR-F02", "Vibracao_Velocidade_RMS")] == 6.5
    assert by[("MTR-F02", "Temperatura")] == 45


def test_parse_row_skips_header_and_blank():
    assert parse_row([], MOTOR_COLUMNS) == []
    assert parse_row(["", "x"], MOTOR_COLUMNS) == []  # sem timestamp
    assert parse_row(["Byte[]", "a", "b"], MOTOR_COLUMNS) == []  # cabecalho
