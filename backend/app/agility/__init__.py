"""QShield crypto-agility layer — the project's core contribution.

Import surface for application code:

    from app.agility import kem, sig, reload

``kem`` and ``sig`` resolve their algorithm from ``policy.yaml`` at call time.
``reload()`` re-reads the policy after it has been edited. Application code
imports nothing deeper than this module and never names an algorithm.
"""

from __future__ import annotations

from .errors import (
    AgilityError,
    AlgorithmNotRegistered,
    PolicyError,
    ProviderUnavailable,
)
from .facade import kem, sig
from .interfaces import (
    Encapsulation,
    KEMProvider,
    KeyPair,
    ProviderStatus,
    SignatureProvider,
    SignatureResult,
)
from .policy import Policy, load_policy, write_active_suite
from .registry import Registry, get_registry, reload

__all__ = [
    "AgilityError",
    "AlgorithmNotRegistered",
    "Encapsulation",
    "KEMProvider",
    "KeyPair",
    "Policy",
    "PolicyError",
    "ProviderStatus",
    "ProviderUnavailable",
    "Registry",
    "SignatureProvider",
    "SignatureResult",
    "get_registry",
    "kem",
    "load_policy",
    "reload",
    "sig",
    "write_active_suite",
]
