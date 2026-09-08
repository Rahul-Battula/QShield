"""Qiskit Lab — the Aer backend factory, resource projections, and the
``/api/quantum/*`` endpoints. Circuit tests skip without the ``quantum`` extra;
the resource estimator is pure Python and always runs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.threat import resource_estimate as re


@pytest.fixture
def client(policy_file):
    return TestClient(create_app())


@pytest.fixture(scope="module")
def _qiskit():
    pytest.importorskip("qiskit")
    pytest.importorskip("qiskit_aer")


# ---------------------------------------------------------------------------
# Resource projection (no Qiskit needed)
# ---------------------------------------------------------------------------

def test_rsa_projection_is_in_the_published_ballpark():
    p = re.estimate("RSA", 2048)
    assert p.attack.startswith("Shor")
    assert 3000 <= p.logical_qubits <= 9000        # cf. Gidney-Ekerå ~6200
    assert 1e6 <= p.physical_qubits <= 1e8         # cf. ~20M
    assert p.feasible_year and p.feasible_year > 2024
    assert "not a prediction" in p.to_dict()["disclaimer"].lower()


def test_lower_error_rate_needs_fewer_physical_qubits():
    hi = re.estimate("RSA", 2048, phys_error_rate=1e-3)
    lo = re.estimate("RSA", 2048, phys_error_rate=1e-4)
    assert lo.code_distance < hi.code_distance
    assert lo.physical_qubits < hi.physical_qubits


def test_ecc_breaks_with_fewer_qubits_than_rsa():
    assert re.estimate("ECC", 256).physical_qubits < re.estimate("RSA", 3072).physical_qubits


def test_aes128_grover_runtime_is_astronomically_long():
    p = re.estimate("AES", 128)
    assert p.attack.startswith("Grover")
    assert p.runtime_seconds > 3.15e7 * 1e6        # far more than a million years


def test_growth_curve_crosses_feasibility_once():
    gc = re.growth_curve("RSA", 2048)
    flags = [row["feasible"] for row in gc["series"]]
    assert any(flags) and flags == sorted(flags)  # monotonic: infeasible then feasible


def test_faster_growth_brings_the_year_forward():
    slow = re.estimate("RSA", 2048, annual_growth=1.3).feasible_year
    fast = re.estimate("RSA", 2048, annual_growth=2.0).feasible_year
    assert fast <= slow


def test_unknown_algorithm_rejected():
    with pytest.raises(ValueError):
        re.estimate("frobnicator", 256)


def test_estimate_endpoint(client):
    r = client.post("/api/quantum/estimate",
                    json={"algorithm": "RSA", "key_bits": 2048, "phys_error_rate": 1e-3})
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "RSA-2048"
    assert body["growth_curve"] and body["physical_qubits"] > 1e6


# ---------------------------------------------------------------------------
# Aer factory + circuits
# ---------------------------------------------------------------------------

def test_noise_model_degrades_grover(_qiskit):
    from app.threat import qiskit_backend as qb

    ideal = qb.demo_grover(4, mode="ideal")
    noisy = qb.demo_grover(4, mode="noisy")
    assert ideal["measured"] == ideal["target"]
    assert noisy["success_probability"] < ideal["success_probability"]
    # standard metrics present
    for k in ("backend", "n_qubits", "depth_pre_transpile", "depth_post_transpile",
              "ops", "wall_ms"):
        assert k in ideal


def test_grover_success_curve_rises_to_the_optimum(_qiskit):
    from app.threat import qiskit_backend as qb

    c = qb.grover_success_curve(3, mode="ideal")
    probs = [p["success_probability"] for p in c["curve"]]
    assert len(probs) == c["optimal_iterations"]
    assert probs[-1] > 0.9


@pytest.mark.parametrize("N,a,factors", [(15, 7, {3, 5}), (21, 2, {3, 7}), (35, 2, {5, 7})])
def test_demo_shor_recovers_factors(_qiskit, N, a, factors):
    from app.threat import qiskit_backend as qb

    r = qb.demo_shor(N, a=a)
    assert r["order_verified"]
    assert set(r["factors"]) == factors


def test_demo_shor_rejects_unsupported_N(_qiskit):
    from app.threat import qiskit_backend as qb

    with pytest.raises(ValueError):
        qb.demo_shor(33)


def test_compare_shor_returns_both_histograms(_qiskit):
    from app.threat import qiskit_backend as qb

    c = qb.compare_shor(15, a=7)
    assert c["ideal"]["histogram"] and c["noisy"]["histogram"]
    assert c["noise_applied"] is True


def test_quantum_endpoints(client, _qiskit):
    g = client.post("/api/quantum/grover", json={"n_bits": 4, "backend": "noisy"})
    assert g.status_code == 200 and "success_curve" in g.json()

    s = client.post("/api/quantum/shor", json={"N": 15, "a": 7})
    assert s.status_code == 200 and set(s.json()["factors"]) == {3, 5}

    s21 = client.post("/api/quantum/shor", json={"N": 21, "a": 2})
    assert s21.status_code == 200 and set(s21.json()["factors"]) == {3, 7}

    cmp = client.post("/api/quantum/compare", json={"N": 15, "a": 7})
    assert cmp.status_code == 200 and cmp.json()["ideal"]["factors"] == [3, 5]

    bad = client.post("/api/quantum/shor", json={"N": 33})
    assert bad.status_code == 400
