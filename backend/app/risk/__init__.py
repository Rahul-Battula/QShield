"""QShield Phase 3 — risk prioritisation.

Takes the Phase 2 CBOM and answers "what do we migrate first?" using Mosca's
inequality (X + Y > Z), a blended 0–100 risk score, and a clustering of the
findings into migration work packages.

    from app.discovery import scan_estate
    from app.risk import prioritise, render

    report = prioritise(scan_estate())
    print(render(report, "markdown"))

The CRQC horizon, per-subsystem data shelf lives and assessment year come from
the ``mosca`` block of ``policy.yaml``.
"""

from __future__ import annotations

from .clustering import WorkPackage, build_work_packages
from .migration_cost import estimate_migration_years
from .mosca import MoscaAssessment, assess
from .prioritise import RiskReport, prioritise
from .report import render, render_markdown, render_table
from .scoring import PriorityBand, RiskScore, score_asset, time_pressure
from .shelflife import estimate_shelf_life

__all__ = [
    "MoscaAssessment",
    "PriorityBand",
    "RiskReport",
    "RiskScore",
    "WorkPackage",
    "assess",
    "build_work_packages",
    "estimate_migration_years",
    "estimate_shelf_life",
    "prioritise",
    "render",
    "render_markdown",
    "render_table",
    "score_asset",
    "time_pressure",
]
