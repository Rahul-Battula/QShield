# QShield — Post-Quantum Cryptography Migration Command Centre

> ## Disclaimer — read first
>
> **QShield is a reference implementation and a migration-planning tool. It is
> NOT production cryptography and it has NOT been audited.** Do not use it to
> protect real data. Its cryptographic code exists to demonstrate an
> architecture — the crypto-agility layer — not to be a hardened library.
> Where QShield reports quantum-resource estimates or algorithm sizes drawn
> from published research, those are cited in code comments and are the cited
> authors' figures, not QShield's own measurements. Benchmarks that QShield
> does produce are measured on the machine you run them on and will differ on
> yours.

---

## Run it

**Windows:** double-click **`run.bat`** (or `run.bat` from a terminal).
**macOS / Linux / Git Bash:** `./run.sh`.

Either one installs dependencies on first use, starts the backend — which also
serves the frontend — and opens the dashboard at
**http://127.0.0.1:8000/**. Press `Ctrl+C` to stop.

Needs Python 3.11–3.13 on the system (the launcher prefers `py -3.11`).
Everything else — the per-phase CLIs, the tests — is in [Setup](#setup) below.

**Deploy:** there is a `Dockerfile`. Any host that builds a Docker image
(Render, Railway, Fly, Cloud Run, …) works with no extra config — it reads
`$PORT`, binds all interfaces, and serves the dashboard at `/`. Locally:
`docker build -t qshield . && docker run -p 8000:8000 qshield`.

---

## The thesis

There are two problems, not one.

1. **RSA and ECC will break** under a large fault-tolerant quantum computer.
   The answer is the NIST PQC standards: ML-KEM (FIPS 203), ML-DSA (FIPS 204),
   SLH-DSA (FIPS 205).
2. **The NIST algorithms will themselves eventually be broken.** SIKE, a NIST
   Round-4 candidate, was broken on a single laptop in roughly an hour in 2022.
   Hardcoding ML-KEM today repeats the exact mistake of hardcoding RSA in 1995.

So the deliverable is **not** "we migrated to Kyber." It is **the architecture
that makes every future migration a configuration change.** Every design
decision in QShield serves that thesis.

## Build phases

| Phase | Contents | Status |
|------:|----------|--------|
| 1 | Crypto-agility layer + hot-swap acceptance test | **done** |
| 2 | Mock government estate + CBOM discovery scanner | **done** |
| 3 | Risk prioritisation (Mosca inequality, scoring, clustering) | **done** |
| 4 | Quantum threat engine (Shor, Grover, resource estimation, QRNG) | **done** |
| 5 | Migration engine + demo land-records application | **done** |
| 6 | Benchmark harness + HTTP API + React dashboard | **done** |

## Phase 1 — what is here now

A provider-abstraction library. Application code only ever calls:

```python
from app.agility import kem, sig, reload

kp  = kem.generate_keypair()
enc = kem.encapsulate(kp.public_key)          # -> Encapsulation(ciphertext, shared_secret, algorithm)
ss  = kem.decapsulate(kp.private_key, enc.ciphertext)

skp = sig.generate_keypair()
s   = sig.sign(skp.private_key, b"message")   # -> SignatureResult(signature, algorithm)
ok  = sig.verify(skp.public_key, b"message", s.signature)
```

The concrete algorithm is resolved at runtime from `policy.yaml`. **Application
code never names an algorithm.** Changing the one line `active_suite:` in
`policy.yaml` and calling `reload()` swaps the algorithm with zero code change —
this is proven by `backend/tests/test_agility_hotswap.py`, which is the
project's central claim and was written before the providers it exercises.

### Provider families

| Family | Algorithms | Backend | Default status on Windows |
|--------|------------|---------|---------------------------|
| classical | RSA-2048 (OAEP KEM), ECDH-P256, X25519, ECDSA-P256 | `cryptography` | `LIVE` |
| ML-KEM (FIPS 203) | ML-KEM-512/768/1024 | pure-Python `kyber-py` | `LIVE` |
| ML-DSA (FIPS 204) | ML-DSA-44/65/87 | pure-Python `dilithium-py` | `LIVE` |
| SLH-DSA (FIPS 205) | SLH-DSA-SHA2-128s/192s/256s | `liboqs` if importable | `REFERENCE_ONLY` unless liboqs present |
| HQC (code-based KEM) | HQC-128/192/256 | `liboqs` if importable | `REFERENCE_ONLY` unless liboqs present |
| hybrid composites | X25519+ML-KEM-768, ECDSA-P256+ML-DSA-65 | combiner over the above | `LIVE` (**the default suite**) |

A `REFERENCE_ONLY` provider is declared in policy, appears in every table and
benchmark with **published** sizes clearly labelled as not measured locally,
and raises `ProviderUnavailable` if you actually try to run it. Being able to
*declare* an algorithm you cannot yet run is part of what a real crypto-agility
layer must do.

> **Note on SLH-DSA:** the original plan was to run SLH-DSA live via a
> pure-Python implementation. There is no pure-Python SLH-DSA on PyPI mature
> enough to depend on for a live demo on Windows, so SLH-DSA is
> `REFERENCE_ONLY` unless `liboqs-python` is installed. Install
> `requirements-liboqs.txt` to make SLH-DSA and HQC `LIVE`.

## Setup

Python 3.11–3.13. Install from the repo root:

```powershell
cd path\to\app
pip install -r requirements.txt         # runtime + API + test/lint tooling

# optional — live SLH-DSA and HQC; needs CMake + a C compiler
pip install -r requirements-liboqs.txt
# optional — re-run the Phase 4 circuits on Qiskit
pip install -r requirements-qiskit.txt
```

A virtualenv is not required; use one if you prefer to keep dependencies
isolated. Then, from `backend/`:

```powershell
cd backend
ruff check .
pytest -q          # 258 passed (a few skip without the optional qiskit extra)
```

The hot-swap acceptance tests pass; reference-provider tests assert
`ProviderUnavailable` (or run live when `liboqs` is installed).

## Phase 2 — what is here now

A cryptographic discovery scanner that produces a **CBOM** (Cryptographic Bill
of Materials): an inventory of every place an estate uses cryptography, each
entry classified by how it fares against a classical and a quantum attacker.

```powershell
cd D:\app
python -m app.discovery                      # scan the bundled mock estate
python -m app.discovery --format markdown     # or: json
python -m app.discovery path\to\real\estate --fail-on-vulnerable
```

* **`mock_estate/`** is a deliberately vulnerable stand-in for a government
  department's IT estate — a land registry, a **health-records API** (SHA-1
  record IDs, RS256 JWTs, RC4 at the edge), a **treasury payment gateway**
  (Triple-DES PIN blocks, a 1024-bit RSA settlement key, TLS 1.0 on the
  ISO 8583 link), an SSH bastion, SAML SSO, and a legacy mainframe — plus
  ML-KEM / ML-DSA / AES-256 as safe controls.
