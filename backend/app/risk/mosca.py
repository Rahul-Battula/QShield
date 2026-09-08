"""Mosca's inequality — the timing test at the centre of Phase 3.

Michele Mosca's formulation: let

* **X** = how many years the data must remain confidential (its shelf life),
* **Y** = how many years it takes to migrate the systems that protect it,
* **Z** = how many years until a cryptographically relevant quantum computer
  (CRQC) exists.

If **X + Y > Z** the migration finishes only after the data it protects is
already harvestable — the "harvest now, decrypt later" window is already open.
The quantity ``X + Y - Z`` is how many years too late the current plan is, and
``Z - X - Y`` years from now is the latest moment a migration can *start* and
still finish in time.

This module does the arithmetic and nothing else. X comes from
:mod:`.shelflife`, Y from :mod:`.migration_cost`, Z from ``policy.yaml``'s
``mosca`` block.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ..agility.policy import MoscaConfig


@dataclass(frozen=True, slots=True)
class MoscaAssessment:
    """The result of applying Mosca's inequality to one asset."""

    shelf_life_years: float
    """X — years the protected data must stay confidential."""
    migration_years: float
    """Y — years to migrate this asset to a quantum-safe primitive."""
    horizon_years: float
    """Z — years from the assessment year to the assumed CRQC arrival."""
    assessment_year: int
    crqc_year: int

    @property
    def exposure_gap_years(self) -> float:
        """``X + Y - Z``. Positive means the plan finishes too late, by this many
        years; zero or negative means there is still slack."""
        return self.shelf_life_years + self.migration_years - self.horizon_years

    @property
    def latest_safe_start_year(self) -> float:
        """The last calendar year a migration can begin and still beat the
        inequality: ``crqc_year - X - Y``."""
        return self.crqc_year - self.shelf_life_years - self.migration_years

    @property
    def years_until_must_start(self) -> float:
        """Years from the assessment year until :attr:`latest_safe_start_year`.
        Negative means the start date is already in the past."""
        return self.latest_safe_start_year - self.assessment_year

    @property
    def is_too_late(self) -> bool:
        """``True`` when ``X + Y > Z`` — action needed now, not on a schedule."""
        return self.exposure_gap_years > 0

    def to_dict(self) -> dict:
        return {
            "shelf_life_years": round(self.shelf_life_years, 2),
            "migration_years": round(self.migration_years, 2),
            "horizon_years": round(self.horizon_years, 2),
            "assessment_year": self.assessment_year,
            "crqc_year": self.crqc_year,
            "exposure_gap_years": round(self.exposure_gap_years, 2),
            "latest_safe_start_year": round(self.latest_safe_start_year, 1),
            "years_until_must_start": round(self.years_until_must_start, 1),
            "is_too_late": self.is_too_late,
        }


def resolve_assessment_year(mosca: MoscaConfig, override: int | None = None) -> int:
    """Pick the assessment year: an explicit override, else the policy's pinned
    ``assessment_year``, else the current calendar year."""
    if override is not None:
        return override
    if mosca.assessment_year is not None:
        return mosca.assessment_year
    return datetime.date.today().year


def assess(
    shelf_life_years: float,
    migration_years: float,
    mosca: MoscaConfig,
    assessment_year: int | None = None,
) -> MoscaAssessment:
    """Apply Mosca's inequality for one asset against the policy horizon."""
    year = resolve_assessment_year(mosca, assessment_year)
    crqc = mosca.crqc_year()
    return MoscaAssessment(
        shelf_life_years=float(shelf_life_years),
        migration_years=float(migration_years),
        horizon_years=float(crqc - year),
        assessment_year=year,
        crqc_year=crqc,
    )
