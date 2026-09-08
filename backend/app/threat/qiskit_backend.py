"""Real Qiskit circuits for the Phase 4 demonstrations.

The pure-Python :mod:`app.threat.simulator` is the default and needs nothing
installed. This module runs the *same demonstrations* — Grover search, Shor
order-finding, a quantum RNG — as actual :class:`qiskit.QuantumCircuit` objects
executed on Aer, through the shared factory in :mod:`app.threat.aer` (so
noise, transpilation and reported metrics are consistent everywhere).

Two entry points:

* ``run_grover`` / ``run_order_finding`` / ``run_random_bits`` — thin, used by
  the ``engine="qiskit"`` path of :mod:`.grover` / :mod:`.shor` / :mod:`.qrng`.
* ``demo_grover`` / ``demo_shor`` / ``compare_shor`` / ``grover_success_curve``
  — full-payload functions behind the ``/api/quantum/*`` endpoints, returning
  circuit metrics, a text diagram and (for compare) ideal vs noisy histograms.

Circuits are small. The Shor order-finding step builds the controlled
modular-multiplication as a permutation :class:`~qiskit.circuit.library.UnitaryGate`
and controls it; that is exact but its transpiled cost grows with the work
register, so ``ideal`` covers N <= 15 and ``matrix`` (MPS) is used for N up to 35.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from fractions import Fraction

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import UnitaryGate

from . import aer

_GROVER_MAX_QUBITS = 12
_SHOR_STATEVECTOR_MAX = 13   # ideal/noisy: total qubits (N <= 15)
_SHOR_MPS_MAX = 22           # matrix: total qubits (covers N = 35)
_ALLOWED_SHOR_N = (15, 21, 35)


# ---------------------------------------------------------------------------
# Grover
# ---------------------------------------------------------------------------

def _mcz(qc: QuantumCircuit, qubits: list[int]) -> None:
    if len(qubits) == 1:
        qc.z(qubits[0])
        return
    qc.h(qubits[-1])
    qc.mcx(qubits[:-1], qubits[-1])
    qc.h(qubits[-1])


def _grover_oracle(qc: QuantumCircuit, n: int, marked: Iterable[int]) -> None:
    for m in marked:
        zeros = [q for q in range(n) if not (m >> q) & 1]
        for q in zeros:
            qc.x(q)
        _mcz(qc, list(range(n)))
        for q in zeros:
            qc.x(q)


def _grover_diffuser(qc: QuantumCircuit, n: int) -> None:
    for q in range(n):
        qc.h(q)
        qc.x(q)
    _mcz(qc, list(range(n)))
    for q in range(n):
        qc.x(q)
        qc.h(q)


def build_grover_circuit(n_qubits: int, marked: set[int], iterations: int) -> QuantumCircuit:
    if not 1 <= n_qubits <= _GROVER_MAX_QUBITS:
        raise ValueError(f"qiskit Grover demo supports 1..{_GROVER_MAX_QUBITS} qubits")
    qc = QuantumCircuit(n_qubits, n_qubits, name=f"grover_n{n_qubits}_it{iterations}")
    qc.h(range(n_qubits))
    for _ in range(iterations):
        _grover_oracle(qc, n_qubits, marked)
        _grover_diffuser(qc, n_qubits)
    qc.measure(range(n_qubits), range(n_qubits))
    return qc


def _hist_to_int(counts: dict[str, int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for bits, n in counts.items():
        out[int(bits, 2)] = out.get(int(bits, 2), 0) + n
    return out


def run_grover(
    n_qubits: int, marked: set[int], iterations: int, *,
    shots: int = 1024, seed: int = aer.DEFAULT_SEED,
) -> tuple[int, dict[int, int]]:
    """Backward-compatible: ``(most_frequent_outcome, {outcome: shots})`` on ideal Aer."""
    qc = build_grover_circuit(n_qubits, marked, iterations)
    res = aer.run(qc, aer.make_backend("ideal", seed=seed), shots=shots, diagram=False)
    hist = _hist_to_int(res.counts)
    return max(hist, key=hist.get), hist


def optimal_iterations(n_qubits: int, n_marked: int = 1) -> int:
    N = 1 << n_qubits
    theta = math.asin(math.sqrt(max(1, n_marked) / N))
    return max(1, round((math.pi / 2 - theta) / (2 * theta)))


def demo_grover(
    n_bits: int, *, iterations: int | None = None, mode: str = "ideal",
    shots: int = 2048, target: int | None = None, **noise,
) -> dict:
    """Full-payload single Grover run."""
    target = (1 << n_bits) - 1 if target is None else target
    iters = iterations if iterations is not None else optimal_iterations(n_bits, 1)
    qc = build_grover_circuit(n_bits, {target}, iters)
    res = aer.run(qc, aer.make_backend(mode, **noise), shots=shots)
    hist = _hist_to_int(res.counts)
    total = sum(hist.values()) or 1
    return {
        **res.to_dict(),
        "algorithm": "grover",
        "n_bits": n_bits,
        "iterations": iters,
        "optimal_iterations": optimal_iterations(n_bits, 1),
        "target": target,
        "measured": max(hist, key=hist.get),
        "success_probability": round(hist.get(target, 0) / total, 4),
        "histogram": {str(k): v for k, v in sorted(hist.items())},
    }


def grover_success_curve(
    n_bits: int, *, mode: str = "ideal", shots: int = 2048,
    target: int | None = None, **noise,
) -> dict:
    """Success probability at every iteration count from 1 to the optimum."""
    target = (1 << n_bits) - 1 if target is None else target
    opt = optimal_iterations(n_bits, 1)
    backend = aer.make_backend(mode, **noise)
    curve = []
    for it in range(1, opt + 1):
        qc = build_grover_circuit(n_bits, {target}, it)
        res = aer.run(qc, backend, shots=shots, diagram=False)
        hist = _hist_to_int(res.counts)
        total = sum(hist.values()) or 1
        curve.append({"iterations": it,
                      "success_probability": round(hist.get(target, 0) / total, 4)})
    return {"algorithm": "grover", "n_bits": n_bits, "target": target,
            "optimal_iterations": opt, "mode": mode, "shots": shots, "curve": curve}


# ---------------------------------------------------------------------------
# Shor order-finding
# ---------------------------------------------------------------------------

def _inverse_qft(qc: QuantumCircuit, qubits: list[int]) -> None:
    n = len(qubits)
    for i in range(n // 2):
        qc.swap(qubits[i], qubits[n - 1 - i])
    for j in range(n):
        for m in range(j):
            qc.cp(-math.pi / (1 << (j - m)), qubits[m], qubits[j])
        qc.h(qubits[j])


def _controlled_modmul_gate(factor: int, N: int, n_work: int) -> UnitaryGate:
    """The controlled permutation ``ctrl=1: |y> -> |(factor*y) mod N>`` (for
    ``y < N``) as one exact unitary on ``1 + n_work`` qubits, with qubit 0 the
    control. Applied directly (no ``.control()``) so Aer runs it as a single
    ``unitary`` instruction — decomposing a generic controlled n-qubit unitary
    to basis gates is what makes the naive circuit slow."""
    dim = 1 << (n_work + 1)
    m = np.zeros((dim, dim), dtype=complex)
    for ctrl in (0, 1):
        for y in range(1 << n_work):
            col = (y << 1) | ctrl
            ny = (factor * y) % N if (ctrl and y < N) else y
            m[(ny << 1) | ctrl, col] = 1.0
    return UnitaryGate(m, label=f"c*{factor}%{N}")


def build_order_finding_circuit(a: int, N: int, n_count: int, n_work: int) -> QuantumCircuit:
    count = list(range(n_count))
    work = list(range(n_count, n_count + n_work))
    qc = QuantumCircuit(n_count + n_work, n_count, name=f"shor_N{N}_a{a}")
    qc.h(count)
    qc.x(work[0])
    for j, cq in enumerate(count):
        factor = pow(a, 1 << j, N)
        qc.append(_controlled_modmul_gate(factor, N, n_work), [cq, *work])
    _inverse_qft(qc, count)
    qc.measure(count, range(n_count))
    return qc


def _shor_dims(N: int) -> tuple[int, int]:
    """(counting qubits, work qubits). The counting register is kept as small as
    continued-fraction recovery allows so the demo runs in seconds rather than
    the textbook ``2 * n_work``."""
    n_work = max(1, N.bit_length())
    n_count = min(2 * n_work, n_work + 4)
    return n_count, n_work


def run_order_finding(
    a: int, N: int, n_count: int, n_work: int, *,
    shots: int = 256, seed: int = aer.DEFAULT_SEED,
) -> int:
    """Backward-compatible: most-frequent counting-register value on ideal Aer."""
    total = n_count + n_work
    if total > _SHOR_STATEVECTOR_MAX:
        raise ValueError(
            f"N={N} needs {total} qubits; the statevector Qiskit Shor path is "
            f"capped at {_SHOR_STATEVECTOR_MAX} (N<=15). Use engine='python', or "
            f"the /api/quantum/shor endpoint with backend='matrix'."
        )
    qc = build_order_finding_circuit(a, N, n_count, n_work)
    res = aer.run(qc, aer.make_backend("ideal", seed=seed), shots=shots, diagram=False)
    hist = _hist_to_int(res.counts)
    return max(hist, key=hist.get)


def _order_from_measurement(measured: int, n_count: int, N: int) -> int:
    return Fraction(measured, 1 << n_count).limit_denominator(N).denominator


def demo_shor(
    N: int, *, a: int = 2, mode: str = "ideal", shots: int = 1024,
    seed: int = aer.DEFAULT_SEED, attempts: int = 12, **noise,
) -> dict:
    """Full-payload Shor: run the circuit, recover the order and (when possible)
    the factors."""
    if N not in _ALLOWED_SHOR_N:
        raise ValueError(f"Shor demo supports N in {_ALLOWED_SHOR_N}; got {N}")
    if math.gcd(a, N) != 1:
        g = math.gcd(a, N)
        return {"algorithm": "shor", "N": N, "a": a, "mode": mode,
                "factors": sorted((g, N // g)), "order": None,
                "note": f"gcd({a},{N})={g} — factors found classically, no circuit run",
                "counts": {}, "shots": 0, "ops": {}, "n_qubits": 0}

    n_count, n_work = _shor_dims(N)
    total = n_count + n_work
    if total > _SHOR_MPS_MAX:
        raise ValueError(f"N={N} needs {total} qubits, beyond the {_SHOR_MPS_MAX} cap.")
    if total > _SHOR_STATEVECTOR_MAX and mode != "matrix":
        mode = "matrix"  # transparently fall back for the bigger circuits

    qc = build_order_finding_circuit(a, N, n_count, n_work)
    first = aer.run(qc, aer.make_backend(mode, seed=seed, **noise), shots=shots)

    order = None
    for k in range(attempts):
        if k == 0:
            res = first
        else:
            bk = aer.make_backend(mode, seed=seed + 1 + k, **noise)
            res = aer.run(qc, bk, shots=shots, diagram=False)
        hist = _hist_to_int(res.counts)
        # try the top few peaks, not only the mode
        for measured, _ in sorted(hist.items(), key=lambda kv: -kv[1])[:4]:
            r = _order_from_measurement(measured, n_count, N)
            if r and pow(a, r, N) == 1:
                order = r
                break
        if order:
            break

    factors: list[int] = []
    if order and order % 2 == 0:
        y = pow(a, order // 2, N)
        if y != N - 1:
            for cand in (math.gcd(y - 1, N), math.gcd(y + 1, N)):
                if 1 < cand < N and N % cand == 0:
                    factors = sorted({cand, N // cand})
                    break

    return {
        **first.to_dict(),
        "algorithm": "shor",
        "N": N,
        "a": a,
        "mode": mode,
        "counting_qubits": n_count,
        "work_qubits": n_work,
        "order": order,
        "order_verified": bool(order and pow(a, order, N) == 1),
        "factors": factors,
        "histogram": {str(k): v for k, v in sorted(_hist_to_int(first.counts).items())},
    }


def compare_shor(N: int, *, a: int = 2, shots: int = 1024, **noise) -> dict:
    """Run the *same* Shor circuit on the ideal and noisy backends and return
    both histograms — the visual that shows what noise costs."""
    mode = "matrix" if sum(_shor_dims(N)) > _SHOR_STATEVECTOR_MAX else "ideal"
    ideal = demo_shor(N, a=a, mode=mode, shots=shots)
    noisy_mode = "noisy" if mode == "ideal" else "matrix"  # MPS has no noise model here
    noisy = demo_shor(N, a=a, mode=noisy_mode, shots=shots, **noise)
    return {
        "N": N, "a": a, "shots": shots,
        "ideal": ideal,
        "noisy": noisy,
        "noise_applied": noisy_mode == "noisy",
        "note": ("N>15 runs on the MPS backend, which does not carry the "
                 "gate-noise model; the comparison then shows sampling spread only."
                 if noisy_mode != "noisy" else ""),
    }


# ---------------------------------------------------------------------------
# QRNG
# ---------------------------------------------------------------------------

def run_random_bits(n_bits: int, *, batch: int = 12, seed: int = aer.DEFAULT_SEED) -> list[int]:
    if n_bits <= 0:
        return []
    qc = QuantumCircuit(batch, batch, name="qrng")
    qc.h(range(batch))
    qc.measure(range(batch), range(batch))
    backend = aer.make_backend("ideal", seed=seed)
    shots = -(-n_bits // batch)
    memory = backend.run(qc, shots=shots, memory=True).result().get_memory()
    bits: list[int] = []
    for word in memory:
        bits.extend(int(c) for c in reversed(word))
    return bits[:n_bits]
