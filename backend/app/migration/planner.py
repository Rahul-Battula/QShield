"""Phased migration planning — turning the ranked backlog into dated waves.

A ministry cannot migrate everything at once. :func:`plan_waves` groups the
Phase 3 ranked findings by priority band into sequential waves, spreads their
target dates between now and the earliest Mosca deadline, orders the work inside
each wave so the cheap configuration changes land before the code changes, and
reports each wave's share of the total risk it removes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..discovery.cbom import AssetKind
from ..risk.prioritise import RiskReport
from ..risk.scoring import PriorityBand

# Do the quick, low-risk changes first within a wave.
_KIND_ORDER = {
    AssetKind.PROTOCOL_CONFIG: 0,
    AssetKind.TOKEN_CONFIG: 1,
    AssetKind.CERTIFICATE: 2,
    AssetKind.PUBLIC_KEY: 3,
    AssetKind.PRIVATE_KEY: 3,
    AssetKind.LIBRARY_CALL: 4,
}
_BAND_NAME = {"P1": "do now", "P2": "this planning cycle", "P3": "backlog",
              "P4": "monitor"}
_DEFAULT_TARGET = "hybrid (X25519+ML-KEM-768 / ECDSA-P256+ML-DSA-65)"


@dataclass(frozen=True, slots=True)
class Wave:
    id: str
    name: str
    band: str
    start_date: str
    target_date: str
    effort_years: float
    risk_reduction_pct: float
    target_suite: str
    items: list[dict]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "band": self.band,
            "start_date": self.start_date, "target_date": self.target_date,
            "effort_years": round(self.effort_years, 2),
            "risk_reduction_pct": round(self.risk_reduction_pct, 1),
            "target_suite": self.target_suite,
            "size": len(self.items), "items": self.items,
        }


def plan_waves(report: RiskReport, *, start: date | None = None) -> dict:
    """One wave per populated priority band, P1 first, with target dates spread
    from ``start`` to the earliest latest-safe-start date in the backlog."""
    start = start or date.today()
    scores = list(report.scores)
    total_score = sum(s.score for s in scores) or 1.0

    # The hard deadline: the earliest year any finding must have started by.
    earliest_start = min(
        (s.mosca.latest_safe_start_year for s in scores), default=start.year + 4
    )
    deadline = date(max(int(earliest_start), start.year + 1), 12, 31)
    horizon_days = max(365, (deadline - start).days)

    bands = [b for b in PriorityBand if any(s.band is b for s in scores)]
    waves: list[Wave] = []
    for i, band in enumerate(bands):
        members = sorted(
            (s for s in scores if s.band is band),
            key=lambda s: (_KIND_ORDER.get(s.asset.kind, 5), -s.score),
        )
        w_start = start + timedelta(days=int(i * horizon_days / max(1, len(bands))))
        w_end = start + timedelta(days=int((i + 1) * horizon_days / max(1, len(bands))))
        effort = sum(s.mosca.migration_years for s in members)
        reduction = 100.0 * sum(s.score for s in members) / total_score
        waves.append(Wave(
            id=f"wave-{i + 1}",
            name=f"Wave {i + 1}: {_BAND_NAME.get(band.value, band.value)}",
            band=band.value,
            start_date=w_start.isoformat(),
            target_date=w_end.isoformat(),
            effort_years=effort,
            risk_reduction_pct=reduction,
            target_suite=_common_target(members),
            items=[{
                "location": s.asset.location,
                "detail": s.asset.detail,
                "system": s.system,
                "kind": s.asset.kind.value,
                "score": s.score,
                "migration_years": round(s.mosca.migration_years, 2),
                "past_start_date": s.mosca.is_too_late,
            } for s in members],
        ))

    return {
        "generated_for_year": report.assessment_year,
        "crqc_year": report.crqc_year,
        "deadline": deadline.isoformat(),
        "total_findings": len(scores),
        "total_effort_years": round(sum(w.effort_years for w in waves), 2),
        "waves": [w.to_dict() for w in waves],
    }


def _common_target(members) -> str:
    recs = [s.asset.recommendation for s in members if "suite" in s.asset.recommendation]
    if not recs:
        return _DEFAULT_TARGET
    # the recommendation string already names a policy suite
    return max(set(recs), key=recs.count)
