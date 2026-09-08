"""Synthetic labelled government crypto assets for training the risk models.

Each row is a plausible asset; the label is a "true" migration priority computed
from a weighting with one deliberate non-linearity — the harvest-now-decrypt-
later kicker: a quantum-vulnerable primitive protecting long-retention data is
disproportionately urgent. The gradient-boosted model learns that interaction,
which is why its feature importances are informative.
"""

from __future__ import annotations

import random

from .features import FEATURES


def generate(n: int = 3000, seed: int = 0) -> tuple[list[list[float]], list[float], list[str]]:
    """Return ``(X, y_priority, y_band)``."""
    rng = random.Random(seed)
    X: list[list[float]] = []
    y_priority: list[float] = []
    y_band: list[str] = []

    for _ in range(n):
        qvs = rng.triangular(0, 100, 80)                 # skewed toward vulnerable
        retention = rng.choice([1, 3, 5, 7, 10, 15, 25, 30, 40])
        exposure = rng.choices([0, 1, 2], weights=[3, 2, 4])[0]
        classification = rng.choices([0, 1, 2, 3], weights=[1, 3, 3, 2])[0]
        effort = rng.triangular(5, 100, 35)
        criticality = min(100, 25 * classification + 20 * exposure + rng.uniform(-15, 15))
        criticality = max(0, criticality)
        deps = rng.randint(0, 25)

        priority = (
            0.42 * qvs
            + 0.22 * min(retention, 30) / 30 * 100
            + 0.12 * exposure * 50
            + 0.10 * classification * 33
            + 0.08 * criticality
            - 0.15 * effort
            + 0.04 * deps
        )
        # harvest-now-decrypt-later interaction
        if qvs > 65 and retention >= 15:
            priority += 18
        if qvs > 90:                                     # already broken -> do now
            priority += 10
        priority = max(0.0, min(100.0, priority + rng.gauss(0, 4)))

        X.append([qvs, retention, exposure, classification, effort, criticality, deps])
        y_priority.append(round(priority, 2))
        y_band.append("High" if priority >= 66 else "Medium" if priority >= 38 else "Low")

    assert len(X[0]) == len(FEATURES)
    return X, y_priority, y_band
