"""Phase 6 acceptance tests — the benchmark harness.

The harness must measure live suites, must not fabricate timings for a suite it
cannot run, and must report reference sizes for the latter.
"""

from __future__ import annotations

import json

import pytest

from app.benchmark import benchmark_suite, render_markdown, render_text, run_all


def test_live_suite_is_measured(policy_file):
    b = benchmark_suite("classical", iterations=3)
    assert b.live is True
    assert set(b.timings) == {
        "kem_keygen", "encapsulate", "decapsulate", "sig_keygen", "sign", "verify"
    }
    for t in b.timings.values():
        assert t.median_ms > 0
        assert t.min_ms <= t.median_ms <= t.p95_ms
    assert b.sizes.kem_public and b.sizes.ciphertext and b.sizes.signature
    assert b.handshake_ms() > 0


def test_hybrid_suite_is_live_and_larger_than_classical(policy_file):
    classical = benchmark_suite("classical", iterations=3)
    hybrid = benchmark_suite("hybrid", iterations=3)
    assert hybrid.live
    assert hybrid.sizes.ciphertext > classical.sizes.ciphertext
    assert hybrid.sizes.signature > classical.sizes.signature


def test_reference_only_suite_has_sizes_but_no_timings(policy_file):
    b = benchmark_suite("code-based", iterations=3)  # HQC-192, no liboqs here
    assert b.live is False
    assert b.timings == {}
    assert b.handshake_ms() is None
    # HQC-192 published public-key size, from the reference metadata
    assert b.sizes.kem_public == 4522
    assert "REFERENCE_ONLY" in b.note


def test_unknown_suite_raises(policy_file):
    with pytest.raises(KeyError):
        benchmark_suite("does-not-exist")


def test_run_all_covers_every_policy_suite(policy_file):
    report = run_all(iterations=2)
    from app.agility.policy import load_policy

    assert {s.suite for s in report.suites} == set(load_policy().suites)
    assert report.baseline().suite == "classical"


def test_report_serialises_and_renders(policy_file):
    report = run_all(["classical", "hybrid", "code-based"], iterations=2)
    payload = json.loads(report.to_json())
    assert len(payload["suites"]) == 3
    hybrid = next(s for s in payload["suites"] if s["suite"] == "hybrid")
    assert hybrid["handshake_vs_classical"] is not None
    ref = next(s for s in payload["suites"] if s["suite"] == "code-based")
    assert ref["live"] is False and ref["handshake_vs_classical"] is None

    assert "Timings" in render_text(report)
    assert render_markdown(report).startswith("# QShield benchmark")


def test_cli_runs(policy_file, capsys):
    from app.benchmark.__main__ import main

    assert main(["--iterations", "2", "--suites", "classical,pqc"]) == 0
    assert main(["--iterations", "2", "--format", "json"]) == 0
    assert main(["--suites", "nope"]) == 2
    assert "classical" in capsys.readouterr().out
