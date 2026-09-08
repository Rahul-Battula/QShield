"""Quantum random number generation.

A column of Hadamard gates measured in the computational basis produces
uniformly distributed bits from quantum measurement rather than a deterministic
algorithm. QShield runs this on the pure-Python simulator; because the simulator
itself samples with a seedable PRNG the output here is *not* cryptographically
strong — it demonstrates the construction. A real QRNG reads a hardware entropy
source; :func:`random_bytes` labels which source produced the bytes so the
distinction is never lost.

:func:`monobit_frequency_test` is the NIST SP 800-22 frequency (monobit) test,
included so the demo can show the output passing a basic randomness check.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass

from .simulator import Statevector

_SIM_SOURCE = "qshield-statevector-sim (seedable; demo only)"
_QISKIT_SOURCE = "qiskit-aer H|0> measurement (seeded; demo only)"
_OS_SOURCE = "os.urandom (OS CSPRNG)"


def quantum_random_bits(
    n_bits: int, *, seed: int | None = None, batch: int = 12, engine: str = "python"
) -> list[int]:
    """Generate ``n_bits`` bits by measuring ``H|0>`` on ``batch`` qubits at a
    time. ``engine="qiskit"`` runs it on Aer (requires the ``quantum`` extra)."""
    if n_bits <= 0:
        return []
    if engine == "qiskit":
        from .backend import require_qiskit
        require_qiskit()
        from . import qiskit_backend
        return qiskit_backend.run_random_bits(n_bits, batch=batch, seed=seed or 0)
    if engine != "python":
        raise ValueError(f"unknown engine {engine!r}; use 'python' or 'qiskit'")

    rng = random.Random(seed)
    out: list[int] = []
    qubits = list(range(batch))
    while len(out) < n_bits:
        sv = Statevector(batch)
        for q in qubits:
            sv.h(q)
        value = next(iter(sv.sample(qubits, 1, rng)))
        for pos in range(batch):
            out.append((value >> pos) & 1)
    return out[:n_bits]


@dataclass(frozen=True, slots=True)
class RandomBytes:
    data: bytes
    source: str
    monobit_p_value: float

    @property
    def looks_random(self) -> bool:
        return self.monobit_p_value >= 0.01


def random_bytes(
    n: int, *, quantum: bool = True, seed: int | None = None, engine: str = "python"
) -> RandomBytes:
    """Return ``n`` random bytes, from the quantum RNG (``quantum=True``, on the
    bundled simulator or, with ``engine="qiskit"``, on Aer) or the OS CSPRNG,
    with the monobit test p-value attached."""
    if quantum:
        bits = quantum_random_bits(n * 8, seed=seed, engine=engine)
        data = bytes(
            sum(bits[i * 8 + k] << k for k in range(8)) for i in range(n)
        )
        source = _QISKIT_SOURCE if engine == "qiskit" else _SIM_SOURCE
    else:
        data = os.urandom(n)
        bits = [(byte >> k) & 1 for byte in data for k in range(8)]
        source = _OS_SOURCE
    return RandomBytes(data, source, monobit_frequency_test(bits))


def monobit_frequency_test(bits: list[int]) -> float:
    """NIST SP 800-22 frequency (monobit) test. Returns a p-value; >= 0.01 is a
    pass. Needs at least ~100 bits to be meaningful."""
    if not bits:
        return 0.0
    s = sum(1 if b else -1 for b in bits)
    s_obs = abs(s) / math.sqrt(len(bits))
    return math.erfc(s_obs / math.sqrt(2))