* **`app.discovery.ast_scan`** parses Python with the `ast` module (exact
  line numbers, `key_size=` read off the keyword node, comments ignored);
  **`app.discovery.detectors`** covers JavaScript / Java / Go by pattern,
  plus TLS/SSH/JWT config and real X.509 and key parsing via `cryptography`.
  Every asset also gets a `data_classification` / `data_retention_years` /
  `network_exposure` inferred from its path, and the CBOM exports as JSON or
  CSV (`/api/cbom/export`).
* **`app.discovery.classify`** is the Phase 2 thesis in one table: Shor
  breaks every deployed public-key primitive (`QUANTUM_BROKEN`), Grover halves
  symmetric strength (`QUANTUM_WEAKENED`), and MD5 / SHA-1 / 3DES / RC4 / old
  TLS are `CLASSICALLY_BROKEN` and urgent regardless of the quantum timeline.
  Every verdict carries its rationale and a recommendation that names a
  `policy.yaml` suite.
* **`scan_estate()`** is deterministic — the same tree always yields the same
  CBOM, so two scans can be diffed. `cbom.to_dict()` is what Phase 3 consumes.

`backend/tests/test_discovery.py` is the acceptance test: it scans the committed
mock estate and asserts the expected findings and classifications.

## Phase 3 — what is here now

Given the CBOM, **which finding do you migrate first?** Phase 3 answers that
with Mosca's inequality and a ranked, clustered backlog.

```powershell
cd D:\app
python -m app.risk                            # ranked table for the mock estate
python -m app.risk --format markdown           # ranked table + work packages
python -m app.risk --top 20 --assessment-year 2026
python -m app.risk --fail-on-p1                # exit 1 if any P1 finding
```

