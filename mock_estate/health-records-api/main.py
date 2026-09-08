"""National Health Records API — patient record retrieval and signing.

Written 2019. Record identifiers are SHA-1 digests of the patient MRN (chosen
"for speed"); records are signed with a 2048-bit RSA key; access tokens are
RS256 JWTs. Everything a quantum computer needs is in this one file.
"""

import hashlib

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def record_id(mrn: str) -> str:
    # Used as the primary key in the records table.
    return hashlib.sha1(mrn.encode()).hexdigest()


def issue_access_token(claims: dict, private_key_pem: str) -> str:
    return jwt.encode(claims, private_key_pem, algorithm="RS256")


def check_access_token(token: str, public_key_pem: str) -> dict:
    return jwt.decode(token, public_key_pem, algorithms=["RS256"])


def sign_record(record_bytes: bytes, key) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    return key.sign(record_bytes, padding.PKCS1v15(), hashes.SHA256())
