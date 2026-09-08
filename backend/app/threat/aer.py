"""Shared Aer backend factory and run harness for the Qiskit engine.

Every Qiskit demonstration goes through :func:`make_backend` and :func:`run`
so that noise, method selection, transpilation and the reported metrics are
identical across Shor, Grover and the comparison endpoint.

Three modes:

* ``ideal``   — ``AerSimulator()``
* ``noisy``   — ``AerSimulator`` with a depolarizing + readout noise model
* ``matrix``  — ``AerSimulator(method="matrix_product_state")`` for the larger
  Shor circuits that exceed a laptop's statevector budget

All results are reproducible: :data:`DEFAULT_SEED` is passed as
``seed_simulator`` unless a caller overrides it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

DEFAULT_SEED = 20260907
MAX_SHOTS = 8192

# Noise-rate defaults (per the spec).
DEFAULT_P1 = 1e-3   # 1-qubit gate depolarizing
DEFAULT_P2 = 1e-2   # 2-qubit gate depolarizing
DEFAULT_RO = 2e-2   # readout error

_1Q_GATES = ("id", "rz", "sx", "x", "h", "ry", "rx")
_2Q_GATES = ("cx", "cz", "swap", "cp")


def build_noise_model(p1: float = DEFAULT_P1, p2: float = DEFAULT_P2,
                      readout: float = DEFAULT_RO) -> NoiseModel:
    """Depolarizing error on 1q and 2q gates plus a symmetric readout error."""
    nm = NoiseModel()
    if p1 > 0:
        nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), list(_1Q_GATES))
    if p2 > 0:
        nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), list(_2Q_GATES))
    if readout > 0:
        err = ReadoutError([[1 - readout, readout], [readout, 1 - readout]])
        nm.add_all_qubit_readout_error(err)
    return nm


def make_backend(
    mode: str = "ideal",
    *,
    p1: float = DEFAULT_P1,
    p2: float = DEFAULT_P2,
    readout: float = DEFAULT_RO,
    seed: int = DEFAULT_SEED,
) -> AerSimulator:
    """Return an :class:`AerSimulator` configured for ``mode``."""
    if mode == "ideal":
        return AerSimulator(seed_simulator=seed)
    if mode == "noisy":
        return AerSimulator(seed_simulator=seed,
                            noise_model=build_noise_model(p1, p2, readout))
    if mode == "matrix":
        return AerSimulator(method="matrix_product_state", seed_simulator=seed)
    raise ValueError(f"unknown backend mode {mode!r}; use ideal | noisy | matrix")


@dataclass(frozen=True, slots=True)
class RunResult:
    """The standard payload returned for every Qiskit execution."""

    counts: dict[str, int]
    shots: int
    backend: str
    n_qubits: int
    depth_pre_transpile: int
    depth_post_transpile: int
    ops: dict[str, int]
    wall_ms: float
    diagram: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "shots": self.shots,
            "backend": self.backend,
            "n_qubits": self.n_qubits,
            "depth_pre_transpile": self.depth_pre_transpile,
            "depth_post_transpile": self.depth_post_transpile,
            "ops": self.ops,
            "wall_ms": round(self.wall_ms, 2),
            "diagram": self.diagram,
            **self.extra,
        }


def run(
    qc: QuantumCircuit,
    backend: AerSimulator,
    *,
    shots: int = 1024,
    diagram: bool = True,
) -> RunResult:
    """Transpile ``qc`` to ``backend``'s basis, execute it, and collect metrics."""
    shots = max(1, min(int(shots), MAX_SHOTS))
    depth_pre = qc.depth()
    compiled = transpile(qc, backend, seed_transpiler=DEFAULT_SEED)

    started = time.perf_counter()
    result = backend.run(compiled, shots=shots).result()
    wall_ms = (time.perf_counter() - started) * 1000.0

    counts = result.get_counts()
    return RunResult(
        counts={k.replace(" ", ""): v for k, v in counts.items()},
        shots=shots,
        backend=backend.configuration().backend_name,
        n_qubits=qc.num_qubits,
        depth_pre_transpile=depth_pre,
        depth_post_transpile=compiled.depth(),
        ops={k: int(v) for k, v in compiled.count_ops().items()},
        wall_ms=wall_ms,
        diagram=_draw(qc) if diagram else "",
    )


def _draw(qc: QuantumCircuit, max_qubits: int = 14) -> str:
    """A text circuit diagram, guarded so a wide circuit does not blow up the
    payload."""
    if qc.num_qubits > max_qubits:
        return (f"[{qc.num_qubits} qubits, depth {qc.depth()} — diagram omitted; "
                f"see ops and metrics]")
    try:
        return str(qc.draw(output="text", fold=90))
    except Exception:  # pragma: no cover - drawing is best-effort
        return ""
