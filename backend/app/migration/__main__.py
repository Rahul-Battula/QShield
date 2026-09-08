"""``python -m app.migration`` / ``qshield-migrate`` — run a demo migration.

    qshield-migrate plan  <suite>
    qshield-migrate run   <suite> [--records N] [--rollback] [--format ...]

``run`` builds a demo land registry (Phase 5 app), seals ``N`` sample titles
under the current policy suite, migrates onto ``<suite>``, checks the
crypto-agility thesis held, and optionally rolls back. It edits ``policy.yaml``;
point ``QSHIELD_POLICY`` at a copy if you do not want that.
"""

from __future__ import annotations

import argparse
import json
import sys

from ..landrecords import demo_registry
from .engine import migrate, rollback
from .plan import MigrationPlanError, plan
from .report import render_markdown, render_plan, render_result


def _cmd_plan(args) -> int:
    reg = demo_registry(args.records, seed=args.seed)
    try:
        p = plan(reg, args.suite)
    except MigrationPlanError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(render_plan(p))
    return 0


def _cmd_run(args) -> int:
    reg = demo_registry(args.records, seed=args.seed)
    try:
        result = migrate(reg, args.suite)
    except MigrationPlanError as exc:
        print(exc, file=sys.stderr)
        return 2

    try:
        result.assert_thesis()
    except AssertionError as exc:
        print(f"THESIS VIOLATED: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(result.to_json())
    elif args.format == "markdown":
        print(render_markdown(result))
    else:
        print(render_result(result))

    if args.rollback:
        back = rollback(result, reg)
        back.assert_thesis()
        print("\n-- rolled back --")
        print(render_result(back) if args.format != "json" else back.to_json())

    return 0


def _cmd_waves(args) -> int:
    from ..discovery import scan_estate
    from ..risk import prioritise
    from .planner import plan_waves

    p = plan_waves(prioritise(scan_estate(), assessment_year=args.assessment_year))
    if args.format == "json":
        print(json.dumps(p, indent=2))
        return 0
    print(f"Phased migration plan: deadline {p['deadline']}, "
          f"{p['total_effort_years']} yr-equiv total effort\n")
    for w in p["waves"]:
        print(f"{w['name']}")
        print(f"  {w['start_date']} -> {w['target_date']}   {w['size']} findings   "
              f"{w['effort_years']} yr-equiv   removes {w['risk_reduction_pct']}% of risk")
        print(f"  target: {w['target_suite']}")
        for it in w["items"][:6]:
            flag = "  (OVERDUE)" if it["past_start_date"] else ""
            print(f"    - {it['detail']:22} {it['location']}{flag}")
        if w["size"] > 6:
            print(f"    ... and {w['size'] - 6} more")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qshield-migrate", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="describe a migration without running it")
    p_plan.add_argument("suite")
    p_plan.add_argument("--records", type=int, default=8)
    p_plan.add_argument("--seed", type=int, default=0)

    p_run = sub.add_parser("run", help="run a demo migration and check the thesis")
    p_run.add_argument("suite")
    p_run.add_argument("--records", type=int, default=8)
    p_run.add_argument("--seed", type=int, default=0)
    p_run.add_argument("--rollback", action="store_true")
    p_run.add_argument("--format", choices=("text", "markdown", "json"), default="text")

    p_waves = sub.add_parser("waves", help="phased migration plan (dated waves) for the estate")
    p_waves.add_argument("--assessment-year", type=int, default=None, dest="assessment_year")
    p_waves.add_argument("--format", choices=("text", "json"), default="text")

    args = parser.parse_args(argv)
    return {"plan": _cmd_plan, "run": _cmd_run, "waves": _cmd_waves}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
