"""AST-based Python crypto detection (spec Component 1 — 'Python via AST')."""

from __future__ import annotations

from pathlib import Path

from app.discovery.ast_scan import AstPythonDetector


def _findings(src: str):
    d = AstPythonDetector()
    return list(d.scan(Path("x.py"), src))


def test_reads_key_size_off_the_keyword_argument():
    f = _findings(
        "from cryptography.hazmat.primitives.asymmetric import rsa\n"
        "k = rsa.generate_private_key(public_exponent=65537, key_size=2048)\n"
    )
    rsa = next(x for x in f if x.primitive == "RSA")
    assert rsa.detail == "RSA-2048" and rsa.key_bits == 2048 and rsa.line == 2


def test_hashlib_calls_and_bare_imports():
    f = _findings(
        "import hashlib\n"
        "from hashlib import sha1\n"
        "a = hashlib.md5(b'x')\n"
        "b = sha1(b'y')\n"
        "c = hashlib.pbkdf2_hmac('sha1', b'p', b's', 1000)\n"
    )
    prims = {x.primitive for x in f}
    assert {"MD5", "SHA-1"} <= prims


def test_jwt_algorithm_from_encode_and_decode():
    f = _findings(
        "import jwt\n"
        "t = jwt.encode(c, k, algorithm='RS256')\n"
        "d = jwt.decode(t, k, algorithms=['RS256', 'ES256'])\n"
    )
    tok = [x for x in f if x.kind.value == "TOKEN_CONFIG"]
    assert {x.detail for x in tok} == {"JWT RS256", "JWT ES256"}


def test_pycryptodome_cipher_import_and_use():
    f = _findings(
        "from Crypto.Cipher import DES3\n"
        "c = DES3.new(key, DES3.MODE_CBC)\n"
    )
    assert [x.primitive for x in f].count("3DES") >= 1
    assert any(x.line == 2 for x in f)  # the .new() call, not only the import


def test_hmac_digestmod_is_detected():
    f = _findings(
        "import hmac, hashlib\n"
        "m = hmac.new(k, msg, hashlib.sha1)\n"
    )
    assert any(x.primitive == "SHA-1" and x.detail == "HMAC-SHA-1" for x in f)


def test_comments_and_strings_are_not_findings():
    f = _findings(
        "# k = rsa.generate_private_key(key_size=512)\n"
        "s = 'call hashlib.md5 here'\n"
        "x = 1\n"
    )
    assert f == []


def test_syntax_error_yields_nothing():
    assert _findings("def (:\n  pass\n") == []


def test_pqc_modules_are_flagged_from_imports():
    f = _findings("from kyber_py.ml_kem import ML_KEM_768\nimport dilithium_py\n")
    assert {x.primitive for x in f} == {"ML-KEM", "ML-DSA"}


def test_seed_services_are_inventoried():
    from app.discovery import scan_estate

    locs = {a.location.split("/", 1)[0] for a in scan_estate().assets}
    assert {"health-records-api", "treasury-gateway"} <= locs
