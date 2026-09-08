"""Detectors — the part that actually finds cryptography in files.

Each :class:`Detector` recognises one family of source of evidence (source
code, protocol config, X.509 certificates, key material) and yields
:class:`RawFinding` objects. A raw finding is pre-judgement: it says *what* was
found and *where*, not whether it is a problem. :mod:`.scanner` runs every
detector over every file and hands each finding to :mod:`.classify`.

Detection here is deliberately lexical — regex over text, plus real parsing for
certificates and keys where a library is available. It is meant to be honest
about coverage rather than exhaustive: a real CBOM tool would add AST analysis,
binary scanning and network probing. The gaps are acceptable because the point
of Phase 2 is the *inventory and classification pipeline*, not perfect recall.
"""

from __future__ import annotations

import base64
import re
import struct
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .cbom import AssetKind


@dataclass(frozen=True, slots=True)
class RawFinding:
    """Evidence of one cryptographic usage, before classification."""

    kind: AssetKind
    primitive: str
    detail: str
    evidence: str
    line: int | None = None
    key_bits: int | None = None


class Detector(ABC):
    """Recognises one class of cryptographic evidence in a file."""

    name: str

    @abstractmethod
    def applies(self, path: Path) -> bool:
        """Return ``True`` if this detector should run against ``path``."""

    @abstractmethod
    def scan(self, path: Path, text: str) -> Iterator[RawFinding]:
        """Yield a :class:`RawFinding` for each cryptographic usage found.

        ``text`` is the file decoded as UTF-8 with replacement; detectors that
        need the raw bytes (certificates, DER keys) re-read ``path`` themselves.
        """


def _trim(s: str, limit: int = 160) -> str:
    s = s.strip()
    return s if len(s) <= limit else s[: limit - 3] + "..."


# ---------------------------------------------------------------------------
# Source code
# ---------------------------------------------------------------------------

_SOURCE_SUFFIXES = {
    # .py is handled by AstPythonDetector; everything else stays pattern-based.
    ".js", ".mjs", ".cjs", ".ts", ".java", ".go", ".rb", ".php",
    ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".kt", ".scala", ".rs",
}

