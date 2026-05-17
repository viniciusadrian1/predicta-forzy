"""Pipeline de treino do detector de anomalias de vibracao.

Autoencoder de reconstrucao (MLP) treinado sobre janelas de vibracao em
operacao normal; o limiar e o percentil 99 do erro de reconstrucao.

Executar:  python ml/pipelines/train_anomaly.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import joblib
import numpy as np
from features import MODELS_DIR, load_dataset, next_version
from sklearn.neural_network import MLPRegressor

WINDOW_SIZE = 32


def _windows(values: np.ndarray, size: int) -> np.ndarray:
    return np.array([values[i : i + size] for i in range(len(values) - size + 1)])


def train() -> dict:
    """Treina o autoencoder de vibracao e devolve os metadados."""
    frame = load_dataset()
    normal = frame[frame["label"] == "normal"]["vibration_velocity_rms"].to_numpy(
        dtype=float
    )
    windows = _windows(normal, WINDOW_SIZE)

    model = MLPRegressor(
        hidden_layer_sizes=(16, 6, 16), max_iter=600, random_state=42
    )
    model.fit(windows, windows)
    errors = np.mean((windows - model.predict(windows)) ** 2, axis=1)
    threshold = float(np.percentile(errors, 99))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    version = next_version(MODELS_DIR, "anomaly")
    artifact = MODELS_DIR / f"anomaly_v{version}.pkl"
    joblib.dump(model, artifact)

    meta = {
        "model": "anomaly_autoencoder_mlp",
        "version": f"v{version}",
        "trained_at": datetime.now(UTC).isoformat(),
        "window_size": WINDOW_SIZE,
        "n_windows": int(len(windows)),
        "reconstruction_threshold": round(threshold, 6),
        "artifact": artifact.name,
    }
    (MODELS_DIR / "anomaly_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


if __name__ == "__main__":
    metadata = train()
    print(
        f"Modelo de anomalia treinado: {metadata['artifact']} "
        f"(limiar={metadata['reconstruction_threshold']})"
    )
