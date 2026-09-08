"""QShield Phase 6 — the HTTP API and dashboard.

    python -m app.api

serves a JSON API over every phase (``/api/discovery``, ``/api/risk``,
``/api/threat``, ``/api/benchmark``, ``/api/migration/run``,
``/api/policy/active`` for a live hot-swap) and a single-page React dashboard
at ``/``.

:func:`create_app` returns the FastAPI application for embedding or testing.
"""

from __future__ import annotations

from .app import app, create_app

__all__ = ["app", "create_app"]
