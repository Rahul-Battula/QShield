"""Grover's algorithm — the quantum attack on symmetric primitives.

Grover search finds a marked item among ``N`` in ``~(pi/4) * sqrt(N)``
evaluations instead of ``~N/2``. Applied to a key search that is a quadratic
speed-up, so it *halves the effective key length*: AES-128 offers roughly a
64-bit security level against an ideal quantum attacker, AES-256 roughly
128-bit.

Two caveats QShield states alongside the number:

* Grover parallelises poorly. Splitting the search across ``M`` machines only
  gives a ``sqrt(M)`` speed-up, so the wall-clock cost of a real AES-128 attack
  stays enormous (Grassl et al., 2016). NIST's view is that AES-128 remains
  acceptable for now and AES-256 has a comfortable margin.
* It is optimal: no quantum algorithm beats the ``sqrt`` factor for unstructured
  search (Bennett-Bernstein-Brassard-Vazirani), so a well-sized symmetric
  primitive is a *parameter* problem, not an algorithm problem.

:func:`grover_search` runs the real circuit on the pure-Python simulator for a
small ``n`` so the mechanism is demonstrable end to end.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

from .simulator import Statevector


def grover_effective_bits(key_bits: int) -> int:
    """Effective security level of a ``key_bits``-bit symmetric key against an
    ideal Grover attacker: half, rounded down."""
    return key_bits // 2


def optimal_iterations(n_qubits: int, n_marked: int = 1) -> int:
    """The iteration count that maximises success probability for ``n_marked``
    solutions in a space of ``2**n_qubits``."""
    N = 1 << n_qubits
    if n_marked <= 0 or n_marked >= N:
        return 0
    theta = math.asin(math.sqrt(n_marked / N))
    return max(1, round((math.pi / 2 - theta) / (2 * theta)))


@dataclass(frozen=True, slots=True)
class GroverResult:
    n_qubits: int
    iterations: int
    marked: tuple[int, ...]
    measured: int
    success_probability: float
    classical_queries_avg: float
    quantum_queries: int

    @property
    def found(self) -> bool:
        return self.measured in self.marked

    @property
    def speedup(self) -> float:
        return self.classical_queries_avg / max(1, self.quantum_queries)


def _phase_flip(sv: Statevector, predicate: Callable[[int], bool]) -> None:
    for i in range(len(sv.amp)):
        if sv.amp[i] != 0j and predicate(i & ((1 << sv.n) - 1)):
            sv.amp[i] = -sv.amp[i]


def _diffuser(sv: Statevector, qubits: list[int]) -> None:
    for q in qubits:
        sv.h(q)
    # Reflect about |0...0>: flip the sign of every state except all-zero.
    for i in range(len(sv.amp)):
        if i != 0 and sv.amp[i] != 0j:
            sv.amp[i] = -sv.amp[i]
    for q in qubits:
        sv.h(q)


def grover_search(
    n_qubits: int,
    predicate: Callable[[int], bool],
    *,
    iterations: int | None = None,
    shots: int = 512,
    seed: int = 0,
    engine: str = "python",
) -> GroverResult:
    """Run Grover search for the items satisfying ``predicate`` over
    ``range(2**n_qubits)``.

    ``engine`` selects the implementation: ``"python"`` (default) uses the
    bundled exact statevector simulator; ``"qiskit"`` builds a real
    :class:`qiskit.QuantumCircuit` and runs it on Aer (requires the ``quantum``
    extra).
    """
    if n_qubits < 1 or n_qubits > 16:
        raise ValueError("grover_search supports 1..16 qubits")
    marked = tuple(v for v in range(1 << n_qubits) if predicate(v))
    if not marked:
        raise ValueError("predicate marks no state")

    iters = iterations if iterations is not None else optimal_iterations(
        n_qubits, len(marked)
    )

    if engine == "qiskit":
        from .backend import require_qiskit
        require_qiskit()
        from . import qiskit_backend

        measured, hist = qiskit_backend.run_grover(
            n_qubits, set(marked), iters, shots=max(shots, 1024), seed=seed
        )
        total = sum(hist.values()) or 1
        success = sum(hist.get(m, 0) for m in marked) / total
    elif engine == "python":
        qubits = list(range(n_qubits))
        sv = Statevector(n_qubits)
        for q in qubits:
            sv.h(q)
        for _ in range(iters):
            _phase_flip(sv, predicate)
            _diffuser(sv, qubits)

        rng = random.Random(seed)
        counts = sv.sample(qubits, shots, rng)
        measured = max(counts, key=counts.get)
        dist = sv.register_distribution(qubits)
        success = sum(dist.get(m, 0.0) for m in marked)
    else:
        raise ValueError(f"unknown engine {engine!r}; use 'python' or 'qiskit'")

    N = 1 << n_qubits
    return GroverResult(
        n_qubits=n_qubits,
        iterations=iters,
        marked=marked,
        measured=measured,
        success_probability=success,
        classical_queries_avg=(N + 1) / 2 / len(marked),
        quantum_queries=iters,
    )
