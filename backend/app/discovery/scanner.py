"""Walk an estate, run every detector, classify every finding, return a CBOM.

This is the orchestration layer and nothing more: the interesting decisions are
in :mod:`.detectors` (what counts as evidence) and :mod:`.classify` (what the
evidence means). :func:`scan_estate` is deterministic — the same tree always
produces the same CBOM, asset for asset, so two scans can be diffed.
"""

from __future__ import annotations

from pathlib import Path

from ..config import estate_root
from .cbom import CBOM, SEVERITY, CryptoAsset
from .classify import classify
from .dataclass import classify_location, detector_confidence
from .detectors import DEFAULT_DETECTORS, Detector

# Directories that never contain estate cryptography worth reporting.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".tox",
}
_MAX_BYTES = 2 * 1024 * 1024  # skip anything larger; crypto evidence is small


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > _MAX_BYTES:
                continue
        except OSError:
            continue
        yield path


def scan_estate(
    root: Path | None = None,
    detectors: tuple[Detector, ...] = DEFAULT_DETECTORS,
) -> CBOM:
    """Scan ``root`` (default: :func:`app.config.estate_root`) into a CBOM."""
    base = (root or estate_root()).resolve()
    assets: list[CryptoAsset] = []

    for path in _iter_files(base):
        rel = path.relative_to(base).as_posix()
        applicable = [d for d in detectors if d.applies(path)]
        if not applicable:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for detector in applicable:
            for finding in detector.scan(path, text):
                exposure, rationale, recommendation = classify(
                    finding.primitive, finding.key_bits
                )
                location = f"{rel}:{finding.line}" if finding.line else rel
                _dc, _ret, _net = classify_location(location)
                assets.append(
                    CryptoAsset(
                        kind=finding.kind,
                        primitive=finding.primitive,
                        detail=finding.detail,
                        key_bits=finding.key_bits,
                        location=location,
                        evidence=finding.evidence,
                        detector=detector.name,
                        exposure=exposure,
                        rationale=rationale,
                        recommendation=recommendation,
                        data_classification=_dc,
                        data_retention_years=_ret,
                        network_exposure=_net,
                        confidence=detector_confidence(detector.name),
                    )
                )

    # De-duplicate identical findings (same asset_id) and order most-urgent
    # first, then by location, so the report and any diff are stable.
    unique = {a.asset_id: a for a in assets}
    ordered = sorted(
        unique.values(),
        key=lambda a: (SEVERITY[a.exposure], a.location, a.primitive, a.detail),
    )
    return CBOM(estate_root=str(base), assets=tuple(ordered))
