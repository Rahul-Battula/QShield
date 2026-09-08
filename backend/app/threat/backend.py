"""Qiskit availability gate for the Phase 4 ``engine="qiskit"`` path.

Phase 4's demonstrations run on the pure-Python simulator in
:mod:`app.threat.simulator` by default and need nothing installed. Passing
``engine="qiskit"`` to :func:`~app.threat.grover_search`,
:func:`~app.threat.order_finding` / :func:`~app.threat.factor` or
:func:`~app.threat.random_bytes` instead builds real
:class:`qiskit.QuantumCircuit` objects and runs them on Aer — see
:mod:`app.threat.qiskit_backend`. That requires the optional ``quantum``
extra (``pip install -r requirements-qiskit.txt``).

This module never imports Qiskit at import time — only
:func:`qiskit_available` (an ``importlib`` probe) and :func:`require_qiskit` —
so the package stays import-clean without it.
"""

from __future__ import annotations

import importlib.util


class QuantumBackendUnavailable(RuntimeError):
    """Raised when a Qiskit-only path is requested but Qiskit is not installed."""


def qiskit_available() -> bool:
    """True if ``qiskit`` can be imported in this environment."""
    return importlib.util.find_spec("qiskit") is not None


def require_qiskit() -> None:
    if not qiskit_available():
        raise QuantumBackendUnavailable(
            "this path needs Qiskit; install it with "
            "`pip install -r requirements-qiskit.txt`"
        )
