"""Treasury Payment Gateway — card authorisation and settlement.

Interfaces with the national card switch over ISO 8583. PIN blocks are
encrypted with Triple-DES (the switch has never supported anything else),
message MACs are HMAC-SHA1, and settlement files are signed with a 1024-bit
RSA key that predates the 2016 key-strength policy.
"""

import hashlib
import hmac

from Crypto.Cipher import DES3
from cryptography.hazmat.primitives.asymmetric import rsa


def settlement_signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=1024)


def encrypt_pin_block(pin_block: bytes, tdes_key: bytes) -> bytes:
    cipher = DES3.new(tdes_key, DES3.MODE_ECB)
    return cipher.encrypt(pin_block)


def message_mac(message: bytes, mac_key: bytes) -> bytes:
    return hmac.new(mac_key, message, hashlib.sha1).digest()


def settlement_digest(batch: bytes) -> str:
    return hashlib.sha1(batch).hexdigest()
