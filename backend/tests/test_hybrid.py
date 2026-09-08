"""Hybrid KEM and composite signature behaviour.

The point of hybrid is survivability: the construction must stay correct and
must bind its components together so that tampering with one half is detected.
"""

from __future__ import annotations

import pytest

from app.agility.combiners import pack, unpack
from app.agility.providers import build_kem, build_sig

HYBRID_KEM = "X25519+ML-KEM-768"
COMPOSITE_SIG = "ECDSA-P256+ML-DSA-65"


def test_pack_unpack_roundtrip():
    parts = [b"", b"a", b"bcd", b"\x00" * 100]
    assert unpack(pack(*parts), len(parts)) == parts


def test_unpack_rejects_trailing_bytes():
    with pytest.raises(ValueError):
        unpack(pack(b"a", b"b") + b"x", 2)


def test_hybrid_kem_secret_agreement():
    provider = build_kem(HYBRID_KEM)
    pair = provider.generate_keypair()
    enc = provider.encapsulate(pair.public_key)
    assert provider.decapsulate(pair.private_key, enc.ciphertext) == enc.shared_secret
    assert len(enc.shared_secret) == 32


def test_hybrid_kem_ciphertext_carries_both_components():
    provider = build_kem(HYBRID_KEM)
    pair = provider.generate_keypair()
    enc = provider.encapsulate(pair.public_key)
    x25519_ct, mlkem_ct = unpack(enc.ciphertext, 2)
    assert len(x25519_ct) == 32           # raw X25519 public key
    assert len(mlkem_ct) == 1088          # ML-KEM-768 ciphertext (FIPS 203)


def test_hybrid_kem_tampering_with_one_component_breaks_the_secret():
    provider = build_kem(HYBRID_KEM)
    pair = provider.generate_keypair()
    enc = provider.encapsulate(pair.public_key)

    x25519_ct, mlkem_ct = unpack(enc.ciphertext, 2)
    flipped = bytes([mlkem_ct[0] ^ 0x01]) + mlkem_ct[1:]
    tampered = pack(x25519_ct, flipped)

    recovered = provider.decapsulate(pair.private_key, tampered)
    assert recovered != enc.shared_secret


def test_composite_signature_requires_every_component():
    provider = build_sig(COMPOSITE_SIG)
    message = b"deed-archive:transfer:AP-VZM-2026-000042"
    pair = provider.generate_keypair()
    signed = provider.sign(pair.private_key, message)

    assert provider.verify(pair.public_key, message, signed.signature)

    ecdsa_sig, mldsa_sig = unpack(signed.signature, 2)

    # Drop the post-quantum half -> must fail.
    forged = pack(ecdsa_sig, b"\x00" * len(mldsa_sig))
    assert not provider.verify(pair.public_key, message, forged)

    # Drop the classical half -> must fail.
    forged = pack(b"\x00" * len(ecdsa_sig), mldsa_sig)
    assert not provider.verify(pair.public_key, message, forged)


def test_composite_signature_rejects_wrong_message():
    provider = build_sig(COMPOSITE_SIG)
    pair = provider.generate_keypair()
    signed = provider.sign(pair.private_key, b"original")
    assert not provider.verify(pair.public_key, b"changed", signed.signature)
