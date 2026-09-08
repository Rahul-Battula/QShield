"""Backend capability detection.

The registry asks this module one question — "what can this machine actually
run?" — and builds providers accordingly. The answer depends only on which
optional packages import successfully, never on a C build succeeding at request
time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BackendCapabilities:
    """A snapshot of the crypto backends available in this interpreter."""

    pure_python_mlkem: bool
    """``kyber-py`` importable — ML-KEM runs live."""

    pure_python_mldsa: bool
    """``dilithium-py`` importable — ML-DSA runs live."""

    liboqs: bool
    """``oqs`` (liboqs-python) importable — HQC and SLH-DSA run live."""

    liboqs_version: str | None = None
    liboqs_kems: tuple[str, ...] = field(default_factory=tuple)
    liboqs_sigs: tuple[str, ...] = field(default_factory=tuple)


def detect() -> BackendCapabilities:
    """Probe the interpreter for usable crypto backends. Never raises."""
    try:
        import kyber_py.ml_kem  # noqa: F401

        mlkem = True
    except Exception:
        mlkem = False

    try:
        import dilithium_py.ml_dsa  # noqa: F401

        mldsa = True
    except Exception:
        mldsa = False

    liboqs = False
    version: str | None = None
    kems: tuple[str, ...] = ()
    sigs: tuple[str, ...] = ()
    try:
        import oqs  # type: ignore

        liboqs = True
        try:
            version = str(oqs.oqs_version())
        except Exception:
            version = None
        try:
            kems = tuple(oqs.get_enabled_kem_mechanisms())
            sigs = tuple(oqs.get_enabled_sig_mechanisms())
        except Exception:
            kems, sigs = (), ()
    except Exception:
        liboqs = False

    return BackendCapabilities(
        pure_python_mlkem=mlkem,
        pure_python_mldsa=mldsa,
        liboqs=liboqs,
        liboqs_version=version,
        liboqs_kems=kems,
        liboqs_sigs=sigs,
    )
