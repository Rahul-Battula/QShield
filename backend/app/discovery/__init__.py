"""QShield Phase 2 — cryptographic discovery.

Produces a CBOM (Cryptographic Bill of Materials): an inventory of every place
an estate uses cryptography, each entry classified by its exposure to a
classical or quantum attacker.

    from app.discovery import scan_estate, render

    cbom = scan_estate()                  # scans the bundled mock estate
    print(render(cbom, "markdown"))
    print(cbom.summary())

Phase 3 reads ``cbom.to_dict()`` to prioritise the migration; Phase 5 acts on it.
"""

from __future__ import annotations

from .cbom import CBOM, AssetKind, CryptoAsset, Exposure
from .classify import classify
from .detectors import DEFAULT_DETECTORS, Detector, RawFinding
from .report import render, render_markdown, render_table
from .scanner import scan_estate

__all__ = [
    "CBOM",
    "DEFAULT_DETECTORS",
    "AssetKind",
    "CryptoAsset",
    "Detector",
    "Exposure",
    "RawFinding",
    "classify",
    "render",
    "render_markdown",
    "render_table",
    "scan_estate",
]
