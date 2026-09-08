"""``python -m app.threat`` / ``qshield-threat`` — the quantum threat engine.

    qshield-threat estimates                          # published cost catalogue
    qshield-threat estimate RSA-2048                  # one catalogue entry
    qshield-threat estate [ROOT] [--format ...]       # annotate a scanned estate
    qshield-threat demo shor  --N 15 --a 7
    qshield-threat demo grover --qubits 4 --target 11
    qshield-threat demo qrng  --bytes 32

The demos run on the pure-Python simulator and need nothing installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..agility.policy import load_policy
from ..discovery.scanner import scan_estate
from .engine import assess_estate
from .estimates import available_targets, estimate
from .grover import grover_search
from .qrng import random_bytes
from .report import render_estate_threats, render_estimate_table, render_markdown
from .shor import factor, order_finding


def _cmd_estimates(_args) -> int:
    print(render_estimate_table())
    return 0


def _cmd_estimate(args) -> int:
    try:
        e = estimate(args.target)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        print("known targets:", ", ".join(available_targets()), file=sys.stderr)
        return 2
    print(json.dumps(e.to_dict(), indent=2))
    return 0


def _cmd_estate(args) -> int:
    cbom = scan_estate(args.estate_root)
    et = assess_estate(cbom)
    try:
        crqc = load_policy().mosca.crqc_year()
    except Exception:
        crqc = None
    if args.format == "json":
        print(json.dumps(et.to_dict(), indent=2))
    elif args.format == "markdown":
        print(render_markdown(et, crqc_year=crqc))
    else:
        print(render_estate_threats(et, crqc_year=crqc))
    return 0


def _cmd_demo(args) -> int:
    engine = args.engine
    if args.kind == "shor":
        if args.factorise:
            r = factor(args.N, seed=args.seed, engine=engine)
            print(json.dumps({
                "engine": engine, "N": r.N, "factors": list(r.factors),
                "success": r.success, "witness_a": r.witness, "order": r.order,
            }, indent=2))
        else:
            r = order_finding(args.a, args.N, seed=args.seed, engine=engine)
            print(json.dumps({
                "engine": engine, "a": r.a, "N": r.N, "order": r.order,
                "verified": r.verified,
                "counting_qubits": r.counting_qubits, "work_qubits": r.work_qubits,
            }, indent=2))
        return 0
    if args.kind == "grover":
        res = grover_search(args.qubits, lambda v: v == args.target,
                            seed=args.seed, engine=engine)
        print(json.dumps({
            "engine": engine, "n_qubits": res.n_qubits, "iterations": res.iterations,
            "measured": res.measured, "target": args.target,
            "success_probability": round(res.success_probability, 4),
            "speedup_vs_classical": round(res.speedup, 2),
        }, indent=2))
        return 0
    if args.kind == "qrng":
        rb = random_bytes(args.bytes, quantum=not args.os, seed=args.seed, engine=engine)
        print(json.dumps({
            "engine": engine if not args.os else "os", "hex": rb.data.hex(),
            "source": rb.source,
            "monobit_p_value": round(rb.monobit_p_value, 4),
            "looks_random": rb.looks_random,
        }, indent=2))
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qshield-threat", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("estimates", help="print the published resource-estimate catalogue")

    p_est = sub.add_parser("estimate", help="print one catalogue entry")
    p_est.add_argument("target")

    p_state = sub.add_parser("estate", help="annotate a scanned estate with quantum threats")
    p_state.add_argument("estate_root", nargs="?", type=Path, default=None)
    p_state.add_argument("--format", choices=("text", "markdown", "json"), default="text")

    p_demo = sub.add_parser("demo", help="run a demonstration circuit")
    p_demo.add_argument("kind", choices=("shor", "grover", "qrng"))
    p_demo.add_argument("--engine", choices=("python", "qiskit"), default="python",
                        help="'python' = bundled simulator; 'qiskit' = real circuit on Aer")
    p_demo.add_argument("--N", type=int, default=15)
    p_demo.add_argument("--a", type=int, default=7)
    p_demo.add_argument("--factorise", action="store_true", help="shor: full factoring")
    p_demo.add_argument("--qubits", type=int, default=4)
    p_demo.add_argument("--target", type=int, default=11)
    p_demo.add_argument("--bytes", type=int, default=32)
    p_demo.add_argument("--os", action="store_true", help="qrng: use OS CSPRNG instead")
    p_demo.add_argument("--seed", type=int, default=0)

    args = parser.parse_args(argv)
    return {
        "estimates": _cmd_estimates,
        "estimate": _cmd_estimate,
        "estate": _cmd_estate,
        "demo": _cmd_demo,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
