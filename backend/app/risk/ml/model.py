"""Train, persist, and apply the two risk models.

* ``GradientBoostingRegressor`` — a 0–100 migration priority score.
* ``RandomForestClassifier`` — a High / Medium / Low band.

Both are trained on :mod:`.synthetic` data with a fixed seed and cached to
``_models/`` via joblib; the first call that needs them trains them (~1 s), so
there are no binary blobs in the repo. :func:`explain` gives a per-asset
breakdown: which features pushed this asset up or down, weighted by the model's
own feature importances.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import joblib
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import train_test_split

from .features import FEATURES, to_vector
from .synthetic import generate

_MODEL_DIR = Path(__file__).parent / "_models"
_BUNDLE = _MODEL_DIR / "risk_models.joblib"
_SEED = 20260907

_cache: dict | None = None


def train(seed: int = _SEED, n: int = 3000) -> dict:
    """Fit both models, persist them, and return training metrics."""
    X, y_pri, y_band = generate(n, seed)
    Xtr, Xte, ptr, pte, btr, bte = train_test_split(
        X, y_pri, y_band, test_size=0.2, random_state=seed
    )

    reg = GradientBoostingRegressor(random_state=seed, n_estimators=200, max_depth=3)
    reg.fit(Xtr, ptr)
    clf = RandomForestClassifier(random_state=seed, n_estimators=200)
    clf.fit(Xtr, btr)

    means = [statistics.fmean(col) for col in zip(*X, strict=True)]
    stds = [statistics.pstdev(col) or 1.0 for col in zip(*X, strict=True)]

    bundle = {
        "reg": reg, "clf": clf, "features": FEATURES,
        "means": means, "stds": stds,
        "reg_importances": list(reg.feature_importances_),
        "clf_importances": list(clf.feature_importances_),
        "metrics": {
            "regressor_r2": round(r2_score(pte, reg.predict(Xte)), 3),
            "classifier_accuracy": round(accuracy_score(bte, clf.predict(Xte)), 3),
            "n_train": len(Xtr),
        },
    }
    _MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, _BUNDLE)
    global _cache
    _cache = bundle
    return {"metrics": bundle["metrics"],
            "feature_importances": dict(zip(FEATURES, bundle["reg_importances"], strict=True))}


def _bundle() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if _BUNDLE.exists():
        _cache = joblib.load(_BUNDLE)
        return _cache
    train()
    return _cache


def feature_importances() -> dict:
    b = _bundle()
    return {
        "regressor": dict(zip(FEATURES, [round(x, 4) for x in b["reg_importances"]], strict=True)),
        "classifier": dict(zip(FEATURES, [round(x, 4) for x in b["clf_importances"]], strict=True)),
        "metrics": b["metrics"],
    }


def _predict_one(row: dict) -> tuple[float, str]:
    b = _bundle()
    x = to_vector(row)
    score = float(b["reg"].predict([x])[0])
    band = str(b["clf"].predict([x])[0])
    return max(0.0, min(100.0, score)), band


def explain(row: dict) -> dict:
    """Score + band + per-feature contributions for one asset."""
    b = _bundle()
    x = to_vector(row)
    score, band = _predict_one(row)
    contribs = []
    for name, val, mean, std, imp in zip(
        FEATURES, x, b["means"], b["stds"], b["reg_importances"], strict=True
    ):
        z = (val - mean) / std
        contribs.append({
            "feature": name,
            "value": round(val, 2),
            "importance": round(imp, 4),
            # signed pull: above-average value on an important feature raises the score
            "contribution": round(z * imp * 100, 2),
        })
    contribs.sort(key=lambda c: abs(c["contribution"]), reverse=True)
    top = contribs[:3]
    summary = _summarise(band, top)
    return {"score": round(score, 1), "band": band,
            "contributions": contribs, "summary": summary}


def _summarise(band: str, top: list[dict]) -> str:
    parts = []
    for c in top:
        direction = "raises" if c["contribution"] > 0 else "lowers"
        parts.append(f"{c['feature'].replace('_', ' ')} ({c['value']:g}) {direction} it")
    return f"{band} priority — " + "; ".join(parts) + "."


def rank(assets: list[dict]) -> list[dict]:
    """Return ``assets`` ranked by predicted priority, each annotated with
    score, band and a one-line explanation."""
    out = []
    for a in assets:
        e = explain(a)
        out.append({**a, "priority_score": e["score"], "priority_band": e["band"],
                    "explanation": e["summary"]})
    out.sort(key=lambda r: r["priority_score"], reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out
