"""Connecting the threat model to a real estate.

Given a Phase 2 CBOM, this module says, for every finding, which quantum attack
applies (Shor or Grover), what the published cost of running it is, and — for
the primitives small enough — offers a live demonstration on the simulator.

It also does one cross-check against ``policy.yaml``: the Mosca horizon ``Z``
assumes a CRQC by a certain year; :func:`horizon_commentary` restates what the
resource estimates imply about that assumption so the two are not read in
isolation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..discovery.cbom import CBOM, CryptoAsset, Exposure
from .estimates import ResourceEstimate, estimate_for_primitive

_SHOR_FAMILIES = {"RSA", "DSA", "DH", "ECDSA", "ECDH", "ECDHE", "ED25519",
                  "EDDSA", "X25519", "X448", "ED448"}
_GROVER_FAMILIES = {"AES", "SHA-1", "SHA-224", "SHA-256", "SHA3-256", "3DES",
                    "BLOWFISH"}

_EXPOSURE_BASE = {
    Exposure.CLASSICALLY_BROKEN: 92.0,
    Exposure.QUANTUM_BROKEN: 80.0,
    Exposure.QUANTUM_WEAKENED: 45.0,
    Exposure.UNKNOWN: 35.0,
    Exposure.QUANTUM_SAFE: 4.0,
}


def quantum_vulnerability_score(asset: CryptoAsset) -> float:
    """A single 0–100 quantum-vulnerability score per asset, combining its
    exposure class with a key-size adjustment (a 1024-bit RSA key is worse than
    a 4096-bit one; a 256-bit AES key is better than a 128-bit one)."""
    score = _EXPOSURE_BASE.get(asset.exposure, 35.0)
    fam = asset.primitive.strip().upper()
    kb = asset.key_bits
    if kb:
        if fam in ("RSA", "DSA", "DH") and asset.exposure is Exposure.QUANTUM_BROKEN:
            score += max(-12.0, min(12.0, (2048 - kb) / 128))
        elif fam == "AES":
            score += 8.0 if kb <= 128 else -20.0
    return round(max(0.0, min(100.0, score)), 1)


@dataclass(frozen=True, slots=True)
class AssetThreat:
    """The quantum-attack view of one CBOM asset."""

    asset: CryptoAsset
    attack: str                     # "Shor", "Grover", or "none"
    breaks_completely: bool
    estimate: ResourceEstimate | None
    summary: str

    def to_dict(self) -> dict:
        return {
            "location": self.asset.location,
            "primitive": self.asset.detail,
            "attack": self.attack,
            "breaks_completely": self.breaks_completely,
            "summary": self.summary,
            "estimate": self.estimate.to_dict() if self.estimate else None,
        }


def explain_asset_threat(asset: CryptoAsset) -> AssetThreat:
    """Describe the quantum attack on a single asset."""
    fam = asset.primitive.strip().upper()
    est = estimate_for_primitive(asset.primitive, asset.key_bits)

    if asset.exposure is Exposure.CLASSICALLY_BROKEN:
        return AssetThreat(
            asset, "classical", True, None,
            "Already broken by a classical attacker; a quantum computer is not "
            "required and changes nothing about the urgency.",
        )

    if fam in _SHOR_FAMILIES:
        attack, breaks = "Shor", True
        cost = (f"~{est.physical_qubits:.0g} physical qubits, ~{est.runtime_hours:g} h "
                f"({est.source})" if est else "polynomial time on a CRQC")
        summary = (f"Shor's algorithm recovers the private key in polynomial "
                   f"time; published cost to break the comparable target: {cost}.")
    elif fam in _GROVER_FAMILIES:
        attack, breaks = "Grover", False
        if est:
            summary = (f"Grover's algorithm halves the effective strength to "
                       f"~{est.classical_security_bits // 2}-bit; a real attack "
                       f"still needs ~{est.runtime_hours:.0g} h with no useful "
                       f"parallelism ({est.source}).")
        else:
            summary = "Grover's algorithm halves the effective security level."
    else:
        attack, breaks = "none", False
        if asset.exposure is Exposure.QUANTUM_SAFE:
            summary = "No quantum attack beyond Grover's manageable factor applies."
        else:
            summary = "No standard quantum attack is catalogued for this primitive."

    return AssetThreat(asset, attack, breaks, est, summary)


@dataclass(frozen=True, slots=True)
class EstateThreat:
    threats: tuple[AssetThreat, ...]

    def shor_targets(self) -> list[AssetThreat]:
        return [t for t in self.threats if t.attack == "Shor"]

    def grover_targets(self) -> list[AssetThreat]:
        return [t for t in self.threats if t.attack == "Grover"]

    def classically_broken(self) -> list[AssetThreat]:
        return [t for t in self.threats if t.attack == "classical"]

    def summary(self) -> dict:
        return {
            "assets": len(self.threats),
            "shor_targets": len(self.shor_targets()),
            "grover_targets": len(self.grover_targets()),
            "classically_broken": len(self.classically_broken()),
            "unaffected": sum(1 for t in self.threats if t.attack == "none"),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "threats": [t.to_dict() for t in self.threats],
        }


def assess_estate(cbom: CBOM) -> EstateThreat:
    """Annotate every CBOM asset with its quantum-attack view."""
    return EstateThreat(tuple(explain_asset_threat(a) for a in cbom.assets))


def horizon_commentary(crqc_year: int) -> str:
    """A short, source-anchored note on what the resource estimates say about a
    CRQC-arrival assumption."""
    return (
        f"policy.yaml assumes a cryptographically relevant quantum computer by "
        f"{crqc_year}. The Gidney-Ekerå (2021) model puts breaking RSA-2048 at "
        f"~20 million physical qubits for ~8 hours; current devices are at the "
        f"1e2-1e3 physical-qubit scale. The gap is engineering scale-up, and "
        f"expert surveys (Global Risk Institute Quantum Threat Timeline) place "
        f"a meaningful probability of that scale within the 2030s — which is "
        f"why {crqc_year} is a planning horizon, not a prediction."
    )
