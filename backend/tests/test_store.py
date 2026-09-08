"""SQLite scan history and the /api/scan · /api/cbom · export endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import store
from app.api import create_app
from app.discovery import scan_estate


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("QSHIELD_DB", str(tmp_path / "scans.db"))
    return tmp_path / "scans.db"


@pytest.fixture
def client(policy_file, db):
    return TestClient(create_app())


def test_save_and_reload_roundtrips(db):
    cbom = scan_estate()
    sid = store.save_scan(cbom, "mock")
    assert sid == 1
    back = store.latest_cbom()
    assert back["summary"]["total"] == len(cbom.assets)
    assert len(store.list_scans()) == 1


def test_scan_endpoint_persists(client):
    r = client.post("/api/scan", json={})
    assert r.status_code == 200
    assert r.json()["scan_id"] == 1
    assert r.json()["summary"]["total"] > 20
    assert client.get("/api/scans").json()["scans"][0]["asset_count"] > 20


def test_cbom_endpoint_scans_on_first_call_then_persists(client):
    first = client.get("/api/cbom").json()
    assert first["assets"] and first["filtered"] == len(first["assets"])
    # a second call reads the persisted copy (same generated_at)
    assert client.get("/api/cbom").json()["generated_at"] == first["generated_at"]


def test_cbom_filters(client):
    client.post("/api/scan", json={})
    broken = client.get("/api/cbom?exposure=CLASSICALLY_BROKEN").json()
    assert broken["filtered"] < broken["summary"]["total"]
    assert all(a["exposure"] == "CLASSICALLY_BROKEN" for a in broken["assets"])
    lr = client.get("/api/cbom?system=land-registry").json()
    assert lr["assets"] and all(a["location"].startswith("land-registry/") for a in lr["assets"])


def test_export_json_and_csv(client):
    client.post("/api/scan", json={})
    j = client.get("/api/cbom/export?format=json")
    assert j.status_code == 200 and "attachment" in j.headers["content-disposition"]

    csv = client.get("/api/cbom/export?format=csv")
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    lines = csv.text.splitlines()
    assert lines[0].startswith("asset_id,kind,primitive")
    assert len(lines) - 1 == client.get("/api/cbom").json()["summary"]["total"]


def test_scan_bad_path_is_400(client):
    r = client.post("/api/scan", json={"path": "/no/such/dir/anywhere"})
    assert r.status_code == 400
