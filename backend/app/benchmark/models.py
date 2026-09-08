"""Result types for the benchmark harness.

A benchmark is only useful if it is honest about what it measured. Every
:class:`SuiteBenchmark` records whether its numbers were *measured on this
machine* (``live``) or are *published reference sizes* for an algorithm that
cannot run here (a ``REFERENCE_ONLY`` provider with no ``liboqs`` backend). The
two are never silently mixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class OpTiming:
    """Timing for one operation over many iterations, milliseconds."""

    op: str
    iterations: int
    min_ms: float
    median_ms: float
    mean_ms: float
    p95_ms: float

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "iterations": self.iterations,
            "min_ms": round(self.min_ms, 4),
            "median_ms": round(self.median_ms, 4),
            "mean_ms": round(self.mean_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
        }


@dataclass(frozen=True, slots=True)
class SizeProfile:
    """On-the-wire and at-rest sizes in bytes; ``None`` where not applicable or
    not known."""

    kem_public: int | None = None
    kem_private: int | None = None
    ciphertext: int | None = None
    shared_secret: int | None = None
    sig_public: int | None = None
    sig_private: int | None = None
    signature: int | None = None

    def to_dict(self) -> dict:
        return {
            "kem_public": self.kem_public,
            "kem_private": self.kem_private,
            "ciphertext": self.ciphertext,
            "shared_secret": self.shared_secret,
            "sig_public": self.sig_public,
            "sig_private": self.sig_private,
            "signature": self.signature,
        }


@dataclass(frozen=True, slots=True)
class SuiteBenchmark:
    suite: str
    kem_algorithm: str
    sig_algorithm: str
    live: bool
    sizes: SizeProfile
    timings: dict[str, OpTiming] = field(default_factory=dict)
    note: str = ""

    def handshake_ms(self) -> float | None:
        """Median cost of one full KEM + signature exchange (keygen once each,
        encapsulate, decapsulate, sign, verify). ``None`` when not measured."""
        if not self.live:
            return None
        need = ("kem_keygen", "encapsulate", "decapsulate",
                "sig_keygen", "sign", "verify")
        if not all(k in self.timings for k in need):
            return None
        return sum(self.timings[k].median_ms for k in need)

    def to_dict(self) -> dict:
        return {
            "suite": self.suite,
            "kem_algorithm": self.kem_algorithm,
            "sig_algorithm": self.sig_algorithm,
            "live": self.live,
            "note": self.note,
            "handshake_ms": (round(self.handshake_ms(), 4)
                             if self.handshake_ms() is not None else None),
            "sizes": self.sizes.to_dict(),
            "timings": {k: v.to_dict() for k, v in self.timings.items()},
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    generated_at: str
    machine: dict
    iterations: int
    message_bytes: int
    suites: list[SuiteBenchmark]

    def baseline(self) -> SuiteBenchmark | None:
        """The ``classical`` suite, if present — the "before" state a migration
        is measured against."""
        return next((s for s in self.suites if s.suite == "classical"), None)

    def to_dict(self) -> dict:
        base = self.baseline()
        base_hs = base.handshake_ms() if base else None
        out_suites = []
        for s in self.suites:
            d = s.to_dict()
            hs = s.handshake_ms()
            d["handshake_vs_classical"] = (
                round(hs / base_hs, 2) if hs and base_hs else None
            )
            out_suites.append(d)
        return {
            "generated_at": self.generated_at,
            "machine": self.machine,
            "iterations": self.iterations,
            "message_bytes": self.message_bytes,
            "suites": out_suites,
        }

    def to_json(self, *, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent)
