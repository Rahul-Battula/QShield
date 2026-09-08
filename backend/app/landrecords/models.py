"""Data types for the demo land-records application.

A :class:`TitleRecord` is the plaintext a registry clerk works with. A
:class:`SealedRecord` is what the registry stores: the confidential fields
encrypted under a KEM-derived key and the whole thing signed, with the KEM and
signature algorithm names recorded *as produced* — the application never chose
them, the active policy did.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class TitleRecord:
    """A land title, as handled in the clear inside the application."""

    parcel_id: str
    owner: str
    area_sqm: float
    survey_note: str
    valuation_gbp: int
    """Confidential: encrypted at rest, never in the public register."""

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> TitleRecord:
        return cls(**json.loads(raw))


@dataclass(frozen=True, slots=True)
class SealedRecord:
    """The stored form: KEM ciphertext + AEAD blob + signature, plus the
    algorithm names that produced them."""

    record_id: str
    parcel_id: str
    owner: str
    kem_algorithm: str
    sig_algorithm: str
    suite: str
    epoch_id: int
    kem_ciphertext: bytes
    nonce: bytes
    blob: bytes
    signature: bytes
    sealed_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    def signing_message(self) -> bytes:
        """The bytes covered by :attr:`signature` — identity plus every
        ciphertext component, so tampering with any of them is detectable."""
        return b"|".join([
            self.record_id.encode(),
            self.parcel_id.encode(),
            self.owner.encode(),
            self.kem_ciphertext,
            self.nonce,
            self.blob,
        ])

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "parcel_id": self.parcel_id,
            "owner": self.owner,
            "kem_algorithm": self.kem_algorithm,
            "sig_algorithm": self.sig_algorithm,
            "suite": self.suite,
            "epoch_id": self.epoch_id,
            "sealed_at": self.sealed_at,
            "ciphertext_bytes": len(self.kem_ciphertext) + len(self.blob),
            "signature_bytes": len(self.signature),
        }
