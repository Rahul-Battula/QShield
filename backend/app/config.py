"""Filesystem path resolution for QShield.

Nothing else in the codebase hardcodes a path. Every location is resolved here
and every location is overridable by an environment variable so that tests can
point at a temporary policy file and a throwaway database.
"""

from __future__ import annotations

import os
from pathlib import Path

# backend/app/config.py  ->  parents[2] == the repository root
_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    """Return the QShield repository root directory."""
    return _REPO_ROOT


def policy_path() -> Path:
    """Return the path to the active ``policy.yaml``.

    Overridable with the ``QSHIELD_POLICY`` environment variable, which the test
    suite uses to run against a temporary copy.
    """
    override = os.environ.get("QSHIELD_POLICY")
    return Path(override) if override else _REPO_ROOT / "policy.yaml"


def db_path() -> Path:
    """Return the path to the SQLite database file.

    Overridable with the ``QSHIELD_DB`` environment variable. Unused in Phase 1;
    defined here so later phases have a single place to ask.
    """
    override = os.environ.get("QSHIELD_DB")
    return Path(override) if override else _REPO_ROOT / "qshield.db"


def estate_root() -> Path:
    """Return the root of the mock government estate scanned by Phase 2 discovery.

    The mock estate is a deliberately vulnerable fixture — TLS configs pinned to
    old protocol versions, source that calls RSA and MD5, SSH configs that keep
    ``ssh-rsa`` — that gives the CBOM scanner something realistic to inventory.

    Overridable with the ``QSHIELD_ESTATE`` environment variable so the scanner
    can be pointed at a real tree or a test's temporary copy.
    """
    override = os.environ.get("QSHIELD_ESTATE")
    return Path(override) if override else _REPO_ROOT / "mock_estate"


def frontend_dir() -> Path:
    """Return the directory the API serves at ``/``.

    Prefers the built Vite dashboard (``frontend/dist``); falls back to the
    zero-build vendored dashboard (``frontend-legacy``) when it has not been
    built. Overridable with the ``QSHIELD_FRONTEND`` environment variable.
    """
    override = os.environ.get("QSHIELD_FRONTEND")
    if override:
        return Path(override)
    built = _REPO_ROOT / "frontend" / "dist"
    if (built / "index.html").exists():
        return built
    return _REPO_ROOT / "frontend-legacy"