# (pattern, primitive, kind). The first capture group, if present, is a size.
_SOURCE_PATTERNS: list[tuple[re.Pattern[str], str, AssetKind]] = [
    (re.compile(r"rsa\.generate_private_key\(|RSA\.generate\(|"
                r"KeyPairGenerator\.getInstance\(\s*[\"']RSA[\"']|"
                r"new\s+RSACryptoServiceProvider|RSA\.Create\(|"
                r"generateKeyPair(?:Sync)?\(\s*[\"']rsa[\"']"), "RSA", AssetKind.LIBRARY_CALL),
    (re.compile(r"DSA\.generate\(|KeyPairGenerator\.getInstance\(\s*[\"']DSA[\"']"),
     "DSA", AssetKind.LIBRARY_CALL),
    (re.compile(r"ec\.generate_private_key\(|ec\.SECP(?:256R1|384R1|521R1)|"
                r"SECP256R1|SECP384R1|prime256v1|secp384r1|"
                r"KeyPairGenerator\.getInstance\(\s*[\"']EC[\"']|"
                r"ECDsa\.Create\(|new\s+ECDSA"), "ECDSA", AssetKind.LIBRARY_CALL),
    (re.compile(r"\bECDH\b"), "ECDH", AssetKind.LIBRARY_CALL),
    (re.compile(r"[Ee]d25519"), "Ed25519", AssetKind.LIBRARY_CALL),
    (re.compile(r"[Xx]25519|curve25519"), "X25519", AssetKind.LIBRARY_CALL),
    (re.compile(r"hashlib\.md5|MD5\.Create\(|createHash\(\s*[\"']md5[\"']|"
                r"MessageDigest\.getInstance\(\s*[\"']MD5[\"']|\bmd5\("),
     "MD5", AssetKind.LIBRARY_CALL),
    (re.compile(r"hashlib\.sha1\b|createHash\(\s*[\"']sha1[\"']|"
                r"MessageDigest\.getInstance\(\s*[\"']SHA-?1[\"']|\bSHA1\b|"
                r"pbkdf2_hmac\(\s*[\"']sha-?1[\"']|hmac-sha1|HMAC-SHA1"),
     "SHA-1", AssetKind.LIBRARY_CALL),
    (re.compile(r"hashlib\.sha512|createHash\(\s*[\"']sha512[\"']|SHA-?512"),
     "SHA-512", AssetKind.LIBRARY_CALL),
    (re.compile(r"hashlib\.sha256|createHash\(\s*[\"']sha256[\"']|"
                r"MessageDigest\.getInstance\(\s*[\"']SHA-?256[\"']"),
     "SHA-256", AssetKind.LIBRARY_CALL),
    (re.compile(r"DES3|TripleDES|DESede|[\"']3DES[\"']|algorithms\.TripleDES|"
                r"Cipher\.getInstance\(\s*[\"']DESede"),
     "3DES", AssetKind.LIBRARY_CALL),
    (re.compile(r"Cipher\.getInstance\(\s*[\"']DES[\"']|[\"']DES/|\bpyDes\b"),
     "DES", AssetKind.LIBRARY_CALL),
    (re.compile(r"\bRC4\b|\bARC4\b|\bARCFOUR\b|Rc4Engine|Cipher\.getInstance\(\s*[\"']RC4"),
     "RC4", AssetKind.LIBRARY_CALL),
    (re.compile(r"Cipher\.getInstance\(\s*[\"']RSA"), "RSA", AssetKind.LIBRARY_CALL),
    (re.compile(r"createCipheriv\(\s*[\"']aes-(\d+)|AES\.new\(|algorithms\.AES\(|"
                r"Aes\.Create\(|Cipher\.getInstance\(\s*[\"']AES"),
     "AES", AssetKind.LIBRARY_CALL),
    (re.compile(r"ML-?KEM|\bKyber\b|kyber_py|\bmlkem\b"), "ML-KEM", AssetKind.LIBRARY_CALL),
    (re.compile(r"ML-?DSA|\bDilithium\b|dilithium_py"), "ML-DSA", AssetKind.LIBRARY_CALL),
    (re.compile(r"SLH-?DSA|\bSPHINCS\+?\b"), "SLH-DSA", AssetKind.LIBRARY_CALL),
]

_SIZE_NEAR = re.compile(r"(?:key_size|keysize|modulusLength|bits|key_length)\s*[=:]\s*(\d+)",
                        re.IGNORECASE)

_JWT_ALG = re.compile(
    r"(?:algorithm|algorithms)\s*=\s*\[?\s*[\"'](RS256|RS384|RS512|PS256|PS384|"
    r"ES256|ES384|ES512|HS256|HS384|HS512|EdDSA|none)[\"']",
    re.IGNORECASE,
)

_JWT_PRIMITIVE = {
    "RS": ("RSA", None), "PS": ("RSA", None),
    "ES": ("ECDSA", None),
    "HS": ("HMAC", None),
    "ED": ("Ed25519", None),
    "NO": ("NONE", None),
}


def _jwt_primitive(alg: str) -> tuple[str, str]:
    fam, _ = _JWT_PRIMITIVE.get(alg[:2].upper(), ("UNKNOWN", None))
    return fam, alg.upper()


class SourceCodeDetector(Detector):
    """Regex scan of source files for crypto-library calls and token settings."""

    name = "source"

    def applies(self, path: Path) -> bool:
        return path.suffix.lower() in _SOURCE_SUFFIXES

    def scan(self, path: Path, text: str) -> Iterator[RawFinding]:
        for lineno, line in enumerate(text.splitlines(), start=1):
            if len(line) > 400:
                line = line[:400]
            for pattern, primitive, kind in _SOURCE_PATTERNS:
                m = pattern.search(line)
                if not m:
                    continue
                bits: int | None = None
                if m.groups() and m.group(1) and m.group(1).isdigit():
                    bits = int(m.group(1))
                if bits is None:
                    near = _SIZE_NEAR.search(line)
                    if near:
                        bits = int(near.group(1))
                detail = f"{primitive}-{bits}" if bits else primitive
                yield RawFinding(kind, primitive, detail, _trim(line), lineno, bits)

            jm = _JWT_ALG.search(line)
            if jm:
                fam, alg = _jwt_primitive(jm.group(1))
                yield RawFinding(
                    AssetKind.TOKEN_CONFIG, fam, f"JWT {alg}", _trim(line), lineno
                )


