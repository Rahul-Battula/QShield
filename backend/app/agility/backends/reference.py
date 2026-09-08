"""``REFERENCE_ONLY`` providers.

When a suite in ``policy.yaml`` names an algorithm that this machine cannot run
live (HQC or SLH-DSA with no ``liboqs`` backend), the registry still builds a
provider for it — one of these. It carries **published** parameter sizes so the
algorithm appears with real numbers in the CBOM, the risk model and the
benchmark tables, clearly flagged as not measured locally. Any attempt to
actually run it raises :class:`ProviderUnavailable`.

Being able to declare an algorithm you cannot yet run is a deliberate feature:
a crypto-agility layer must let an operator stage the *next* migration before
the backend for it exists.

All sizes below are in bytes and are transcribed from the cited primary
sources. Verify against the final NIST standards before relying on them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ProviderUnavailable
from ..interfaces import (
    Encapsulation,
    KEMProvider,
    KeyPair,
    ProviderStatus,
    SignatureProvider,
    SignatureResult,
)


@dataclass(frozen=True)
class ReferenceMeta:
    """Published sizes for an algorithm QShield cannot run on this machine."""

    public_key_bytes: int
    secret_key_bytes: int
    ciphertext_bytes: int | None
    signature_bytes: int | None
    shared_secret_bytes: int | None
    source: str
    note: str


# HQC — code-based KEM. Sizes from the HQC specification, Round-4 version
# (2023-04-30), Table "Sizes in bytes" (see https://pqc-hqc.org/). HQC was
# selected by NIST in March 2025; the draft FIPS is pending and final sizes
# may differ. Shared secret is 64 bytes (SHA3-512 output).
HQC_META: dict[str, ReferenceMeta] = {
    "HQC-128": ReferenceMeta(2249, 2305, 4433, None, 64,
                             "HQC specification, Round 4 (2023-04-30)",
                             "NIST-selected 2025; draft standard pending, verify on finalisation"),
    "HQC-192": ReferenceMeta(4522, 4586, 8978, None, 64,
                             "HQC specification, Round 4 (2023-04-30)",
                             "NIST-selected 2025; draft standard pending, verify on finalisation"),
    "HQC-256": ReferenceMeta(7245, 7317, 14421, None, 64,
                             "HQC specification, Round 4 (2023-04-30)",
                             "NIST-selected 2025; draft standard pending, verify on finalisation"),
}

# SLH-DSA — hash-based signatures. Sizes from FIPS 205 (final, August 2024),
# Table 2 "SLH-DSA parameter sets". The "s" ("small signature") variants are
# used here; the "f" ("fast") variants trade ~2x larger signatures for faster
# signing.
SLH_DSA_META: dict[str, ReferenceMeta] = {
    "SLH-DSA-SHA2-128s": ReferenceMeta(32, 64, None, 7856, None,
                                       "FIPS 205, Table 2 (August 2024)",
                                       "hash-based; slow signing is inherent, not an implementation limit"),
    "SLH-DSA-SHA2-192s": ReferenceMeta(48, 96, None, 16224, None,
                                       "FIPS 205, Table 2 (August 2024)",
                                       "hash-based; slow signing is inherent, not an implementation limit"),
    "SLH-DSA-SHA2-256s": ReferenceMeta(64, 128, None, 29792, None,
                                       "FIPS 205, Table 2 (August 2024)",
                                       "hash-based; slow signing is inherent, not an implementation limit"),
}


class ReferenceKEM(KEMProvider):
    """A declared-but-not-runnable KEM."""

    status = ProviderStatus.REFERENCE_ONLY

    def __init__(self, algorithm: str, meta: ReferenceMeta) -> None:
        self.algorithm = algorithm
        self.meta = meta

    def _unavailable(self) -> ProviderUnavailable:
        return ProviderUnavailable(
            f"{self.algorithm} is declared in policy but cannot run on this "
            f"machine: no liboqs backend. Published sizes are available for "
            f"planning (source: {self.meta.source}). Install "
            f"requirements-liboqs.txt to make it LIVE."
        )

    def generate_keypair(self) -> KeyPair:
        raise self._unavailable()

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        raise self._unavailable()

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        raise self._unavailable()


class ReferenceSig(SignatureProvider):
    """A declared-but-not-runnable signature algorithm."""

    status = ProviderStatus.REFERENCE_ONLY

    def __init__(self, algorithm: str, meta: ReferenceMeta) -> None:
        self.algorithm = algorithm
        self.meta = meta

    def _unavailable(self) -> ProviderUnavailable:
        return ProviderUnavailable(
            f"{self.algorithm} is declared in policy but cannot run on this "
            f"machine: no liboqs backend. Published sizes are available for "
            f"planning (source: {self.meta.source}). Install "
            f"requirements-liboqs.txt to make it LIVE."
        )

    def generate_keypair(self) -> KeyPair:
        raise self._unavailable()

    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        raise self._unavailable()

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        raise self._unavailable()
