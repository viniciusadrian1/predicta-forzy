"""Testes do simulador de demo: parser de replay real + modelo fisico."""

from app.modules.telemetry.demo_sim import load_replay_frames
from app.modules.telemetry.motor_model import MotorModel


def test_load_replay_frames_maps_both_motors(tmp_path):
    # 3 linhas de cabecalho + 1 linha de dado (layout do CSV IO-Link da Forzy).
    csv = tmp_path / "hist.csv"
    csv.write_text(
        "h1\nh2\nh3\n2026-05-19T11:46:10.921;b;b;0.04;0;27;6.5;0.1;45\n",
        encoding="utf-8",
    )
    frames = load_replay_frames(str(csv))
    assert len(frames) == 1
    frame = frames[0]
    assert frame["MTR-F01"] == {
        "Vibracao_Velocidade_RMS": 0.04,
        "Vibracao_Aceleracao_RMS": 0.0,
        "Temperatura": 27.0,
    }
    assert frame["MTR-F02"]["Vibracao_Velocidade_RMS"] == 6.5
    assert frame["MTR-F02"]["Temperatura"] == 45.0


def test_load_replay_frames_missing_file_is_empty():
    assert load_replay_frames("nao/existe.csv") == []


def test_motor_model_stays_in_physical_range():
    # Apos aquecer, as leituras devem cair em faixas plausiveis do motor WEG.
    model = MotorModel()
    reading = None
    for _ in range(30):
        reading = model.step(12.0, 0.75)
    assert 210 < reading.voltage_v < 230
    assert 0 < reading.current_a < 30
    assert 1700 < reading.rotation_rpm < 1800
    assert 25 < reading.temperature_c < 90
    assert 0 < reading.vibration_velocity_rms < 5
    assert 0 <= reading.vibration_acceleration_rms < 2
