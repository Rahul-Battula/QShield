"""Optional ``liboqs`` providers: HQC and SLH-DSA, plus faster lattice paths.

This module is best-effort and is **not** the demo's primary path. If
``liboqs-python`` did not install, :func:`oqs_available` returns ``False`` and
the registry falls back to :mod:`app.agility.backends.reference`.

Algorithm names differ between liboqs releases (for example
``SPHINCS+-SHA2-128s-simple`` in older builds versus ``SLH-DSA-SHA2-128s`` in
newer ones), so each QShield name maps to a list of candidates and the first
one actually enabled in the linked library is used.
"""

from __future__ import annotations

from ..errors import ProviderUnavailable
from ..interfaces import (
    Encapsulation,
    KEMProvider,
    KeyPair,
    ProviderStatus,
    SignatureProvider,
    SignatureResult,
)

try:
    import oqs  # type: ignore

    _OQS_IMPORTED = True
except Exception:  # pragma: no cover - depends on optional native build
    oqs = None  # type: ignore
    _OQS_IMPORTED = False


# QShield name -> ordered liboqs candidate names.
_KEM_CANDIDATES: dict[str, list[str]] = {
    "HQC-128": ["HQC-128"],
    "HQC-192": ["HQC-192"],
    "HQC-256": ["HQC-256"],
    "ML-KEM-512": ["ML-KEM-512", "Kyber512"],
    "ML-KEM-768": ["ML-KEM-768", "Kyber768"],
    "ML-KEM-1024": ["ML-KEM-1024", "Kyber1024"],
}

_SIG_CANDIDATES: dict[str, list[str]] = {
    "SLH-DSA-SHA2-128s": ["SLH-DSA-SHA2-128s", "SPHINCS+-SHA2-128s-simple"],
    "SLH-DSA-SHA2-192s": ["SLH-DSA-SHA2-192s", "SPHINCS+-SHA2-192s-simple"],
    "SLH-DSA-SHA2-256s": ["SLH-DSA-SHA2-256s", "SPHINCS+-SHA2-256s-simple"],
    "ML-DSA-44": ["ML-DSA-44", "Dilithium2"],
    "ML-DSA-65": ["ML-DSA-65", "Dilithium3"],
    "ML-DSA-87": ["ML-DSA-87", "Dilithium5"],
}


def oqs_available() -> bool:
    """Return ``True`` iff ``liboqs-python`` imported successfully."""
    return _OQS_IMPORTED


def _resolve(name: str, candidates: dict[str, list[str]], enabled: list[str]) -> str | None:
    for candidate in candidates.get(name, [name]):
        if candidate in enabled:
            return candidate
    return None


class OQSKEM(KEMProvider):
    """A KEM backed by liboqs. Used for HQC when liboqs is present."""

    status = ProviderStatus.LIVE

    def __init__(self, algorithm: str) -> None:
        if not _OQS_IMPORTED:
            raise ProviderUnavailable(f"{algorithm}: liboqs is not installed")
        self.algorithm = algorithm
        self._name = _resolve(algorithm, _KEM_CANDIDATES, list(oqs.get_enabled_kem_mechanisms()))
        if self._name is None:
            raise ProviderUnavailable(
                f"{algorithm}: not enabled in the linked liboqs build"
            )

    def generate_keypair(self) -> KeyPair:
        with oqs.KeyEncapsulation(self._name) as kem:
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()
        return KeyPair(bytes(public_key), bytes(private_key), self.algorithm)

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        with oqs.KeyEncapsulation(self._name) as kem:
            ciphertext, shared_secret = kem.encap_secret(public_key)
        return Encapsulation(bytes(ciphertext), bytes(shared_secret), self.algorithm)

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        with oqs.KeyEncapsulation(self._name, secret_key=private_key) as kem:
            return bytes(kem.decap_secret(ciphertext))


class OQSSig(SignatureProvider):
    """A signature algorithm backed by liboqs. Used for SLH-DSA when present."""

    status = ProviderStatus.LIVE

    def __init__(self, algorithm: str) -> None:
        if not _OQS_IMPORTED:
            raise ProviderUnavailable(f"{algorithm}: liboqs is not installed")
        self.algorithm = algorithm
        self._name = _resolve(algorithm, _SIG_CANDIDATES, list(oqs.get_enabled_sig_mechanisms()))
        if self._name is None:
            raise ProviderUnavailable(
                f"{algorithm}: not enabled in the linked liboqs build"
            )

    def generate_keypair(self) -> KeyPair:
        with oqs.Signature(self._name) as signer:
            public_key = signer.generate_keypair()
            private_key = signer.export_secret_key()
        return KeyPair(bytes(public_key), bytes(private_key), self.algorithm)

    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        with oqs.Signature(self._name, secret_key=private_key) as signer:
            signature = signer.sign(message)
        return SignatureResult(bytes(signature), self.algorithm)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            with oqs.Signature(self._name) as verifier:
                return bool(verifier.verify(message, signature, public_key))
        except Exception:
            return False
