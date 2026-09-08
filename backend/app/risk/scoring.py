"""Turning a Mosca assessment into a single ranked priority.

The score on 0–100 blends three things a migration planner actually trades off:

* **exposure** — is the primitive broken now, broken by a quantum computer, or
  merely weakened;
* **time pressure** — how close ``X + Y`` is to (or past) ``Z``;
* **blast radius** — how much of the estate shares this primitive, so a single
  fix clears many findings.

The weights are deliberately blunt and are documented inline. Two hard rules
override the arithmetic: a quantum-safe asset can never score above
:data:`_SAFE_CEILING`, and an already-too-late assessment on a broken primitive
is forced to the top band.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ..discovery.cbom import CryptoAsset, Exposure
from .mosca import MoscaAssessment


class PriorityBand(str, enum.Enum):
    P1 = "P1"  # do now
    P2 = "P2"  # this planning cycle
    P3 = "P3"  # backlog
    P4 = "P4"  # monitor only

    @property
    def label(self) -> str:
        return {
            "P1": "P1 — do now",
            "P2": "P2 — this cycle",
            "P3": "P3 — backlog",
            "P4": "P4 — monitor",
        }[self.value]


_EXPOSURE_WEIGHT: dict[Exposure, float] = {
    Exposure.CLASSICALLY_BROKEN: 1.0,
    Exposure.QUANTUM_BROKEN: 0.9,
    Exposure.QUANTUM_WEAKENED: 0.5,
    Exposure.UNKNOWN: 0.4,
    Exposure.QUANTUM_SAFE: 0.0,
}

_W_EXPOSURE = 0.55
_W_PRESSURE = 0.30
_W_BLAST = 0.15

_BLAST_CEILING = 8      # blast radius at which the blast term saturates
_SAFE_CEILING = 3.0     # a QUANTUM_SAFE asset never scores above this
_PRESSURE_SPAN = 10.0   # years either side of the deadline over which pressure ramps

_BAND_THRESHOLDS = ((70.0, PriorityBand.P1), (45.0, PriorityBand.P2),
                    (20.0, PriorityBand.P3))


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def time_pressure(mosca: MoscaAssessment) -> float:
    """0–1, centred on Mosca's latest-safe-start date.

    0.5 when the migration must start this year; ramping to 1.0 once it is
    :data:`_PRESSURE_SPAN` years or more overdue, and down to 0.0 when there is
    that much slack left. This keeps longer-lived data ranked above
    shorter-lived data even when both are already past their start date.
    """
    if mosca.horizon_years <= 0:
        return 1.0
    return _clamp01(0.5 - mosca.years_until_must_start / (2 * _PRESSURE_SPAN))


def _band_for(score: float) -> PriorityBand:
    for threshold, band in _BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return PriorityBand.P4


@dataclass(frozen=True, slots=True)
class RiskScore:
    """One asset, fully assessed and ranked."""

    asset: CryptoAsset
    mosca: MoscaAssessment
    shelf_life_basis: str
    migration_basis: str
    blast_radius: int
    score: float
    band: PriorityBand
    rationale: str

    @property
    def system(self) -> str:
        """The estate subsystem this asset belongs to (first path segment)."""
        return self.asset.location.split("/", 1)[0].split(":", 1)[0]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "band": self.band.value,
            "system": self.system,
            "blast_radius": self.blast_radius,
            "rationale": self.rationale,
            "asset": self.asset.to_dict(),
            "mosca": self.mosca.to_dict(),
            "shelf_life_basis": self.shelf_life_basis,
            "migration_basis": self.migration_basis,
        }


def score_asset(
    asset: CryptoAsset,
    mosca: MoscaAssessment,
    *,
    blast_radius: int,
    shelf_life_basis: str,
    migration_basis: str,
) -> RiskScore:
    """Combine an asset's exposure, Mosca assessment and blast radius into a
    :class:`RiskScore`."""
    exposure_w = _EXPOSURE_WEIGHT[asset.exposure]
    pressure = time_pressure(mosca)
    blast_norm = _clamp01(blast_radius / _BLAST_CEILING)

    raw = _W_EXPOSURE * exposure_w + _W_PRESSURE * pressure + _W_BLAST * blast_norm
    score = round(100.0 * raw, 1)

    if asset.exposure is Exposure.QUANTUM_SAFE:
        score = min(score, _SAFE_CEILING)

    band = _band_for(score)
    forced = ""
    if (
        mosca.is_too_late
        and exposure_w >= 0.9
        and band not in (PriorityBand.P1,)
    ):
        band = PriorityBand.P1
        forced = " (forced to P1: broken primitive already past its Mosca start date)"

    rationale = (
        f"exposure {asset.exposure.value} (w={exposure_w:.2f}), "
        f"time pressure {pressure:.2f} "
        f"(X={mosca.shelf_life_years:.0f}y + Y={mosca.migration_years:.2f}y "
        f"vs Z={mosca.horizon_years:.0f}y), "
        f"blast radius {blast_radius}"
        + (f"; too late by {mosca.exposure_gap_years:.1f}y" if mosca.is_too_late else "")
        + forced
    )
    return RiskScore(
        asset=asset,
        mosca=mosca,
        shelf_life_basis=shelf_life_basis,
        migration_basis=migration_basis,
        blast_radius=blast_radius,
        score=score,
        band=band,
        rationale=rationale,
    )