# ---------------------------------------------------------------------------
# Protocol / application configuration
# ---------------------------------------------------------------------------

_CONFIG_SUFFIXES = {
    ".conf", ".cnf", ".cfg", ".ini", ".yaml", ".yml", ".toml",
    ".properties", ".xml", ".json", ".config",
}
_CONFIG_NAMES = {"sshd_config", "ssh_config", "nginx.conf", "openssl.cnf"}

_TLS_VERSIONS = re.compile(
    r"(?<![\w.-])(SSLv2|SSLv3|TLSv1\.3|TLSv1\.2|TLSv1\.1|TLSv1)(?![\w.])"
)
_PROTO_LINE = re.compile(
    r"(?i)^\s*(?:ssl_protocols|SSLProtocol|Protocols?|MinProtocol|ssl_min_protocol_version)\b(.*)$"
)
_CIPHER_LINE = re.compile(
    r"(?i)^\s*(?:ssl_ciphers?|SSLCipherSuite|Ciphers|cipher|tls-cipher)\b(.*)$"
)
_KEX_LINE = re.compile(r"(?i)^\s*(?:KexAlgorithms|ssl_ecdh_curve|Curves|Groups)\b(.*)$")
_SSH_KEYTYPE = re.compile(
    r"(?i)(?<![\w-])(ssh-rsa|ssh-dss|rsa-sha2-\d+|ecdsa-sha2-nistp\d+|ssh-ed25519)(?![\w-])"
)
_CONF_JWT = re.compile(
    r"(?i)(?:^|[\s\"'])(?:alg|algorithm|jwt_algorithm|signing_algorithm)\s*[:=]\s*"
    r"[\"']?(RS256|RS384|RS512|PS256|ES256|ES384|HS256|HS384|HS512|EdDSA|none)[\"']?"
)
_CONF_HASH = re.compile(
    r"(?i)(?:^|[\s\"'])(?:digest|hash|hash_algorithm|hashing|mac|mac_algorithm|"
    r"signature_hash|pbkdf2_hash|password_hash|algorithm)\s*[:=]\s*[\"']?"
    r"(?:HMAC[-_])?(MD5|SHA-?1|SHA-?224|SHA-?256|SHA-?384|SHA-?512)[\"']?"
)
_HASH_NORM = {"SHA1": "SHA-1", "SHA224": "SHA-224", "SHA256": "SHA-256",
              "SHA384": "SHA-384", "SHA512": "SHA-512", "MD5": "MD5"}
_XML_SIGMETHOD = re.compile(
    r"(?i)(?:SignatureMethod|SignatureAlgorithm)[^>]*?Algorithm\s*=\s*\"[^\"]*?"
    r"#(rsa-sha1|rsa-sha256|rsa-sha512|ecdsa-sha1|ecdsa-sha256|dsa-sha1|hmac-sha1)\""
)
_XML_DIGEST = re.compile(
    r"(?i)DigestMethod[^>]*?Algorithm\s*=\s*\"[^\"]*?#(sha1|sha256|sha384|sha512)\""
)

_WEAK_CIPHER_TOKENS: list[tuple[re.Pattern[str], str, int | None]] = [
    (re.compile(r"(?i)3DES|DES-CBC3|DESede"), "3DES", None),
    (re.compile(r"(?i)(?<![\w-])DES(?![\w-])"), "DES", None),
    (re.compile(r"(?i)RC4|ARCFOUR"), "RC4", None),
    (re.compile(r"(?i)(?<![\w-])(?:e?NULL)(?![\w-])"), "NULL", None),
    (re.compile(r"(?i)(?<![\w-])MD5(?![\w-])"), "MD5", None),
    (re.compile(r"(?i)BF-CBC|BLOWFISH"), "BLOWFISH", None),
    (re.compile(r"(?i)AES[-_]?128"), "AES", 128),
    (re.compile(r"(?i)AES[-_]?256"), "AES", 256),
]

