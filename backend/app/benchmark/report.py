"""Renderings for a :class:`~app.benchmark.models.BenchmarkReport`."""

from __future__ import annotations

from .models import BenchmarkReport, SuiteBenchmark


def _cell(v, unit: str = "") -> str:
    if v is None:
        return "-"
    return f"{v:.2f}{unit}" if isinstance(v, float) else f"{v}{unit}"


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(str(c))) for w, c in zip(widths, row, strict=False)]

    def fmt(cols: tuple[str, ...]) -> str:
        return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths, strict=False))

    return [fmt(headers), "  ".join("-" * w for w in widths)] + [fmt(r) for r in rows]


def render_text(report: BenchmarkReport) -> str:
    base = report.baseline()
    base_hs = base.handshake_ms() if base else None

    timing_rows: list[tuple[str, ...]] = []
    for s in report.suites:
        t = s.timings
        hs = s.handshake_ms()
        timing_rows.append((
            s.suite,
            "yes" if s.live else "REF",
            _cell(t["kem_keygen"].median_ms) if s.live else "-",
            _cell(t["encapsulate"].median_ms) if s.live else "-",
            _cell(t["decapsulate"].median_ms) if s.live else "-",
            _cell(t["sign"].median_ms) if s.live else "-",
            _cell(t["verify"].median_ms) if s.live else "-",
            _cell(hs) if hs is not None else "-",
            f"{hs / base_hs:.2f}x" if hs and base_hs else "-",
        ))
    size_rows: list[tuple[str, ...]] = [
        (s.suite, _cell(s.sizes.kem_public), _cell(s.sizes.ciphertext),
         _cell(s.sizes.sig_public), _cell(s.sizes.signature))
        for s in report.suites
    ]

    out = [
        f"QShield benchmark: {report.iterations} iterations, "
        f"{report.machine['implementation']} {report.machine['python']} on "
        f"{report.machine['platform']}",
        "",
        "Timings (median ms per op):",
        *_table(
            ("SUITE", "LIVE", "KEMgen", "ENCAPS", "DECAPS", "SIGN", "VERIFY",
             "HANDSHAKE", "vs classical"),
            timing_rows,
        ),
        "",
        "Sizes (bytes):",
        *_table(("SUITE", "KEM PUB", "CIPHERTEXT", "SIG PUB", "SIGNATURE"), size_rows),
        "",
        "REF rows are published reference sizes, not measured here.",
    ]
    return "\n".join(out)


def _md_ms(s: SuiteBenchmark, op: str) -> str:
    return f"{s.timings[op].median_ms:.2f}" if s.live else "–"


def render_markdown(report: BenchmarkReport) -> str:
    base = report.baseline()
    base_hs = base.handshake_ms() if base else None
    out = [
        "# QShield benchmark",
        "",
        f"- **Iterations:** {report.iterations}",
        f"- **Machine:** {report.machine['implementation']} "
        f"{report.machine['python']}, {report.machine['platform']}",
        "",
        "| Suite | Live | KEM keygen | Encaps | Decaps | Sign | Verify "
        "| Handshake | vs classical | KEM pub | Ciphertext | Sig pub | Signature |",
        "| --- | :-: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |",
    ]
    for s in report.suites:
        z = s.sizes
        hs = s.handshake_ms()
        out.append(
            f"| `{s.suite}` | {'yes' if s.live else 'ref'} "
            f"| {_md_ms(s, 'kem_keygen')} | {_md_ms(s, 'encapsulate')} "
            f"| {_md_ms(s, 'decapsulate')} | {_md_ms(s, 'sign')} | {_md_ms(s, 'verify')} "
            f"| {f'{hs:.2f}' if hs is not None else '–'} "
            f"| {f'{hs / base_hs:.2f}×' if hs and base_hs else '–'} "
            f"| {z.kem_public or '–'} | {z.ciphertext or '–'} "
            f"| {z.sig_public or '–'} | {z.signature or '–'} |"
        )
    out += ["", "_Timings are indicative wall-clock medians; `ref` rows are "
            "published sizes, not measured here._"]
    return "\n".join(out)
