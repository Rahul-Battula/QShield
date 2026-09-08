"""Policy loading and validation.

A misconfigured ``policy.yaml`` must fail at load time with a clear
:class:`PolicyError`, never silently or later at crypto time.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.agility import PolicyError, load_policy
from app.agility.policy import write_active_suite

VALID = textwrap.dedent(
    """
    version: 1
    active_suite: pqc
    suites:
      pqc:
        kem: ML-KEM-768
        sig: ML-DSA-65
      hybrid:
        kem: X25519+ML-KEM-768
        sig: ECDSA-P256+ML-DSA-65
    mosca:
      active_preset: likely
      presets:
        optimistic: 2030
        likely: 2035
        pessimistic: 2040
    """
).strip()


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_policy_loads(tmp_path):
    policy = load_policy(_write(tmp_path, VALID))
    assert policy.active_suite == "pqc"
    assert policy.active().kem == "ML-KEM-768"
    assert policy.mosca.presets["likely"] == 2035


def test_active_suite_must_exist(tmp_path):
    bad = VALID.replace("active_suite: pqc", "active_suite: nonexistent")
    with pytest.raises(PolicyError):
        load_policy(_write(tmp_path, bad))


def test_active_preset_must_exist(tmp_path):
    bad = VALID.replace("active_preset: likely", "active_preset: wishful")
    with pytest.raises(PolicyError):
        load_policy(_write(tmp_path, bad))


def test_missing_file_raises_policy_error(tmp_path):
    with pytest.raises(PolicyError):
        load_policy(tmp_path / "does-not-exist.yaml")


def test_malformed_yaml_raises_policy_error(tmp_path):
    with pytest.raises(PolicyError):
        load_policy(_write(tmp_path, "version: 1\n  active_suite: : :\n"))


def test_write_active_suite_rejects_unknown_suite(tmp_path):
    p = _write(tmp_path, VALID)
    with pytest.raises(PolicyError):
        write_active_suite("not-a-suite", p)


def test_write_active_suite_switches_and_reparses(tmp_path):
    p = _write(tmp_path, VALID)
    write_active_suite("hybrid", p)
    assert load_policy(p).active_suite == "hybrid"
