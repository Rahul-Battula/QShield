"""Phase 4 acceptance tests — the quantum threat engine.

The demonstrations must actually run: Grover finds the marked state, Shor's
order-finding returns a verified order and factoring recovers the factors, the
QRNG passes a monobit test. All of this is on the bundled pure-Python
simulator, so the suite needs nothing installed. A few tests re-run the same
circuits on Qiskit when the optional extra is present.
"""

from __future__ import annotations

import math

import pytest

from app.discovery import scan_estate
from app.discovery.cbom import AssetKind, CryptoAsset, Exposure
from app.threat import (
    assess_estate,
    available_targets,
    estimate,
    estimate_for_primitive,
    explain_asset_threat,
    factor,
    grover_effective_bits,
    grover_search,
    monobit_frequency_test,
    order_finding,
    random_bytes,
    render_estate_threats,
    render_estimate_table,
    render_markdown,
)
from app.threat.simulator import Statevector, norm


def _asset(primitive, detail, exposure, *, kind=AssetKind.LIBRARY_CALL, key_bits=None):
    return CryptoAsset(
        kind=kind, primitive=primitive, detail=detail,
        location="x/y.py:1", evidence="e", detector="t",
        exposure=exposure, rationale="r", recommendation="rec", key_bits=key_bits,
    )


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

def test_bell_state_is_normalised_and_correlated():
    sv = Statevector(2)
    sv.h(0)
    sv.cx(0, 1)
    p = sv.probabilities()
    assert norm(sv) == pytest.approx(1.0)
    assert p[0b00] == pytest.approx(0.5)
    assert p[0b11] == pytest.approx(0.5)
    assert p[0b01] == p[0b10] == 0.0


@pytest.mark.parametrize("value", range(16))
def test_qft_then_inverse_qft_is_identity(value):
    sv = Statevector(4)
    for b in range(4):
        if (value >> b) & 1:
            sv.x(b)
    sv.qft([0, 1, 2, 3])
    sv.qft([0, 1, 2, 3], inverse=True)
    dist = sv.register_distribution([0, 1, 2, 3])
    assert max(dist, key=dist.get) == value
    assert dist[value] == pytest.approx(1.0, abs=1e-9)


def test_map_register_realises_modular_addition():
    sv = Statevector(3)
    sv.x(0)  # value 1
    sv.map_register([0, 1, 2], lambda v: (v + 5) % 8)
    assert sv.register_distribution([0, 1, 2]) == {6: pytest.approx(1.0)}


# ---------------------------------------------------------------------------
# Grover
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_qubits", [3, 4, 5])
def test_grover_finds_the_marked_state(n_qubits):
    target = (1 << n_qubits) - 2
    res = grover_search(n_qubits, lambda v: v == target, seed=1)
    assert res.measured == target
    assert res.success_probability > 0.9
    assert res.quantum_queries < res.classical_queries_avg


def test_grover_with_two_solutions():
    res = grover_search(4, lambda v: v in (3, 9), seed=2)
    assert res.measured in (3, 9)
    assert set(res.marked) == {3, 9}


def test_grover_effective_bits_halves_the_key():
    assert grover_effective_bits(128) == 64
    assert grover_effective_bits(256) == 128


def test_grover_rejects_an_unsatisfiable_predicate():
    with pytest.raises(ValueError):
        grover_search(3, lambda v: False)


# ---------------------------------------------------------------------------
# Shor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a,N,expected", [(7, 15, 4), (2, 15, 4), (4, 15, 2), (2, 21, 6)])
def test_order_finding_returns_a_verified_order(a, N, expected):
    res = order_finding(a, N, seed=1)
    assert res.order == expected
    assert res.verified
    assert pow(a, res.order, N) == 1


def test_order_finding_rejects_non_coprime_base():
    with pytest.raises(ValueError):
        order_finding(3, 15)


@pytest.mark.parametrize("N,factors", [(15, {3, 5}), (21, {3, 7})])
def test_shor_factoring_recovers_the_factors(N, factors):
    res = factor(N, seed=3)
    assert res.success
    assert set(res.factors) == factors
    assert math.prod(res.factors) == N


def test_shor_handles_even_and_perfect_power_shortcuts():
    assert set(factor(21 * 2).factors) == {2, 21}
    assert set(factor(49).factors) == {7}


# ---------------------------------------------------------------------------
# QRNG
# ---------------------------------------------------------------------------

def test_qrng_output_length_and_determinism_under_seed():
    a = random_bytes(32, seed=7)
    b = random_bytes(32, seed=7)
    assert len(a.data) == 32
    assert a.data == b.data          # seeded simulator sampler
    assert "sim" in a.source


def test_qrng_passes_monobit_and_os_source_labelled():
    rb = random_bytes(256, seed=1)
    assert rb.looks_random
    assert rb.monobit_p_value >= 0.01
    os_rb = random_bytes(64, quantum=False)
    assert "urandom" in os_rb.source


def test_monobit_flags_a_biased_stream():
    assert monobit_frequency_test([1] * 200) < 0.01
    assert monobit_frequency_test([0, 1] * 200) > 0.01


# ---------------------------------------------------------------------------
# Resource estimates
# ---------------------------------------------------------------------------

def test_estimate_catalogue_is_populated():
    assert "RSA-2048" in available_targets()
    e = estimate("RSA-2048")
    assert e.attack.startswith("Shor")
    assert e.physical_qubits > 1e6
    assert "Gidney" in e.source


