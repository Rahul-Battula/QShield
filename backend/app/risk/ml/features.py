"""The feature schema shared by training, prediction and explanation."""

from __future__ import annotations

FEATURES = [
    "quantum_vulnerability_score",   # 0-100, from threat_score
    "data_retention_years",          # the Mosca X
    "network_exposure",              # 0 internal, 1 partner, 2 public_internet
    "data_classification",           # 0 public .. 3 secret
    "migration_effort",              # 0-100, higher = harder
    "service_criticality",           # 0-100
    "dependency_count",              # how many services call this one
]

_EXPOSURE_ORD = {"internal": 0, "partner": 1, "public_internet": 2}
_CLASS_ORD = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}


def to_vector(row: dict) -> list[float]:
    """Ordered feature vector from a feature dict (ordinals already numeric are
    passed through)."""
    def num(key, mapping=None):
        v = row.get(key, 0)
        if mapping and isinstance(v, str):
            return float(mapping.get(v, 0))
        return float(v)

    return [
        num("quantum_vulnerability_score"),
        num("data_retention_years"),
        num("network_exposure", _EXPOSURE_ORD),
        num("data_classification", _CLASS_ORD),
        num("migration_effort"),
        num("service_criticality"),
        num("dependency_count"),
    ]


def exposure_ordinal(name: str) -> int:
    return _EXPOSURE_ORD.get(name, 0)


def classification_ordinal(name: str) -> int:
    return _CLASS_ORD.get(name, 1)
