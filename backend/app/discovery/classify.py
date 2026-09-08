"""Primitive -> quantum exposure. This module is the Phase 2 thesis.

The scanner's job is only to *find* cryptography. The judgement — is this a
problem, and why — lives here, in one table, with the reason attached to every
row. If the consensus on a primitive changes, it changes in one place.

The rules, in plain terms:

* **Shor's algorithm** solves integer factorisation and discrete logarithms in
  polynomial time on a large fault-tolerant quantum computer. That breaks every
  public-key primitive in deployment today: RSA, DSA, Diffie-Hellman, and their
  elliptic-curve forms ECDSA, ECDH, EdDSA/Ed25519, X25519. These are
  :attr:`~app.discovery.cbom.Exposure.QUANTUM_BROKEN`.
* **Grover's algorithm** gives a quadratic speed-up on unstructured search,
  which halves the effective key length of a symmetric primitive. AES-128 drops
  to a 64-bit security level and a 256-bit hash's collision resistance drops to
  128-bit — enough to warrant a parameter bump, not an algorithm change. These
  are :attr:`~app.discovery.cbom.Exposure.QUANTUM_WEAKENED`.
* AES-192/256, SHA-384/512, SHA3 and the NIST PQC standards (ML-KEM, ML-DSA,
  SLH-DSA) keep a sufficient margin and are
  :attr:`~app.discovery.cbom.Exposure.QUANTUM_SAFE`.
* MD5, SHA-1, DES, 3DES, RC4 and the pre-TLS-1.2 protocol versions are
  :attr:`~app.discovery.cbom.Exposure.CLASSICALLY_BROKEN`: a classical
  attacker already defeats them, so they are urgent independent of any quantum
  timeline.

References are the obvious ones — NIST SP 800-131A Rev. 2 for the deprecations,
NIST IR 8413 / FIPS 203-205 for the PQC selections, and the CNSA 2.0 suite for
the government migration target. QShield does not restate them here beyond the
pointer.
"""

from __future__ import annotations

from .cbom import Exposure

# Every recommendation points at a concrete QShield policy suite so the reader
# can go straight from "this is broken" to "swap active_suite to this".
_HYBRID = "Migrate to the 'hybrid' suite (X25519+ML-KEM-768 / ECDSA-P256+ML-DSA-65)."
_PQC = "Migrate to the 'pqc' suite (ML-KEM-768 / ML-DSA-65)."
_BUMP_AES = "Raise to AES-256; no algorithm change needed."
_BUMP_HASH = "Move to SHA-384 or SHA-512."
_REPLACE_NOW = "Replace immediately — this is broken against a classical attacker."
_KEEP = "No action required for quantum resistance."


def _rsa(bits: int | None) -> tuple[Exposure, str, str]:
    size = f"RSA-{bits}" if bits else "RSA"
    return (
        Exposure.QUANTUM_BROKEN,
        f"{size} relies on the hardness of integer factorisation, which Shor's "
        "algorithm solves in polynomial time on a CRQC.",
        _HYBRID,
    )


def _dlog(name: str) -> tuple[Exposure, str, str]:
    return (
        Exposure.QUANTUM_BROKEN,
        f"{name} relies on a discrete-logarithm problem (finite-field or "
        "elliptic-curve), which Shor's algorithm solves in polynomial time.",
        _HYBRID,
    )


