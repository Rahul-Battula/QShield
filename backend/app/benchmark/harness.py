"""Measure every suite in the policy, honestly.

For a suite whose KEM and signature both run here, the harness times keygen,
encapsulate/decapsulate and sign/verify and records the real byte sizes. For a
suite with a ``REFERENCE_ONLY`` component it does not fabricate timings — it
fills in the published sizes from the provider's reference metadata and marks
the row ``live = False``.

The timings are wall-clock ``perf_counter`` samples with one warm-up iteration
discarded. They are indicative, not a controlled measurement: a pure-Python
ML-KEM will look worse here than a C implementation would, and the whole point
of showing them is to make that trade-off visible rather than hidden.
"""

from __future__ import annotations

import platform
import statistics
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter

from ..agility.interfaces import ProviderStatus
from ..agility.policy import Policy, load_policy
from ..agility.providers import build_kem, build_sig
from .models import BenchmarkReport, OpTiming, SizeProfile, SuiteBenchmark

_DEFAULT_ITERATIONS = 30
_DEFAULT_MESSAGE = b"land-record:AP-VZM-2026-000042"


def _machine() -> dict:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
    }


def _time_op(op: str, fn: Callable[[], object], iterations: int) -> OpTiming:
    fn()  # warm-up, discarded
    samples: list[float] = []
    for _ in range(iterations):
        start = perf_counter()
        fn()
        samples.append((perf_counter() - start) * 1000.0)
    samples.sort()
    p95 = samples[min(len(samples) - 1, round(0.95 * (len(samples) - 1)))]
    return OpTiming(
        op=op,
        iterations=iterations,
        min_ms=samples[0],
        median_ms=statistics.median(samples),
        mean_ms=statistics.fmean(samples),
        p95_ms=p95,
    )


def _reference_meta(provider):
    """Reference sizes for a provider that cannot run here, if it carries them
    (directly, or as the single non-live component of a composite)."""
    if getattr(provider, "meta", None) is not None:
        return provider.meta
    for component in getattr(provider, "components", []):
        if component.status is not ProviderStatus.LIVE:
            meta = _reference_meta(component)
            if meta is not None:
                return meta
    return None


def _kem_sizes(kem) -> tuple[int | None, int | None, int | None, int | None]:
    if kem.status is ProviderStatus.LIVE:
        kp = kem.generate_keypair()
        enc = kem.encapsulate(kp.public_key)
        return (len(kp.public_key), len(kp.private_key),
                len(enc.ciphertext), len(enc.shared_secret))
    meta = _reference_meta(kem)
    if meta is None:
        return (None, None, None, None)
    return (meta.public_key_bytes, meta.secret_key_bytes,
            meta.ciphertext_bytes, meta.shared_secret_bytes)


def _sig_sizes(sig, message: bytes) -> tuple[int | None, int | None, int | None]:
    if sig.status is ProviderStatus.LIVE:
        kp = sig.generate_keypair()
        sg = sig.sign(kp.private_key, message)
        return (len(kp.public_key), len(kp.private_key), len(sg.signature))
    meta = _reference_meta(sig)
    if meta is None:
        return (None, None, None)
    return (meta.public_key_bytes, meta.secret_key_bytes, meta.signature_bytes)


def benchmark_suite(
    suite_name: str,
    policy: Policy | None = None,
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    message: bytes = _DEFAULT_MESSAGE,
) -> SuiteBenchmark:
    """Benchmark one named suite without touching the active policy."""
    policy = policy or load_policy()
    if suite_name not in policy.suites:
        raise KeyError(f"no suite {suite_name!r} in policy")
    spec = policy.suites[suite_name]
    kem = build_kem(spec.kem)
    sig = build_sig(spec.sig)

    live = kem.status is ProviderStatus.LIVE and sig.status is ProviderStatus.LIVE
    kpub, kpriv, ct, ss = _kem_sizes(kem)
    spub, spriv, sglen = _sig_sizes(sig, message)
    sizes = SizeProfile(kpub, kpriv, ct, ss, spub, spriv, sglen)

    if not live:
        return SuiteBenchmark(
            suite=suite_name, kem_algorithm=spec.kem, sig_algorithm=spec.sig,
            live=False, sizes=sizes,
            note="REFERENCE_ONLY component: sizes are published figures, not "
                 "measured here; install requirements-liboqs.txt to benchmark it live",
        )

    kp = kem.generate_keypair()
    enc = kem.encapsulate(kp.public_key)
    skp = sig.generate_keypair()
    sg = sig.sign(skp.private_key, message)

    timings = {
        "kem_keygen": _time_op("kem_keygen", kem.generate_keypair, iterations),
        "encapsulate": _time_op("encapsulate", lambda: kem.encapsulate(kp.public_key), iterations),
        "decapsulate": _time_op("decapsulate", lambda: kem.decapsulate(kp.private_key, enc.ciphertext), iterations),
        "sig_keygen": _time_op("sig_keygen", sig.generate_keypair, iterations),
        "sign": _time_op("sign", lambda: sig.sign(skp.private_key, message), iterations),
        "verify": _time_op("verify", lambda: sig.verify(skp.public_key, message, sg.signature), iterations),
    }
    return SuiteBenchmark(
        suite=suite_name, kem_algorithm=spec.kem, sig_algorithm=spec.sig,
        live=True, sizes=sizes, timings=timings, note="",
    )


def run_all(
    suites: list[str] | None = None,
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    message: bytes = _DEFAULT_MESSAGE,
) -> BenchmarkReport:
    """Benchmark every suite in the policy (or the given subset)."""
    policy = load_policy()
    names = suites or list(policy.suites)
    return BenchmarkReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        machine=_machine(),
        iterations=iterations,
        message_bytes=len(message),
        suites=[benchmark_suite(n, policy, iterations=iterations, message=message)
                for n in names],
    )
