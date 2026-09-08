"""What application code imports: ``kem`` and ``sig``.

These two objects are thin proxies. Every attribute access and method call is
forwarded to the provider held by the current :class:`~app.agility.registry.Registry`,
so a :func:`~app.agility.registry.reload` is picked up on the very next call
with no re-import and no re-wiring on the caller's side.

Application code calls ``kem.encapsulate(...)`` / ``sig.sign(...)`` and reads
``.algorithm`` for audit logging. It never constructs a provider and never
names an algorithm.
"""

from __future__ import annotations

from .interfaces import Encapsulation, KeyPair, ProviderStatus, SignatureResult
from .registry import get_registry


class _KEMFacade:
    """Process-wide proxy to the active KEM provider."""

    @property
    def algorithm(self) -> str:
        return get_registry().kem.algorithm

    @property
    def status(self) -> ProviderStatus:
        return get_registry().kem.status

    def generate_keypair(self) -> KeyPair:
        return get_registry().kem.generate_keypair()

    def encapsulate(self, public_key: bytes) -> Encapsulation:
        return get_registry().kem.encapsulate(public_key)

    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        return get_registry().kem.decapsulate(private_key, ciphertext)


class _SigFacade:
    """Process-wide proxy to the active signature provider."""

    @property
    def algorithm(self) -> str:
        return get_registry().sig.algorithm

    @property
    def status(self) -> ProviderStatus:
        return get_registry().sig.status

    def generate_keypair(self) -> KeyPair:
        return get_registry().sig.generate_keypair()

    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        return get_registry().sig.sign(private_key, message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return get_registry().sig.verify(public_key, message, signature)


kem = _KEMFacade()
sig = _SigFacade()
