"""THE acceptance test — QShield's central claim.

Claim: changing only ``policy.yaml`` and calling ``reload()`` makes the running
service use a different cryptographic algorithm, with zero application-code
changes.

The "application" in these tests is the helper :func:`_roundtrip`. It calls
``kem.generate_keypair() / encapsulate() / decapsulate()`` and
``sig.sign() / verify()`` and nothing else. It never imports a backend, never
constructs a provider, and never mentions an algorithm. Only
:func:`write_active_suite` — which edits the ``active_suite:`` line of the
policy file — chooses what runs.

This file was written before the providers it exercises.
"""

from __future__ import annotations

from app.agility import kem, reload, sig
from app.agility.policy import write_active_suite


def _roundtrip() -> tuple[str, int]:
    """Do a full KEM round-trip. Return (algorithm, ciphertext length)."""
    pair = kem.generate_keypair()
    enc = kem.encapsulate(pair.public_key)
    recovered = kem.decapsulate(pair.private_key, enc.ciphertext)
    assert recovered == enc.shared_secret, "KEM round-trip disagreed on the secret"
    return enc.algorithm, len(enc.ciphertext)


def test_default_suite_is_hybrid(policy_file):
    """The shipped default must be hybrid — that is what real deployments run."""
    assert kem.algorithm == "X25519+ML-KEM-768"
    assert sig.algorithm == "ECDSA-P256+ML-DSA-65"


def test_kem_hotswap_classical_to_pqc_to_hybrid(policy_file):
    write_active_suite("classical", policy_file)
    reload()
    algo_classical, ct_classical = _roundtrip()
    assert algo_classical == "RSA-2048"

    # The ONLY change between these blocks is one line of policy.yaml.
    write_active_suite("pqc", policy_file)
    reload()
    algo_pqc, ct_pqc = _roundtrip()
    assert algo_pqc == "ML-KEM-768"
    # Different algorithm, provably: the ciphertext on the wire is a different size.
    assert ct_pqc != ct_classical

    write_active_suite("hybrid", policy_file)
    reload()
    algo_hybrid, ct_hybrid = _roundtrip()
    assert algo_hybrid == "X25519+ML-KEM-768"
    # The hybrid ciphertext carries both component ciphertexts, so it is larger
    # than the ML-KEM one alone.
    assert ct_hybrid > ct_pqc


def test_signature_hotswap_and_tamper_detection(policy_file):
    message = b"land-record:AP-VZM-2026-000042"

    write_active_suite("classical", policy_file)
    reload()
    assert sig.algorithm == "ECDSA-P256"
    pair = sig.generate_keypair()
    signed = sig.sign(pair.private_key, message)
    assert sig.verify(pair.public_key, message, signed.signature)
    assert not sig.verify(pair.public_key, b"tampered", signed.signature)

    write_active_suite("pqc", policy_file)
    reload()
    assert sig.algorithm == "ML-DSA-65"
    pair = sig.generate_keypair()
    signed = sig.sign(pair.private_key, message)
    assert sig.verify(pair.public_key, message, signed.signature)
    assert not sig.verify(pair.public_key, b"tampered", signed.signature)


def test_reload_without_policy_change_is_stable(policy_file):
    before = _roundtrip()[0]
    reload()
    after = _roundtrip()[0]
    assert before == after == "X25519+ML-KEM-768"


def test_ciphertext_size_signature_of_each_kem_suite(policy_file):
    """Each suite leaves a distinct fingerprint on the wire — the clearest
    possible evidence that the algorithm really changed."""
    sizes: dict[str, int] = {}
    for suite in ("classical", "classical-ecdh", "pqc", "pqc-high", "hybrid"):
        write_active_suite(suite, policy_file)
        reload()
        algo, ct_len = _roundtrip()
        sizes[algo] = ct_len
    # No two suites produced the same ciphertext length.
    assert len(set(sizes.values())) == len(sizes), sizes
