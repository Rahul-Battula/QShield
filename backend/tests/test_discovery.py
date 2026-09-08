"""Phase 2 acceptance tests — the CBOM scanner.

Claim: pointed at an estate, the scanner produces a complete, classified
inventory of its cryptography, distinguishing what a classical attacker already
breaks, what a quantum computer will break, and what is safe.

The end-to-end tests run against the bundled ``mock_estate/`` (committed, so the
expected findings are fixed). The classifier and the certificate/key parsers
are also exercised directly.
"""

from __future__ import annotations

import datetime
import json

import pytest

from app.config import estate_root
from app.discovery import (
    AssetKind,
    Exposure,
    classify,
    render,
    render_markdown,
    render_table,
    scan_estate,
)
from app.discovery.detectors import CertificateDetector, KeyMaterialDetector


@pytest.fixture(scope="module")
def cbom():
    """One scan of the bundled mock estate, shared by the read-only tests."""
    return scan_estate(estate_root())


def _find(cbom, *, primitive=None, location_contains=None, kind=None):
    out = []
    for a in cbom.assets:
        if primitive is not None and a.primitive != primitive:
            continue
        if location_contains is not None and location_contains not in a.location:
            continue
        if kind is not None and a.kind != kind:
            continue
        out.append(a)
    return out


# ---------------------------------------------------------------------------
# End-to-end: the mock estate
# ---------------------------------------------------------------------------

def test_scan_produces_a_nontrivial_inventory(cbom):
    assert len(cbom.assets) >= 20
    assert cbom.summary()["total"] == len(cbom.assets)
    # Every exposure count sums back to the total.
    s = cbom.summary()
    assert sum(s[e.value] for e in Exposure) == s["total"]


def test_rsa_keygen_in_source_is_quantum_broken(cbom):
    hits = _find(cbom, primitive="RSA", location_contains="records_service.py")
    assert hits, "expected the RSA keypair generation in the land-registry service"
    call = next(a for a in hits if a.kind == AssetKind.LIBRARY_CALL)
    assert call.detail == "RSA-2048"
    assert call.key_bits == 2048
    assert call.exposure is Exposure.QUANTUM_BROKEN
    assert "Shor" in call.rationale
    assert "hybrid" in call.recommendation


def test_md5_password_hash_is_classically_broken(cbom):
    hits = _find(cbom, primitive="MD5", location_contains="auth.py")
    assert hits
    assert hits[0].exposure is Exposure.CLASSICALLY_BROKEN


def test_legacy_tls_versions_flagged(cbom):
    tls = [a for a in cbom.assets if a.detail.startswith(("TLSv1", "SSLv"))]
    versions = {a.detail for a in tls}
    assert "TLSv1" in versions and "TLSv1.1" in versions
    for a in tls:
        if a.detail in ("TLSv1", "TLSv1.1"):
            assert a.exposure is Exposure.CLASSICALLY_BROKEN
        if a.detail in ("TLSv1.2", "TLSv1.3"):
            assert a.exposure is Exposure.QUANTUM_SAFE


def test_triple_des_and_rc4_ciphers_flagged(cbom):
    assert _find(cbom, primitive="3DES")
    assert all(a.exposure is Exposure.CLASSICALLY_BROKEN
               for a in _find(cbom, primitive="3DES"))
    assert _find(cbom, primitive="RC4")


def test_ssh_config_key_exchange_and_key_types(cbom):
    dh = _find(cbom, primitive="DH", location_contains="sshd_config")
    assert dh and dh[0].exposure is Exposure.QUANTUM_BROKEN
    rsa_keytype = _find(cbom, primitive="RSA", location_contains="sshd_config")
    assert rsa_keytype and rsa_keytype[0].exposure is Exposure.QUANTUM_BROKEN


def test_authorized_keys_rsa_bit_size_recovered(cbom):
    keys = _find(cbom, location_contains="authorized_keys", kind=AssetKind.PUBLIC_KEY)
    by_detail = {a.detail for a in keys}
    assert "RSA-3072" in by_detail  # parsed from the real ssh-rsa blob
    assert "RSA-1024" in by_detail
    assert any(a.primitive == "Ed25519" for a in keys)
    assert all(a.exposure is Exposure.QUANTUM_BROKEN
               for a in keys if a.primitive in ("RSA", "Ed25519"))


def test_saml_metadata_rsa_sha1_signature(cbom):
    sig = _find(cbom, location_contains="metadata.xml", primitive="RSA")
    assert sig and sig[0].kind == AssetKind.TOKEN_CONFIG
    digest = _find(cbom, location_contains="metadata.xml", primitive="SHA-1")
    assert digest


def test_jwt_rs256_is_a_token_config_finding(cbom):
    tok = _find(cbom, kind=AssetKind.TOKEN_CONFIG, primitive="RSA")
    assert tok, "expected RS256 JWT/token findings"
    assert any("records_service.py" in a.location for a in tok)


def test_post_quantum_controls_are_reported_safe(cbom):
    mlkem = _find(cbom, primitive="ML-KEM")
    mldsa = _find(cbom, primitive="ML-DSA")
    assert mlkem and mldsa
    assert all(a.exposure is Exposure.QUANTUM_SAFE for a in mlkem + mldsa)


def test_aes256_and_sha512_controls_are_safe(cbom):
    aes = _find(cbom, primitive="AES", location_contains="rotate.js")
    assert aes and aes[0].key_bits == 256
    assert aes[0].exposure is Exposure.QUANTUM_SAFE
    assert all(a.exposure is Exposure.QUANTUM_SAFE
               for a in _find(cbom, primitive="SHA-512"))