_KEX_TOKENS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(?i)sntrup761x25519|mlkem768x25519|x25519mlkem768|x25519kyber768"),
     "ML-KEM", "PQC hybrid key exchange"),
    (re.compile(r"(?i)diffie-hellman-group1-sha1|diffie-hellman-group-exchange-sha1|"
                r"diffie-hellman-group14-sha1"), "DH", "SHA-1 group exchange"),
    (re.compile(r"(?i)diffie-hellman|(?<![\w-])DHE(?![\w-])|ffdhe\d+"), "DH", "finite-field DH"),
    (re.compile(r"(?i)ecdh-sha2-nistp\d+|(?<![\w-])ECDHE?(?![\w-])|secp\d+r1|prime256v1"),
     "ECDH", "elliptic-curve DH"),
    (re.compile(r"(?i)curve25519"), "X25519", "curve25519 key exchange"),
]


class ConfigDetector(Detector):
    """Scan TLS/SSH/token configuration for protocol versions, cipher suites,
    key-exchange groups and signed-token algorithms."""

    name = "config"

    def applies(self, path: Path) -> bool:
        return path.suffix.lower() in _CONFIG_SUFFIXES or path.name in _CONFIG_NAMES

    def scan(self, path: Path, text: str) -> Iterator[RawFinding]:
        for lineno, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            pm = _PROTO_LINE.match(raw)
            if pm:
                for ver in _TLS_VERSIONS.findall(pm.group(1)):
                    yield RawFinding(
                        AssetKind.PROTOCOL_CONFIG, ver, ver, _trim(line), lineno
                    )

            cm = _CIPHER_LINE.match(raw)
            if cm:
                seen: set[tuple[str, int | None]] = set()
                for pat, prim, bits in _WEAK_CIPHER_TOKENS:
                    if pat.search(cm.group(1)) and (prim, bits) not in seen:
                        seen.add((prim, bits))
                        detail = f"{prim}-{bits}" if bits else prim
                        yield RawFinding(
                            AssetKind.PROTOCOL_CONFIG, prim, detail, _trim(line),
                            lineno, bits,
                        )

            km = _KEX_LINE.match(raw)
            if km:
                seen_kex: set[str] = set()
                for pat, prim, note in _KEX_TOKENS:
                    if pat.search(km.group(1)) and prim not in seen_kex:
                        seen_kex.add(prim)
                        yield RawFinding(
                            AssetKind.PROTOCOL_CONFIG, prim, note, _trim(line), lineno
                        )

            for kt in _SSH_KEYTYPE.findall(line):
                ktl = kt.lower()
                prim = ("RSA" if ktl.startswith(("ssh-rsa", "rsa-sha2"))
                        else "DSA" if ktl == "ssh-dss"
                        else "ECDSA" if ktl.startswith("ecdsa-")
                        else "Ed25519")
                yield RawFinding(
                    AssetKind.PROTOCOL_CONFIG, prim, f"SSH key type {kt}",
                    _trim(line), lineno,
                )

            jm = _CONF_JWT.search(raw)
            if jm:
                fam, alg = _jwt_primitive(jm.group(1))
                yield RawFinding(
                    AssetKind.TOKEN_CONFIG, fam, f"token alg {alg}", _trim(line), lineno
                )

            hm = _CONF_HASH.search(raw)
            if hm:
                prim = _HASH_NORM.get(hm.group(1).upper().replace("-", ""), hm.group(1))
                yield RawFinding(
                    AssetKind.PROTOCOL_CONFIG, prim, f"configured hash {prim}",
                    _trim(line), lineno,
                )

            for sig in _XML_SIGMETHOD.findall(line):
                fam = ("RSA" if sig.startswith("rsa")
                       else "ECDSA" if sig.startswith("ecdsa") else "DSA")
                yield RawFinding(
                    AssetKind.TOKEN_CONFIG, fam, f"XML-DSig {sig}", _trim(line), lineno
                )
            for dig in _XML_DIGEST.findall(line):
                prim = {"sha1": "SHA-1", "sha256": "SHA-256",
                        "sha384": "SHA-384", "sha512": "SHA-512"}[dig.lower()]
                yield RawFinding(
                    AssetKind.TOKEN_CONFIG, prim, f"XML-DSig digest {dig}",
                    _trim(line), lineno,
                )