def test_estimate_lookup_is_case_insensitive_and_reports_unknown():
    assert estimate("rsa-2048").target == "RSA-2048"
    with pytest.raises(KeyError):
        estimate("RSA-9999")


def test_estimate_for_primitive_picks_the_nearest_variant():
    assert estimate_for_primitive("RSA", 3072).target == "RSA-3072"
    assert estimate_for_primitive("RSA", 1100).target == "RSA-1024"
    assert estimate_for_primitive("ECDSA").target == "ECC-P256"
    assert estimate_for_primitive("AES", 256).target == "AES-256"
    assert estimate_for_primitive("ML-KEM") is None


# ---------------------------------------------------------------------------
# Engine — CBOM integration
# ---------------------------------------------------------------------------

def test_shor_family_is_flagged_broken_with_a_cost():
    t = explain_asset_threat(_asset("RSA", "RSA-2048", Exposure.QUANTUM_BROKEN,
                                    key_bits=2048))
    assert t.attack == "Shor"
    assert t.breaks_completely
    assert t.estimate.target == "RSA-2048"
    assert "polynomial time" in t.summary


def test_grover_family_is_weakened_not_broken():
    t = explain_asset_threat(_asset("AES", "AES-128", Exposure.QUANTUM_WEAKENED,
                                    key_bits=128))
    assert t.attack == "Grover"
    assert not t.breaks_completely


def test_classically_broken_primitive_is_not_attributed_to_a_quantum_attack():
    t = explain_asset_threat(_asset("MD5", "MD5", Exposure.CLASSICALLY_BROKEN))
    assert t.attack == "classical"
    assert "not required" in t.summary


def test_pqc_primitive_has_no_quantum_attack():
    t = explain_asset_threat(_asset("ML-KEM", "ML-KEM", Exposure.QUANTUM_SAFE))
    assert t.attack == "none"


def test_assess_estate_over_the_mock_estate():
    et = assess_estate(scan_estate())
    s = et.summary()
    assert s["assets"] == len(scan_estate().assets)
    assert s["shor_targets"] > 0
    assert s["classically_broken"] > 0
    assert sum((s["shor_targets"], s["grover_targets"],
                s["classically_broken"], s["unaffected"])) == s["assets"]


def test_threat_renderers_produce_output():
    et = assess_estate(scan_estate())
    assert "broken by Shor" in render_estate_threats(et, crqc_year=2035)
    md = render_markdown(et, crqc_year=2035)
    assert md.startswith("# Quantum threat assessment")
    assert "Horizon" in md
    table = render_estimate_table()
    assert "RSA-2048" in table and "PHYSICAL Q" in table


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_subcommands_run(capsys):
    from app.threat.__main__ import main

    assert main(["estimates"]) == 0
    assert main(["estimate", "RSA-2048"]) == 0
    assert main(["estate", "--format", "json"]) == 0
    assert main(["demo", "shor", "--N", "15", "--a", "7"]) == 0
    assert main(["demo", "grover", "--qubits", "3", "--target", "5"]) == 0
    assert main(["demo", "qrng", "--bytes", "8"]) == 0
    out = capsys.readouterr().out
    assert "RSA-2048" in out


def test_cli_unknown_estimate_target_exits_nonzero():
    from app.threat.__main__ import main

    assert main(["estimate", "NOPE-1"]) == 2


# ---------------------------------------------------------------------------
# Qiskit engine — runs the same demonstrations as real circuits on Aer.
# Skipped unless the optional `quantum` extra is installed.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _qiskit():
    pytest.importorskip("qiskit")
    pytest.importorskip("qiskit_aer")


def test_engine_argument_is_validated():
    with pytest.raises(ValueError):
        grover_search(3, lambda v: v == 1, engine="banana")
    with pytest.raises(ValueError):
        order_finding(7, 15, engine="banana")


def test_qiskit_backend_unavailable_is_explicit(monkeypatch):
    import app.threat.backend as bk
    monkeypatch.setattr(bk, "qiskit_available", lambda: False)
    with pytest.raises(bk.QuantumBackendUnavailable):
        grover_search(3, lambda v: v == 1, engine="qiskit")


def test_qiskit_grover_finds_the_marked_state(_qiskit):
    py = grover_search(4, lambda v: v == 11, seed=1, engine="python")
    qk = grover_search(4, lambda v: v == 11, seed=1, engine="qiskit")
    assert qk.measured == 11 == py.measured
    assert qk.success_probability > 0.9
    assert qk.quantum_queries == py.quantum_queries


def test_qiskit_shor_order_finding_and_factoring(_qiskit):
    o = order_finding(7, 15, seed=2, engine="qiskit")
    assert o.order == 4 and o.verified
    f = factor(15, seed=3, engine="qiskit")
    assert f.success and set(f.factors) == {3, 5}


def test_qiskit_shor_rejects_N_beyond_its_ceiling(_qiskit):
    with pytest.raises(ValueError):
        order_finding(2, 21, engine="qiskit")  # python engine handles this one


def test_qiskit_qrng_produces_labelled_random_bytes(_qiskit):
    rb = random_bytes(64, seed=1, engine="qiskit")
    assert len(rb.data) == 64
    assert "qiskit" in rb.source
    assert rb.looks_random
