"""Estimating Y — how long it takes to migrate one asset.

A one-line change to a TLS config is not the same job as re-keying a hardware
security module or recompiling a mainframe batch program. Y is estimated from
the kind of asset, where it lives, and — crucially — whether QShield's Phase 1
crypto-agility layer already offers a live drop-in replacement, because that is
exactly the lever that turns a code change into a configuration change.

The numbers are in years and are order-of-magnitude, not project estimates.
Their job is to *rank* work, and the ranking is not sensitive to the exact
constants.
"""

from __future__ import annotations

from ..discovery.cbom import AssetKind, CryptoAsset

# Base effort by asset kind, in years.
_BASE_YEARS: dict[AssetKind, float] = {
    AssetKind.PROTOCOL_CONFIG: 0.25,   # edit a config, redeploy
    AssetKind.TOKEN_CONFIG: 0.5,       # rotate signing keys, coordinate verifiers
    AssetKind.CERTIFICATE: 0.75,       # re-issue through a CA
    AssetKind.PUBLIC_KEY: 0.75,
    AssetKind.PRIVATE_KEY: 0.75,
    AssetKind.LIBRARY_CALL: 1.0,       # change code, test, release
}
_DEFAULT_BASE = 1.0

# A legacy platform multiplies everything: no CI, scarce expertise, long change
# windows. Matched against the asset's location.
_LEGACY_MARKERS = ("legacy", "mainframe", "cobol", "as400", "vms")
_LEGACY_MULTIPLIER = 3.0

# If the recommended target is a suite QShield already runs live, the migration
# is a policy edit plus a redeploy — the Phase 1 payoff.
_AGILITY_DISCOUNT = 0.5

_MIN_YEARS, _MAX_YEARS = 0.1, 10.0


def _agility_covered(asset: CryptoAsset, live_suites: set[str]) -> bool:
    rec = asset.recommendation.lower()
    return any(f"'{suite}'" in rec for suite in live_suites)


def estimate_migration_years(
    asset: CryptoAsset,
    live_suites: set[str] | None = None,
) -> tuple[float, str]:
    """Return ``(years, basis)`` — the estimated Y for ``asset``.

    ``live_suites`` is the set of ``policy.yaml`` suite names that QShield can
    run live here; when the asset's recommendation points at one of them the
    estimate is discounted.
    """
    live_suites = live_suites or set()
    years = _BASE_YEARS.get(asset.kind, _DEFAULT_BASE)
    reasons = [f"{asset.kind.value.lower()} base {years}y"]

    loc = asset.location.lower()
    if any(marker in loc for marker in _LEGACY_MARKERS):
        years *= _LEGACY_MULTIPLIER
        reasons.append(f"legacy platform x{_LEGACY_MULTIPLIER}")

    if _agility_covered(asset, live_suites):
        years *= _AGILITY_DISCOUNT
        reasons.append(f"agility drop-in x{_AGILITY_DISCOUNT}")

    years = max(_MIN_YEARS, min(_MAX_YEARS, years))
    return round(years, 3), "; ".join(reasons)
