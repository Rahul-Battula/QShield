"""Phased migration wave planner (spec Component 5)."""

from __future__ import annotations

import datetime

from fastapi.testclient import TestClient

from app.api import create_app
from app.discovery import scan_estate
from app.migration.planner import plan_waves
from app.risk import prioritise


def _plan():
    report = prioritise(scan_estate(), assessment_year=2026)
    return plan_waves(report, start=datetime.date(2026, 1, 15))


def test_waves_are_ordered_p1_first_with_spread_dates():
    p = _plan()
    assert p["waves"][0]["band"] == "P1"
    dates = [w["start_date"] for w in p["waves"]]
    assert dates == sorted(dates)
    assert p["waves"][0]["start_date"] == "2026-01-15"
    assert p["deadline"] > p["waves"][-1]["start_date"]


def test_p1_wave_removes_most_of_the_risk():
    p = _plan()
    p1 = next(w for w in p["waves"] if w["band"] == "P1")
    assert p1["risk_reduction_pct"] > 50
    assert sum(w["risk_reduction_pct"] for w in p["waves"]) <= 100.5


def test_config_changes_are_scheduled_before_code_within_a_wave():
    p = _plan()
    for w in p["waves"]:
        kinds = [it["kind"] for it in w["items"]]
        first_code = next((i for i, k in enumerate(kinds) if k == "LIBRARY_CALL"), len(kinds))
        last_config = max((i for i, k in enumerate(kinds)
                           if k in ("PROTOCOL_CONFIG", "TOKEN_CONFIG")), default=-1)
        assert last_config < first_code or first_code == len(kinds)


def test_every_finding_lands_in_exactly_one_wave():
    p = _plan()
    total = sum(w["size"] for w in p["waves"])
    assert total == p["total_findings"] == len(scan_estate().assets)


def test_effort_and_target_reported():
    p = _plan()
    assert p["total_effort_years"] > 0
    assert all(w["target_suite"] for w in p["waves"])


def test_plan_endpoint(policy_file):
    c = TestClient(create_app())
    body = c.get("/api/migration/plan?assessment_year=2026").json()
    assert len(body["waves"]) >= 1 and body["deadline"]
    mosca = c.get("/api/migration/mosca?assessment_year=2026").json()
    assert mosca["findings_past_start_date"] > 0
    assert mosca["worst_deficit_years"] > 0