# ---------------------------------------------------------------------------
# X.509 certificates
# ---------------------------------------------------------------------------

_CERT_SUFFIXES = {".pem", ".crt", ".cer", ".cert", ".ca-bundle"}


class CertificateDetector(Detector):
    """Parse X.509 certificates and inventory their public-key and signature
    algorithms. Uses ``cryptography``; PEM bundles with multiple certs are all
    read."""

    name = "certificate"

    def applies(self, path: Path) -> bool:
        return path.suffix.lower() in _CERT_SUFFIXES

    def scan(self, path: Path, text: str) -> Iterator[RawFinding]:
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
        except ImportError:  # pragma: no cover - cryptography is a hard dependency
            return

        data = path.read_bytes()
        certs = []
        try:
            certs = list(x509.load_pem_x509_certificates(data))
        except Exception:
            try:
                certs = [x509.load_der_x509_certificate(data)]
            except Exception:
                return

        for cert in certs:
            pub = cert.public_key()
            try:
                cn = cert.subject.rfc4514_string()
            except Exception:
                cn = "<unparsed subject>"
            expiry = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
            evidence = _trim(f"{cn} — expires {expiry:%Y-%m-%d}")

            if isinstance(pub, rsa.RSAPublicKey):
                bits = pub.key_size
                yield RawFinding(AssetKind.CERTIFICATE, "RSA", f"RSA-{bits}",
                                 evidence, None, bits)
            elif isinstance(pub, ec.EllipticCurvePublicKey):
                yield RawFinding(AssetKind.CERTIFICATE, "ECDSA",
                                 f"ECDSA-{pub.curve.name}", evidence, None,
                                 pub.curve.key_size)
            elif isinstance(pub, ed25519.Ed25519PublicKey):
                yield RawFinding(AssetKind.CERTIFICATE, "Ed25519", "Ed25519",
                                 evidence, None)
            elif isinstance(pub, ed448.Ed448PublicKey):
                yield RawFinding(AssetKind.CERTIFICATE, "Ed448", "Ed448",
                                 evidence, None)

            sig_hash = getattr(cert.signature_hash_algorithm, "name", None)
            hash_map = {"md5": "MD5", "sha1": "SHA-1", "sha224": "SHA-224",
                        "sha256": "SHA-256", "sha384": "SHA-384", "sha512": "SHA-512"}
            if sig_hash in hash_map:
                yield RawFinding(
                    AssetKind.CERTIFICATE, hash_map[sig_hash],
                    f"cert signature hash {sig_hash}", evidence, None,
                )


# ---------------------------------------------------------------------------
# Key material
# ---------------------------------------------------------------------------

