"""The migration engine — a policy hot-swap plus a bulk re-seal, proven.

:func:`migrate` performs the whole operation:

1. verify every stored record under the current policy and decrypt it into
   memory (a re-encryption migration has to hold plaintext transiently);
2. edit ``policy.yaml``'s ``active_suite`` and call ``reload()`` — the one
   change that constitutes the migration;
3. generate a fresh key epoch for the new suite and re-seal every record from
   the held plaintext;
4. verify every record again and record the before/after algorithm for each.

No land-records code is edited or even imported differently between steps 1 and
3. :meth:`MigrationResult.assert_thesis` checks exactly that: the algorithms
changed, nothing in the application was touched, and every record still opens.

:func:`rollback` is just :func:`migrate` back to the original suite — a
migration is symmetric, which is the property that makes "when, not if" a
manageable prospect.
"""

from __future__ import annotations

from time import perf_counter

from ..agility import reload
from ..agility.policy import write_active_suite
from ..landrecords import LandRegistry
from .plan import plan
from .result import MigrationResult, RecordMigration


def migrate(registry: LandRegistry, to_suite: str) -> MigrationResult:
    """Migrate ``registry`` onto ``to_suite`` and return a full result."""
    the_plan = plan(registry, to_suite)

    before_verify = registry.verify_all()
    before_algos = {rid: registry.sealed(rid) for rid in registry.record_ids()}
    # Only records that verify can be carried across; a migration cannot recover
    # one that is already corrupt. ``before_all_valid`` below reflects the rest.
    plaintext = {
        rid: registry.open(rid) for rid, ok in before_verify.items() if ok
    }

    # -- the migration itself: one line of policy, then reload -------
    write_active_suite(to_suite)
    reload()
    registry.rekey()

    records: list[RecordMigration] = []
    t0 = perf_counter()
    for rid, record in plaintext.items():
        started = perf_counter()
        sealed = registry.replace(rid, record)
        records.append(RecordMigration(
            record_id=rid,
            before_kem=before_algos[rid].kem_algorithm,
            before_sig=before_algos[rid].sig_algorithm,
            after_kem=sealed.kem_algorithm,
            after_sig=sealed.sig_algorithm,
            reseal_seconds=perf_counter() - started,
        ))
    total = perf_counter() - t0

    after_verify = registry.verify_all()
    return MigrationResult(
        plan=the_plan,
        records=records,
        before_all_valid=all(before_verify.values()),
        after_all_valid=all(after_verify.values()),
        reseal_seconds=total,
    )


def rollback(result: MigrationResult, registry: LandRegistry) -> MigrationResult:
    """Undo ``result`` by migrating ``registry`` back to its original suite."""
    return migrate(registry, result.plan.from_suite)
