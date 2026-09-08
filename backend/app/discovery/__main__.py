"""``python -m app.discovery`` / ``qshield-discover`` — scan an estate.

    qshield-discover [ESTATE_ROOT] [--format table|markdown|json]
                     [--fail-on-vulnerable]

With no path it scans :func:`app.config.estate_root` (the bundled mock
estate). ``--fail-on-vulnerable`` exits non-zero when anything classically
broken or quantum-broken is present, which is what a CI gate wants.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .report import render
from .scanner import scan_estate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qshield-discover", description=__doc__)
    parser.add_argument("estate_root", nargs="?", type=Path, default=None,
                        help="directory to scan (default: the bundled mock estate)")
    parser.add_argument("--format", choices=("table", "markdown", "json"),
                        default="table")
    parser.add_argument("--fail-on-vulnerable", action="store_true",
                        help="exit 1 if any classically-broken or quantum-broken "
                             "asset is found")
    args = parser.parse_args(argv)

    cbom = scan_estate(args.estate_root)
    print(render(cbom, args.format))

    if args.fail_on_vulnerable and cbom.urgent():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
