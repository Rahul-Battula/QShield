"""Exception hierarchy for the crypto-agility layer.

The distinction that matters to callers: a :class:`PolicyError` means the
operator misconfigured ``policy.yaml`` and must fix it; a
:class:`ProviderUnavailable` means the policy is fine but the selected
algorithm cannot run on this machine (typically a ``REFERENCE_ONLY`` provider
with no ``liboqs`` backend installed).
"""

from __future__ import annotations


class AgilityError(Exception):
    """Base class for every error raised by the crypto-agility layer."""


class PolicyError(AgilityError):
    """``policy.yaml`` is missing, malformed, or internally inconsistent."""


class AlgorithmNotRegistered(AgilityError):
    """A suite in ``policy.yaml`` names an algorithm QShield does not know."""


class ProviderUnavailable(AgilityError):
    """The selected algorithm is known and declared but cannot run here.

    Raised by ``REFERENCE_ONLY`` providers. The algorithm still appears in
    discovery, risk and benchmark output using published reference figures; it
    simply cannot perform a live cryptographic operation without an additional
    backend (``liboqs-python``).
    """
