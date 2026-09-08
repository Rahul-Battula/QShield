"""Phase 6 acceptance tests — the HTTP API and dashboard.

Each endpoint is a thin wrapper over a phase package; the tests check the wiring
and the shapes, and that the live hot-swap / migration endpoints actually move
the policy and move it back.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.api import create_app


@pytest.fixture
def client(policy_file):
    # policy_file points QSHIELD_POLICY at a temp copy, so the mutating
    # endpoints do not touch the repo's policy.yaml.
    return TestClient(create_app())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_policy_lists_suites_and_horizon(client):
    body = client.get("/api/policy").json()
    assert body["active_suite"] == "hybrid"
    assert "pqc" in body["suites"]
    assert body["mosca"]["crqc_year"] == body["mosca"]["presets"][body["mosca"]["active_preset"]]


def test_discovery_endpoint(client):
    body = client.get("/api/discovery").json()
    assert body["summary"]["total"] > 20
    assert body["assets"]


def test_risk_endpoint_accepts_assessment_year(client):
    body = client.get("/api/risk?assessment_year=2026").json()
    assert body["summary"]["assessment_year"] == 2026
    assert body["summary"]["bands"]["P1"] > 0
    assert body["work_packages"]


def test_threat_endpoints(client):
    body = client.get("/api/threat").json()
    assert body["summary"]["shor_targets"] > 0
    assert body["horizon"]
    est = client.get("/api/threat/estimates").json()
    assert any(t["target"] == "RSA-2048" for t in est["targets"])


@pytest.mark.parametrize("kind,check", [
    ("grover", lambda j: j["measured"] == j["target"]),
    ("shor", lambda j: j["order"] == 4 and j["verified"]),
    ("qrng", lambda j: len(j["hex"]) == 64 and j["looks_random"]),
])
def test_threat_demo(client, kind, check):
    r = client.post(f"/api/threat/demo/{kind}",
                    json={"qubits": 3, "target": 5, "N": 15, "a": 7, "n_bytes": 32})
    assert r.status_code == 200
    assert check(r.json())


def test_threat_demo_unknown_kind(client):
    assert client.post("/api/threat/demo/nope", json={}).status_code == 404


def test_benchmark_endpoint(client):
    body = client.get("/api/benchmark?iterations=2").json()
    suites = {s["suite"] for s in body["suites"]}
    assert "classical" in suites and "hybrid" in suites
    ref = next(s for s in body["suites"] if s["suite"] == "code-based")
    assert ref["live"] is False


def test_migration_endpoint_upholds_thesis_and_moves_policy(client):
    r = client.post("/api/migration/run", json={"to_suite": "pqc", "records": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["thesis_ok"] is True
    assert body["summary"]["algorithms_after"] == [["ML-KEM-768", "ML-DSA-65"]]
    # the hot-swap really happened
    assert client.get("/api/policy").json()["active_suite"] == "pqc"
    # and can be swapped back
    assert client.post("/api/policy/active", json={"suite": "hybrid"}).json()["active_suite"] == "hybrid"


def test_migration_endpoint_rejects_unknown_suite(client):
    assert client.post("/api/migration/run", json={"to_suite": "nope"}).status_code == 400


def test_policy_active_rejects_unknown_suite(client):
    assert client.post("/api/policy/active", json={"suite": "nope"}).status_code == 400


def test_dashboard_is_served(client):
    """The API serves the built Vite dashboard (frontend/dist), or the vendored
    frontend-legacy/ when it has not been built."""
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="root"' in r.text
    # every referenced /static asset resolves
    assets = re.findall(r'(?:src|href)="(/static/[^"]+)"', r.text)
    assert assets, "index.html references no /static asset"
    for path in assets:
        assert client.get(path).status_code == 200
    # nothing is pulled from a CDN at runtime
    assert "cdnjs" not in r.text and "unpkg" not in r.text


# --- crypto-agility endpoint surface (spec Component 4) -------------------

def test_agility_policy_and_demo(client):
    assert client.get("/api/agility/policy").json()["active_suite"] == "hybrid"
    d = client.post("/api/agility/demo").json()
    assert d["kem_roundtrip_ok"] and d["signature_verified"]
    assert d["kem_algorithm"] == "X25519+ML-KEM-768"


def test_agility_switch_reports_before_after(client):
    r = client.post("/api/agility/switch", json={"suite": "pqc"})
    assert r.status_code == 200
    body = r.json()
    assert body["from"] == "hybrid" and body["to"] == "pqc"
    assert body["application_code_changed"] is False
    assert body["before"]["sizes"]["ciphertext"] != body["after"]["sizes"]["ciphertext"]
    assert client.get("/api/agility/policy").json()["active_suite"] == "pqc"


def test_agility_switch_rejects_unknown(client):
    assert client.post("/api/agility/switch", json={"suite": "nope"}).status_code == 400
