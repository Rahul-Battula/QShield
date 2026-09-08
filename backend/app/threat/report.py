"""Renderings for the Phase 4 threat engine."""

from __future__ import annotations

from .engine import EstateThreat, horizon_commentary
from .estimates import available_targets, estimate


def render_estimate_table() -> str:
    """The full published resource-estimate catalogue."""
    rows = []
    for name in available_targets():
        e = estimate(name)
        rows.append((
            e.target, e.attack.split(" ")[0],
            str(e.classical_security_bits),
            f"{e.logical_qubits:,}",
            f"{e.physical_qubits:.1e}",
            f"{e.runtime_hours:.1e}" if e.runtime_hours >= 1000 else f"{e.runtime_hours:g}",
        ))
    headers = ("TARGET", "ATTACK", "SEC-BITS", "LOGICAL Q", "PHYSICAL Q", "RUNTIME h")
    widths = [len(h) for h in headers]
    for r in rows:
        widths = [max(w, len(c)) for w, c in zip(widths, r)]

    def fmt(cols):
        return "  ".join(c.ljust(w) for c, w in zip(cols, widths))

    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines += [fmt(r) for r in rows]
    lines.append("")
    lines.append("Figures are the cited authors' estimates under their own cost "
                 "models; see app.threat.estimates for sources.")
    return "\n".join(lines)


def render_estate_threats(et: EstateThreat, *, crqc_year: int | None = None) -> str:
    s = et.summary()
    lines = [
        f"{s['assets']} assets: {s['shor_targets']} broken by Shor, "
        f"{s['grover_targets']} weakened by Grover, "
        f"{s['classically_broken']} already broken classically, "
        f"{s['unaffected']} unaffected.",
        "",
    ]
    for t in et.threats:
        if t.attack in ("none", "classical"):
            continue
        lines.append(f"[{t.attack:6}] {t.asset.detail:22} {t.asset.location}")
        lines.append(f"          {t.summary}")
    if crqc_year is not None:
        lines += ["", horizon_commentary(crqc_year)]
    return "\n".join(lines)


def render_markdown(et: EstateThreat, *, crqc_year: int | None = None) -> str:
    s = et.summary()
    out = [
        "# Quantum threat assessment",
        "",
        f"- **Assets analysed:** {s['assets']}",
        f"- **Broken by Shor:** {s['shor_targets']}  ·  "
        f"**Weakened by Grover:** {s['grover_targets']}  ·  "
        f"**Already broken classically:** {s['classically_broken']}  ·  "
        f"**Unaffected:** {s['unaffected']}",
        "",
        "## Findings",
        "",
        "| Attack | Primitive | Location | Consequence |",
        "| --- | --- | --- | --- |",
    ]
    for t in et.threats:
        if t.attack == "none":
            continue
        out.append(f"| {t.attack} | {t.asset.detail} | `{t.asset.location}` | {t.summary} |")
    if crqc_year is not None:
        out += ["", "## Horizon", "", horizon_commentary(crqc_year)]
    return "\n".join(out)
