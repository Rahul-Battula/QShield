"""QShield Phase 6 — the benchmark harness.

Times keygen, encapsulate/decapsulate and sign/verify for every suite in
``policy.yaml`` and records the byte sizes, so the cost of each migration
target is visible rather than assumed. Suites with a component that cannot run
here are reported with published reference sizes and no fabricated timings.

    from app.benchmark import run_all, render_text

    print(render_text(run_all(iterations=50)))
"""

from __future__ import annotations

from .harness import benchmark_suite, run_all
from .models import BenchmarkReport, OpTiming, SizeProfile, SuiteBenchmark
from .report import render_markdown, render_text

__all__ = [
    "BenchmarkReport",
    "OpTiming",
    "SizeProfile",
    "SuiteBenchmark",
    "benchmark_suite",
    "render_markdown",
    "render_text",
    "run_all",
]
