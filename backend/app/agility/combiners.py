"""Hybrid and composite providers.

Hybrid key establishment and composite signatures are the default in QShield
because they are what real deployments ship: Chrome, Cloudflare and Signal all
run hybrid X25519+ML-KEM. The security goal is *survivability* — the construct
stays secure as long as at least one component does, so the eventual break of
ML-KEM (or of X25519 by a quantum computer) is not fatal on its own.

Wire formats here are length-prefixed concatenations (see :func:`pack`), so a
hybrid public key, ciphertext or signature is self-describing given the number
of components.

**KEM combiner.** The two shared secrets are concatenated and fed, together
with a transcript of both ciphertexts, into HKDF-SHA256. Binding the
ciphertexts into the KDF follows the approach taken by X-Wing and the IETF
hybrid-KEM drafts and prevents an attacker who can manipulate one component
ciphertext from steering the combined secret.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .interfaces import (
    Encapsulation,
    KEMProvider,
    KeyPair,
    ProviderStatus,
    SignatureProvider,
    SignatureResult,
)

_HYBRID_KEM_INFO = b"qshield-hybrid-kem-v1"
_COMBINED_SECRET_BYTES = 32


def pack(*parts: bytes) -> bytes:
    """Length-prefix and concatenate ``parts`` (4-byte big-endian lengths)."""
    out = bytearray()
    for part in parts:
        out += len(part).to_bytes(4, "big")
        out += part
    return bytes(out)


def unpack(blob: bytes, count: int) -> list[bytes]:
    """Inverse of :func:`pack`. Raises ``ValueError`` on a malformed blob."""
    parts: list[bytes] = []
    offset = 0
    for _ in range(count):
        if offset + 4 > len(blob):
            raise ValueError("packed blob truncated in length prefix")
        size = int.from_bytes(blob[offset : offset + 4], "big")
        offset += 4
        if offset + size > len(blob):
            raise ValueError("packed blob truncated in payload")
        parts.append(blob[offset : offset + size])
        offset += size
    if offset != len(blob):
        raise ValueError("packed blob has trailing bytes")
    return parts


def _combined_status(components) -> ProviderStatus:
    live = all(c.status == ProviderStatus.LIVE for c in components)
    return ProviderStatus.LIVE if live else ProviderStatus.REFERENCE_ONLY


class HybridKEMProvider(KEMProvider):
    """N-component hybrid KEM (QShield ships two-component suites)."""

    def __init__(self, algorithm: str, components: list[KEMProvider]) -> None:
        if len(components) < 2:
            raise ValueError("a hybrid KEM needs at least two components")
        self.algorithm = algorithm
        self.components = components
        self.status = _combined_status(components)

    def generate_keypair(self) -> KeyPair:
        pairs = [c.generate_keypair() for c in self.components]
        return KeyPair(
            public_key=pack(*(p.public_key for p in pairs)),
            private_key=pack(*(p.private_key for p in pairs)),
            algorithm=self.algorithm,
        )

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        public_keys = unpack(public_key, len(self.components))
        ciphertexts: list[bytes] = []
        secrets = bytearray()
        for component, pub in zip(self.components, public_keys):
            enc = component.encapsulate(pub)
            ciphertexts.append(enc.ciphertext)
            secrets += enc.shared_secret
        combined_ct = pack(*ciphertexts)
        shared_secret = self._combine(bytes(secrets), combined_ct)
        return Encapsulation(combined_ct, shared_secret, self.algorithm)

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        private_keys = unpack(private_key, len(self.components))
        ciphertexts = unpack(ciphertext, len(self.components))
        secrets = bytearray()
        for component, priv, ct in zip(self.components, private_keys, ciphertexts):
            secrets += component.decapsulate(priv, ct)
        return self._combine(bytes(secrets), ciphertext)

    @staticmethod
    def _combine(concatenated_secrets: bytes, transcript: bytes) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=_COMBINED_SECRET_BYTES,
            salt=None,
            info=_HYBRID_KEM_INFO,
        ).derive(concatenated_secrets + transcript)


class CompositeSignatureProvider(SignatureProvider):
    """N-component composite signature: every component must verify."""

    def __init__(self, algorithm: str, components: list[SignatureProvider]) -> None:
        if len(components) < 2:
            raise ValueError("a composite signature needs at least two components")
        self.algorithm = algorithm
        self.components = components
        self.status = _combined_status(components)

    def generate_keypair(self) -> KeyPair:
        pairs = [c.generate_keypair() for c in self.components]
        return KeyPair(
            public_key=pack(*(p.public_key for p in pairs)),
            private_key=pack(*(p.private_key for p in pairs)),
            algorithm=self.algorithm,
        )

    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        private_keys = unpack(private_key, len(self.components))
        signatures = [
            component.sign(priv, message).signature
            for component, priv in zip(self.components, private_keys)
        ]
        return SignatureResult(pack(*signatures), self.algorithm)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            public_keys = unpack(public_key, len(self.components))
            signatures = unpack(signature, len(self.components))
        except ValueError:
            return False
        return all(
            component.verify(pub, message, sig)
            for component, pub, sig in zip(self.components, public_keys, signatures)
        )
