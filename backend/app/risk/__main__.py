"""``python -m app.risk`` / ``qshield-risk`` — rank an estate's migration.

    qshield-risk [ESTATE_ROOT] [--format table|markdown|json] [--top N]
                 [--assessment-year YYYY] [--fail-on-p1]

Scans the estate (Phase 2), then scores and clusters the findings (Phase 3)
against the ``mosca`` horizon in ``policy.yaml``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..discovery.scanner import scan_estate
from .prioritise import prioritise
from .report import render
from .scoring import PriorityBand


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qshield-risk", description=__doc__)
    parser.add_argument("estate_root", nargs="?", type=Path, default=None,
                        help="directory to scan (default: the bundled mock estate)")
    parser.add_argument("--format", choices=("table", "markdown", "json"),
                        default="table")
    parser.add_argument("--top", type=int, default=None,
                        help="show only the top N findings in the table")
    parser.add_argument("--assessment-year", type=int, default=None,
                        help="year to treat as 'now' (default: policy or current year)")
    parser.add_argument("--fail-on-p1", action="store_true",
                        help="exit 1 if any finding lands in band P1")
    args = parser.parse_args(argv)

    cbom = scan_estate(args.estate_root)
    report = prioritise(cbom, assessment_year=args.assessment_year)
    print(render(report, args.format, args.top))

    if args.fail_on_p1 and any(s.band is PriorityBand.P1 for s in report.scores):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
