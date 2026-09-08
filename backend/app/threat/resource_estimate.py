"""Extrapolating the toy demos to real key sizes — a projection, not a prediction.

The Shor and Grover circuits QShield runs on Aer factor N <= 35 and search a
handful of bits. This module scales those mechanisms up to RSA-2048, ECC-P256
and friends using textbook asymptotics and a simplified surface-code model, and
then reads a "year it becomes feasible" off a stated hardware-growth curve.

**Every number here is a projection under the assumptions printed alongside it.**
The asymptotic forms follow Gidney & Ekerå (2021) for factoring and Roetteler
et al. (2017) for elliptic-curve discrete log; the surface-code overhead is the
standard ``~2 d^2`` physical qubits per logical qubit with a routing/magic-state
factor. Different cost models differ by an order of magnitude — see
``app.threat.estimates`` for the peer-reviewed point estimates this is
calibrated against.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Surface-code model constants.
_P_THRESHOLD = 1e-2          # surface-code threshold
_PREFACTOR = 0.1            # logical error rate prefactor
_CYCLE_TIME_S = 1e-6        # physical measurement cycle
_ROUTING_FACTOR = 2.0      # magic-state factories + routing, on top of the data tiles

# Hardware-growth defaults for the "years until breakable" projection.
_BASE_YEAR = 2024
_BASE_PHYSICAL_QUBITS = 1_100      # order of the largest devices in 2024
_ANNUAL_GROWTH = 1.5              # physical-qubit count multiplier per year


@dataclass(frozen=True, slots=True)
class ResourceProjection:
    target: str
    attack: str
    classical_security_bits: int
    logical_qubits: int
    toffoli_count: float
    code_distance: int
    physical_qubits: float
    runtime_seconds: float
    feasible_year: int | None
    assumptions: dict

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "attack": self.attack,
            "classical_security_bits": self.classical_security_bits,
            "logical_qubits": self.logical_qubits,
            "toffoli_count": _sig(self.toffoli_count),
            "code_distance": self.code_distance,
            "physical_qubits": _sig(self.physical_qubits),
            "runtime_seconds": _sig(self.runtime_seconds),
            "runtime_human": _human_time(self.runtime_seconds),
            "feasible_year": self.feasible_year,
            "assumptions": self.assumptions,
            "disclaimer": "Projection under the stated assumptions, not a prediction.",
        }


def _sig(x: float, digits: int = 3) -> float:
    if x == 0:
        return 0.0
    return round(x, -math.floor(math.log10(abs(x))) + (digits - 1))


def _human_time(s: float) -> str:
    for unit, span in (("years", 3.15e7), ("days", 86400), ("hours", 3600),
                       ("minutes", 60)):
        if s >= span:
            return f"{s / span:.1f} {unit}"
    return f"{s:.1f} seconds"


def _algo_costs(algorithm: str, key_bits: int) -> tuple[str, int, int, float]:
    """(attack, classical_security_bits, logical_qubits, toffoli_count)."""
    a = algorithm.strip().upper()
    n = key_bits
    if a in ("RSA", "DH", "DSA"):
        # Gidney-Ekerå: ~2n + O(log n) logical qubits; ~0.3 n^3 Toffolis.
        logical = 2 * n + 3 * max(1, int(math.log2(n)))
        toffoli = 0.3 * n ** 3
        sec = {1024: 80, 2048: 112, 3072: 128, 4096: 140}.get(n, int(n / 18))
        return "Shor (factoring / discrete log)", sec, logical, toffoli
    if a in ("ECC", "ECDSA", "ECDH", "EDDSA", "ED25519", "X25519"):
        # Roetteler et al.: ~9n logical qubits for an n-bit curve.
        logical = 9 * n + 2 * max(1, int(math.log2(n)))
        toffoli = 0.5 * n ** 3
        sec = {256: 128, 384: 192, 521: 256}.get(n, n // 2)
        return "Shor (elliptic-curve discrete log)", sec, logical, toffoli
    if a == "AES":
        # Grover: ~sqrt(2^k) iterations, each an AES circuit (~1.5e3 Toffolis).
        toffoli = (2 ** (n / 2)) * 1.5e3
        logical = {128: 3000, 192: 4600, 256: 6600}.get(n, 3000)
        return "Grover (key search)", n, logical, toffoli
    raise ValueError(f"no resource model for {algorithm!r}")


def _code_distance(toffoli_count: float, phys_error_rate: float,
                   target_logical_error: float = 1e-2) -> int:
    """Smallest odd distance d so the expected logical-error count over the whole
    computation stays below ``target_logical_error``."""
    if phys_error_rate >= _P_THRESHOLD:
        return 999  # below threshold -> no finite distance helps
    budget = target_logical_error / max(1.0, toffoli_count)
    ratio = phys_error_rate / _P_THRESHOLD
    d = 3
    while d < 200:
        p_logical = _PREFACTOR * ratio ** ((d + 1) / 2)
        if p_logical <= budget:
            return d
        d += 2
    return d


def _physical_qubits(logical: int, d: int) -> float:
    return logical * (2 * d * d) * _ROUTING_FACTOR


def _runtime_seconds(toffoli: float, d: int) -> float:
    # One Toffoli ~ d code cycles of magic-state consumption, with parallelism.
    return toffoli * (d * _CYCLE_TIME_S / 2.5)


def _feasible_year(required_physical: float, base_qubits: int, growth: float) -> int | None:
    if required_physical <= base_qubits:
        return _BASE_YEAR
    if growth <= 1:
        return None
    years = math.log(required_physical / base_qubits) / math.log(growth)
    return _BASE_YEAR + math.ceil(years)


def estimate(
    algorithm: str,
    key_bits: int,
    *,
    phys_error_rate: float = 1e-3,
    base_qubits: int = _BASE_PHYSICAL_QUBITS,
    annual_growth: float = _ANNUAL_GROWTH,
) -> ResourceProjection:
    """Project the cost of breaking ``algorithm`` at ``key_bits`` bits."""
    attack, sec, logical, toffoli = _algo_costs(algorithm, key_bits)
    d = _code_distance(toffoli, phys_error_rate)
    phys = _physical_qubits(logical, d)
    runtime = _runtime_seconds(toffoli, d)
    year = _feasible_year(phys, base_qubits, annual_growth)
    return ResourceProjection(
        target=f"{algorithm.upper()}-{key_bits}",
        attack=attack,
        classical_security_bits=sec,
        logical_qubits=logical,
        toffoli_count=toffoli,
        code_distance=d,
        physical_qubits=phys,
        runtime_seconds=runtime,
        feasible_year=year,
        assumptions={
            "physical_error_rate": phys_error_rate,
            "surface_code_threshold": _P_THRESHOLD,
            "cycle_time_seconds": _CYCLE_TIME_S,
            "routing_factor": _ROUTING_FACTOR,
            "base_year": _BASE_YEAR,
            "base_physical_qubits": base_qubits,
            "annual_qubit_growth": annual_growth,
        },
    )


def growth_curve(
    algorithm: str, key_bits: int, *, phys_error_rate: float = 1e-3,
    base_qubits: int = _BASE_PHYSICAL_QUBITS, annual_growth: float = _ANNUAL_GROWTH,
    through_year: int = 2050,
) -> dict:
    """Available vs required physical qubits per year — the data behind the
    'years until breakable' chart."""
    proj = estimate(algorithm, key_bits, phys_error_rate=phys_error_rate,
                    base_qubits=base_qubits, annual_growth=annual_growth)
    series = []
    for y in range(_BASE_YEAR, through_year + 1):
        available = base_qubits * annual_growth ** (y - _BASE_YEAR)
        series.append({"year": y, "available_physical_qubits": _sig(available),
                       "feasible": available >= proj.physical_qubits})
    return {
        "target": proj.target,
        "required_physical_qubits": _sig(proj.physical_qubits),
        "feasible_year": proj.feasible_year,
        "series": series,
        "assumptions": proj.assumptions,
        "disclaimer": "Projection under the stated assumptions, not a prediction.",
    }
