"""``python -m app.benchmark`` / ``qshield-bench`` — time every suite.

    qshield-bench                              # all suites, text table
    qshield-bench --iterations 100 --format markdown
    qshield-bench --suites classical,hybrid,pqc --format json
"""

from __future__ import annotations

import argparse
import sys

from .harness import run_all
from .report import render_markdown, render_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qshield-bench", description=__doc__)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--suites", default=None,
                        help="comma-separated subset (default: every suite in policy)")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    args = parser.parse_args(argv)

    suites = [s.strip() for s in args.suites.split(",")] if args.suites else None
    try:
        report = run_all(suites, iterations=args.iterations)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.format == "json":
        print(report.to_json())
    elif args.format == "markdown":
        print(render_markdown(report))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
