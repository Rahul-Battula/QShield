"""Data-risk classification of a finding from its location.

The scanner knows *where* a primitive lives but not *what it protects*. A real
CBOM program gets that from a data-classification register; QShield approximates
it from the path — a land registry keeps records effectively forever and is on
the public internet, a legacy batch host is internal and shorter-lived — so that
Phase 3's Mosca maths and the ML model have a plausible ``X`` and exposure to
work with.
"""

from __future__ import annotations

# (path fragment, classification, retention years, network exposure)
_RULES: list[tuple[str, str, int, str]] = [
    ("land-registry", "confidential", 30, "public_internet"),
    ("land", "confidential", 30, "public_internet"),
    ("health", "secret", 25, "partner"),
    ("records-db", "confidential", 25, "internal"),
    ("treasury", "secret", 10, "public_internet"),
    ("payment", "secret", 10, "public_internet"),
    ("bank", "secret", 10, "public_internet"),
    ("tax", "confidential", 7, "public_internet"),
    ("identity", "confidential", 7, "public_internet"),
    ("sso", "confidential", 7, "public_internet"),
    ("defence", "secret", 40, "internal"),
    ("legacy", "internal", 7, "internal"),
    ("mainframe", "internal", 7, "internal"),
]

DEFAULT = ("internal", 10, "internal")


def classify_location(location: str) -> tuple[str, int, str]:
    """Return ``(data_classification, data_retention_years, network_exposure)``
    for a finding at ``location``."""
    loc = location.lower()
    for fragment, cls, years, exposure in _RULES:
        if fragment in loc:
            return cls, years, exposure
    return DEFAULT


# Detector -> confidence: real parsing beats a regex on a line.
_DETECTOR_CONFIDENCE = {
    "certificate": 0.98,
    "key": 0.95,
    "source": 0.9,
    "config": 0.75,
}


def detector_confidence(detector: str) -> float:
    return _DETECTOR_CONFIDENCE.get(detector, 0.7)
