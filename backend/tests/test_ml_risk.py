"""Phase 3 scikit-learn risk models — training, ranking, explanation, and the
``/api/risk/rank`` + ``/api/risk/explain`` endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.risk.ml import FEATURES, explain, rank, train


@pytest.fixture
def client(policy_file):
    return TestClient(create_app())


@pytest.fixture(scope="module")
def _trained():
    return train()


def _asset(**kw) -> dict:
    base = dict(
        asset_id="x", detail="RSA-2048",
        quantum_vulnerability_score=50, data_retention_years=10,
        network_exposure="internal", data_classification="internal",
        migration_effort=30, service_criticality=40, dependency_count=5,
    )
    base.update(kw)
    return base


def test_training_produces_usable_models(_trained):
    m = _trained["metrics"]
    assert m["regressor_r2"] > 0.8
    assert m["classifier_accuracy"] > 0.75
    imp = _trained["feature_importances"]
    assert set(imp) == set(FEATURES)
    # the harvest-now-decrypt-later story: these two dominate
    ranked = sorted(imp.items(), key=lambda kv: -kv[1])
    assert {ranked[0][0], ranked[1][0]} == {
        "quantum_vulnerability_score", "data_retention_years"
    }


def test_vulnerable_long_retention_outranks_safe_shortlived(_trained):
    urgent = _asset(quantum_vulnerability_score=90, data_retention_years=30,
                    network_exposure="public_internet", data_classification="confidential")
    benign = _asset(quantum_vulnerability_score=5, data_retention_years=3,
                    network_exposure="internal", data_classification="public")
    out = rank([urgent, benign])
    assert out[0]["priority_score"] > out[1]["priority_score"]
    assert out[0]["priority_band"] == "High"
    assert out[1]["priority_band"] == "Low"


def test_explanation_names_the_drivers(_trained):
    e = explain(_asset(quantum_vulnerability_score=95, data_retention_years=40))
    assert 0 <= e["score"] <= 100
    assert e["band"] in ("High", "Medium", "Low")
    assert len(e["contributions"]) == len(FEATURES)
    top = e["contributions"][0]
    assert "quantum_vulnerability_score" in {c["feature"] for c in e["contributions"][:2]}
    assert abs(top["contribution"]) >= abs(e["contributions"][-1]["contribution"])
    assert "priority" in e["summary"].lower()


def test_rank_is_ordered_and_numbered(_trained):
    out = rank([_asset(quantum_vulnerability_score=q) for q in (10, 90, 50, 30)])
    assert [r["rank"] for r in out] == [1, 2, 3, 4]
    assert [r["priority_score"] for r in out] == sorted(
        (r["priority_score"] for r in out), reverse=True
    )


def test_risk_rank_endpoint(client):
    r = client.get("/api/risk/rank?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(create_app_scan())
    assert 1 <= len(body["queue"]) <= 10
    assert body["model"]["metrics"]["regressor_r2"] > 0.8
    row = body["queue"][0]
    assert {"rank", "priority_score", "priority_band", "explanation", "asset_id"} <= set(row)


def test_risk_explain_endpoint(client):
    queue = client.get("/api/risk/rank?limit=1").json()["queue"]
    aid = queue[0]["asset_id"]
    e = client.get(f"/api/risk/explain/{aid}").json()
    assert e["asset_id"] == aid
    assert len(e["contributions"]) == len(FEATURES)
    assert client.get("/api/risk/explain/not-a-real-id").status_code == 404


def create_app_scan():
    from app.discovery import scan_estate
    return scan_estate().assets
