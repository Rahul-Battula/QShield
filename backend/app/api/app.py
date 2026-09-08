"""The QShield HTTP API — one JSON surface over all six phases.

Endpoints are thin: each one calls straight into the phase package and returns
its ``to_dict()``. ``POST /api/policy/active`` and ``POST /api/migration/run``
mutate ``policy.yaml`` (through :func:`app.agility.policy.write_active_suite`
and ``reload``), which is the live-demo behaviour; point ``QSHIELD_POLICY`` at a
copy if that is not wanted.

The single-page dashboard (the top-level ``frontend/`` tree, resolved by
:func:`app.config.frontend_dir`) is served at ``/``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..agility import reload
from ..agility.policy import PolicyError, load_policy, write_active_suite
from ..benchmark import run_all
from ..config import estate_root, frontend_dir, policy_path, repo_root
from ..discovery import scan_estate
from ..landrecords import demo_registry
from ..migration import MigrationPlanError, migrate
from ..risk import prioritise
from ..threat import assess_estate, available_targets, estimate, horizon_commentary
from ..threat.grover import grover_search
from ..threat.qrng import random_bytes
from ..threat.shor import factor, order_finding

_bench_cache: dict[int, dict] = {}


class SuiteBody(BaseModel):
    suite: str = Field(..., description="a suite name defined in policy.yaml")


class MigrationBody(BaseModel):
    to_suite: str
    records: int = Field(8, ge=1, le=200)


class DemoBody(BaseModel):
    N: int = 15
    a: int = 7
    factorise: bool = False
    qubits: int = 4
    target: int = 11
    n_bytes: int = 32
    seed: int = 0
    engine: str = "python"  # "python" (bundled simulator) or "qiskit" (Aer)


class _NoiseBody(BaseModel):
    backend: str = Field("ideal", pattern="^(ideal|noisy|matrix)$")
    shots: int = Field(2048, ge=1, le=8192)
    p1: float = Field(1e-3, ge=0, le=0.5)
    p2: float = Field(1e-2, ge=0, le=0.5)
    readout: float = Field(2e-2, ge=0, le=0.5)


class ShorBody(_NoiseBody):
    N: int = 15
    a: int = 2
    seed: int = 20260907
    shots: int = Field(1024, ge=1, le=8192)


class GroverBody(_NoiseBody):
    n_bits: int = Field(4, ge=2, le=8)
    iterations: int | None = None
    target: int | None = None


class CompareBody(_NoiseBody):
    N: int = 15
    a: int = 2
    shots: int = Field(1024, ge=1, le=8192)


class EstimateBody(BaseModel):
    algorithm: str = "RSA"
    key_bits: int = 2048
    phys_error_rate: float = Field(1e-3, gt=0, le=0.05)
    annual_growth: float = Field(1.5, gt=1.0, le=5.0)


class ScanBody(BaseModel):
    path: str | None = None  # directory to scan; default = the bundled mock estate


def _require_qiskit() -> None:
    from ..threat.backend import qiskit_available
    if not qiskit_available():
        raise HTTPException(503, "the Qiskit Lab needs the 'quantum' extra: "
                                 "pip install -r requirements-qiskit.txt")


def _csv_cell(v: object) -> str:
    s = "" if v is None else str(v)
    return f'"{s}"' if any(c in s for c in ',"\n') else s


def _seed_policy_if_missing() -> None:
    """A deployment points ``QSHIELD_POLICY`` at a writable path (so the
    hot-swap and migration endpoints can rewrite it) that may not exist yet.
    Copy the version bundled in the repo into place so the very first request
    that reads the policy succeeds."""
    target = policy_path()
    bundled = repo_root() / "policy.yaml"
    if target != bundled and not target.exists() and bundled.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundled, target)


def create_app() -> FastAPI:
    _seed_policy_if_missing()
    app = FastAPI(title="QShield", version=__version__,
                  description="Post-quantum cryptography migration command centre")

    @app.get("/api/health")
    def health() -> dict:
        from ..threat import qiskit_available

        return {"status": "ok", "version": __version__,
                "qiskit": qiskit_available()}

    @app.get("/api/policy")
    def get_policy() -> dict:
        p = load_policy()
        return {
            "active_suite": p.active_suite,
            "suites": {name: {"kem": s.kem, "sig": s.sig}
                       for name, s in p.suites.items()},
            "mosca": {
                "active_preset": p.mosca.active_preset,
                "presets": p.mosca.presets,
                "crqc_year": p.mosca.crqc_year(),
            },
        }

    @app.post("/api/policy/active")
    def set_active(body: SuiteBody) -> dict:
        try:
            write_active_suite(body.suite)
        except PolicyError as exc:
            raise HTTPException(400, str(exc)) from exc
        reload()
        return {"active_suite": load_policy().active_suite}

    # -- crypto-agility: the spec's /api/agility/* surface ------------
    @app.get("/api/agility/policy")
    def agility_policy() -> dict:
        return get_policy()

    @app.post("/api/agility/reload")
    def agility_reload() -> dict:
        reload()
        return {"active_suite": load_policy().active_suite, "reloaded": True}

    @app.post("/api/agility/switch")
    def agility_switch(body: SuiteBody) -> dict:
        """Change the active suite and return a before/after comparison of key
        sizes, ciphertext/signature sizes and operation timings — with no
        application code touched."""
        from ..benchmark.harness import benchmark_suite

        policy = load_policy()
        if body.suite not in policy.suites:
            raise HTTPException(400, f"unknown suite {body.suite!r}")
        before = benchmark_suite(policy.active_suite, policy, iterations=15)
        try:
            write_active_suite(body.suite)
        except PolicyError as exc:
            raise HTTPException(400, str(exc)) from exc
        reload()
        after = benchmark_suite(body.suite, load_policy(), iterations=15)
        return {
            "from": before.suite, "to": after.suite,
            "application_code_changed": False,
            "before": before.to_dict(),
            "after": after.to_dict(),
        }

    @app.post("/api/agility/demo")
    def agility_demo() -> dict:
        """A full KEM + signature handshake under whatever policy is active."""
        from ..agility import kem, sig

        kp = kem.generate_keypair()
        enc = kem.encapsulate(kp.public_key)
        ss = kem.decapsulate(kp.private_key, enc.ciphertext)
        skp = sig.generate_keypair()
        msg = b"land-record:AP-VZM-2026-000042"
        signed = sig.sign(skp.private_key, msg)
        ok = sig.verify(skp.public_key, msg, signed.signature)
        return {
            "active_suite": load_policy().active_suite,
            "kem_algorithm": enc.algorithm,
            "sig_algorithm": signed.algorithm,
            "kem_roundtrip_ok": ss == enc.shared_secret,
            "signature_verified": ok,
            "note": "resolved from policy.yaml at call time; the calling code "
                    "names no algorithm.",
        }

    @app.get("/api/discovery")
    def discovery() -> dict:
        return scan_estate().to_dict()

    @app.post("/api/scan")
    def scan(body: ScanBody | None = None) -> dict:
        from ..discovery.scanner import scan_estate as _scan
        from ..store import save_scan

        b = body or ScanBody()
        target = b.path or str(estate_root())
        if b.path and not Path(b.path).is_dir():
            raise HTTPException(400, f"not a directory: {b.path!r}")
        try:
            cbom = _scan(Path(target) if b.path else None)
        except OSError as exc:
            raise HTTPException(400, f"cannot scan {target!r}: {exc}") from exc
        scan_id = save_scan(cbom, target)
        return {"scan_id": scan_id, "target": target, "summary": cbom.summary()}

    @app.get("/api/cbom")
    def cbom(exposure: str | None = None, system: str | None = None) -> dict:
        from ..store import latest_cbom

        data = latest_cbom()
        if data is None:  # nothing persisted yet — scan the default estate once
            from ..store import save_scan
            fresh = scan_estate()
            save_scan(fresh, str(estate_root()))
            data = fresh.to_dict()
        assets = data["assets"]
        if exposure:
            assets = [a for a in assets if a["exposure"] == exposure]
        if system:
            assets = [a for a in assets if a["location"].split("/", 1)[0] == system]
        return {**data, "assets": assets, "filtered": len(assets)}

    @app.get("/api/cbom/export")
    def cbom_export(format: str = "json") -> Response:
        from ..store import latest_cbom

        data = latest_cbom() or scan_estate().to_dict()
        if format == "csv":
            rows = ["asset_id,kind,primitive,detail,key_bits,location,detector,"
                    "exposure,data_classification,data_retention_years,"
                    "network_exposure,confidence,recommendation"]
            for a in data["assets"]:
                rows.append(",".join(_csv_cell(a.get(c)) for c in (
                    "asset_id", "kind", "primitive", "detail", "key_bits", "location",
                    "detector", "exposure", "data_classification",
                    "data_retention_years", "network_exposure", "confidence",
                    "recommendation")))
            return PlainTextResponse("\n".join(rows), media_type="text/csv",
                                     headers={"Content-Disposition":
                                              "attachment; filename=qshield-cbom.csv"})
        return Response(json.dumps(data, indent=2), media_type="application/json",
                        headers={"Content-Disposition":
                                 "attachment; filename=qshield-cbom.json"})

    @app.get("/api/scans")
    def scans() -> dict:
        from ..store import list_scans
        return {"scans": list_scans()}

    @app.get("/api/risk")
    def risk(assessment_year: int | None = None) -> dict:
        return prioritise(scan_estate(), assessment_year=assessment_year).to_dict()

    @app.get("/api/risk/rank")
    def risk_rank(limit: int = 200) -> dict:
        from ..risk.ml import feature_importances
        from ..risk.ml_rank import rank_cbom

        ranked = rank_cbom(scan_estate())
        return {
            "model": feature_importances(),
            "count": len(ranked),
            "queue": ranked[: max(1, min(limit, 500))],
        }

    @app.get("/api/risk/explain/{asset_id}")
    def risk_explain(asset_id: str) -> dict:
        from ..risk.ml_rank import explain_asset

        out = explain_asset(scan_estate(), asset_id)
        if out is None:
            raise HTTPException(404, f"no asset {asset_id!r} in the current scan")
        return out

    @app.get("/api/threat")
    def threat() -> dict:
        et = assess_estate(scan_estate())
        out = et.to_dict()
        try:
            out["horizon"] = horizon_commentary(load_policy().mosca.crqc_year())
        except PolicyError:
            out["horizon"] = None
        return out

    @app.get("/api/threat/estimates")
    def threat_estimates() -> dict:
        return {"targets": [estimate(t).to_dict() for t in available_targets()]}

    @app.post("/api/threat/demo/{kind}")
    def threat_demo(kind: str, body: DemoBody | None = None) -> dict:
        from ..threat.backend import QuantumBackendUnavailable

        b = body or DemoBody()
        eng = b.engine
        try:
            if kind == "shor":
                if b.factorise:
                    r = factor(b.N, seed=b.seed, engine=eng)
                    return {"engine": eng, "N": r.N, "factors": list(r.factors),
                            "success": r.success, "witness_a": r.witness, "order": r.order}
                r = order_finding(b.a, b.N, seed=b.seed, engine=eng)
                return {"engine": eng, "a": r.a, "N": r.N, "order": r.order,
                        "verified": r.verified,
                        "qubits": r.counting_qubits + r.work_qubits}
            if kind == "grover":
                g = grover_search(b.qubits, lambda v: v == b.target,
                                  seed=b.seed, engine=eng)
                return {"engine": eng, "n_qubits": g.n_qubits, "iterations": g.iterations,
                        "measured": g.measured, "target": b.target,
                        "success_probability": round(g.success_probability, 4),
                        "speedup": round(g.speedup, 2)}
            if kind == "qrng":
                rb = random_bytes(b.n_bytes, seed=b.seed, engine=eng)
                return {"engine": eng, "hex": rb.data.hex(), "source": rb.source,
                        "monobit_p_value": round(rb.monobit_p_value, 4),
                        "looks_random": rb.looks_random}
        except QuantumBackendUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        raise HTTPException(404, f"unknown demo {kind!r}")

    # -- Qiskit Lab: real Aer circuits with full metrics ---------------
    @app.post("/api/quantum/shor")
    def quantum_shor(body: ShorBody) -> dict:
        _require_qiskit()
        try:
            from ..threat import qiskit_backend as qb
            return qb.demo_shor(body.N, a=body.a, mode=body.backend, shots=body.shots,
                                seed=body.seed, p1=body.p1, p2=body.p2, readout=body.readout)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/quantum/grover")
    def quantum_grover(body: GroverBody) -> dict:
        _require_qiskit()
        from ..threat import qiskit_backend as qb
        try:
            single = qb.demo_grover(body.n_bits, iterations=body.iterations,
                                    mode=body.backend, shots=body.shots, target=body.target,
                                    p1=body.p1, p2=body.p2, readout=body.readout)
            curve = qb.grover_success_curve(body.n_bits, mode=body.backend,
                                            shots=body.shots, target=body.target,
                                            p1=body.p1, p2=body.p2, readout=body.readout)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        single["success_curve"] = curve["curve"]
        return single

    @app.post("/api/quantum/compare")
    def quantum_compare(body: CompareBody) -> dict:
        _require_qiskit()
        from ..threat import qiskit_backend as qb
        try:
            return qb.compare_shor(body.N, a=body.a, shots=body.shots,
                                   p1=body.p1, p2=body.p2, readout=body.readout)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/quantum/estimate")
    def quantum_estimate(body: EstimateBody) -> dict:
        from ..threat.resource_estimate import estimate, growth_curve
        try:
            proj = estimate(body.algorithm, body.key_bits,
                            phys_error_rate=body.phys_error_rate,
                            annual_growth=body.annual_growth)
            curve = growth_curve(body.algorithm, body.key_bits,
                                 phys_error_rate=body.phys_error_rate,
                                 annual_growth=body.annual_growth)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        out = proj.to_dict()
        out["growth_curve"] = curve["series"]
        return out

    @app.get("/api/benchmark")
    def benchmark(iterations: int = 20) -> dict:
        iterations = max(1, min(iterations, 500))
        if iterations not in _bench_cache:
            _bench_cache[iterations] = run_all(iterations=iterations).to_dict()
        return _bench_cache[iterations]

    @app.post("/api/migration/run")
    def migration_run(body: MigrationBody) -> dict:
        reg = demo_registry(body.records)
        try:
            result = migrate(reg, body.to_suite)
        except MigrationPlanError as exc:
            raise HTTPException(400, str(exc)) from exc
        payload = result.to_dict()
        try:
            result.assert_thesis()
            payload["thesis_ok"] = True
            payload["thesis_error"] = None
        except AssertionError as exc:
            payload["thesis_ok"] = False
            payload["thesis_error"] = str(exc)
        return payload

    @app.get("/api/migration/plan")
    def migration_plan(assessment_year: int | None = None) -> dict:
        from ..migration.planner import plan_waves

        report = prioritise(scan_estate(), assessment_year=assessment_year)
        return plan_waves(report)

    @app.get("/api/migration/mosca")
    def migration_mosca(assessment_year: int | None = None) -> dict:
        report = prioritise(scan_estate(), assessment_year=assessment_year)
        too_late = report.too_late()
        return {
            "assessment_year": report.assessment_year,
            "crqc_year": report.crqc_year,
            "findings_past_start_date": len(too_late),
            "worst_deficit_years": round(max(
                (s.mosca.exposure_gap_years for s in report.scores), default=0.0), 1),
            "examples": [
                {"detail": s.asset.detail, "location": s.asset.location,
                 "shelf_life_years": s.mosca.shelf_life_years,
                 "migration_years": round(s.mosca.migration_years, 2),
                 "deficit_years": round(s.mosca.exposure_gap_years, 1)}
                for s in too_late[:8]
            ],
        }

    frontend = frontend_dir()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (frontend / "index.html").read_text(encoding="utf-8")

    app.mount("/static", StaticFiles(directory=frontend), name="static")
    return app


app = create_app()