# Exact-match primitives (already normalised by the detectors).
_TABLE: dict[str, tuple[Exposure, str, str]] = {
    "DSA": _dlog("DSA"),
    "DH": _dlog("Diffie-Hellman"),
    "ECDSA": _dlog("ECDSA"),
    "ECDH": _dlog("ECDH"),
    "ECDHE": _dlog("ECDHE"),
    "EDDSA": _dlog("EdDSA"),
    "ED25519": _dlog("Ed25519"),
    "ED448": _dlog("Ed448"),
    "X25519": _dlog("X25519"),
    "X448": _dlog("X448"),
    "MD5": (Exposure.CLASSICALLY_BROKEN,
            "MD5 has practical collision attacks and must not be used for any "
            "security purpose.", _REPLACE_NOW),
    "SHA-1": (Exposure.CLASSICALLY_BROKEN,
              "SHA-1 has a practical chosen-prefix collision (SHAttered, 2017) "
              "and is withdrawn by NIST.", _REPLACE_NOW),
    "DES": (Exposure.CLASSICALLY_BROKEN,
            "Single-DES has a 56-bit key and is brute-forceable in hours.",
            _REPLACE_NOW),
    "3DES": (Exposure.CLASSICALLY_BROKEN,
             "Triple-DES is limited by the Sweet32 birthday bound on its 64-bit "
             "block and is disallowed by NIST after 2023.", _REPLACE_NOW),
    "RC4": (Exposure.CLASSICALLY_BROKEN,
            "RC4 has exploitable keystream biases and is prohibited by RFC 7465.",
            _REPLACE_NOW),
    "BLOWFISH": (Exposure.CLASSICALLY_BROKEN,
                 "Blowfish's 64-bit block makes it vulnerable to the Sweet32 "
                 "birthday attack on long-lived connections.", _REPLACE_NOW),
    "NULL": (Exposure.CLASSICALLY_BROKEN,
             "A NULL cipher provides no confidentiality at all.", _REPLACE_NOW),
    "NONE": (Exposure.CLASSICALLY_BROKEN,
             "An unsigned ('alg: none') token can be forged by anyone.",
             _REPLACE_NOW),
    "HMAC": (Exposure.QUANTUM_SAFE,
             "HMAC is not affected by Shor's algorithm; with a >=256-bit key it "
             "retains a >=128-bit margin under Grover. Note the shared-secret key "
             "-distribution problem is unchanged.", _KEEP),
    "SSLV3": (Exposure.CLASSICALLY_BROKEN,
              "SSL 3.0 is broken by POODLE and is prohibited by RFC 7568.",
              _REPLACE_NOW),
    "TLSV1": (Exposure.CLASSICALLY_BROKEN,
              "TLS 1.0 is deprecated by RFC 8996; it permits CBC and weak "
              "renegotiation.", _REPLACE_NOW),
    "TLSV1.1": (Exposure.CLASSICALLY_BROKEN,
                "TLS 1.1 is deprecated by RFC 8996.", _REPLACE_NOW),
    "TLSV1.2": (Exposure.QUANTUM_SAFE,
                "TLS 1.2 is acceptable classically; its quantum exposure is "
                "entirely in the key-exchange and signature primitives it "
                "negotiates, which are inventoried separately.", _KEEP),
    "TLSV1.3": (Exposure.QUANTUM_SAFE,
                "TLS 1.3 is current; quantum exposure is in the negotiated "
                "groups and signatures, inventoried separately.", _KEEP),
    "SHA-256": (Exposure.QUANTUM_WEAKENED,
                "Grover's algorithm reduces SHA-256's collision resistance to "
                "roughly 2^128 work; acceptable for most uses, marginal where "
                "long-term collision resistance is required.", _BUMP_HASH),
    "SHA-224": (Exposure.QUANTUM_WEAKENED,
                "224-bit output leaves a ~112-bit post-Grover margin.", _BUMP_HASH),
    "SHA-384": (Exposure.QUANTUM_SAFE,
                "384-bit output retains a ~192-bit margin under Grover.", _KEEP),
    "SHA-512": (Exposure.QUANTUM_SAFE,
                "512-bit output retains a ~256-bit margin under Grover.", _KEEP),
    "SHA3-256": (Exposure.QUANTUM_WEAKENED,
                 "As with SHA-256, Grover halves the effective collision "
                 "resistance.", _BUMP_HASH),
    "SHA3-512": (Exposure.QUANTUM_SAFE, "512-bit output retains its margin.", _KEEP),
    "ML-KEM": (Exposure.QUANTUM_SAFE,
               "ML-KEM (FIPS 203) is a NIST post-quantum standard with no known "
               "quantum or classical break.", _KEEP),
    "ML-DSA": (Exposure.QUANTUM_SAFE,
               "ML-DSA (FIPS 204) is a NIST post-quantum signature standard.",
               _KEEP),
    "SLH-DSA": (Exposure.QUANTUM_SAFE,
                "SLH-DSA (FIPS 205) is a hash-based NIST signature standard with "
                "the most conservative assumption available.", _KEEP),
    "HQC": (Exposure.QUANTUM_SAFE,
            "HQC is the NIST-selected code-based KEM, on different mathematics "
            "from the lattice schemes.", _KEEP),
}

# Aliases the detectors may emit, mapped onto a canonical key above.
_ALIAS: dict[str, str] = {
    "KYBER": "ML-KEM",
    "DILITHIUM": "ML-DSA",
    "SPHINCS+": "SLH-DSA",
    "SPHINCS": "SLH-DSA",
    "RSASSA-PSS": "RSA",
    "RSA-PSS": "RSA",
    "DHE": "DH",
    "DIFFIE-HELLMAN": "DH",
    "SECP256R1": "ECDSA",
    "PRIME256V1": "ECDSA",
    "P-256": "ECDSA",
    "P-384": "ECDSA",
    "CURVE25519": "X25519",
}


def classify(primitive: str, key_bits: int | None = None) -> tuple[Exposure, str, str]:
    """Return ``(exposure, rationale, recommendation)`` for a primitive.

    ``primitive`` is matched case-insensitively. ``key_bits`` refines the
    families where the size determines the verdict (RSA, AES).
    """
    key = primitive.strip().upper()
    key = _ALIAS.get(key, key)

    if key == "RSA":
        return _rsa(key_bits)

    if key == "AES":
        if key_bits is None or key_bits <= 128:
            return (
                Exposure.QUANTUM_WEAKENED,
                f"AES-{key_bits or 128} has its effective security level halved "
                "to ~64-bit by Grover's algorithm.",
                _BUMP_AES,
            )
        return (
            Exposure.QUANTUM_SAFE,
            f"AES-{key_bits} retains a ~{key_bits // 2}-bit security level under "
            "Grover's algorithm.",
            _KEEP,
        )

    if key in _TABLE:
        return _TABLE[key]

    return (
        Exposure.UNKNOWN,
        f"{primitive!r} is not in the QShield classification table; a human "
        "should assess it.",
        "Manually assess this primitive's quantum exposure.",
    )