_KEY_SUFFIXES = {".pub", ".key"}
_KEY_NAMES = {
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "authorized_keys", "authorized_keys2",
}
_SSH_PUBLINE = re.compile(
    r"^(ssh-rsa|ssh-dss|ecdsa-sha2-nistp\d+|ssh-ed25519)\s+([A-Za-z0-9+/=]+)"
)
_PEM_PRIVATE = re.compile(
    r"-----BEGIN (RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)


def _ssh_rsa_bits(blob_b64: str) -> int | None:
    """Recover the modulus size from an ``ssh-rsa`` public blob.

    Wire format (RFC 4253): string "ssh-rsa", mpint e, mpint n. The bit length
    of ``n`` is the key size.
    """
    try:
        blob = base64.b64decode(blob_b64, validate=True)
    except Exception:
        return None
    off = 0

    def field() -> bytes | None:
        nonlocal off
        if off + 4 > len(blob):
            return None
        (ln,) = struct.unpack(">I", blob[off : off + 4])
        off += 4
        if off + ln > len(blob):
            return None
        v = blob[off : off + ln]
        off += ln
        return v

    if field() != b"ssh-rsa":
        return None
    field()  # e
    n = field()
    if not n:
        return None
    n = n.lstrip(b"\x00")
    return len(n) * 8 if n else None


class KeyMaterialDetector(Detector):
    """Inventory SSH public keys and PEM private keys by algorithm and size."""

    name = "key"

    def applies(self, path: Path) -> bool:
        # ``.pem`` is ambiguous (cert or key); this detector runs on it too and
        # simply yields nothing when the file holds no private key / SSH key.
        return (
            path.suffix.lower() in _KEY_SUFFIXES
            or path.suffix.lower() == ".pem"
            or path.name in _KEY_NAMES
        )

    def scan(self, path: Path, text: str) -> Iterator[RawFinding]:
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _SSH_PUBLINE.match(line.strip())
            if not m:
                continue
            keytype, blob = m.group(1), m.group(2)
            if keytype == "ssh-rsa":
                bits = _ssh_rsa_bits(blob)
                yield RawFinding(AssetKind.PUBLIC_KEY, "RSA",
                                 f"RSA-{bits}" if bits else "RSA",
                                 _trim(f"{keytype} {blob[:24]}..."), lineno, bits)
            elif keytype == "ssh-dss":
                yield RawFinding(AssetKind.PUBLIC_KEY, "DSA", "DSA-1024",
                                 _trim(f"{keytype} {blob[:24]}..."), lineno, 1024)
            elif keytype.startswith("ecdsa-sha2-"):
                curve = keytype.rsplit("-", 1)[-1]
                yield RawFinding(AssetKind.PUBLIC_KEY, "ECDSA", f"ECDSA-{curve}",
                                 _trim(f"{keytype} {blob[:24]}..."), lineno)
            elif keytype == "ssh-ed25519":
                yield RawFinding(AssetKind.PUBLIC_KEY, "Ed25519", "Ed25519",
                                 _trim(f"{keytype} {blob[:24]}..."), lineno)

        pm = _PEM_PRIVATE.search(text)
        if pm:
            yield from self._pem_private(path, text, pm.group(1))

    def _pem_private(self, path: Path, text: str, header: str | None) -> Iterator[RawFinding]:
        try:
            from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key,
                load_ssh_private_key,
            )
        except ImportError:  # pragma: no cover
            return

        data = text.encode("utf-8", "replace")
        key = None
        for loader in (load_pem_private_key, load_ssh_private_key):
            try:
                key = loader(data, password=None)
                break
            except Exception:
                continue

        if key is None:
            fam = {"RSA ": "RSA", "EC ": "ECDSA", "DSA ": "DSA"}.get(header or "", "UNKNOWN")
            yield RawFinding(AssetKind.PRIVATE_KEY, fam, f"{fam} private key",
                             _trim(f"PEM private key ({(header or 'PKCS#8').strip()})"), 1)
            return

        if isinstance(key, rsa.RSAPrivateKey):
            yield RawFinding(AssetKind.PRIVATE_KEY, "RSA", f"RSA-{key.key_size}",
                             "PEM RSA private key", 1, key.key_size)
        elif isinstance(key, ec.EllipticCurvePrivateKey):
            yield RawFinding(AssetKind.PRIVATE_KEY, "ECDSA", f"ECDSA-{key.curve.name}",
                             "PEM EC private key", 1, key.curve.key_size)
        elif isinstance(key, ed25519.Ed25519PrivateKey):
            yield RawFinding(AssetKind.PRIVATE_KEY, "Ed25519", "Ed25519",
                             "PEM Ed25519 private key", 1)


def _default_detectors() -> tuple[Detector, ...]:
    # Late import: ast_scan imports names from this module, which are all
    # defined above by the time this runs at the bottom of the file.
    from .ast_scan import AstPythonDetector

    return (
        AstPythonDetector(),   # .py — precise, structural
        SourceCodeDetector(),  # .js/.java/.go/... — pattern-based
        ConfigDetector(),
        CertificateDetector(),
        KeyMaterialDetector(),
    )


DEFAULT_DETECTORS: tuple[Detector, ...] = _default_detectors()
