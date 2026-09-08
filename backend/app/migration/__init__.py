"""QShield Phase 5 — the migration engine.

Turns "change one line of ``policy.yaml``" into an executed, verified migration
of a running application's stored data, and proves the crypto-agility claim by
checking that the application itself was never touched.

    from app.landrecords import demo_registry
    from app.migration import migrate, rollback

    reg = demo_registry(20)                       # sealed under the active suite
    result = migrate(reg, "pqc").assert_thesis()  # now on ML-KEM-768 / ML-DSA-65
    rollback(result, reg).assert_thesis()         # and back again

The subject is :mod:`app.landrecords`, a small land registry that seals and
opens titles through the ``app.agility`` facades and nothing else.
"""

from __future__ import annotations

from .engine import migrate, rollback
from .plan import MigrationPlan, MigrationPlanError, plan
from .report import render_markdown, render_plan, render_result
from .result import MigrationResult, RecordMigration, ThesisViolation

__all__ = [
    "MigrationPlan",
    "MigrationPlanError",
    "MigrationResult",
    "RecordMigration",
    "ThesisViolation",
    "migrate",
    "plan",
    "render_markdown",
    "render_plan",
    "render_result",
    "rollback",
]
