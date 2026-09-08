"""Adapter: a Phase 2 CBOM -> feature rows -> the scikit-learn risk models.

Keeps :mod:`app.risk.ml` free of any QShield-specific types — it takes and
returns plain dicts — and puts the "where do the features come from" logic here.
"""

from __future__ import annotations

import hashlib

from ..discovery.cbom import CBOM, CryptoAsset
from ..threat.engine import quantum_vulnerability_score
from .migration_cost import estimate_migration_years
from .ml import explain as _ml_explain
from .ml import rank as _ml_rank

_LIVE_SUITES = {"hybrid", "pqc", "pqc-high", "classical", "classical-ecdh"}

_CLASS_ORD = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}
_EXPO_ORD = {"internal": 0, "partner": 1, "public_internet": 2}


def _dependency_count(location: str) -> int:
    """Deterministic 0–24 stand-in for a real service-dependency graph."""
    return hashlib.sha256(location.encode()).digest()[0] % 25


def _criticality(asset: CryptoAsset) -> float:
    c = _CLASS_ORD.get(asset.data_classification, 1)
    e = _EXPO_ORD.get(asset.network_exposure, 0)
    return round(min(100.0, 22 * c + 18 * e + 10), 1)


def features_for(asset: CryptoAsset) -> dict:
    """The feature row for one CBOM asset."""
    years, _ = estimate_migration_years(asset, _LIVE_SUITES)
    return {
        "asset_id": asset.asset_id,
        "detail": asset.detail,
        "primitive": asset.primitive,
        "location": asset.location,
        "exposure": asset.exposure.value,
        "quantum_vulnerability_score": quantum_vulnerability_score(asset),
        "data_retention_years": asset.data_retention_years,
        "data_classification": asset.data_classification,
        "network_exposure": asset.network_exposure,
        "migration_effort": round(min(100.0, years * 18), 1),
        "service_criticality": _criticality(asset),
        "dependency_count": _dependency_count(asset.location),
    }


def rank_cbom(cbom: CBOM) -> list[dict]:
    """Every asset ranked by the model's predicted migration priority."""
    return _ml_rank([features_for(a) for a in cbom.assets])


def explain_asset(cbom: CBOM, asset_id: str) -> dict | None:
    """Full feature contribution breakdown for one asset id."""
    for a in cbom.assets:
        if a.asset_id == asset_id:
            row = features_for(a)
            return {**row, **_ml_explain(row)}
    return None
