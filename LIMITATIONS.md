# LIMITATIONS

QShield is a hackathon prototype and a planning tool. This file states plainly
what is real, what is a reference implementation, what is a projection, and what
a production deployment would require. Read it before drawing conclusions from
any number the tool reports.

## Cryptography

| Area | Status |
|---|---|
| Classical providers (RSA, X25519, ECDH-P256, ECDSA, Ed25519) | Real, via the `cryptography` library. Suitable for benchmarking and the demo; not a security review of your deployment. |
| ML-KEM / ML-DSA (pure-Python) | **Reference implementation.** `kyber-py` / `dilithium-py` follow FIPS 203/204 but are **not constant-time**, not side-channel hardened, and not audited. Never use them to protect real data. |
| SLH-DSA, HQC | `REFERENCE_ONLY` unless `liboqs-python` is installed — declared with published parameter sizes, cannot perform a live operation. |
| Hybrid X25519 + ML-KEM-768 | Real construction (both secrets into one HKDF), but inherits the reference-implementation caveat of its ML-KEM half. |
| Crypto-agility layer | Real and the centrepiece — algorithm resolves from `policy.yaml` at call time, no application code change. |

Production would require FIPS-validated, constant-time implementations
(e.g. AWS-LC, BoringSSL, liboqs with a vetted build), an HSM or KMS for key
custody, and a formal cryptographic review.

## Quantum engine

| Area | Status |
|---|---|
| Grover, Shor order-finding, QRNG on Aer | **Real Qiskit circuits**, executed on `qiskit-aer`. Reproducible with a fixed seed. |
| Bundled pure-Python simulator (`engine="python"`) | Exact statevector simulation, correct but slow; the zero-dependency default. |
| Shor demo range | N ∈ {15, 21, 35} only. The controlled modular-multiplication is built as an exact permutation unitary; this does not scale, and a laptop cannot simulate larger. A hung demo is a failed demo. |
| Noise model | A generic depolarizing (1q/2q) + readout model with adjustable rates. It is **illustrative**, not a calibrated model of any real device. |
| MPS backend | Used for the N=21/35 Shor circuits; it does **not** carry the gate-noise model, so the ideal-vs-noisy comparison there shows sampling spread only. |
| Resource estimates (`resource_estimate.py`) | **Projections under stated assumptions, not predictions.** Textbook asymptotics (Gidney–Ekerå, Roetteler et al.) plus a simplified surface-code overhead. Different cost models differ by an order of magnitude; `estimates.py` carries the peer-reviewed point figures for comparison. |
| "Feasible year" | A reading off a single assumed hardware-growth curve. It is a scenario, not a forecast. |

## CBOM scanner

- Python is parsed with the `ast` module (exact line numbers, keyword-argument
  values, no false hits in comments or strings). Everything else — JavaScript,
  Java, Go, config files — is **lexical** (regex), plus real X.509 / SSH-key
  parsing. Good recall on common patterns; misses obfuscated or indirect usage.
  No taint / data-flow analysis.
- Java coverage is a handful of `Cipher.getInstance` / `KeyPairGenerator` /
  `MessageDigest` patterns.
- `data_classification`, `data_retention_years` and `network_exposure` are
  **inferred from the file path**, not from a real data-classification
  register. In production these come from the department's asset inventory.
- `confidence` is a coarse per-detector constant, not a calibrated probability.
- `dependency_count` in the ML features is a deterministic stand-in for a real
  service-dependency graph.

## ML risk model

- Trained on **synthetic** assets (`app.risk.ml.synthetic`), not on any
  real ministry inventory. It learns the weighting that generated that data —
  its value here is demonstrating the *shape* of a prioritisation pipeline
  (features, importances, per-asset explanation), not a validated model.
- Feature contributions are `importance × z-scored value`, a lightweight
  approximation, not SHAP values.

## Persistence and deployment

- Persistence is stdlib `sqlite3` (a single-file scan history), not a
  production database.
- The hot-swap and migration endpoints rewrite `policy.yaml` (or the file named
  by `QSHIELD_POLICY`); state is per-process and per-file, not multi-user.
- No authentication, authorisation, rate limiting, or audit logging.

## What production PQC migration additionally needs

Formal data-classification input; discovery across binaries, network services
and cloud key stores; integration with CI to block new quantum-vulnerable
crypto; staged rollout with monitoring and rollback; FIPS-validated PQC
libraries; HSM-backed key management; and cryptographic sign-off from a
qualified reviewer.
