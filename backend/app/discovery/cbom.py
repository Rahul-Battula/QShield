"""The CBOM data model — a Cryptographic Bill of Materials.

A CBOM is to cryptography what an SBOM is to dependencies: a single inventory of
every place the estate uses a cryptographic primitive, where it is, and whether
a quantum computer breaks it. Phase 3 reads this inventory to prioritise the
migration; Phase 5 acts on it.

Nothing here performs detection or classification. :mod:`.detectors` finds raw
evidence, :mod:`.classify` decides the quantum exposure, and :mod:`.scanner`
assembles the pieces into the :class:`CBOM` defined here.
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime


class AssetKind(str, enum.Enum):
    """What sort of cryptographic object an asset is."""

    CERTIFICATE = "CERTIFICATE"
    PRIVATE_KEY = "PRIVATE_KEY"
    PUBLIC_KEY = "PUBLIC_KEY"
    PROTOCOL_CONFIG = "PROTOCOL_CONFIG"
    """A TLS/SSH/VPN setting that pins a protocol version, cipher or key exchange."""
    LIBRARY_CALL = "LIBRARY_CALL"
    """Source code invoking a crypto library (``rsa.generate_private_key`` ...)."""
    TOKEN_CONFIG = "TOKEN_CONFIG"
    """A JWT / SAML / signed-token algorithm selection."""


class Exposure(str, enum.Enum):
    """How a primitive fares against classical and quantum attackers.

    Ordered most to least urgent; :data:`SEVERITY` gives the numeric rank used
    for sorting and for the scanner's non-zero exit code.
    """

    CLASSICALLY_BROKEN = "CLASSICALLY_BROKEN"
    """Already unsafe without a quantum computer — MD5, SHA-1, DES, 3DES, RC4,
    TLS 1.0/1.1, SSLv3. Fix this regardless of the quantum timeline."""

    QUANTUM_BROKEN = "QUANTUM_BROKEN"
    """Shor's algorithm recovers the private key in polynomial time — every
    deployed public-key primitive: RSA, DSA, DH, ECDSA, ECDH, EdDSA, X25519."""

    QUANTUM_WEAKENED = "QUANTUM_WEAKENED"
    """Grover's algorithm halves the effective security level but does not break
    it — AES-128, SHA-256 used for its collision resistance. Usually a
    parameter bump, not an algorithm change."""

    QUANTUM_SAFE = "QUANTUM_SAFE"
    """No known quantum speed-up beyond Grover's manageable factor — the NIST
    PQC standards, AES-192/256, SHA-384/512, SHA3."""

    UNKNOWN = "UNKNOWN"
    """The primitive could not be recognised; a human must look."""


SEVERITY: dict[Exposure, int] = {
    Exposure.CLASSICALLY_BROKEN: 0,
    Exposure.QUANTUM_BROKEN: 1,
    Exposure.QUANTUM_WEAKENED: 2,
    Exposure.UNKNOWN: 3,
    Exposure.QUANTUM_SAFE: 4,
}


@dataclass(frozen=True, slots=True)
class CryptoAsset:
    """One cryptographic usage found somewhere in the estate."""

    kind: AssetKind
    primitive: str
    """The algorithm family, normalised — ``RSA``, ``ECDSA``, ``SHA-1``, ``AES``."""
    detail: str
    """The specific instance — ``RSA-2048``, ``ECDSA-P256``, ``TLSv1.1``."""
    location: str
    """``relative/path:line`` (line omitted for whole-file findings like certs)."""
    evidence: str
    """The matched text, trimmed — what a reviewer needs to confirm the finding."""
    detector: str
    """Name of the detector that produced this asset."""
    exposure: Exposure
    rationale: str
    """Why this exposure — the attack that applies, or why none does."""
    recommendation: str
    """The concrete next step, naming a ``policy.yaml`` suite where one fits."""
    key_bits: int | None = None

    # -- data-risk context (populated by the scanner from path heuristics) --
    data_classification: str = "internal"
    """public | internal | confidential | secret — sensitivity of what this
    primitive protects."""
    data_retention_years: int = 10
    """How long that data must stay confidential — the ``X`` in Mosca."""
    network_exposure: str = "internal"
    """internal | partner | public_internet — where the primitive is reachable."""
    confidence: float = 0.8
    """0–1 detector confidence: real cert/key parsing is high, a regex on a
    config line is lower."""

    @property
    def asset_id(self) -> str:
        """Stable short id, derived from the identifying fields.

        Deterministic across runs so a CBOM can be diffed between scans.
        """
        seed = f"{self.location}|{self.primitive}|{self.detail}|{self.kind.value}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "kind": self.kind.value,
            "primitive": self.primitive,
            "detail": self.detail,
            "key_bits": self.key_bits,
            "location": self.location,
            "evidence": self.evidence,
            "detector": self.detector,
            "exposure": self.exposure.value,
            "rationale": self.rationale,
            "recommendation": self.recommendation,
            "data_classification": self.data_classification,
            "data_retention_years": self.data_retention_years,
            "network_exposure": self.network_exposure,
            "confidence": round(self.confidence, 2),
        }


@dataclass(frozen=True, slots=True)
class CBOM:
    """The full inventory produced by one scan of an estate."""

    estate_root: str
    assets: tuple[CryptoAsset, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    def quantum_vulnerable(self) -> list[CryptoAsset]:
        """Assets an attacker with a quantum computer defeats — the migration
        backlog. Excludes ``CLASSICALLY_BROKEN`` (already a backlog of its own)."""
        return [
            a for a in self.assets
            if a.exposure in (Exposure.QUANTUM_BROKEN, Exposure.QUANTUM_WEAKENED)
        ]

    def urgent(self) -> list[CryptoAsset]:
        """Everything already unsafe or quantum-broken — the fix-first set."""
        return [
            a for a in self.assets
            if a.exposure in (Exposure.CLASSICALLY_BROKEN, Exposure.QUANTUM_BROKEN)
        ]

    def by_exposure(self) -> dict[Exposure, list[CryptoAsset]]:
        out: dict[Exposure, list[CryptoAsset]] = {e: [] for e in Exposure}
        for a in self.assets:
            out[a.exposure].append(a)
        return out

    def summary(self) -> dict[str, int]:
        """Count of assets per exposure, plus the total. Sums to ``len(assets)``."""
        counts = Counter(a.exposure.value for a in self.assets)
        return {"total": len(self.assets), **{e.value: counts.get(e.value, 0) for e in Exposure}}

    def to_dict(self) -> dict:
        return {
            "estate_root": self.estate_root,
            "generated_at": self.generated_at,
            "summary": self.summary(),
            "assets": [a.to_dict() for a in self.assets],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_csv(self) -> str:
        """One row per asset — for import into a spreadsheet or a ticketing tool."""
        import csv
        import io

        cols = ["asset_id", "kind", "primitive", "detail", "key_bits", "location",
                "detector", "exposure", "data_classification",
                "data_retention_years", "network_exposure", "confidence",
                "recommendation"]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for a in self.assets:
            w.writerow(a.to_dict())
        return buf.getvalue()
