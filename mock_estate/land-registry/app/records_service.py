"""Land Registry records API — issues and verifies title-deed tokens.

Representative of a service written in 2018 against the ``cryptography`` and
``pyjwt`` libraries, with the algorithm chosen once and hard-coded ever since.
"""

import hashlib

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def issue_signing_key():
    # 2048-bit RSA: the estate standard since 2011.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def deed_fingerprint(deed_bytes: bytes) -> str:
    # Used as the deed's public reference number.
    return hashlib.sha256(deed_bytes).hexdigest()


def issue_token(claims: dict, private_key_pem: str) -> str:
    return jwt.encode(claims, private_key_pem, algorithm="RS256")


def verify_token(token: str, public_key_pem: str) -> dict:
    return jwt.decode(token, public_key_pem, algorithms=["RS256"])
