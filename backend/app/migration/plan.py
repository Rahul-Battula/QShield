"""Describing a migration before it runs.

A :class:`MigrationPlan` is a read-only summary: which suite the registry moves
from and to, the concrete KEM and signature algorithms on each side, how many
records are affected, and a one-line note from the Phase 4 threat model on what
is wrong with the algorithms being retired.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..agility.policy import Policy, load_policy
from ..discovery.cbom import Exposure
from ..discovery.classify import classify
from ..landrecords import LandRegistry

# Longest first so "ML-KEM" wins over a hypothetical "ML".
_FAMILIES = [
    "ML-KEM", "ML-DSA", "SLH-DSA", "X25519", "X448", "ED25519", "ECDSA",
    "ECDH", "RSA", "DSA", "DH", "AES", "HQC",
]


class MigrationPlanError(RuntimeError):
    pass


def _components(algorithm: str) -> list[str]:
    """Primitive family per component of a (possibly composite) suite algorithm:
    ``X25519+ML-KEM-768`` -> ``["X25519", "ML-KEM"]``; ``RSA-2048`` -> ``["RSA"]``."""
    out: list[str] = []
    for comp in algorithm.split("+"):
        c = comp.strip().upper()
        out.append(next((f for f in _FAMILIES if c.startswith(f)), c))
    return out


def _role_note(label: str, algorithm: str) -> str:
    fams = _components(algorithm)
    exposures = {f: classify(f)[0] for f in fams}
    if any(e is Exposure.QUANTUM_SAFE for e in exposures.values()):
        broken = [f for f, e in exposures.items() if e is not Exposure.QUANTUM_SAFE]
        if not broken:
            return f"{algorithm} ({label}) is already quantum-safe."
        return (f"{algorithm} ({label}) is a hybrid: {', '.join(broken)} would "
                f"fall to Shor, but the composite survives on its PQC component.")
    return (f"{algorithm} ({label}) has no quantum-safe component — Shor recovers "
            f"the private key in polynomial time.")


def _threat_note(from_kem: str, from_sig: str) -> str:
    return "  ".join([_role_note("KEM", from_kem), _role_note("signature", from_sig)])


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    from_suite: str
    to_suite: str
    from_kem: str
    from_sig: str
    to_kem: str
    to_sig: str
    record_count: int
    affected_algorithms: dict[tuple[str, str], int]
    threat_note: str

    @property
    def is_noop(self) -> bool:
        return self.from_suite == self.to_suite

    def to_dict(self) -> dict:
        return {
            "from_suite": self.from_suite,
            "to_suite": self.to_suite,
            "from": {"kem": self.from_kem, "sig": self.from_sig},
            "to": {"kem": self.to_kem, "sig": self.to_sig},
            "record_count": self.record_count,
            "affected_algorithms": [
                {"kem": k, "sig": s, "records": n}
                for (k, s), n in self.affected_algorithms.items()
            ],
            "threat_note": self.threat_note,
        }


def plan(registry: LandRegistry, to_suite: str, *, policy: Policy | None = None) -> MigrationPlan:
    """Build the plan to move ``registry`` onto ``to_suite``."""
    policy = policy or load_policy()
    if to_suite not in policy.suites:
        raise MigrationPlanError(
            f"unknown suite {to_suite!r}; policy defines {sorted(policy.suites)}"
        )
    from_suite = policy.active_suite
    src, dst = policy.suites[from_suite], policy.suites[to_suite]
    return MigrationPlan(
        from_suite=from_suite,
        to_suite=to_suite,
        from_kem=src.kem,
        from_sig=src.sig,
        to_kem=dst.kem,
        to_sig=dst.sig,
        record_count=len(registry),
        affected_algorithms=dict(registry.algorithms_in_use()),
        threat_note=_threat_note(src.kem, src.sig),
    )
