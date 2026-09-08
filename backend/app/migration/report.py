"""Renderings for a migration plan and result."""

from __future__ import annotations

from .plan import MigrationPlan
from .result import MigrationResult


def render_plan(p: MigrationPlan) -> str:
    lines = [
        f"Migration plan: {p.from_suite}  ->  {p.to_suite}"
        + ("   (no-op)" if p.is_noop else ""),
        f"  KEM:       {p.from_kem}  ->  {p.to_kem}",
        f"  signature: {p.from_sig}  ->  {p.to_sig}",
        f"  records affected: {p.record_count}",
        f"  retiring:  {p.threat_note}",
    ]
    return "\n".join(lines)


def render_result(r: MigrationResult) -> str:
    s = r.summary()
    before = ", ".join(f"{k}/{v}" for k, v in sorted(r.algorithms_before()))
    after = ", ".join(f"{k}/{v}" for k, v in sorted(r.algorithms_after()))
    ms = [rec.reseal_seconds * 1000 for rec in r.records] or [0.0]
    lines = [
        f"{s['from_suite']}  ->  {s['to_suite']}",
        f"  records:          {s['records']} "
        f"({s['records_changed']} changed algorithm)",
        f"  before:           {before}",
        f"  after:            {after}",
        f"  verified before:  {s['before_all_valid']}",
        f"  verified after:   {s['after_all_valid']}",
        f"  application code:  {'UNCHANGED' if not s['app_code_touched'] else 'MODIFIED'}",
        f"  re-seal time:     {s['reseal_seconds'] * 1000:.1f} ms total, "
        f"{sum(ms) / len(ms):.2f} ms/record",
    ]
    return "\n".join(lines)


def render_markdown(r: MigrationResult) -> str:
    s = r.summary()
    out = [
        f"# Migration: `{s['from_suite']}` -> `{s['to_suite']}`",
        "",
        f"- **Records:** {s['records']} ({s['records_changed']} changed algorithm)",
        f"- **Verified before / after:** {s['before_all_valid']} / {s['after_all_valid']}",
        f"- **Application code:** {'unchanged' if not s['app_code_touched'] else 'MODIFIED'}",
        f"- **Retiring:** {r.plan.threat_note}",
        "",
        "| Record | KEM before -> after | Signature before -> after | Re-seal |",
        "| --- | --- | --- | --: |",
    ]
    for rec in r.records:
        out.append(
            f"| {rec.record_id} | {rec.before_kem} -> {rec.after_kem} "
            f"| {rec.before_sig} -> {rec.after_sig} "
            f"| {rec.reseal_seconds * 1000:.2f} ms |"
        )
    return "\n".join(out)
