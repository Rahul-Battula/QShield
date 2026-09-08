"""The outcome of a migration: before/after algorithms per record, and the
checks that make the crypto-agility claim falsifiable."""

from __future__ import annotations

from dataclasses import dataclass

from .plan import MigrationPlan


class ThesisViolation(AssertionError):
    """A migration did not behave the way QShield claims migrations behave."""


@dataclass(frozen=True, slots=True)
class RecordMigration:
    record_id: str
    before_kem: str
    before_sig: str
    after_kem: str
    after_sig: str
    reseal_seconds: float

    @property
    def kem_changed(self) -> bool:
        return self.before_kem != self.after_kem

    @property
    def sig_changed(self) -> bool:
        return self.before_sig != self.after_sig

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "before": {"kem": self.before_kem, "sig": self.before_sig},
            "after": {"kem": self.after_kem, "sig": self.after_sig},
            "reseal_ms": round(self.reseal_seconds * 1000, 2),
        }


@dataclass(frozen=True, slots=True)
class MigrationResult:
    plan: MigrationPlan
    records: tuple[RecordMigration, ...] | list[RecordMigration]
    before_all_valid: bool
    after_all_valid: bool
    reseal_seconds: float
    app_code_touched: bool = False  # nothing in app.landrecords changed

    def algorithms_before(self) -> set[tuple[str, str]]:
        return {(r.before_kem, r.before_sig) for r in self.records}

    def algorithms_after(self) -> set[tuple[str, str]]:
        return {(r.after_kem, r.after_sig) for r in self.records}

    def changed_count(self) -> int:
        return sum(1 for r in self.records if r.kem_changed or r.sig_changed)

    def assert_thesis(self) -> MigrationResult:
        """Raise :class:`ThesisViolation` unless this migration upheld the
        crypto-agility claim."""
        if self.app_code_touched:
            raise ThesisViolation("application code was modified during migration")
        if not self.before_all_valid:
            raise ThesisViolation("records were already invalid before migration")
        if not self.after_all_valid:
            raise ThesisViolation("records did not all verify after migration")
        if not self.plan.is_noop and self.changed_count() != len(self.records):
            raise ThesisViolation(
                "policy changed suite but some records kept their algorithms"
            )
        if self.plan.is_noop and self.changed_count() != 0:
            raise ThesisViolation("no-op migration changed an algorithm")
        return self

    def summary(self) -> dict:
        return {
            "from_suite": self.plan.from_suite,
            "to_suite": self.plan.to_suite,
            "records": len(self.records),
            "records_changed": self.changed_count(),
            "algorithms_before": sorted(map(list, self.algorithms_before())),
            "algorithms_after": sorted(map(list, self.algorithms_after())),
            "before_all_valid": self.before_all_valid,
            "after_all_valid": self.after_all_valid,
            "app_code_touched": self.app_code_touched,
            "reseal_seconds": round(self.reseal_seconds, 4),
        }

    def to_dict(self) -> dict:
        return {
            "plan": self.plan.to_dict(),
            "summary": self.summary(),
            "records": [r.to_dict() for r in self.records],
        }

    def to_json(self, *, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent)
