"""Human-readable renderings of a :class:`~app.discovery.cbom.CBOM`.

Three formats: a terminal table (default), Markdown (for pasting into a
migration plan or a PR), and JSON (:meth:`CBOM.to_json`, for Phase 3 to consume).
"""

from __future__ import annotations

from .cbom import CBOM, Exposure

_EXPOSURE_LABEL = {
    Exposure.CLASSICALLY_BROKEN: "BROKEN NOW",
    Exposure.QUANTUM_BROKEN: "QUANTUM-BROKEN",
    Exposure.QUANTUM_WEAKENED: "QUANTUM-WEAKENED",
    Exposure.QUANTUM_SAFE: "SAFE",
    Exposure.UNKNOWN: "UNKNOWN",
}


def render_table(cbom: CBOM) -> str:
    """A fixed-width table, most-urgent rows first."""
    rows = [
        (
            _EXPOSURE_LABEL[a.exposure],
            a.detail,
            a.kind.value,
            a.location,
        )
        for a in cbom.assets
    ]
    headers = ("EXPOSURE", "ALGORITHM", "KIND", "LOCATION")
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(c)) for w, c in zip(widths, row)]

    def fmt(cols: tuple[str, ...]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(cols, widths))

    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines += [fmt(r) for r in rows]

    s = cbom.summary()
    lines.append("")
    lines.append(
        f"{s['total']} assets: "
        f"{s['CLASSICALLY_BROKEN']} broken now, "
        f"{s['QUANTUM_BROKEN']} quantum-broken, "
        f"{s['QUANTUM_WEAKENED']} quantum-weakened, "
        f"{s['QUANTUM_SAFE']} safe, "
        f"{s['UNKNOWN']} unknown"
    )
    return "\n".join(lines)


def render_markdown(cbom: CBOM) -> str:
    """A Markdown document: summary line, table, then the rationale per asset."""
    s = cbom.summary()
    out = [
        "# Cryptographic Bill of Materials",
        "",
        f"- **Estate:** `{cbom.estate_root}`",
        f"- **Generated:** {cbom.generated_at}",
        f"- **Assets:** {s['total']} "
        f"({s['CLASSICALLY_BROKEN']} broken now, {s['QUANTUM_BROKEN']} quantum-broken, "
        f"{s['QUANTUM_WEAKENED']} quantum-weakened, {s['QUANTUM_SAFE']} safe, "
        f"{s['UNKNOWN']} unknown)",
        "",
        "| Exposure | Algorithm | Kind | Location | Recommendation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for a in cbom.assets:
        out.append(
            f"| {_EXPOSURE_LABEL[a.exposure]} | {a.detail} | {a.kind.value} "
            f"| `{a.location}` | {a.recommendation} |"
        )
    out.append("")
    out.append("## Rationale")
    out.append("")
    for a in cbom.assets:
        out.append(f"- **`{a.location}` — {a.detail}** ({_EXPOSURE_LABEL[a.exposure]}): "
                   f"{a.rationale}")
    return "\n".join(out)


def render(cbom: CBOM, fmt: str = "table") -> str:
    if fmt == "json":
        return cbom.to_json()
    if fmt == "markdown":
        return render_markdown(cbom)
    return render_table(cbom)
