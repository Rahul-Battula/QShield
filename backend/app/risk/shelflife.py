"""Estimating X — how long an asset's data must stay protected.

Mosca's X is a business fact, not a cryptographic one: it is the number of years
a land title, a tax record or a session token must remain confidential and its
signatures unforgeable. QShield cannot know this for a real estate, so it does
two things:

1. ships a coarse default keyed on the part of the estate an asset lives in
   (a land registry keeps records effectively forever; a tax system has a
   statutory retention period; an identity service's material rotates), and
2. lets ``policy.yaml``'s ``mosca.data_classes`` override and extend that map.

The match is on a leading fragment of the asset's ``location`` path, longest
fragment wins. Anything unmatched uses :data:`DEFAULT_SHELF_LIFE_YEARS`.
"""

from __future__ import annotations

from ..discovery.cbom import CryptoAsset

DEFAULT_SHELF_LIFE_YEARS = 10

# Built-in defaults. Deliberately conservative: over-stating X makes the risk
# assessment more cautious, which is the safe direction to err.
DEFAULT_DATA_CLASSES: dict[str, int] = {
    "land-registry": 30,
    "records-db": 25,
    "identity-service": 7,
    "tax-portal": 7,
    "legacy-mainframe": 7,
    "payments": 7,
    "health": 25,
}


def _location_prefixes(location: str) -> list[str]:
    """Leading path fragments of a location, longest first.

    ``land-registry/app/records_service.py:15`` ->
    ``["land-registry/app/records_service.py", "land-registry/app",
       "land-registry"]``.
    """
    path = location.split(":", 1)[0]
    parts = path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))][::-1]


def estimate_shelf_life(
    asset: CryptoAsset,
    data_classes: dict[str, int] | None = None,
) -> tuple[float, str]:
    """Return ``(years, basis)`` — the estimated X for ``asset`` and a short
    explanation of where the number came from."""
    merged = {**DEFAULT_DATA_CLASSES, **(data_classes or {})}
    for prefix in _location_prefixes(asset.location):
        if prefix in merged:
            return float(merged[prefix]), f"data class '{prefix}' = {merged[prefix]}y"
    return float(DEFAULT_SHELF_LIFE_YEARS), f"default {DEFAULT_SHELF_LIFE_YEARS}y"
