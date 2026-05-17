"""Pipeline de treino do modelo de baseline de operacao (Isolation Forest).

Treina apenas com dados de operacao normal e versiona o artefato em
ml/models/baseline_v{N}.pkl, com metadados em baseline_meta.json.

Executar:  python ml/pipelines/train_baseline.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import joblib
from features import MODELS_DIR, build_features, load_dataset, next_version
from sklearn.ensemble import IsolationForest


def train() -> dict:
    """Treina o Isolation Forest e devolve os metadados do artefato."""
    frame = load_dataset()
    normal = frame[frame["label"] == "normal"]
    features = build_features(normal)

    model = IsolationForest(n_estimators=200, contamination=0.03, random_state=42)
    model.fit(features.to_numpy(dtype=float))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    version = next_version(MODELS_DIR, "baseline")
    artifact = MODELS_DIR / f"baseline_v{version}.pkl"
    joblib.dump(model, artifact)

    meta = {
        "model": "baseline_isolation_forest",
        "version": f"v{version}",
        "trained_at": datetime.now(UTC).isoformat(),
        "n_samples": int(len(features)),
        "n_features": int(features.shape[1]),
        "features": list(features.columns),
        "artifact": artifact.name,
    }
    (MODELS_DIR / "baseline_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


if __name__ == "__main__":
    metadata = train()
    print(f"Modelo baseline treinado: {metadata['artifact']} ({metadata['n_samples']} amostras)")
