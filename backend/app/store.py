"""A tiny SQLite scan history — stdlib ``sqlite3``, one table.

``POST /api/scan`` persists a CBOM here; ``GET /api/cbom`` reads the latest one
back, so the dashboard survives a page reload without re-scanning. This is not a
production datastore (see LIMITATIONS.md) — it is a single file at
:func:`app.config.db_path`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .config import db_path
from .discovery.cbom import CBOM

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    target       TEXT NOT NULL,
    asset_count  INTEGER NOT NULL,
    cbom_json    TEXT NOT NULL
);
"""


def _connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def save_scan(cbom: CBOM, target: str, *, path: Path | None = None) -> int:
    """Persist ``cbom`` and return the new scan id."""
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO scans (created_at, target, asset_count, cbom_json) "
            "VALUES (?, ?, ?, ?)",
            (datetime.now(UTC).isoformat(timespec="seconds"), target,
             len(cbom.assets), cbom.to_json(indent=0)),
        )
        return int(cur.lastrowid)


def latest_cbom(*, path: Path | None = None) -> dict | None:
    """The most recently persisted CBOM as a dict, or ``None`` if nothing has
    been scanned yet."""
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT cbom_json FROM scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return json.loads(row["cbom_json"]) if row else None


def list_scans(*, path: Path | None = None, limit: int = 50) -> list[dict]:
    """Scan history, newest first, metadata only."""
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, created_at, target, asset_count FROM scans "
            "ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
