"""QShield demo application — a land registry built on the crypto-agility layer.

The registry seals each title (confidential fields encrypted under a KEM-derived
AES-GCM key, the whole record signed) and stores it. It calls only
``app.agility.kem`` and ``app.agility.sig``; it never names an
algorithm. That is what makes it a valid subject for :mod:`app.migration`,
which changes the algorithms underneath it with no edit here.

    from app.landrecords import demo_registry

    reg = demo_registry(10)
    assert all(reg.verify_all().values())
    print(reg.algorithms_in_use())
"""

from __future__ import annotations

from .models import SealedRecord, TitleRecord
from .registry import (
    IntegrityError,
    KeyEpoch,
    LandRegistry,
    NotRekeyed,
    RecordNotFound,
    RegistryError,
)
from .sample import demo_registry, sample_titles

__all__ = [
    "IntegrityError",
    "KeyEpoch",
    "LandRegistry",
    "NotRekeyed",
    "RecordNotFound",
    "RegistryError",
    "SealedRecord",
    "TitleRecord",
    "demo_registry",
    "sample_titles",
]
