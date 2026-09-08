"""Pure-Python post-quantum providers.

ML-KEM (FIPS 203) via ``kyber-py`` and ML-DSA (FIPS 204) via ``dilithium-py``.
Both are pure Python: no C toolchain, no build step, importable on the demo
laptop with a plain ``pip install``. They are the reason the demo can never be
broken by a compiler failing on the day.

These libraries are pinned to their 1.x API in ``pyproject.toml``:

    kyber-py     ek, dk = ML_KEM_768.keygen()
                 key, ct = ML_KEM_768.encaps(ek)
                 key     = ML_KEM_768.decaps(dk, ct)

    dilithium-py pk, sk = ML_DSA_65.keygen()
                 sig    = ML_DSA_65.sign(sk, msg)
                 ok     = ML_DSA_65.verify(pk, msg, sig)
"""

from __future__ import annotations

from dilithium_py.ml_dsa import ML_DSA_44, ML_DSA_65, ML_DSA_87
from kyber_py.ml_kem import ML_KEM_512, ML_KEM_768, ML_KEM_1024

from ..errors import AlgorithmNotRegistered
from ..interfaces import Encapsulation, KEMProvider, KeyPair, SignatureProvider, SignatureResult

_ML_KEM_IMPL = {
    "ML-KEM-512": ML_KEM_512,
    "ML-KEM-768": ML_KEM_768,
    "ML-KEM-1024": ML_KEM_1024,
}

_ML_DSA_IMPL = {
    "ML-DSA-44": ML_DSA_44,
    "ML-DSA-65": ML_DSA_65,
    "ML-DSA-87": ML_DSA_87,
}


class MLKEMProvider(KEMProvider):
    """ML-KEM / FIPS 203, all three parameter sets."""

    def __init__(self, algorithm: str) -> None:
        if algorithm not in _ML_KEM_IMPL:
            raise AlgorithmNotRegistered(f"unknown ML-KEM parameter set: {algorithm!r}")
        self.algorithm = algorithm
        self._impl = _ML_KEM_IMPL[algorithm]

    def generate_keypair(self) -> KeyPair:
        encaps_key, decaps_key = self._impl.keygen()
        return KeyPair(
            public_key=bytes(encaps_key),
            private_key=bytes(decaps_key),
            algorithm=self.algorithm,
        )

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        shared_secret, ciphertext = self._impl.encaps(public_key)
        return Encapsulation(bytes(ciphertext), bytes(shared_secret), self.algorithm)

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        return bytes(self._impl.decaps(private_key, ciphertext))


class MLDSAProvider(SignatureProvider):
    """ML-DSA / FIPS 204, all three parameter sets."""

    def __init__(self, algorithm: str) -> None:
        if algorithm not in _ML_DSA_IMPL:
            raise AlgorithmNotRegistered(f"unknown ML-DSA parameter set: {algorithm!r}")
        self.algorithm = algorithm
        self._impl = _ML_DSA_IMPL[algorithm]

    def generate_keypair(self) -> KeyPair:
        public_key, secret_key = self._impl.keygen()
        return KeyPair(
            public_key=bytes(public_key),
            private_key=bytes(secret_key),
            algorithm=self.algorithm,
        )

    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        signature = self._impl.sign(private_key, message)
        return SignatureResult(bytes(signature), self.algorithm)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            return bool(self._impl.verify(public_key, message, signature))
        except Exception:
            # dilithium-py raises on malformed input rather than returning False.
            return False
