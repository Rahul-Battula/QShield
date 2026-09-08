"""QShield Phase 4 — the quantum threat engine.

Two halves:

* **Demonstrations that run.** Shor's order-finding and factoring
  (:mod:`.shor`), Grover search (:mod:`.grover`) and a quantum RNG
  (:mod:`.qrng`) execute for small parameters on either of two engines:
  ``engine="python"`` (default) — a pure-Python exact statevector simulator
  (:mod:`.simulator`), no dependencies, no build step — or ``engine="qiskit"``
  — real :class:`qiskit.QuantumCircuit` objects on Aer (:mod:`.qiskit_backend`,
  needs the optional ``quantum`` extra).
* **Numbers that matter.** :mod:`.estimates` carries the published
  surface-code resource estimates for breaking real primitives (RSA-2048,
  ECC-P256, AES-128, ...) as the cited authors' figures.

:mod:`.engine` joins these to a Phase 2 CBOM: for each finding it names the
attack (Shor or Grover), attaches the published cost, and cross-checks the
``policy.yaml`` Mosca horizon against what the estimates imply.

    from app.discovery import scan_estate
    from app.threat import assess_estate, render_estate_threats

    et = assess_estate(scan_estate())
    print(render_estate_threats(et))
"""

from __future__ import annotations

from .backend import QuantumBackendUnavailable, qiskit_available
from .engine import (
    AssetThreat,
    EstateThreat,
    assess_estate,
    explain_asset_threat,
    horizon_commentary,
)
from .estimates import (
    ResourceEstimate,
    available_targets,
    estimate,
    estimate_for_primitive,
)
from .grover import GroverResult, grover_effective_bits, grover_search
from .qrng import RandomBytes, monobit_frequency_test, quantum_random_bits, random_bytes
from .report import render_estate_threats, render_estimate_table, render_markdown
from .shor import FactorResult, OrderResult, factor, order_finding
from .simulator import Statevector

__all__ = [
    "AssetThreat",
    "EstateThreat",
    "FactorResult",
    "GroverResult",
    "OrderResult",
    "QuantumBackendUnavailable",
    "RandomBytes",
    "ResourceEstimate",
    "Statevector",
    "assess_estate",
    "available_targets",
    "estimate",
    "estimate_for_primitive",
    "explain_asset_threat",
    "factor",
    "grover_effective_bits",
    "grover_search",
    "horizon_commentary",
    "monobit_frequency_test",
    "order_finding",
    "qiskit_available",
    "quantum_random_bits",
    "random_bytes",
    "render_estate_threats",
    "render_estimate_table",
    "render_markdown",
]
