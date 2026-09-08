"""Shor's algorithm — the quantum attack on public-key primitives.

Shor's algorithm factors integers and computes discrete logarithms in
polynomial time on a fault-tolerant quantum computer. That breaks RSA (via
factoring) and Diffie-Hellman / DSA / ECDH / ECDSA / EdDSA (via discrete log)
outright — not weakened, broken. Every public-key primitive in deployment today
rests on one of these two problems.

The core quantum step is *order finding*: given ``a`` coprime to ``N``, find the
smallest ``r`` with ``a**r == 1 (mod N)``. From ``r`` (when it is even and
``a**(r/2) != -1 mod N``) the factors of ``N`` fall out classically as
``gcd(a**(r/2) +- 1, N)``.

:func:`order_finding` runs the real phase-estimation circuit — a uniform
superposition over a counting register, controlled multiplication-by-``a``
powers on a work register, an inverse QFT, and a continued-fraction step on the
measured phase — on the pure-Python simulator. It is limited by qubit count to
small ``N`` (15, 21, 33, 35, ...), which is exactly the regime where Shor has
actually been demonstrated on hardware; the barrier to RSA-2048 is scale, and
:mod:`app.threat.estimates` carries the published figures for that.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from fractions import Fraction

from .simulator import Statevector


def _bit_length(n: int) -> int:
    return max(1, n.bit_length())


@dataclass(frozen=True, slots=True)
class OrderResult:
    a: int
    N: int
    order: int | None
    counting_qubits: int
    work_qubits: int
    phase_numerator: int
    phase_denominator: int
    measured_value: int

    @property
    def verified(self) -> bool:
        return self.order is not None and pow(self.a, self.order, self.N) == 1


def _phase_python(a: int, N: int, n_count: int, n_work: int, shots: int,
                  rng: random.Random) -> int:
    """One phase-estimation shot batch on the bundled statevector simulator;
    returns the most-frequent counting-register value."""
    count_qs = list(range(n_count))
    work_qs = list(range(n_count, n_count + n_work))
    sv = Statevector(n_count + n_work)
    for q in count_qs:
        sv.h(q)
    sv.x(work_qs[0])  # work register starts at |1>
    for j, cq in enumerate(count_qs):
        factor = pow(a, 1 << j, N)

        def mul(v: int, factor: int = factor) -> int:
            return (v * factor) % N if v < N else v

        sv.map_register(work_qs, mul, controls=[cq])
    sv.qft(count_qs, inverse=True)
    counts = sv.sample(count_qs, shots, rng)
    return max(counts, key=counts.get)


def order_finding(
    a: int,
    N: int,
    *,
    counting_qubits: int | None = None,
    shots: int = 64,
    seed: int = 0,
    attempts: int = 12,
    engine: str = "python",
) -> OrderResult:
    """Find the multiplicative order of ``a`` modulo ``N`` with quantum phase
    estimation.

    ``engine="python"`` (default) runs the circuit on the bundled statevector
    simulator; ``engine="qiskit"`` builds a real phase-estimation circuit and
    runs it on Aer (requires the ``quantum`` extra). Both feed the same
    continued-fraction post-processing and retry loop.
    """
    if math.gcd(a, N) != 1:
        raise ValueError(f"a={a} is not coprime to N={N}")
    if engine not in ("python", "qiskit"):
        raise ValueError(f"unknown engine {engine!r}; use 'python' or 'qiskit'")

    n_work = _bit_length(N)
    n_count = counting_qubits or 2 * n_work
    if n_count + n_work > 20:
        raise ValueError(
            f"N={N} needs {n_count + n_work} qubits; simulator caps at 20"
        )

    if engine == "qiskit":
        from .backend import require_qiskit
        require_qiskit()
        from . import qiskit_backend

    rng = random.Random(seed)
    best: OrderResult | None = None

    for _attempt in range(attempts):
        if engine == "qiskit":
            measured = qiskit_backend.run_order_finding(
                a, N, n_count, n_work,
                shots=max(shots, 256), seed=rng.randint(0, 2**31 - 1),
            )
        else:
            measured = _phase_python(a, N, n_count, n_work, shots, rng)
        frac = Fraction(measured, 1 << n_count).limit_denominator(N)
        r = frac.denominator

        candidate = OrderResult(
            a=a, N=N, order=(r if r > 0 else None),
            counting_qubits=n_count, work_qubits=n_work,
            phase_numerator=frac.numerator, phase_denominator=frac.denominator,
            measured_value=measured,
        )
        if candidate.verified:
            return candidate
        # keep the smallest plausible r seen, as a fallback
        if best is None or (candidate.order or math.inf) < (best.order or math.inf):
            best = candidate

    return best if best is not None else candidate


@dataclass(frozen=True, slots=True)
class FactorResult:
    N: int
    factors: tuple[int, ...]
    witness: int | None
    order: int | None
    order_result: OrderResult | None

    @property
    def success(self) -> bool:
        return len(self.factors) >= 2 and math.prod(self.factors) == self.N


def factor(N: int, *, seed: int = 0, max_bases: int = 10,
           engine: str = "python") -> FactorResult:
    """Factor ``N`` (small, odd, composite, not a prime power) with Shor's
    algorithm: try bases ``a``, quantum-find the order, derive the factors.

    ``engine`` is passed through to :func:`order_finding` (``"python"`` or
    ``"qiskit"``)."""
    if N % 2 == 0:
        return FactorResult(N, (2, N // 2), None, None, None)

    # Perfect-power quick check (Shor's classical pre-step).
    for k in range(2, _bit_length(N) + 1):
        root = round(N ** (1.0 / k))
        for r in (root - 1, root, root + 1):
            if r > 1 and r ** k == N:
                return FactorResult(N, (r, N // r), None, None, None)

    rng = random.Random(seed)
    tried = 0
    for a in range(2, N):
        if tried >= max_bases:
            break
        if math.gcd(a, N) != 1:
            g = math.gcd(a, N)
            return FactorResult(N, (g, N // g), a, None, None)
        tried += 1
        res = order_finding(a, N, seed=rng.randint(0, 1 << 30), engine=engine)
        r = res.order
        if not res.verified or r is None or r % 2 != 0:
            continue
        y = pow(a, r // 2, N)
        if y == N - 1:
            continue
        p, q = math.gcd(y - 1, N), math.gcd(y + 1, N)
        for cand in (p, q):
            if 1 < cand < N and N % cand == 0:
                return FactorResult(N, (cand, N // cand), a, r, res)

    return FactorResult(N, (N,), None, None, None)
