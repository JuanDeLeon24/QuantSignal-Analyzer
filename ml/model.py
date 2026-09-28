"""
Modelo base de QuantSignal AI: estima P(ganar) de una operacion a partir
de sus features + direccion.

- Gradient Boosting (sklearn), tolera valores faltantes.
- Validacion respetando el tiempo: se entrena con el pasado y se evalua
  con el 20% mas reciente (nunca se mezcla futuro en el entrenamiento).
- Reporta metricas globales y SOLO sobre tus operaciones, para saber si
  el modelo sirve para tu forma de operar.
- Cada entrenamiento queda registrado en models/model_history.jsonl.
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd

from config import settings
from ml.features import FEATURE_VERSION, feature_columns

MODEL_FILE = "quantsignal_model.joblib"
HUMAN_SOURCES = ("MANUAL", "LIVE", "IMPORT", "PAPER")

_cache = {"mtime": None, "bundle": None}


def model_features():
    return feature_columns() + ["dir_long"]


def _metrics(y, p, w=None):
    from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
    out = {"n": int(len(y)), "base_rate": round(float(np.mean(y)), 4) if len(y) else None}
    if len(y) == 0:
        return out
    out["accuracy"] = round(float(accuracy_score(y, p >= 0.5)), 4)
    out["brier"] = round(float(brier_score_loss(y, p)), 4)
    if len(set(y)) > 1:
        out["auc"] = round(float(roc_auc_score(y, p)), 4)
    return out


def _psi(expected, actual, bins=10):
    """Population Stability Index: >0.25 = deriva fuerte, 0.1-0.25 moderada."""
    e = pd.Series(expected).dropna()
    a = pd.Series(actual).dropna()
    if len(e) < 50 or len(a) < 20 or e.nunique() < 3:
        return None
    qs = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(qs) < 3:
        return None
    qs[0], qs[-1] = -np.inf, np.inf
    pe = np.histogram(e, qs)[0] / len(e) + 1e-4
    pa = np.histogram(a, qs)[0] / len(a) + 1e-4
    return float(np.sum((pa - pe) * np.log(pa / pe)))


def _reliability(y, p, bins=8):
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df["p"], q=min(bins, max(2, df["p"].nunique())), duplicates="drop")
    g = df.groupby("bin", observed=True)
    return [
        {"p_media": round(float(x["p"].mean()), 4), "frecuencia_real": round(float(x["y"].mean()), 4),
         "n": int(len(x))}
        for _, x in g
    ]


class CalibratedModel:
    """Modelo + calibracion isotonica (las probabilidades significan lo que dicen)."""

    def __init__(self, model, calibrator):
        self.model = model
        self.calibrator = calibrator

    def predict_proba(self, X):
        raw = self.model.predict_proba(X)[:, 1]
        p = self.calibrator.predict(raw) if self.calibrator is not None else raw
        p = np.clip(p, 0.001, 0.999)
        return np.column_stack([1 - p, p])


def _hgb(random_state):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
        l2_regularization=1.0, min_samples_leaf=40,
        early_stopping=True, validation_fraction=0.15, random_state=random_state,
    )


def _fit_calibrated(X, y, w, random_state, calib_fraction=0.2):
    """Entrena con el pasado y calibra con el tramo mas reciente."""
    from sklearn.isotonic import IsotonicRegression
    n = len(X)
    c = int(n * (1 - calib_fraction))
    m = _hgb(random_state).fit(X.iloc[:c], y[:c], sample_weight=w[:c])
    cal = None
    if n - c >= 50 and len(set(y[c:])) > 1:
        cal = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
        cal.fit(m.predict_proba(X.iloc[c:])[:, 1], y[c:], sample_weight=w[c:])
    return CalibratedModel(m, cal)


def train_model(ds, test_fraction=0.2, min_samples=200, save=True, random_state=42, embargo_days=30):
    """
    Validacion temporal con embargo:
      [ entrenamiento | embargo | prueba ]
    Las muestras cuyo resultado se solapa con el inicio de la prueba se
    descartan del entrenamiento (evita fuga de informacion).
    """
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    ds = ds.dropna(subset=["label_win"]).sort_values("time").reset_index(drop=True)
    if len(ds) < min_samples:
        raise ValueError(
            f"Solo hay {len(ds)} muestras; se necesitan al menos {min_samples}. "
            "Incluye datos de mercado o registra mas operaciones."
        )

    feats = model_features()
    X = ds[feats].astype(float)
    y = ds["label_win"].astype(int).values
    w = ds["weight"].astype(float).values

    cut = int(len(ds) * (1 - test_fraction))
    cut_time = ds["time"].iloc[cut]
    train_mask = (ds["time"] < cut_time - pd.Timedelta(days=embargo_days)).values
    test_mask = np.arange(len(ds)) >= cut
    if train_mask.sum() < min_samples // 2:
        train_mask = np.arange(len(ds)) < cut

    Xtr, ytr, wtr = X[train_mask], y[train_mask], w[train_mask]
    Xte, yte = X[test_mask], y[test_mask]
    test = ds[test_mask]

    model = _fit_calibrated(Xtr, ytr, wtr, random_state)
    p_test = model.predict_proba(Xte)[:, 1]

    metrics = {"test_all": _metrics(yte, p_test)}
    for src in sorted(test["source"].unique()):
        m = (test["source"] == src).values
        metrics[f"test_{src}"] = _metrics(yte[m], p_test[m])
    human = test["source"].isin(HUMAN_SOURCES).values
    metrics["test_tus_operaciones"] = _metrics(yte[human], p_test[human])

    # Linea base: regresion logistica. Si el modelo complejo no la supera, sobra.
    try:
        base = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(max_iter=500, C=0.5))
        base.fit(Xtr, ytr, logisticregression__sample_weight=wtr)
        metrics["baseline_logistica"] = _metrics(yte, base.predict_proba(Xte)[:, 1])
    except Exception:  # noqa: BLE001
        pass

    importance = []
    try:
        n = min(len(Xte), 3000)
        pi = permutation_importance(model.model, Xte.iloc[-n:], yte[-n:],
                                    n_repeats=5, random_state=random_state, scoring="roc_auc")
        importance = sorted(
            [{"feature": f, "importance": round(float(v), 5)} for f, v in zip(feats, pi.importances_mean)],
            key=lambda d: d["importance"], reverse=True,
        )
    except Exception:  # noqa: BLE001
        pass

    drift = []
    for f in feats:
        v = _psi(Xtr[f], Xte[f])
        if v is not None:
            drift.append({"feature": f, "psi": round(v, 4)})
    drift.sort(key=lambda d: d["psi"], reverse=True)

    # Modelo final (todos los datos, calibrado con el tramo mas reciente)
    final = _fit_calibrated(X, y, w, random_state)

    card = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "feature_version": FEATURE_VERSION,
        "engine_version": settings.ENGINE_VERSION,
        "rows": int(len(ds)),
        "rows_by_source": ds["source"].value_counts().to_dict(),
        "test_from": str(cut_time),
        "embargo_days": embargo_days,
        "metrics": metrics,
        "reliability": _reliability(yte, p_test),
        "importance": importance[:20],
        "drift_psi": drift[:10],
        "warnings": _warnings(ds, metrics, drift),
    }

    if save:
        import joblib
        settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": final, "features": feats, "card": card},
                    settings.MODELS_DIR / MODEL_FILE)
        with open(settings.MODELS_DIR / "model_history.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(card, ensure_ascii=False, default=str) + "\n")
        (settings.MODELS_DIR / "model_card.json").write_text(
            json.dumps(card, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    return card


def _warnings(ds, metrics, drift=None):
    w = []
    n_human = int(ds["source"].isin(HUMAN_SOURCES).sum())
    if n_human < 30:
        w.append(
            f"Solo {n_human} operaciones tuyas cerradas con features. Con menos de ~30 "
            "el modelo aprende casi solo del mercado simulado; sigue registrando."
        )
    auc = metrics.get("test_all", {}).get("auc")
    if auc is not None and auc < 0.53:
        w.append(
            f"AUC de prueba {auc}: el modelo apenas supera al azar. No lo uses para "
            "decidir; usalo como referencia mientras crece el dataset."
        )
    base = metrics.get("baseline_logistica", {}).get("auc")
    if auc is not None and base is not None and auc <= base:
        w.append(
            f"El modelo (AUC {auc}) no supera a una regresion logistica simple (AUC {base}): "
            "la complejidad no aporta todavia."
        )
    strong = [d["feature"] for d in (drift or []) if d["psi"] > 0.25]
    if strong:
        w.append("Deriva fuerte (PSI>0.25) en: " + ", ".join(strong[:5])
                 + ". El mercado reciente es distinto al de entrenamiento.")
    return w


def load_bundle():
    path = settings.MODELS_DIR / MODEL_FILE
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    if _cache["mtime"] != mtime:
        import joblib
        _cache["bundle"] = joblib.load(path)
        _cache["mtime"] = mtime
    return _cache["bundle"]


def predict_trade(features, direction):
    """P(ganar) para un vector de features. None si no hay modelo o direccion."""
    if direction not in ("LONG", "SHORT"):
        return None
    bundle = load_bundle()
    if bundle is None:
        return None
    if bundle["card"].get("feature_version") != FEATURE_VERSION:
        return None
    row = {f: (features or {}).get(f) for f in bundle["features"]}
    row["dir_long"] = 1.0 if direction == "LONG" else 0.0
    X = pd.DataFrame([row], columns=bundle["features"]).astype(float)
    p = float(bundle["model"].predict_proba(X)[0, 1])
    return {"p_win": round(p, 4), "trained_at": bundle["card"]["trained_at"]}
