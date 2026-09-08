"""Renderings of a :class:`~app.risk.prioritise.RiskReport`."""

from __future__ import annotations

from .prioritise import RiskReport


def _start_by(rs) -> str:
    y = rs.mosca.latest_safe_start_year
    if y <= rs.mosca.assessment_year:
        return "OVERDUE"
    return str(int(y))


def render_table(report: RiskReport, top: int | None = None) -> str:
    rows = []
    scores = report.scores if top is None else report.scores[:top]
    for rank, rs in enumerate(scores, start=1):
        rows.append((
            str(rank),
            f"{rs.score:.1f}",
            rs.band.value,
            rs.asset.detail,
            rs.system,
            rs.asset.location,
            _start_by(rs),
        ))
    headers = ("#", "SCORE", "BAND", "ALGORITHM", "SYSTEM", "LOCATION", "START BY")
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(c)) for w, c in zip(widths, row)]

    def fmt(cols):
        return "  ".join(c.ljust(w) for c, w in zip(cols, widths))

    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines += [fmt(r) for r in rows]

    s = report.summary()
    b = s["bands"]
    lines += [
        "",
        f"{s['assets_scored']} assets scored | "
        f"P1 {b['P1']}  P2 {b['P2']}  P3 {b['P3']}  P4 {b['P4']} | "
        f"{s['too_late']} past their Mosca start date | "
        f"horizon: CRQC {s['crqc_year']} ({s['preset']}), assessed {s['assessment_year']}",
    ]
    return "\n".join(lines)


def render_markdown(report: RiskReport) -> str:
    s = report.summary()
    b = s["bands"]
    out = [
        "# Post-quantum migration priorities",
        "",
        f"- **Estate:** `{report.estate_root}`",
        f"- **Horizon:** CRQC assumed {s['crqc_year']} (`{s['preset']}` preset), "
        f"assessed as of {s['assessment_year']}",
        f"- **Findings scored:** {s['assets_scored']} — "
        f"P1 {b['P1']}, P2 {b['P2']}, P3 {b['P3']}, P4 {b['P4']}",
        f"- **Past their Mosca start date:** {s['too_late']}",
        "",
        "## Ranked findings",
        "",
        "| # | Score | Band | Algorithm | System | Location | Start by |",
        "| --: | --: | --- | --- | --- | --- | --- |",
    ]
    for rank, rs in enumerate(report.scores, start=1):
        out.append(
            f"| {rank} | {rs.score:.1f} | {rs.band.value} | {rs.asset.detail} "
            f"| {rs.system} | `{rs.asset.location}` | {_start_by(rs)} |"
        )

    out += ["", "## Work packages", ""]
    for wp in report.work_packages:
        out += [
            f"### {wp.id} — {wp.title}",
            "",
            f"- **Top band:** {wp.top_band.value}  ·  "
            f"**Findings:** {wp.size}  ·  "
            f"**Est. effort:** {wp.total_migration_years:.1f} yr-equiv  ·  "
            f"**Max score:** {wp.max_score:.1f}",
            f"- **Systems:** {', '.join(wp.systems)}",
            f"- **Primitives:** {', '.join(wp.primitives)}",
            f"- **Targets:** {'; '.join(wp.recommended_targets)}",
            "",
        ]
        for m in wp.scores:
            out.append(f"  - `{m.asset.location}` — {m.asset.detail} "
                       f"({m.band.value}, {m.score:.1f})")
        out.append("")
    return "\n".join(out)


def render(report: RiskReport, fmt: str = "table", top: int | None = None) -> str:
    if fmt == "json":
        return report.to_json()
    if fmt == "markdown":
        return render_markdown(report)
    return render_table(report, top)