* **Mosca's inequality — `X + Y > Z`.** `X` is how long the data must stay
  secret (`app.risk.shelflife`, from `mosca.data_classes` in `policy.yaml`);
  `Y` is how long the migration takes (`app.risk.migration_cost`, cheaper
  when QShield's agility layer already has a live drop-in); `Z` is the years to
  the assumed CRQC (`mosca.presets[active_preset]`). When `X + Y > Z` the plan
  finishes after the data is already exposed — `app.risk.mosca` reports by
  how many years, and the latest year a migration can still start.
* **Score (0–100) and priority band P1–P4** (`app.risk.scoring`): a blend of
  exposure, Mosca time pressure and blast radius (how many findings one fix
  clears). Quantum-safe findings are capped near zero; a broken primitive that
  is already past its Mosca start date is forced to P1.
* **Work packages** (`app.risk.clustering`): a small deterministic k-means
  groups the backlog into coherent units — usually one subsystem and one
  primitive family — ordered by their most urgent member, with an aggregate
  effort estimate and the target `policy.yaml` suite.
* **scikit-learn queue** (`app.risk.ml`): a `GradientBoostingRegressor`
  scores migration priority 0–100 and a `RandomForestClassifier` bands it
  High / Medium / Low, both trained on synthetic government assets with a
  harvest-now-decrypt-later interaction. `/api/risk/rank` returns the ranked
  queue with the model's feature importances; `/api/risk/explain/{id}` breaks
  one asset down into per-feature contributions. Models train on first use and
  cache to `_models/`.

`prioritise(scan_estate())` returns the Mosca report;
`backend/tests/{test_risk,test_ml_risk}.py` are the acceptance tests.

## Phase 4 — what is here now

The attacks themselves — demonstrated, and costed.

```powershell
cd D:\app
python -m app.threat estimates                          # published CRQC cost catalogue
python -m app.threat estate --format markdown            # annotate the scanned estate
python -m app.threat demo shor  --N 21 --a 2 --factorise
python -m app.threat demo grover --qubits 5 --target 30
python -m app.threat demo grover --engine qiskit --qubits 4 --target 11
python -m app.threat demo qrng  --bytes 32
```

* **Two engines run the same circuits.** `--engine python` (default) uses a
  pure-Python exact statevector simulator (`app.threat.simulator`, no
  dependencies, no build step); `--engine qiskit` builds real
  `qiskit.QuantumCircuit` objects and runs them on Aer
  (`app.threat.qiskit_backend`, needs `pip install -r requirements-qiskit.txt`).
  * **Shor** (`app.threat.shor`) — quantum order-finding by phase
    estimation, then classical factoring. `factor(21)` → `(3, 7)` with a
    verified order on the python engine; the qiskit engine covers up to N = 15
    (`factor(15, engine="qiskit")` → `(3, 5)`).
  * **Grover** (`app.threat.grover`) — amplitude amplification finding a
    marked state in `~(π/4)·√N` iterations, plus `grover_effective_bits()` (the
    key-length halving) with NIST's parallelism caveat.
  * **QRNG** (`app.threat.qrng`) — measured `H|0>` bits with the NIST
    SP 800-22 monobit test; the byte source is always labelled so a seeded
    simulator is never mistaken for a hardware entropy source.
* **Noise and scale** (`app.threat.aer`, `.qiskit_backend`,
  `.resource_estimate`) — a shared Aer factory with `ideal | noisy | matrix`
  backends and a depolarizing + readout noise model whose rates are parameters;
  `demo_shor` for N ∈ {15, 21, 35}; `compare_shor` runs the *same* circuit on
  the ideal and noisy backends; and a computed surface-code projection
  (logical → physical qubits vs code distance, runtime, "feasible year" off a
  stated hardware-growth curve — labelled a projection, calibrated against
  Gidney–Ekerå). `app.threat.estimates` still carries the peer-reviewed
  point figures for comparison.
* **`app.threat.engine`** joins this to the Phase 2 CBOM: every finding gets
  its attack (Shor / Grover / already-classical), its published break cost, a
  0–100 `quantum_vulnerability_score`, and a cross-check of the `policy.yaml`
  Mosca horizon against what the estimates imply.

The dashboard's **Quantum Lab** tab drives all of this — Grover with a
success-probability curve, Shor, the ideal-vs-noisy comparison, and the
projection sliders. `backend/tests/{test_threat,test_quantum_lab}.py` are the
acceptance tests; the Qiskit
tests skip when the extra is absent.

## Phase 5 — what is here now

The migration, executed against a running application and proven to round-trip.

```powershell
cd D:\app
python -m app.migration plan pqc
python -m app.migration run pqc --records 20 --rollback
python -m app.migration waves --assessment-year 2026   # dated phased plan
```

* **`app.landrecords`** is the demo application: an in-memory land registry
  that seals each title (confidential fields encrypted under a KEM-derived
  AES-256-GCM key, the whole record signed) and opens it again. It calls only
  `app.agility.kem` and `app.agility.sig` — no algorithm name, no
  backend import, no branch on a suite. Keys are held per `KeyEpoch`, tied to
  the suite active when they were generated.
* **`app.migration`** performs a migration end to end: verify and decrypt
  every stored record under the current policy, edit `active_suite` in
  `policy.yaml` and `reload()`, generate a fresh key epoch, re-seal every
  record, verify again — capturing each record's algorithm before and after.
  `rollback()` is the same operation back to the original suite, because a
  migration is symmetric.
* **`MigrationResult.assert_thesis()`** is the falsifiable claim: it fails
  unless the application code was untouched, every record was valid before,
  every record is valid after, and (for a real suite change) *every* record's
  algorithm actually changed.
* **`app.migration.planner`** turns the Phase 3 ranked backlog into dated
  waves — one per priority band, P1 first, target dates spread from now to the
  earliest Mosca start date, configuration changes ordered before code changes
  within each wave, and each wave's share of the total risk it removes.
  `/api/migration/plan` and `/api/migration/mosca`, or `qshield-migrate waves`.

A `hybrid -> pqc` migration of 20 records re-seals in a few hundred
milliseconds, moves every record from `X25519+ML-KEM-768 / ECDSA-P256+ML-DSA-65`
to `ML-KEM-768 / ML-DSA-65`, and rolls straight back — with nothing in
`app.landrecords` changed. `backend/tests/test_migration.py` is the
acceptance test.

## Phase 6 — what is here now

The numbers, and a UI over all six phases.

```powershell
cd D:\qshield
python -m app.benchmark --iterations 100      # time every suite
python -m app.api                             # then open http://127.0.0.1:8000/
```

* **`app.benchmark`** times keygen, encapsulate/decapsulate and sign/verify
  for every suite in `policy.yaml` and records the byte sizes. A suite with a
  `REFERENCE_ONLY` component (`code-based`, `hash-based-sig` without `liboqs`)
  is reported with its published sizes and **no fabricated timings** —
  `live = false`. Handshake cost is shown as a multiple of the `classical`
  baseline, so "hybrid costs 0.9x classical, ciphertext 4x larger" is read off
  directly.
* **`app.api`** is a FastAPI app. One JSON endpoint per phase
  (`/api/discovery`, `/api/scan` + `/api/cbom` + `/api/cbom/export?format=csv`,
  `/api/risk` and `/api/risk/rank` + `/api/risk/explain/{id}`, `/api/threat`,
  `/api/benchmark`, `/api/migration/run`), plus `/api/policy/active` for a live
  hot-swap and the **Qiskit Lab** endpoints
  `/api/quantum/{shor,grover,compare,estimate}` (real Aer circuits with
  noise-rate parameters). Handlers are thin.
* **The dashboard** lives in its own top-level [`frontend/`](frontend/) tree —
  a Vite + React 18 + TypeScript app styled with Tailwind CSS and charted with
  Recharts (`npm run build`; `frontend/dist/` is committed so it also runs with
  no Node toolchain). Seven views: Overview, Discovery (CBOM + CSV export), Risk
  (Mosca ranking, work packages, and the scikit-learn queue with per-asset
  feature contributions), Threat, **Quantum Lab** (Grover with a
  success-probability curve, Shor for N ∈ {15,21,35}, an ideal-vs-noisy
  histogram comparison, and the resource projection with error-rate /
  qubit-growth sliders), Benchmark, and Migrate. Served at `/` via
  `app.config.frontend_dir()`, which falls back to the zero-build
  [`frontend-legacy/`](frontend-legacy/) dashboard when `dist/` is absent.

Persistence is a stdlib `sqlite3` scan history at `QSHIELD_DB`.
`backend/tests/{test_api,test_benchmark,test_quantum_lab,test_ml_risk,test_store}.py`
are the acceptance tests.

## Working on it

Local setup, the layout, and the branch/commit conventions are in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Before pushing a change, run `ruff check`
and `pytest -q` from `backend/` — both must be clean (258 passed; a few skip
without the optional `qiskit` extra).

## License

MIT — see [`LICENSE`](LICENSE). QShield is a reference implementation and is not
production cryptography; see the disclaimer at the top of this file.
