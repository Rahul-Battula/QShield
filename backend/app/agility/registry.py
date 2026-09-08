"""The hot-swap point.

A :class:`Registry` holds the provider objects for the currently active suite.
Migrating algorithms is exactly: edit ``policy.yaml``, call :func:`reload`,
which rebuilds this one object. Nothing else in the process changes and no
application code is touched.

The module keeps a process-wide current registry. The public facade
(:mod:`app.agility.facade`) reads from it on every call, so a ``reload``
takes effect immediately for every caller.
"""

from __future__ import annotations

from dataclasses import dataclass

from .interfaces import KEMProvider, SignatureProvider
from .policy import Policy, load_policy
from .providers import build_kem, build_sig


@dataclass
class Registry:
    """The resolved providers for one policy snapshot."""

    policy: Policy
    kem: KEMProvider
    sig: SignatureProvider

    @classmethod
    def from_policy(cls, policy: Policy) -> Registry:
        suite = policy.active()
        return cls(
            policy=policy,
            kem=build_kem(suite.kem),
            sig=build_sig(suite.sig),
        )


_current: Registry | None = None


def get_registry() -> Registry:
    """Return the current registry, building it from ``policy.yaml`` on first use."""
    global _current
    if _current is None:
        _current = Registry.from_policy(load_policy())
    return _current


def reload() -> Registry:
    """Re-read ``policy.yaml`` and rebuild the current registry.

    This is the entire mechanism of a QShield migration.
    """
    global _current
    _current = Registry.from_policy(load_policy())
    return _current
