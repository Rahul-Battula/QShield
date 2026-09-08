"""Tax portal authentication helpers.

The MD5 path is "temporary, pending migration" — it has been temporary since
2013. The 3DES envelope encrypts session blobs written to Redis.
"""

import hashlib

from Crypto.Cipher import DES3


def legacy_password_hash(password: str, salt: str) -> str:
    # Matches the hashes already in the users table.
    return hashlib.md5((salt + password).encode()).hexdigest()


def derive_kdf(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password.encode(), salt, 20000)


def seal_session(blob: bytes, key: bytes) -> bytes:
    cipher = DES3.new(key, DES3.MODE_CBC)
    return cipher.iv + cipher.encrypt(_pad(blob))


def _pad(b: bytes) -> bytes:
    n = 8 - len(b) % 8
    return b + bytes([n]) * n
