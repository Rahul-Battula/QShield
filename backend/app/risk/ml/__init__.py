"""Scikit-learn risk prioritisation for QShield.

    from app.risk.ml import rank, explain, feature_importances

A ``GradientBoostingRegressor`` scores migration priority 0–100 and a
``RandomForestClassifier`` bands it High / Medium / Low, both trained on
synthetic government crypto assets (:mod:`.synthetic`). Models train on first
use and cache to ``_models/``.
"""

from __future__ import annotations

from .features import FEATURES
from .model import explain, feature_importances, rank, train

__all__ = ["FEATURES", "explain", "feature_importances", "rank", "train"]