def test_aes128_is_only_weakened_not_broken(cbom):
    aes128 = [a for a in _find(cbom, primitive="AES") if a.key_bits == 128]
    assert aes128
    assert all(a.exposure is Exposure.QUANTUM_WEAKENED for a in aes128)


def test_urgent_and_vulnerable_partitions(cbom):
    urgent = cbom.urgent()
    assert urgent  # there is plenty broken in the mock estate
    assert all(a.exposure in (Exposure.CLASSICALLY_BROKEN, Exposure.QUANTUM_BROKEN)
               for a in urgent)
    assert all(a.exposure in (Exposure.QUANTUM_BROKEN, Exposure.QUANTUM_WEAKENED)
               for a in cbom.quantum_vulnerable())


def test_assets_are_ordered_most_urgent_first(cbom):
    from app.discovery.cbom import SEVERITY

    severities = [SEVERITY[a.exposure] for a in cbom.assets]
    assert severities == sorted(severities)


# ---------------------------------------------------------------------------
# Determinism and reporting
# ---------------------------------------------------------------------------

def test_scan_is_deterministic():
    a = scan_estate(estate_root())
    b = scan_estate(estate_root())
    assert [x.asset_id for x in a.assets] == [x.asset_id for x in b.assets]


def test_asset_ids_are_stable_and_unique(cbom):
    ids = [a.asset_id for a in cbom.assets]
    assert len(ids) == len(set(ids))
    assert all(len(i) == 12 for i in ids)


def test_empty_estate_gives_empty_cbom(tmp_path):
    (tmp_path / "notes.txt").write_text("nothing cryptographic here")
    cbom = scan_estate(tmp_path)
    assert cbom.assets == ()
    assert cbom.summary()["total"] == 0


def test_json_report_round_trips(cbom):
    payload = json.loads(cbom.to_json())
    assert payload["summary"]["total"] == len(cbom.assets)
    assert len(payload["assets"]) == len(cbom.assets)
    assert {"asset_id", "primitive", "exposure", "rationale"} <= set(payload["assets"][0])


def test_table_and_markdown_render(cbom):
    table = render_table(cbom)
    assert "EXPOSURE" in table and "QUANTUM-BROKEN" in table
    md = render_markdown(cbom)
    assert md.startswith("# Cryptographic Bill of Materials")
    assert "## Rationale" in md
    assert render(cbom, "json") == cbom.to_json()


def test_env_override_points_the_scanner_elsewhere(tmp_path, monkeypatch):
    (tmp_path / "svc.py").write_text("import hashlib\nh = hashlib.md5(b'x')\n")
    monkeypatch.setenv("QSHIELD_ESTATE", str(tmp_path))
    cbom = scan_estate()  # no argument -> reads QSHIELD_ESTATE
    assert [a.primitive for a in cbom.assets] == ["MD5"]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "primitive,bits,expected",
    [
        ("RSA", 2048, Exposure.QUANTUM_BROKEN),
        ("RSA", 4096, Exposure.QUANTUM_BROKEN),
        ("ECDSA", None, Exposure.QUANTUM_BROKEN),
        ("ECDH", None, Exposure.QUANTUM_BROKEN),
        ("Ed25519", None, Exposure.QUANTUM_BROKEN),
        ("X25519", None, Exposure.QUANTUM_BROKEN),
        ("DSA", None, Exposure.QUANTUM_BROKEN),
        ("3DES", None, Exposure.CLASSICALLY_BROKEN),
        ("DES", None, Exposure.CLASSICALLY_BROKEN),
        ("RC4", None, Exposure.CLASSICALLY_BROKEN),
        ("MD5", None, Exposure.CLASSICALLY_BROKEN),
        ("SHA-1", None, Exposure.CLASSICALLY_BROKEN),
        ("AES", 128, Exposure.QUANTUM_WEAKENED),
        ("AES", 256, Exposure.QUANTUM_SAFE),
        ("SHA-256", None, Exposure.QUANTUM_WEAKENED),
        ("SHA-512", None, Exposure.QUANTUM_SAFE),
        ("ML-KEM", None, Exposure.QUANTUM_SAFE),
        ("ML-DSA", None, Exposure.QUANTUM_SAFE),
        ("SLH-DSA", None, Exposure.QUANTUM_SAFE),
        ("Kyber", None, Exposure.QUANTUM_SAFE),
        ("Frobnicator-9000", None, Exposure.UNKNOWN),
    ],
)
def test_classify_table(primitive, bits, expected):
    exposure, rationale, recommendation = classify(primitive, bits)
    assert exposure is expected
    assert rationale and recommendation


def test_classify_is_case_insensitive():
    assert classify("rsa", 2048)[0] is Exposure.QUANTUM_BROKEN
    assert classify("Ml-Kem")[0] is Exposure.QUANTUM_SAFE


# ---------------------------------------------------------------------------
# Certificate and key detectors, in isolation
# ---------------------------------------------------------------------------

def _selfsigned(private_key, hash_alg):
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.example")])
    now = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(private_key, hash_alg)
    )


def test_certificate_detector_reads_rsa_cert(tmp_path):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = _selfsigned(key, hashes.SHA256())
    p = tmp_path / "server.crt"
    p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    findings = list(CertificateDetector().scan(p, p.read_text()))
    prims = {f.primitive for f in findings}
    assert "RSA" in prims and "SHA-256" in prims
    rsa_finding = next(f for f in findings if f.primitive == "RSA")
    assert rsa_finding.key_bits == 2048
    assert rsa_finding.kind is AssetKind.CERTIFICATE


def test_key_detector_parses_pem_private_key(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    p = tmp_path / "service.key"
    p.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    findings = list(KeyMaterialDetector().scan(p, p.read_text()))
    assert findings and findings[0].primitive == "ECDSA"
    assert findings[0].kind is AssetKind.PRIVATE_KEY
