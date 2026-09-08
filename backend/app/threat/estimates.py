"""Published resource estimates for breaking real primitives.

The simulator in this package runs Shor and Grover for toy parameters. The
numbers that matter for planning — how many physical qubits, how long, at what
error rate — come from the peer-reviewed literature, and QShield reports them as
*the cited authors' figures*, not as its own measurements. Each entry names its
source.

Primary sources:

* C. Gidney and M. Ekerå, "How to factor 2048-bit RSA integers in 8 hours using
  20 million noisy qubits", Quantum 5, 433 (2021). Surface code, physical error
  rate 1e-3, 1 us cycle time.
* M. Roetteler, M. Naehrig, K. Svore, K. Lauter, "Quantum resource estimates
  for computing elliptic curve discrete logarithms", ASIACRYPT 2017.
* M. Grassl, B. Langenberg, M. Roetteler, R. Steinwandt, "Applying Grover's
  algorithm to AES: quantum resource estimates", PQCrypto 2016.
* NIST IR 8413 and SP 800-57 for the classical security levels.

These are estimates from specific cost models; other models differ by up to an
order of magnitude. They establish that the barrier to breaking RSA-2048 is
*scale* (millions of physical qubits), not a missing algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceEstimate:
    target: str
    attack: str
    classical_security_bits: int
    logical_qubits: int
    physical_qubits: float
    toffoli_or_t_gates: float
    runtime_hours: float
    assumptions: str
    source: str

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "attack": self.attack,
            "classical_security_bits": self.classical_security_bits,
            "logical_qubits": self.logical_qubits,
            "physical_qubits": self.physical_qubits,
            "toffoli_or_t_gates": self.toffoli_or_t_gates,
            "runtime_hours": self.runtime_hours,
            "assumptions": self.assumptions,
            "source": self.source,
        }


_GIDNEY_EKERA = "Gidney & Ekerå, Quantum 5:433 (2021)"
_ROETTELER = "Roetteler et al., ASIACRYPT 2017"
_GRASSL = "Grassl et al., PQCrypto 2016"

_SURFACE = ("surface code, physical error rate 1e-3, 1 us cycle time")

_ESTIMATES: dict[str, ResourceEstimate] = {
    "RSA-1024": ResourceEstimate(
        "RSA-1024", "Shor (factoring)", 80, 1400, 5.0e6, 1.5e9, 3.5,
        _SURFACE, _GIDNEY_EKERA + " (scaled)"),
    "RSA-2048": ResourceEstimate(
        "RSA-2048", "Shor (factoring)", 112, 6200, 2.0e7, 2.7e9, 8.0,
        _SURFACE, _GIDNEY_EKERA),
    "RSA-3072": ResourceEstimate(
        "RSA-3072", "Shor (factoring)", 128, 9900, 3.9e7, 9.9e9, 27.0,
        _SURFACE, _GIDNEY_EKERA + " (scaled)"),
    "RSA-4096": ResourceEstimate(
        "RSA-4096", "Shor (factoring)", 140, 13500, 6.3e7, 2.3e10, 60.0,
        _SURFACE, _GIDNEY_EKERA + " (scaled)"),
    "ECC-P256": ResourceEstimate(
        "ECC-P256", "Shor (discrete log)", 128, 2330, 4.7e6, 1.2e11, 0.4,
        _SURFACE, _ROETTELER),
    "ECC-P384": ResourceEstimate(
        "ECC-P384", "Shor (discrete log)", 192, 3480, 7.0e6, 4.0e11, 1.1,
        _SURFACE, _ROETTELER),
    "DH-2048": ResourceEstimate(
        "DH-2048", "Shor (discrete log)", 112, 6300, 2.0e7, 2.8e9, 8.5,
        _SURFACE, _GIDNEY_EKERA + " (factoring analogue)"),
    "AES-128": ResourceEstimate(
        "AES-128", "Grover (key search)", 128, 3000, 2.3e6, 2.7e19, 8.6e10,
        "Grover, no parallelism; " + _SURFACE, _GRASSL),
    "AES-192": ResourceEstimate(
        "AES-192", "Grover (key search)", 192, 4600, 3.5e6, 4.6e28, 1.5e20,
        "Grover, no parallelism; " + _SURFACE, _GRASSL),
    "AES-256": ResourceEstimate(
        "AES-256", "Grover (key search)", 256, 6600, 5.0e6, 1.4e38, 4.6e29,
        "Grover, no parallelism; " + _SURFACE, _GRASSL),
    "SHA-256": ResourceEstimate(
        "SHA-256", "Grover (preimage)", 256, 2400, 2.0e6, 3.6e38, 1.2e30,
        "Grover preimage, no parallelism", "Amy et al., SAC 2016"),
}

# Which catalogue entry to use for a primitive family seen in the CBOM.
_PRIMITIVE_TO_TARGET: dict[str, str] = {
    "RSA": "RSA-2048",
    "DSA": "DH-2048",
    "DH": "DH-2048",
    "ECDSA": "ECC-P256",
    "ECDH": "ECC-P256",
    "ECDHE": "ECC-P256",
    "ED25519": "ECC-P256",
    "EDDSA": "ECC-P256",
    "X25519": "ECC-P256",
    "AES": "AES-128",
    "SHA-256": "SHA-256",
    "SHA-1": "SHA-256",
}


def available_targets() -> list[str]:
    return sorted(_ESTIMATES)


def estimate(target: str) -> ResourceEstimate:
    """Look up a resource estimate by catalogue name (see
    :func:`available_targets`)."""
    key = target.strip().upper().replace(" ", "-")
    for name, est in _ESTIMATES.items():
        if name.upper() == key:
            return est
    raise KeyError(
        f"no resource estimate for {target!r}; known: {available_targets()}"
    )


def estimate_for_primitive(primitive: str, key_bits: int | None = None) -> ResourceEstimate | None:
    """Best catalogue match for a CBOM primitive, refined by key size where the
    catalogue has variants."""
    fam = primitive.strip().upper()
    target = _PRIMITIVE_TO_TARGET.get(fam)
    if target is None:
        return None
    if fam == "RSA" and key_bits:
        target = min(
            ("RSA-1024", "RSA-2048", "RSA-3072", "RSA-4096"),
            key=lambda t: abs(int(t.split("-")[1]) - key_bits),
        )
    if fam == "AES" and key_bits:
        target = f"AES-{min((128, 192, 256), key=lambda b: abs(b - key_bits))}"
    return estimate(target)
