"""The contract that makes every future migration a configuration change.

Application code depends only on the abstract types in this module. The result
dataclasses each carry the ``algorithm`` that produced them so that callers,
tests and audit logs can record *which* algorithm ran without the application
ever having selected it.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderStatus(str, enum.Enum):
    """Whether a provider can perform live cryptographic operations here."""

    LIVE = "LIVE"
    """Runs on this machine with the installed backends."""

    REFERENCE_ONLY = "REFERENCE_ONLY"
    """Declared and described with published figures, but not runnable here.

    Calling a cryptographic method raises
    :class:`app.agility.errors.ProviderUnavailable`.
    """


@dataclass(frozen=True, slots=True)
class KeyPair:
    """A public/private key pair, both sides serialised to bytes.

    Serialisation is provider-specific and opaque to the caller: classical
    providers use DER (SubjectPublicKeyInfo / PKCS#8) or raw 32-byte keys,
    post-quantum providers use their native byte encodings, and composite
    providers use a length-prefixed concatenation of their components.
    """

    public_key: bytes
    private_key: bytes
    algorithm: str


@dataclass(frozen=True, slots=True)
class Encapsulation:
    """The output of :meth:`KEMProvider.encapsulate`."""

    ciphertext: bytes
    shared_secret: bytes
    algorithm: str


@dataclass(frozen=True, slots=True)
class SignatureResult:
    """The output of :meth:`SignatureProvider.sign`."""

    signature: bytes
    algorithm: str


class KEMProvider(ABC):
    """A key-encapsulation mechanism.

    Concrete subclasses set :attr:`algorithm` (the identifier reported to
    callers) and, if they cannot run here, override :attr:`status` to
    :attr:`ProviderStatus.REFERENCE_ONLY`.
    """

    algorithm: str
    status: ProviderStatus = ProviderStatus.LIVE

    @abstractmethod
    def generate_keypair(self) -> KeyPair:
        """Generate a fresh key pair for this KEM."""

    @abstractmethod
    def encapsulate(self, public_key: bytes) -> Encapsulation:
        """Encapsulate a fresh shared secret to ``public_key``."""

    @abstractmethod
    def decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        """Recover the shared secret from ``ciphertext`` using ``private_key``."""


class SignatureProvider(ABC):
    """A digital-signature algorithm."""

    algorithm: str
    status: ProviderStatus = ProviderStatus.LIVE

    @abstractmethod
    def generate_keypair(self) -> KeyPair:
        """Generate a fresh signing key pair."""

    @abstractmethod
    def sign(self, private_key: bytes, message: bytes) -> SignatureResult:
        """Sign ``message`` with ``private_key``."""

    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Return ``True`` iff ``signature`` is valid for ``message``."""
