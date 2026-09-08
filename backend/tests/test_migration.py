"""Phase 5 acceptance test — the migration engine.

Claim: changing only ``policy.yaml`` and re-sealing migrates a running
application's entire data set to a different algorithm, reversibly, with the
application code untouched. :meth:`MigrationResult.assert_thesis` is the
falsifiable form of that claim; these tests drive it across several suite pairs.
"""

from __future__ import annotations

import json

import pytest

from app.landrecords import demo_registry
from app.migration import (
    MigrationPlanError,
    ThesisViolation,
    migrate,
    plan,
    rollback,
)
from app.migration.report import render_markdown, render_plan, render_result


def test_plan_describes_the_change(policy_file):
    reg = demo_registry(5)
    p = plan(reg, "pqc")
    assert (p.from_suite, p.to_suite) == ("hybrid", "pqc")
    assert p.from_kem == "X25519+ML-KEM-768"
    assert p.to_kem == "ML-KEM-768"
    assert p.record_count == 5
    assert "hybrid" in p.threat_note.lower() or "quantum-safe" in p.threat_note.lower()


def test_plan_rejects_unknown_suite(policy_file):
    with pytest.raises(MigrationPlanError):
        plan(demo_registry(1), "no-such-suite")


def test_migrate_hybrid_to_pqc_changes_every_record(policy_file):
    reg = demo_registry(8, seed=1)
    result = migrate(reg, "pqc")
    result.assert_thesis()

    assert result.before_all_valid and result.after_all_valid
    assert result.changed_count() == 8
    assert result.algorithms_before() == {("X25519+ML-KEM-768", "ECDSA-P256+ML-DSA-65")}
    assert result.algorithms_after() == {("ML-KEM-768", "ML-DSA-65")}
    assert result.app_code_touched is False
    # the registry really is usable on the new suite
    assert all(reg.verify_all().values())
    assert reg.open(reg.record_ids()[0]).parcel_id.startswith("AP-")


@pytest.mark.parametrize("target", ["classical", "classical-ecdh", "pqc", "pqc-high"])
def test_migrate_to_each_suite_upholds_the_thesis(policy_file, target):
    reg = demo_registry(4, seed=2)
    migrate(reg, target).assert_thesis()
    assert reg.current_suite == target
    assert all(reg.verify_all().values())


def test_round_trip_returns_to_the_original_algorithms(policy_file):
    reg = demo_registry(6, seed=4)
    original = reg.algorithms_in_use()

    forward = migrate(reg, "classical")
    forward.assert_thesis()
    assert reg.algorithms_in_use() == {("RSA-2048", "ECDSA-P256"): 6}

    back = rollback(forward, reg)
    back.assert_thesis()
    assert reg.algorithms_in_use() == original
    assert all(reg.verify_all().values())


def test_noop_migration_rotates_keys_without_changing_algorithms(policy_file):
    reg = demo_registry(3)
    ids = reg.record_ids()
    before_ct = {i: reg.sealed(i).kem_ciphertext for i in ids}

    result = migrate(reg, "hybrid")
    result.assert_thesis()
    assert result.plan.is_noop
    assert result.changed_count() == 0
    # keys were rotated: same algorithm, different ciphertext
    assert all(reg.sealed(i).kem_ciphertext != before_ct[i] for i in ids)


def test_thesis_violation_is_raised_when_records_start_invalid(policy_file):
    reg = demo_registry(2)
    import dataclasses
    rid = reg.record_ids()[0]
    reg._records[rid] = dataclasses.replace(reg.sealed(rid), owner="tamper")

    result = migrate(reg, "pqc")
    assert result.before_all_valid is False
    with pytest.raises(ThesisViolation):
        result.assert_thesis()


def test_data_survives_a_two_hop_migration(policy_file):
    reg = demo_registry(5, seed=9)
    plaintext_before = {i: reg.open(i) for i in reg.record_ids()}

    migrate(reg, "classical").assert_thesis()
    migrate(reg, "pqc-high").assert_thesis()

    for rid, original in plaintext_before.items():
        assert reg.open(rid) == original


def test_result_serialises(policy_file):
    reg = demo_registry(3)
    result = migrate(reg, "pqc")
    payload = json.loads(result.to_json())
    assert payload["summary"]["to_suite"] == "pqc"
    assert len(payload["records"]) == 3
    assert payload["records"][0]["before"]["kem"] == "X25519+ML-KEM-768"


def test_reports_render(policy_file):
    reg = demo_registry(3)
    p = plan(reg, "pqc")
    assert "hybrid  ->  pqc" in render_plan(p)
    result = migrate(reg, "pqc")
    text = render_result(result)
    assert "UNCHANGED" in text
    assert "ML-KEM-768/ML-DSA-65" in text
    md = render_markdown(result)
    assert md.startswith("# Migration:")


def test_cli_run_and_rollback(policy_file, capsys):
    from app.migration.__main__ import main

    assert main(["plan", "pqc"]) == 0
    assert main(["run", "pqc", "--records", "4", "--rollback"]) == 0
    out = capsys.readouterr().out
    assert "rolled back" in out
    assert main(["run", "nope"]) == 2
