"""Algorithm-name -> provider construction.

This is the only place that maps the strings in ``policy.yaml`` (``ML-KEM-768``,
``X25519+ML-KEM-768``, ``HQC-192`` ...) to concrete provider objects. A ``+`` in
a name means a hybrid/composite; each side is resolved recursively.

Backend selection rule:

* ML-KEM / ML-DSA         -> pure-Python (always LIVE, no build step)
* RSA / ECDH / X25519 / ECDSA -> ``cryptography`` (always LIVE)
* HQC / SLH-DSA           -> ``liboqs`` if importable, else REFERENCE_ONLY
"""

from __future__ import annotations

from .backends import oqs_backend
from .backends.classical import (
    ECDHP256KEM,
    RSA2048KEM,
    X25519KEM,
    ECDSAP256Sig,
)
from .backends.pqc_purepy import MLDSAProvider, MLKEMProvider
from .backends.reference import HQC_META, SLH_DSA_META, ReferenceKEM, ReferenceSig
from .combiners import CompositeSignatureProvider, HybridKEMProvider
from .errors import AlgorithmNotRegistered
from .interfaces import KEMProvider, SignatureProvider

_ML_KEM = {"ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"}
_ML_DSA = {"ML-DSA-44", "ML-DSA-65", "ML-DSA-87"}


def build_kem(name: str) -> KEMProvider:
    """Construct the KEM provider named ``name``."""
    if "+" in name:
        parts = [p.strip() for p in name.split("+")]
        return HybridKEMProvider(name, [build_kem(p) for p in parts])

    if name in _ML_KEM:
        return MLKEMProvider(name)
    if name == "RSA-2048":
        return RSA2048KEM()
    if name == "ECDH-P256":
        return ECDHP256KEM()
    if name == "X25519":
        return X25519KEM()
    if name.startswith("HQC-"):
        meta = HQC_META.get(name)
        if meta is None:
            raise AlgorithmNotRegistered(f"unknown HQC parameter set: {name!r}")
        if oqs_backend.oqs_available():
            try:
                return oqs_backend.OQSKEM(name)
            except Exception:
                pass  # linked liboqs lacks HQC; fall through to reference
        return ReferenceKEM(name, meta)

    raise AlgorithmNotRegistered(f"unknown KEM algorithm: {name!r}")


def build_sig(name: str) -> SignatureProvider:
    """Construct the signature provider named ``name``."""
    if "+" in name:
        parts = [p.strip() for p in name.split("+")]
        return CompositeSignatureProvider(name, [build_sig(p) for p in parts])

    if name in _ML_DSA:
        return MLDSAProvider(name)
    if name == "ECDSA-P256":
        return ECDSAP256Sig()
    if name.startswith("SLH-DSA-"):
        meta = SLH_DSA_META.get(name)
        if meta is None:
            raise AlgorithmNotRegistered(f"unknown SLH-DSA parameter set: {name!r}")
        if oqs_backend.oqs_available():
            try:
                return oqs_backend.OQSSig(name)
            except Exception:
                pass  # linked liboqs lacks this set; fall through to reference
        return ReferenceSig(name, meta)

    raise AlgorithmNotRegistered(f"unknown signature algorithm: {name!r}")
