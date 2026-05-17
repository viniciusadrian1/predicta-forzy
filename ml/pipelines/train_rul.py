"""Pipeline de treino do estimador de RUL (vida util remanescente).

Regressao linear da tendencia de vibracao; o RUL e a extrapolacao ate o
limite de fim de vida da DIN ISO 10816/20816 (7,1 mm/s). Privilegia
explicabilidade sobre complexidade.

Executar:  python ml/pipelines/train_rul.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import joblib
import numpy as np
from features import MODELS_DIR, load_dataset, next_version
from sklearn.linear_model import LinearRegression

VIBRATION_FAILURE_THRESHOLD = 7.1


def train() -> dict:
    """Ajusta a regressao da tendencia de vibracao e devolve os metadados."""
    frame = load_dataset()
    seconds = (frame["time"] - frame["time"].iloc[0]).dt.total_seconds()
    features = seconds.to_numpy(dtype=float).reshape(-1, 1)
    target = frame["vibration_velocity_rms"].to_numpy(dtype=float)

    model = LinearRegression().fit(features, target)
    slope_per_day = float(model.coef_[0]) * 86400.0
    current = float(target[-1])
    rul_days = (
        (VIBRATION_FAILURE_THRESHOLD - current) / slope_per_day
        if slope_per_day > 0
        else None
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    version = next_version(MODELS_DIR, "rul")
    artifact = MODELS_DIR / f"rul_v{version}.pkl"
    joblib.dump(model, artifact)

    meta = {
        "model": "rul_linear_regression",
        "version": f"v{version}",
        "trained_at": datetime.now(UTC).isoformat(),
        "n_samples": int(len(target)),
        "trend_mm_s_per_day": round(slope_per_day, 6),
        "current_vibration": round(current, 4),
        "rul_days": round(rul_days, 1) if rul_days is not None else None,
        "failure_threshold_mm_s": VIBRATION_FAILURE_THRESHOLD,
        "artifact": artifact.name,
    }
    (MODELS_DIR / "rul_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


if __name__ == "__main__":
    metadata = train()
    print(f"Modelo de RUL treinado: {metadata['artifact']} (RUL={metadata['rul_days']} dias)")
