"""Feature engineering compartilhada pelos pipelines de ML offline.

Le o dataset historico (formato wide) e constroi a matriz de features:
valores instantaneos, estatisticas em janela movel, taxa de variacao e uma
feature espectral (FFT) sobre a serie de vibracao.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SENSOR_COLUMNS = [
    "voltage_v",
    "current_a",
    "temperature_c",
    "rotation_rpm",
    "vibration_velocity_rms",
    "vibration_acceleration_rms",
]

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "telemetry_history.csv"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def load_dataset(path: Path = DATA_PATH) -> pd.DataFrame:
    """Carrega o dataset historico ordenado por tempo."""
    frame = pd.read_csv(path, parse_dates=["time"])
    return frame.sort_values("time").reset_index(drop=True)


def _spectral_feature(series: pd.Series, window: int = 64) -> pd.Series:
    """Razao de energia de alta frequencia em cada janela (via FFT)."""
    values = series.to_numpy(dtype=float)
    output = np.zeros(len(values))
    for index in range(window, len(values)):
        segment = values[index - window : index]
        spectrum = np.abs(np.fft.rfft(segment - segment.mean()))
        total = float(spectrum.sum())
        if total > 0:
            output[index] = float(spectrum[len(spectrum) // 2 :].sum()) / total
    return pd.Series(output, index=series.index)


def build_features(frame: pd.DataFrame, window: int = 15) -> pd.DataFrame:
    """Constroi a matriz de features a partir do dataframe de telemetria."""
    features = pd.DataFrame(index=frame.index)
    for column in SENSOR_COLUMNS:
        features[column] = frame[column]
        features[f"{column}_mean"] = frame[column].rolling(window, min_periods=1).mean()
        features[f"{column}_std"] = (
            frame[column].rolling(window, min_periods=1).std().fillna(0.0)
        )
    features["vibration_roc"] = (
        frame["vibration_velocity_rms"].diff().abs().fillna(0.0)
    )
    features["vibration_spectral"] = _spectral_feature(
        frame["vibration_velocity_rms"]
    )
    return features.fillna(0.0)


def next_version(models_dir: Path, prefix: str) -> int:
    """Calcula a proxima versao para um artefato ``<prefix>_v<N>.pkl``."""
    existing = list(models_dir.glob(f"{prefix}_v*.pkl"))
    versions = []
    for path in existing:
        stem = path.stem.replace(f"{prefix}_v", "")
        if stem.isdigit():
            versions.append(int(stem))
    return (max(versions) + 1) if versions else 1
