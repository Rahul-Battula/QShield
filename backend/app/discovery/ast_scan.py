"""AST-based cryptography detection for Python source.

Regex has good recall but no structure: it cannot read a keyword argument, tell
an import from a comment, or follow ``from hashlib import md5`` to a bare
``md5()`` call. This detector parses the file and walks the tree, so line
numbers are exact, ``key_size=`` is read straight off the ``keyword`` node, and
a ``# jwt.encode(...)`` in a comment is never a finding.

It replaces :class:`SourceCodeDetector` for ``.py`` files; that detector still
handles JavaScript, Java, Go and the rest by pattern.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from .cbom import AssetKind
from .detectors import Detector, RawFinding, _trim

_HASH_METHODS = {
    "md5": "MD5", "sha1": "SHA-1", "sha224": "SHA-224", "sha256": "SHA-256",
    "sha384": "SHA-384", "sha512": "SHA-512",
}
# module/name -> primitive for imports that are themselves the finding
_IMPORT_PRIMITIVE = {
    "kyber_py": "ML-KEM", "dilithium_py": "ML-DSA", "pqcrypto": "ML-KEM",
}
# cryptography's `algorithms.X` / pycryptodome `Crypto.Cipher.X`
_CIPHER_NAME = {
    "AES": "AES", "TripleDES": "3DES", "DES3": "3DES", "DES": "DES",
    "ARC4": "RC4", "Blowfish": "BLOWFISH", "ChaCha20": "ChaCha20",
}
_JWT_ALG = {"RS": "RSA", "PS": "RSA", "ES": "ECDSA", "HS": "HMAC",
            "ED": "Ed25519", "NO": "NONE"}


def _attr_chain(node: ast.AST) -> list[str]:
    """``a.b.c`` -> ``['a', 'b', 'c']`` for Name/Attribute chains."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return parts[::-1]


def _const(node: ast.AST):
    return node.value if isinstance(node, ast.Constant) else None


class AstPythonDetector(Detector):
    """Parse ``.py`` files and report cryptographic usage from the AST."""

    name = "source"  # same detector-confidence bucket as the regex source scanner

    def applies(self, path: Path) -> bool:
        return path.suffix.lower() == ".py"

    def scan(self, path: Path, text: str) -> Iterator[RawFinding]:
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            return

        # imported-name -> the dotted module it came from
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    aliases[a.asname or a.name.split(".")[0]] = a.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    aliases[a.asname or a.name] = f"{node.module}.{a.name}"

        def src(node: ast.AST) -> str:
            seg = ast.get_source_segment(text, node)
            return _trim(seg or "")

        # -- imports that are themselves a finding --------------------
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            mod = node.module if isinstance(node, ast.ImportFrom) else ""
            # a whole PQC module: `import kyber_py...` / `from kyber_py import ...`
            for candidate in [mod, *(a.name for a in node.names)]:
                top = (candidate or "").split(".")[0]
                if top in _IMPORT_PRIMITIVE:
                    prim = _IMPORT_PRIMITIVE[top]
                    yield RawFinding(AssetKind.LIBRARY_CALL, prim, prim,
                                     src(node), node.lineno)
                    break
            # a specific cipher class out of pycryptodome / cryptography
            if "Cipher" in mod or "crypto" in mod.lower():
                for a in node.names:
                    if a.name in _CIPHER_NAME:
                        prim = _CIPHER_NAME[a.name]
                        yield RawFinding(AssetKind.LIBRARY_CALL, prim, prim,
                                         src(node), node.lineno)

        # -- calls -----------------------------------------------
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            yield from self._from_call(node, aliases, src)

    def _from_call(self, node: ast.Call, aliases: dict[str, str], src) -> Iterator[RawFinding]:
        func = node.func
        chain = _attr_chain(func)
        name = chain[-1] if chain else ""
        root = chain[0] if chain else ""
        kwargs = {k.arg: k.value for k in node.keywords if k.arg}

        # rsa / ec keypair generation
        if name == "generate_private_key":
            joined = ".".join(chain).lower()
            if "rsa" in joined or aliases.get(root, "").endswith("rsa"):
                kb = _const(kwargs.get("key_size"))
                yield RawFinding(AssetKind.LIBRARY_CALL, "RSA",
                                 f"RSA-{kb}" if kb else "RSA", src(node), node.lineno,
                                 kb if isinstance(kb, int) else None)
                return
            if "ec" in chain or "ec" in joined:
                yield RawFinding(AssetKind.LIBRARY_CALL, "ECDSA", "ECDSA",
                                 src(node), node.lineno)
                return

        # hashlib.<h>() or bare <h>() from `from hashlib import md5`
        if name in _HASH_METHODS and (root == "hashlib"
                                      or aliases.get(name, "").startswith("hashlib")):
            h = _HASH_METHODS[name]
            yield RawFinding(AssetKind.LIBRARY_CALL, h, h, src(node), node.lineno)
            return

        # hmac.new(key, msg, hashlib.sha1) — the digestmod is the finding
        if name in ("new", "HMAC") and (root == "hmac"
                                        or aliases.get(root, "").startswith("hmac")):
            for arg in list(node.args) + [k.value for k in node.keywords]:
                dm = _attr_chain(arg)
                if len(dm) == 2 and dm[0] == "hashlib" and dm[1] in _HASH_METHODS:
                    h = _HASH_METHODS[dm[1]]
                    yield RawFinding(AssetKind.LIBRARY_CALL, h, f"HMAC-{h}",
                                     src(node), node.lineno)
                    return

        # hashlib.pbkdf2_hmac("sha1", ...)
        if name == "pbkdf2_hmac" and node.args:
            algo = _const(node.args[0])
            if isinstance(algo, str) and algo.lower() in _HASH_METHODS:
                h = _HASH_METHODS[algo.lower()]
                yield RawFinding(AssetKind.LIBRARY_CALL, h, f"PBKDF2-{h}",
                                 src(node), node.lineno)
                return

        # DES3.new(...) / AES.new(...) — imported cipher class
        if name == "new" and root in _CIPHER_NAME:
            prim = _CIPHER_NAME[root]
            yield RawFinding(AssetKind.LIBRARY_CALL, prim, prim, src(node), node.lineno)
            return

        # cryptography: Cipher(algorithms.AES(key), ...) / algorithms.TripleDES(...)
        if name in _CIPHER_NAME and "algorithms" in chain:
            prim = _CIPHER_NAME[name]
            yield RawFinding(AssetKind.LIBRARY_CALL, prim, prim, src(node), node.lineno)
            return

        # jwt.encode(..., algorithm="RS256") / jwt.decode(..., algorithms=["RS256"])
        if name in ("encode", "decode") and (root == "jwt"
                                             or aliases.get(root, "").startswith("jwt")):
            algs: list[str] = []
            alg = kwargs.get("algorithm")
            if isinstance(_const(alg), str):
                algs.append(_const(alg))
            algos = kwargs.get("algorithms")
            if isinstance(algos, ast.List):
                algs += [_const(e) for e in algos.elts if isinstance(_const(e), str)]
            for a in algs:
                fam = _JWT_ALG.get(a[:2].upper(), "UNKNOWN")
                yield RawFinding(AssetKind.TOKEN_CONFIG, fam, f"JWT {a.upper()}",
                                 src(node), node.lineno)
            return
