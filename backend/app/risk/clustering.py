"""Grouping the ranked findings into migration work packages.

A flat list of two hundred findings is not a plan. Phase 3 clusters the
findings so that each group is a coherent piece of work — typically "one
subsystem, one primitive family, similar effort" — that a team can pick up and
finish.

The clustering is a small, deterministic k-means over a five-feature vector.
It is pure Python and seeded, so the same risk report always produces the same
packages. k-means is enough here: the features are already meaningful and
low-dimensional, the groups only need to be coherent rather than optimal, and a
heavier model would add a dependency and a training step for no gain in a
planning artefact. The feature engineering below is the substance; the
algorithm is deliberately ordinary.

Features per asset (each scaled to 0–1):

* exposure weight,
* Mosca time pressure,
* migration effort (Y, normalised),
* asset-kind ordinal,
* subsystem ordinal.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from ..discovery.cbom import AssetKind
from .scoring import _EXPOSURE_WEIGHT, PriorityBand, RiskScore, time_pressure

_KIND_ORDER = list(AssetKind)
_SEED = 20250901
_ITERATIONS = 50


def _feature_vector(rs: RiskScore, systems: list[str]) -> list[float]:
    kind_ord = _KIND_ORDER.index(rs.asset.kind) / max(1, len(_KIND_ORDER) - 1)
    sys_ord = systems.index(rs.system) / max(1, len(systems) - 1)
    y_norm = min(1.0, rs.mosca.migration_years / 3.0)
    return [
        _EXPOSURE_WEIGHT[rs.asset.exposure],
        time_pressure(rs.mosca),
        y_norm,
        kind_ord,
        sys_ord,
    ]


def _dist2(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _kmeans(points: list[list[float]], k: int) -> list[int]:
    """Return a cluster index per point. Deterministic: fixed seed, k-means++
    seeding, fixed iteration count, index order tie-breaks."""
    rng = random.Random(_SEED)
    n = len(points)
    if k >= n:
        return list(range(n))

    # k-means++ seeding.
    centres = [points[rng.randrange(n)]]
    while len(centres) < k:
        d2 = [min(_dist2(p, c) for c in centres) for p in points]
        total = sum(d2)
        if total == 0:
            centres.append(points[rng.randrange(n)])
            continue
        target = rng.random() * total
        acc = 0.0
        for p, weight in zip(points, d2):
            acc += weight
            if acc >= target:
                centres.append(p)
                break

    assign = [0] * n
    for _ in range(_ITERATIONS):
        moved = False
        for i, p in enumerate(points):
            best, best_d = 0, math.inf
            for ci, c in enumerate(centres):
                d = _dist2(p, c)
                if d < best_d:
                    best, best_d = ci, d
            if assign[i] != best:
                assign[i] = best
                moved = True
        for ci in range(k):
            members = [points[i] for i in range(n) if assign[i] == ci]
            if members:
                centres[ci] = [sum(col) / len(members) for col in zip(*members)]
        if not moved:
            break
    return assign


def _default_k(n: int) -> int:
    if n <= 3:
        return max(1, n)
    return max(2, min(8, round(math.sqrt(n / 2))))


_KIND_SHORT = {
    AssetKind.LIBRARY_CALL: "source",
    AssetKind.PROTOCOL_CONFIG: "config",
    AssetKind.TOKEN_CONFIG: "tokens",
    AssetKind.CERTIFICATE: "certs",
    AssetKind.PUBLIC_KEY: "keys",
    AssetKind.PRIVATE_KEY: "keys",
}


@dataclass(frozen=True, slots=True)
class WorkPackage:
    """A coherent unit of migration work covering several findings."""

    id: str
    title: str
    dominant_system: str
    dominant_primitive: str
    dominant_kind: str
    systems: tuple[str, ...]
    primitives: tuple[str, ...]
    scores: tuple[RiskScore, ...]
    total_migration_years: float
    max_score: float
    mean_score: float
    recommended_targets: tuple[str, ...]

    @property
    def size(self) -> int:
        return len(self.scores)

    @property
    def top_band(self) -> PriorityBand:
        return min((s.band for s in self.scores), key=lambda b: b.value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "dominant_system": self.dominant_system,
            "dominant_primitive": self.dominant_primitive,
            "dominant_kind": self.dominant_kind,
            "systems": list(self.systems),
            "primitives": list(self.primitives),
            "size": self.size,
            "top_band": self.top_band.value,
            "max_score": self.max_score,
            "mean_score": round(self.mean_score, 1),
            "total_migration_years": round(self.total_migration_years, 2),
            "recommended_targets": list(self.recommended_targets),
            "members": [
                {"score": s.score, "band": s.band.value, "detail": s.asset.detail,
                 "location": s.asset.location}
                for s in self.scores
            ],
        }


def _mode(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    # Highest count, then alphabetical for a stable tie-break.
    return sorted(counts, key=lambda v: (-counts[v], v))[0]


def build_work_packages(scores: list[RiskScore], k: int | None = None) -> list[WorkPackage]:
    """Cluster ``scores`` into work packages, ordered by their most urgent
    member (highest score first)."""
    if not scores:
        return []

    systems = sorted({s.system for s in scores})
    vectors = [_feature_vector(s, systems) for s in scores]
    k = k or _default_k(len(scores))
    assignment = _kmeans(vectors, k)

    groups: dict[int, list[RiskScore]] = {}
    for idx, cluster in enumerate(assignment):
        groups.setdefault(cluster, []).append(scores[idx])

    packages: list[WorkPackage] = []
    for members in groups.values():
        members.sort(key=lambda s: s.score, reverse=True)
        dom_system = _mode([s.system for s in members])
        dom_primitive = _mode([s.asset.primitive for s in members])
        dom_kind = _KIND_SHORT.get(
            max(
                {s.asset.kind for s in members},
                key=lambda kd: sum(1 for s in members if s.asset.kind == kd),
            ),
            "mixed",
        )
        targets = tuple(sorted({s.asset.recommendation for s in members}))
        lead = members[0]  # already sorted by score, descending
        extra = f" +{len(members) - 1} more" if len(members) > 1 else ""
        packages.append(
            WorkPackage(
                id="",  # assigned after ordering
                title=f"{lead.system}: {lead.asset.primitive}{extra} ({dom_kind})",
                dominant_system=dom_system,
                dominant_primitive=dom_primitive,
                dominant_kind=dom_kind,
                systems=tuple(sorted({s.system for s in members})),
                primitives=tuple(sorted({s.asset.primitive for s in members})),
                scores=tuple(members),
                total_migration_years=sum(s.mosca.migration_years for s in members),
                max_score=max(s.score for s in members),
                mean_score=sum(s.score for s in members) / len(members),
                recommended_targets=targets,
            )
        )

    packages.sort(key=lambda p: (p.max_score, p.mean_score), reverse=True)
    return [replace(p, id=f"wp-{i:02d}") for i, p in enumerate(packages, start=1)]
