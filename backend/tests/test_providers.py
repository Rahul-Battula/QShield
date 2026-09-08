"""Per-provider correctness, exercised directly (not through policy).

Every ``LIVE`` provider must round-trip. Every ``REFERENCE_ONLY`` provider must
refuse to run with :class:`ProviderUnavailable` while still reporting published
sizes.
"""

from __future__ import annotations

import pytest

from app.agility import ProviderStatus, ProviderUnavailable
from app.agility.backends import oqs_backend
from app.agility.providers import build_kem, build_sig

LIVE_KEMS = ["RSA-2048", "ECDH-P256", "X25519", "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"]
LIVE_SIGS = ["ECDSA-P256", "ML-DSA-44", "ML-DSA-65", "ML-DSA-87"]
REFERENCE_KEMS = ["HQC-128", "HQC-192", "HQC-256"]
REFERENCE_SIGS = ["SLH-DSA-SHA2-128s", "SLH-DSA-SHA2-192s", "SLH-DSA-SHA2-256s"]


@pytest.mark.parametrize("name", LIVE_KEMS)
def test_live_kem_roundtrip(name):
    provider = build_kem(name)
    assert provider.algorithm == name
    assert provider.status == ProviderStatus.LIVE

    pair = provider.generate_keypair()
    enc = provider.encapsulate(pair.public_key)
    assert provider.decapsulate(pair.private_key, enc.ciphertext) == enc.shared_secret
    assert len(enc.shared_secret) >= 16


@pytest.mark.parametrize("name", LIVE_KEMS)
def test_live_kem_wrong_key_does_not_recover_secret(name):
    provider = build_kem(name)
    receiver = provider.generate_keypair()
    intruder = provider.generate_keypair()
    enc = provider.encapsulate(receiver.public_key)
    # Decapsulating with the wrong private key must not yield the real secret.
    try:
        recovered = provider.decapsulate(intruder.private_key, enc.ciphertext)
    except Exception:
        return  # rejecting outright is an acceptable outcome
    assert recovered != enc.shared_secret


@pytest.mark.parametrize("name", LIVE_SIGS)
def test_live_sig_roundtrip_and_tamper(name):
    provider = build_sig(name)
    assert provider.algorithm == name
    assert provider.status == ProviderStatus.LIVE

    message = b"citizen-portal:session-open"
    pair = provider.generate_keypair()
    signed = provider.sign(pair.private_key, message)
    assert provider.verify(pair.public_key, message, signed.signature)
    assert not provider.verify(pair.public_key, message + b"!", signed.signature)
    assert not provider.verify(pair.public_key, message, signed.signature + b"\x00")


@pytest.mark.parametrize("name", REFERENCE_KEMS)
def test_reference_kem_declared_but_unavailable(name):
    provider = build_kem(name)
    if oqs_backend.oqs_available():
        pytest.skip("liboqs present: HQC is LIVE, not REFERENCE_ONLY")
    assert provider.status == ProviderStatus.REFERENCE_ONLY
    assert provider.meta.public_key_bytes > 0
    assert provider.meta.ciphertext_bytes and provider.meta.ciphertext_bytes > 0
    assert provider.meta.source
    with pytest.raises(ProviderUnavailable):
        provider.generate_keypair()
    with pytest.raises(ProviderUnavailable):
        provider.encapsulate(b"\x00" * 32)


@pytest.mark.parametrize("name", REFERENCE_SIGS)
def test_reference_sig_declared_but_unavailable(name):
    provider = build_sig(name)
    if oqs_backend.oqs_available():
        pytest.skip("liboqs present: SLH-DSA is LIVE, not REFERENCE_ONLY")
    assert provider.status == ProviderStatus.REFERENCE_ONLY
    assert provider.meta.signature_bytes and provider.meta.signature_bytes > 0
    assert "FIPS 205" in provider.meta.source
    with pytest.raises(ProviderUnavailable):
        provider.generate_keypair()
    with pytest.raises(ProviderUnavailable):
        provider.sign(b"\x00" * 32, b"message")


def test_unknown_algorithm_is_rejected():
    from app.agility import AlgorithmNotRegistered

    with pytest.raises(AlgorithmNotRegistered):
        build_kem("RSA-9999")
    with pytest.raises(AlgorithmNotRegistered):
        build_sig("ML-DSA-999")
