"""Treina os modelos PRONTOS do Predicta (offline) e os versiona no repositorio.

Substitui o retreino em memoria (sob demanda) por artefatos validados que o
serving carrega direto. Gera duas coisas:

1. BASELINE DE ANOMALIA por motor fisico (MTR-F01 / MTR-F02), treinado no dado
   REAL da Forzy (IO-Link, ``data/history_forzy_iolink.csv``). Mesma estrutura
   (``ModelBundle``) que o runtime ja consome -> vira ``artifacts/<tag>.joblib``.

2. CLASSIFICADOR DE TIPO DE FALHA, treinado no dado SINTETICO rotulado
   (``ml/data/raw/telemetry_history.csv``), usando SOMENTE features de vibracao
   + temperatura (as unicas que os motores reais possuem). Ainda NAO e ligado no
   serving: o objetivo aqui e medir as metricas e decidir depois.

Uso (a partir de ``backend/``)::

    python -m app.scripts.train_shipped_models

Observacao de compatibilidade: o ``.joblib`` e um pickle de estimadores sklearn;
a versao de scikit-learn do container tem de casar com a do treino (ver o pin em
pyproject). O loader do serving cai no retreino se a desserializacao falhar.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split

from app.modules.ml.service import (
    ARTIFACTS_DIR,
    VIBRATION_VARIABLE,
    fit_bundle,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
REAL_CSV = BACKEND_DIR / "data" / "history_forzy_iolink.csv"
SYNTHETIC_CSV = BACKEND_DIR.parent / "ml" / "data" / "raw" / "telemetry_history.csv"

# Mapeamento Porta IO-Link -> ativo (mesmo do import_history: P1=M1=F01, P2=F02).
# (col_velocidade, col_aceleracao, col_temperatura) 0-based na linha do CSV real.
REAL_MOTORS: dict[str, tuple[int, int, int]] = {
    "MTR-F01": (3, 4, 5),
    "MTR-F02": (6, 7, 8),
}
ROLL_WINDOW = 15  # janela das estatisticas moveis do classificador


def _rule(char: str = "-") -> str:
    return char * 68


# --------------------------------------------------------------------------- #
# 1) BASELINE DE ANOMALIA (dado real, por motor)
# --------------------------------------------------------------------------- #
def _load_real_motor(tag: str, cols: tuple[int, int, int]) -> pd.DataFrame:
    """Le o CSV IO-Link real e devolve o wide canonico de UM motor."""
    vel, accel, temp = cols
    raw = pd.read_csv(REAL_CSV, sep=";", skiprows=3, header=None, decimal=".")
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(raw[0], format="ISO8601", errors="coerce"),
            "Temperatura": pd.to_numeric(raw[temp], errors="coerce"),
            "Vibracao_Velocidade_RMS": pd.to_numeric(raw[vel], errors="coerce"),
            "Vibracao_Aceleracao_RMS": pd.to_numeric(raw[accel], errors="coerce"),
        }
    )
    frame = frame.dropna().set_index("time").sort_index()
    return frame


def train_real_baselines() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    print(_rule("="))
    print("1) BASELINE DE ANOMALIA — dado REAL Forzy (IO-Link)")
    print(_rule("="))
    for tag, cols in REAL_MOTORS.items():
        wide = _load_real_motor(tag, cols)
        available = [
            c
            for c in ("Temperatura", "Vibracao_Velocidade_RMS", "Vibracao_Aceleracao_RMS")
            if c in wide.columns
        ]
        bundle = fit_bundle(wide, available)
        out = ARTIFACTS_DIR / f"{tag}.joblib"
        joblib.dump(bundle, out)

        # Validacao possivel: o dado real e todo operacao (sem falha rotulada),
        # entao a metrica honesta e a TAXA DE FALSO ALARME (o quanto o baseline
        # marca "anomalo" no proprio normal). Recall em falha real fica sem medir.
        feats = wide[available].to_numpy(dtype=float)
        flagged = int((bundle.baseline.predict(feats) == -1).sum())
        rate = 100.0 * flagged / len(feats)
        vib = wide[VIBRATION_VARIABLE]
        print(f"\n[{tag}]  {len(wide)} amostras  |  versao {bundle.version}")
        print(f"  features: {', '.join(available)}")
        print(
            f"  vibracao real: min {vib.min():.2f}  mediana {vib.median():.2f}  "
            f"p95 {vib.quantile(0.95):.2f}  max {vib.max():.2f} mm/s"
        )
        print(f"  autoencoder: limiar de reconstrucao {bundle.anomaly_threshold:.5f}")
        print(f"  FALSO ALARME (baseline marca anomalo no proprio normal): {rate:.1f}%")
        print(f"  -> salvo em {out.relative_to(BACKEND_DIR.parent)}")
    print(
        "\n  Nota: sem falha rotulada no dado real, so da pra medir falso alarme."
        "\n  Recall (pegar falha de verdade) fica sem validacao ate haver dado"
        "\n  run-to-failure real."
    )


# --------------------------------------------------------------------------- #
# 2) CLASSIFICADOR DE TIPO DE FALHA (dado sintetico rotulado)
# --------------------------------------------------------------------------- #
def _build_fault_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Features SO de vibracao + temperatura (deployaveis nos motores reais)."""
    base = {
        "vel": frame["vibration_velocity_rms"],
        "accel": frame["vibration_acceleration_rms"],
        "temp": frame["temperature_c"],
    }
    feats = pd.DataFrame(index=frame.index)
    for name, series in base.items():
        feats[name] = series
        feats[f"{name}_mean"] = series.rolling(ROLL_WINDOW, min_periods=1).mean()
        feats[f"{name}_std"] = series.rolling(ROLL_WINDOW, min_periods=1).std().fillna(0.0)
    feats["vel_roc"] = base["vel"].diff().abs().fillna(0.0)
    return feats.fillna(0.0)


