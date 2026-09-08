"""Phase 3 entry point: a CBOM in, a ranked migration plan out.

    from app.discovery import scan_estate
    from app.risk import prioritise

    report = prioritise(scan_estate())
    print(report.summary())
    for rs in report.scores[:10]:
        print(rs.band.value, rs.score, rs.asset.detail, rs.asset.location)

``prioritise`` reads the ``mosca`` block of ``policy.yaml`` for the CRQC
horizon, the data-class shelf lives and the assessment year. Quantum-safe
findings are scored (so the picture is complete) but kept out of the work
packages, which are the actionable backlog.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..agility.policy import Policy, load_policy
from ..discovery.cbom import CBOM, Exposure
from .clustering import WorkPackage, build_work_packages
from .migration_cost import estimate_migration_years
from .mosca import assess, resolve_assessment_year
from .scoring import PriorityBand, RiskScore, score_asset
from .shelflife import estimate_shelf_life

# Suites QShield ships that run live on every platform (Phase 1). Used only to
# discount migration effort when a finding's recommendation points at one.
_LIVE_SUITES = {"hybrid", "pqc", "pqc-high", "classical", "classical-ecdh"}


@dataclass(frozen=True, slots=True)
class RiskReport:
    """The full Phase 3 output for one estate."""

    estate_root: str
    assessment_year: int
    crqc_year: int
    preset: str
    scores: tuple[RiskScore, ...]
    work_packages: tuple[WorkPackage, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    def band_counts(self) -> dict[str, int]:
        c = Counter(s.band.value for s in self.scores)
        return {b.value: c.get(b.value, 0) for b in PriorityBand}

    def too_late(self) -> list[RiskScore]:
        return [s for s in self.scores if s.mosca.is_too_late
                and s.asset.exposure is not Exposure.QUANTUM_SAFE]

    def summary(self) -> dict:
        return {
            "assets_scored": len(self.scores),
            "work_packages": len(self.work_packages),
            "bands": self.band_counts(),
            "too_late": len(self.too_late()),
            "assessment_year": self.assessment_year,
            "crqc_year": self.crqc_year,
            "preset": self.preset,
        }

    def to_dict(self) -> dict:
        return {
            "estate_root": self.estate_root,
            "generated_at": self.generated_at,
            "summary": self.summary(),
            "scores": [s.to_dict() for s in self.scores],
            "work_packages": [wp.to_dict() for wp in self.work_packages],
        }

    def to_json(self, *, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent)


def _blast_radii(cbom: CBOM) -> dict[tuple[str, str], int]:
    """Count assets per (subsystem, primitive): fixing one usually fixes all."""
    counts: Counter[tuple[str, str]] = Counter()
    for a in cbom.assets:
        system = a.location.split("/", 1)[0].split(":", 1)[0]
        counts[(system, a.primitive)] += 1
    return dict(counts)


def prioritise(
    cbom: CBOM,
    policy: Policy | None = None,
    assessment_year: int | None = None,
) -> RiskReport:
    """Score and cluster a CBOM into a ranked migration plan."""
    policy = policy or load_policy()
    mosca_cfg = policy.mosca
    year = resolve_assessment_year(mosca_cfg, assessment_year)
    data_classes = mosca_cfg.data_classes
    blast = _blast_radii(cbom)

    scores: list[RiskScore] = []
    for asset in cbom.assets:
        x, x_basis = estimate_shelf_life(asset, data_classes)
        y, y_basis = estimate_migration_years(asset, _LIVE_SUITES)
        m = assess(x, y, mosca_cfg, year)
        system = asset.location.split("/", 1)[0].split(":", 1)[0]
        scores.append(
            score_asset(
                asset, m,
                blast_radius=blast.get((system, asset.primitive), 1),
                shelf_life_basis=x_basis,
                migration_basis=y_basis,
            )
        )

    scores.sort(key=lambda s: (s.score, s.asset.location), reverse=True)

    backlog = [s for s in scores if s.asset.exposure is not Exposure.QUANTUM_SAFE]
    packages = build_work_packages(backlog)

    return RiskReport(
        estate_root=cbom.estate_root,
        assessment_year=year,
        crqc_year=mosca_cfg.crqc_year(),
        preset=mosca_cfg.active_preset,
        scores=tuple(scores),
        work_packages=tuple(packages),
    )
