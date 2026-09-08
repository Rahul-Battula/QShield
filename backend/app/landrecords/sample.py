"""Synthetic land titles for the demo and the tests."""

from __future__ import annotations

import random

from .models import TitleRecord
from .registry import LandRegistry

_DISTRICTS = ["VZM", "GNT", "KKD", "SKL", "NLR", "CTR"]
_OWNERS = [
    "A. Rao", "S. Devi", "M. Khan", "P. Naidu", "L. Fernandes", "R. Kumar",
    "T. Begum", "V. Reddy", "J. D'Souza", "K. Sharma",
]
_NOTES = [
    "Boundary re-surveyed after 2019 flood; north pin reset.",
    "Access easement to adjoining parcel recorded in schedule B.",
    "Partition from parent parcel; mutation pending in revenue records.",
    "Well and pump-house included; irrigation channel along east edge.",
    "Structure on plot predates title; regularised under 2021 scheme.",
]


def sample_titles(n: int, *, seed: int = 0) -> list[TitleRecord]:
    rng = random.Random(seed)
    out: list[TitleRecord] = []
    for _ in range(n):
        district = rng.choice(_DISTRICTS)
        out.append(TitleRecord(
            parcel_id=f"AP-{district}-2026-{rng.randint(1, 999999):06d}",
            owner=rng.choice(_OWNERS),
            area_sqm=round(rng.uniform(120, 4000), 1),
            survey_note=rng.choice(_NOTES),
            valuation_gbp=rng.randint(15_000, 900_000),
        ))
    return out


def demo_registry(n: int = 8, *, seed: int = 0) -> LandRegistry:
    """A registry keyed for the active policy suite and populated with ``n``
    sealed sample titles."""
    reg = LandRegistry()
    reg.rekey()
    for record in sample_titles(n, seed=seed):
        reg.register(record)
    return reg
