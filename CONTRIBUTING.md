# Working on QShield

## Ground rules

- **QShield is a reference implementation, not production cryptography.** New
  cryptographic code demonstrates the crypto-agility architecture; it is not
  expected to be constant-time or side-channel hardened. Keep that framing.
- **Application code must never name a concrete algorithm.** Algorithms are
  resolved at runtime from `policy.yaml` through `app.agility`. Hardcoding an
  algorithm outside a provider backend defeats the point of the project.

## Local setup

Python 3.11–3.13. Install from the repo root (a virtualenv is optional, not
required):

```powershell
cd path\to\app
pip install -r requirements.txt

# optional: live SLH-DSA and HQC (needs CMake + a C compiler)
pip install -r requirements-liboqs.txt
# optional: re-run the Phase 4 circuits on Qiskit
pip install -r requirements-qiskit.txt
```

## Layout

- `backend/` — the Python package `app` (the six phases) and its tests.
- `frontend/` — the dashboard, served by `app.api`; no build step.
- `mock_estate/` — the deliberately vulnerable fixture the scanner inventories.
- `policy.yaml` — the crypto policy; the file the whole project turns on.

## Before every change

Run both from `backend/` and make sure they are clean:

```powershell
cd backend
ruff check .
pytest -q
```

Expect `258 passed` (a few tests skip if the optional `qiskit` extra is absent).
`REFERENCE_ONLY` provider tests assert `ProviderUnavailable`, or run live when
`liboqs` is installed — both count as green.

## Commit conventions

- Imperative subject under ~72 characters (e.g. `Add HQC-192 reference
  provider`), with a body explaining *why* when it is not obvious.
- Keep each commit focused on one concern or one build phase.
