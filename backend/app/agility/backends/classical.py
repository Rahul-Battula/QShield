"""Pre-quantum providers, implemented with the ``cryptography`` package.

These are the algorithms government systems run today and the algorithms a
quantum computer breaks. They are ``LIVE`` here so QShield can benchmark them
honestly against the post-quantum options and so the demo can show a real
"before" state.

KEM note: RSA and ECDH are not natively key-encapsulation mechanisms. They are
wrapped into the KEM shape used everywhere else in QShield:

* ``RSA-2048`` — generate 32 random bytes, RSA-OAEP-encrypt them. The random
  bytes are the shared secret.
* ``ECDH-P256`` / ``X25519`` — ephemeral-static Diffie-Hellman: the ciphertext
  is the ephemeral public key, the shared secret is HKDF-SHA256 of the DH
  output. This is the standard ECIES / HPKE construction.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_der_private_key,
    load_der_public_key,
)

from ..interfaces import Encapsulation, KEMProvider, KeyPair, SignatureProvider, SignatureResult

_SHARED_SECRET_BYTES = 32


def _hkdf(data: bytes, info: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=_SHARED_SECRET_BYTES,
        salt=None,
        info=info,
    ).derive(data)


class RSA2048KEM(KEMProvider):
    """RSA-2048 with OAEP-SHA256, wrapped as a KEM. Quantum-vulnerable."""

    algorithm = "RSA-2048"
    _OAEP = padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )

    def generate_keypair(self) -> KeyPair:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return KeyPair(
            public_key=key.public_key().public_bytes(
                Encoding.DER, PublicFormat.SubjectPublicKeyInfo
            ),
            private_key=key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            ),
            algorithm=self.algorithm,
        )

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        pub = load_der_public_key(public_key)
        shared_secret = os.urandom(_SHARED_SECRET_BYTES)
        ciphertext = pub.encrypt(shared_secret, self._OAEP)  # type: ignore[union-attr]
        return Encapsulation(ciphertext, shared_secret, self.algorithm)

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        priv = load_der_private_key(private_key, password=None)
        return priv.decrypt(ciphertext, self._OAEP)  # type: ignore[union-attr]


class _DHKEM(KEMProvider):
    """Shared logic for the two Diffie-Hellman KEMs."""

    _info: bytes

    def _generate(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def _load_private(self, blob: bytes):  # pragma: no cover - overridden
        raise NotImplementedError

    def _load_public(self, blob: bytes):  # pragma: no cover - overridden
        raise NotImplementedError

    def _serialize_private(self, key) -> bytes:  # pragma: no cover - overridden
        raise NotImplementedError

    def _serialize_public(self, key) -> bytes:  # pragma: no cover - overridden
        raise NotImplementedError

    def _exchange(self, private_key, peer_public_key) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def generate_keypair(self) -> KeyPair:
        key = self._generate()
        return KeyPair(
            public_key=self._serialize_public(key.public_key()),
            private_key=self._serialize_private(key),
            algorithm=self.algorithm,
        )

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        peer = self._load_public(public_key)
        ephemeral = self._generate()
        shared = self._exchange(ephemeral, peer)
        return Encapsulation(
            ciphertext=self._serialize_public(ephemeral.public_key()),
            shared_secret=_hkdf(shared, self._info),
            algorithm=self.algorithm,
        )

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        priv = self._load_private(private_key)
        ephemeral_pub = self._load_public(ciphertext)
        shared = self._exchange(priv, ephemeral_pub)
        return _hkdf(shared, self._info)


class ECDHP256KEM(_DHKEM):
    """Ephemeral-static ECDH on NIST P-256. Quantum-vulnerable."""

    algorithm = "ECDH-P256"
    _info = b"qshield-ecdh-p256-kem-v1"

    def _generate(self):
        return ec.generate_private_key(ec.SECP256R1())

    def _load_private(self, blob: bytes):
        return load_der_private_key(blob, password=None)

    def _load_public(self, blob: bytes):
        return load_der_public_key(blob)

    def _serialize_private(self, key) -> bytes:
        return key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())

    def _serialize_public(self, key) -> bytes:
        return key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)

    def _exchange(self, private_key, peer_public_key) -> bytes:
        return private_key.exchange(ec.ECDH(), peer_public_key)


class X25519KEM(_DHKEM):
    """Ephemeral-static X25519. Quantum-vulnerable; the classical half of the
    default hybrid suite."""

    algorithm = "X25519"
    _info = b"qshield-x25519-kem-v1"

    def _generate(self):
        return x25519.X25519PrivateKey.generate()

    def _load_private(self, blob: bytes):
        return x25519.X25519PrivateKey.from_private_bytes(blob)

    def _load_public(self, blob: bytes):
        return x25519.X25519PublicKey.from_public_bytes(blob)

    def _serialize_private(self, key) -> bytes:
        return key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    def _serialize_public(self, key) -> bytes:
        return key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def _exchange(self, private_key, peer_public_key) -> bytes:
        return private_key.exchange(peer_public_key)


class ECDSAP256Sig(SignatureProvider):
    """ECDSA on NIST P-256 with SHA-256. Quantum-vulnerable; the classical half
    of the default hybrid signature suite."""

    algorithm = "ECDSA-P256"

    def generate_keypair(self) -> KeyPair:
        key = ec.generate_private_key(ec.SECP256R1())
        return KeyPair(
            public_key=key.public_key().public_bytes(
                Encoding.DER, PublicFormat.SubjectPublicKeyInfo
            ),
            private_key=key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            ),
            algorithm=self.algorithm,
        )

    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        priv = load_der_private_key(private_key, password=None)
        signature = priv.sign(message, ec.ECDSA(hashes.SHA256()))  # type: ignore[union-attr]
        return SignatureResult(signature, self.algorithm)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        pub = load_der_public_key(public_key)
        try:
            pub.verify(signature, message, ec.ECDSA(hashes.SHA256()))  # type: ignore[union-attr]
            return True
        except InvalidSignature:
            return False
