"""A minimal exact statevector simulator — pure Python, no dependencies.

QShield's Phase 4 demonstrations (Grover search, Shor order-finding, a quantum
RNG) need to *run* with no build step, so this is the default engine. It is
~200 lines of exact linear algebra over Python ``complex`` and is enough for
the small circuits the demonstrations use (roughly <= 16 qubits).

It is a teaching simulator, not a performant one: amplitudes are a flat list of
length ``2**n`` and every gate is an O(2**n) sweep. Qubit 0 is the least
significant bit, so a register's integer value is
``sum(bit(q_i) << position_i)``.

:mod:`app.threat.qiskit_backend` is the second engine (``engine="qiskit"``)
— the same demonstrations as real Qiskit circuits on Aer, when the optional
``quantum`` extra is installed.
"""

from __future__ import annotations

import cmath
import math
import random
from collections.abc import Callable, Sequence

_SQRT1_2 = 1.0 / math.sqrt(2.0)


class Statevector:
    """The pure state of ``n`` qubits, initialised to |0...0>."""

    __slots__ = ("amp", "n")

    def __init__(self, n: int) -> None:
        if n < 1 or n > 20:
            raise ValueError("simulator supports 1..20 qubits")
        self.n = n
        self.amp: list[complex] = [0j] * (1 << n)
        self.amp[0] = 1 + 0j

    # -- single-qubit gates -------------------------------------------------

    def _apply_1q(self, q: int, a: complex, b: complex, c: complex, d: complex) -> None:
        """Apply the 2x2 matrix [[a, b], [c, d]] to qubit ``q``."""
        step = 1 << q
        amp = self.amp
        for base in range(0, 1 << self.n, step << 1):
            for i in range(base, base + step):
                j = i | step
                x, y = amp[i], amp[j]
                amp[i] = a * x + b * y
                amp[j] = c * x + d * y

    def h(self, q: int) -> Statevector:
        self._apply_1q(q, _SQRT1_2, _SQRT1_2, _SQRT1_2, -_SQRT1_2)
        return self

    def x(self, q: int) -> Statevector:
        self._apply_1q(q, 0, 1, 1, 0)
        return self

    def phase(self, q: int, theta: float) -> Statevector:
        self._apply_1q(q, 1, 0, 0, cmath.exp(1j * theta))
        return self

    # -- controlled gates -------------------------------------------------

    def cphase(self, control: int, target: int, theta: float) -> Statevector:
        factor = cmath.exp(1j * theta)
        cbit, tbit = 1 << control, 1 << target
        amp = self.amp
        for i in range(len(amp)):
            if (i & cbit) and (i & tbit):
                amp[i] *= factor
        return self

    def cx(self, control: int, target: int) -> Statevector:
        cbit, tbit = 1 << control, 1 << target
        amp = self.amp
        for i in range(len(amp)):
            if (i & cbit) and not (i & tbit):
                j = i | tbit
                amp[i], amp[j] = amp[j], amp[i]
        return self

    # -- register-level helpers -----------------------------------------

    def permute(self, mapping: Callable[[int], int]) -> Statevector:
        """Apply a basis permutation: ``mapping`` must be a bijection on
        ``range(2**n)``. Used to realise reversible classical arithmetic."""
        new = [0j] * len(self.amp)
        for i, a in enumerate(self.amp):
            if a != 0j:
                new[mapping(i)] = a
        self.amp = new
        return self

    def map_register(
        self,
        qubits: Sequence[int],
        func: Callable[[int], int],
        *,
        controls: Sequence[int] = (),
    ) -> Statevector:
        """Replace the value ``v`` held in ``qubits`` with ``func(v)`` (a
        bijection on ``range(2**len(qubits))``), optionally only when every
        qubit in ``controls`` is set."""
        cmask = 0
        for c in controls:
            cmask |= 1 << c
        qbits = [1 << q for q in qubits]

        def mapping(i: int) -> int:
            if cmask and (i & cmask) != cmask:
                return i
            v = 0
            for pos, qb in enumerate(qbits):
                if i & qb:
                    v |= 1 << pos
            nv = func(v)
            j = i
            for pos, qb in enumerate(qbits):
                j = (j | qb) if (nv >> pos) & 1 else (j & ~qb)
            return j

        return self.permute(mapping)

    def qft(self, qubits: Sequence[int], *, inverse: bool = False) -> Statevector:
        """(Inverse) quantum Fourier transform over ``qubits`` (qubits[0] = LSB),
        including the bit-reversal swaps.

        Forward: the H/controlled-phase ladder from the most significant qubit
        down, then swaps. Inverse: swaps first, then the ladder run in reverse
        with negated phases.
        """
        qs = list(qubits)
        k = len(qs)
        if inverse:
            for a in range(k // 2):
                self._swap(qs[a], qs[k - 1 - a])
            for i in range(k):
                for j in range(i):
                    self.cphase(qs[j], qs[i], -math.pi / (1 << (i - j)))
                self.h(qs[i])
        else:
            for i in range(k - 1, -1, -1):
                self.h(qs[i])
                for j in range(i):
                    self.cphase(qs[j], qs[i], math.pi / (1 << (i - j)))
            for a in range(k // 2):
                self._swap(qs[a], qs[k - 1 - a])
        return self

    def _swap(self, q1: int, q2: int) -> None:
        self.cx(q1, q2)
        self.cx(q2, q1)
        self.cx(q1, q2)

    # -- measurement ----------------------------------------------------

    def probabilities(self) -> list[float]:
        return [abs(a) ** 2 for a in self.amp]

    def register_distribution(self, qubits: Sequence[int]) -> dict[int, float]:
        """Marginal probability of each value of ``qubits``."""
        qbits = [1 << q for q in qubits]
        out: dict[int, float] = {}
        for i, a in enumerate(self.amp):
            p = abs(a) ** 2
            if p == 0.0:
                continue
            v = 0
            for pos, qb in enumerate(qbits):
                if i & qb:
                    v |= 1 << pos
            out[v] = out.get(v, 0.0) + p
        return out

    def sample(self, qubits: Sequence[int], shots: int, rng: random.Random) -> dict[int, int]:
        dist = self.register_distribution(qubits)
        values = list(dist)
        weights = [dist[v] for v in values]
        counts: dict[int, int] = {}
        for _ in range(shots):
            (pick,) = rng.choices(values, weights=weights, k=1)
            counts[pick] = counts.get(pick, 0) + 1
        return counts


def norm(sv: Statevector) -> float:
    return math.sqrt(sum(abs(a) ** 2 for a in sv.amp))
