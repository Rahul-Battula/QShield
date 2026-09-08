"""Shared fixtures.

``policy_file`` gives each test its own writable copy of the real
``policy.yaml``. The copy is pointed at through the ``QSHIELD_POLICY``
environment variable (see :mod:`app.config`), and the agility registry is
reloaded before and after the test so nothing leaks between tests.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def policy_file(tmp_path: Path):
    """Yield a path to a temporary, writable copy of ``policy.yaml``."""
    source = _REPO_ROOT / "policy.yaml"
    working = tmp_path / "policy.yaml"
    shutil.copy(source, working)

    previous = os.environ.get("QSHIELD_POLICY")
    os.environ["QSHIELD_POLICY"] = str(working)

    from app.agility import reload

    reload()
    try:
        yield working
    finally:
        if previous is None:
            os.environ.pop("QSHIELD_POLICY", None)
        else:
            os.environ["QSHIELD_POLICY"] = previous
        reload()
