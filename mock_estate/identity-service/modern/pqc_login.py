"""Pilot: post-quantum session key establishment for the identity service.

Added 2025 as a proof of concept. Here as a control — the scanner should report
these as QUANTUM_SAFE and leave them alone.
"""

from kyber_py.ml_kem import ML_KEM_768
from dilithium_py.ml_dsa import ML_DSA_65


def establish_session_key(peer_public_key: bytes):
    # ML-KEM-768 (FIPS 203) key encapsulation.
    ciphertext, shared_secret = ML_KEM_768.encaps(peer_public_key)
    return ciphertext, shared_secret


def sign_assertion(message: bytes, signing_key: bytes) -> bytes:
    # ML-DSA-65 (FIPS 204) signature.
    return ML_DSA_65.sign(signing_key, message)