def train_fault_classifier() -> dict:
    print("\n" + _rule("="))
    print("2) CLASSIFICADOR DE TIPO DE FALHA — dado SINTETICO rotulado")
    print(_rule("="))
    frame = pd.read_csv(SYNTHETIC_CSV).sort_values("time").reset_index(drop=True)
    features = _build_fault_features(frame)
    labels = frame["label"].to_numpy()

    print("\n  distribuicao das classes:")
    for cls, n in frame["label"].value_counts().items():
        print(f"    {cls:<14} {n:>7}  ({100.0 * n / len(frame):.1f}%)")

    x_train, x_test, y_train, y_test = train_test_split(
        features.to_numpy(dtype=float),
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(x_train, y_train)
    pred = clf.predict(x_test)

    report = classification_report(y_test, pred, digits=3, zero_division=0)
    report_dict = classification_report(y_test, pred, output_dict=True, zero_division=0)
    macro_f1 = f1_score(y_test, pred, average="macro")
    bal_acc = balanced_accuracy_score(y_test, pred)
    labels_sorted = sorted(set(labels))
    cm = confusion_matrix(y_test, pred, labels=labels_sorted)

    print("\n  --- metricas (holdout 20%, estratificado) ---")
    print("  " + report.replace("\n", "\n  "))
    print(f"  F1 macro: {macro_f1:.3f}   |   acuracia balanceada: {bal_acc:.3f}")
    print("\n  matriz de confusao (linha=real, coluna=previsto):")
    print("            " + "  ".join(f"{c[:8]:>8}" for c in labels_sorted))
    for name, row in zip(labels_sorted, cm):
        print(f"    {name[:8]:>8}  " + "  ".join(f"{v:>8}" for v in row))

    importances = sorted(
        zip(features.columns, clf.feature_importances_), key=lambda kv: kv[1], reverse=True
    )
    print("\n  top features:")
    for name, imp in importances[:6]:
        print(f"    {name:<12} {imp:.3f}")

    # Salva o artefato + metricas, mas NAO liga no serving (decisao pendente).
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    clf_path = ARTIFACTS_DIR / "fault_classifier.joblib"
    joblib.dump(
        {"model": clf, "features": list(features.columns), "classes": labels_sorted},
        clf_path,
    )
    metrics = {
        "report": report_dict,
        "macro_f1": macro_f1,
        "balanced_accuracy": bal_acc,
        "classes": labels_sorted,
    }
    (ARTIFACTS_DIR / "fault_classifier_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(f"\n  -> classificador salvo em {clf_path.relative_to(BACKEND_DIR.parent)} (NAO ligado)")
    print(
        "\n  ATENCAO — honestidade: treinado em dado SINTETICO. As metricas acima"
        "\n  sao in-distribution. A escala de vibracao do sintetico difere da real"
        "\n  (sintetico normal ~1.7 mm/s; real varia 0.03–7.7), entao a transferencia"
        "\n  para os motores reais NAO esta validada. Decidir a integracao a partir"
        "\n  disto."
    )
    return metrics


def main() -> None:
    train_real_baselines()
    train_fault_classifier()
    print("\n" + _rule("="))
    print("Concluido. Baseline (F01/F02) pronto para subir; classificador aguardando decisao.")
    print(_rule("="))


if __name__ == "__main__":
    main()
