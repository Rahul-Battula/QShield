"""Phase 3 acceptance tests — risk prioritisation.

Claim: given a CBOM and the ``mosca`` horizon from ``policy.yaml``, QShield
ranks every finding by Mosca's inequality plus exposure and blast radius, and
groups the backlog into coherent work packages — deterministically.

The end-to-end tests pin ``assessment_year`` so the arithmetic is fixed.
"""

from __future__ import annotations

import json

import pytest

from app.agility.policy import MoscaConfig, load_policy
from app.discovery import scan_estate
from app.discovery.cbom import AssetKind, CryptoAsset, Exposure
from app.risk import (
    MoscaAssessment,
    PriorityBand,
    assess,
    estimate_migration_years,
    estimate_shelf_life,
    prioritise,
    render,
    render_markdown,
    render_table,
    score_asset,
    time_pressure,
)
from app.risk.mosca import resolve_assessment_year


def _asset(**kw) -> CryptoAsset:
    base = dict(
        kind=AssetKind.LIBRARY_CALL,
        primitive="RSA",
        detail="RSA-2048",
        location="land-registry/app/records_service.py:15",
        evidence="rsa.generate_private_key(...)",
        detector="source",
        exposure=Exposure.QUANTUM_BROKEN,
        rationale="Shor",
        recommendation="Migrate to the 'hybrid' suite.",
        key_bits=2048,
    )
    base.update(kw)
    return CryptoAsset(**base)


# ---------------------------------------------------------------------------
# Mosca's inequality
# ---------------------------------------------------------------------------

def test_mosca_gap_and_start_date():
    m = MoscaAssessment(
        shelf_life_years=25, migration_years=3, horizon_years=9,
        assessment_year=2026, crqc_year=2035,
    )
    assert m.exposure_gap_years == 25 + 3 - 9          # X + Y - Z
    assert m.is_too_late
    assert m.latest_safe_start_year == 2035 - 25 - 3   # 2007
    assert m.years_until_must_start == 2007 - 2026


def test_mosca_not_too_late_when_horizon_is_far():
    m = MoscaAssessment(
        shelf_life_years=2, migration_years=1, horizon_years=20,
        assessment_year=2026, crqc_year=2046,
    )
    assert not m.is_too_late
    assert m.exposure_gap_years == -17


def test_assess_reads_horizon_from_policy():
    cfg = MoscaConfig(active_preset="likely",
                      presets={"optimistic": 2030, "likely": 2035})
    m = assess(shelf_life_years=10, migration_years=1, mosca=cfg, assessment_year=2026)
    assert m.crqc_year == 2035
    assert m.horizon_years == 9


def test_resolve_assessment_year_precedence():
    cfg = MoscaConfig(active_preset="likely", presets={"likely": 2035},
                      assessment_year=2028)
    assert resolve_assessment_year(cfg, override=2030) == 2030   # explicit wins
    assert resolve_assessment_year(cfg) == 2028                  # then policy
    cfg2 = MoscaConfig(active_preset="likely", presets={"likely": 2035})
    assert resolve_assessment_year(cfg2) >= 2024                 # then current year


def test_time_pressure_ramps_around_the_deadline():
    def m(years_until_start):
        # horizon positive; craft years_until_must_start via the properties
        crqc = 2035
        year = 2026
        # years_until_must_start = crqc - X - Y - year  => choose X, Y accordingly
        x = crqc - year - years_until_start
        return MoscaAssessment(shelf_life_years=x, migration_years=0,
                               horizon_years=crqc - year,
                               assessment_year=year, crqc_year=crqc)

    assert time_pressure(m(+10)) == pytest.approx(0.0, abs=0.01)
    assert time_pressure(m(0)) == pytest.approx(0.5, abs=0.01)
    assert time_pressure(m(-10)) == pytest.approx(1.0, abs=0.01)
    assert time_pressure(m(-50)) == 1.0


# ---------------------------------------------------------------------------
# Shelf life (X) and migration cost (Y)
# ---------------------------------------------------------------------------

def test_shelf_life_prefix_match_and_default():
    years, basis = estimate_shelf_life(_asset(location="land-registry/x.py:1"))
    assert years == 30 and "land-registry" in basis
    years, basis = estimate_shelf_life(_asset(location="somewhere-else/x.py:1"))
    assert years == 10 and "default" in basis


def test_shelf_life_policy_override_beats_builtin():
    years, _ = estimate_shelf_life(
        _asset(location="tax-portal/a.py:1"), data_classes={"tax-portal": 99}
    )
    assert years == 99


def test_migration_cost_orders_config_below_code():
    cfg, _ = estimate_migration_years(_asset(kind=AssetKind.PROTOCOL_CONFIG))
    code, _ = estimate_migration_years(_asset(kind=AssetKind.LIBRARY_CALL))
    assert cfg < code


def test_migration_cost_legacy_multiplier_and_agility_discount():
    plain, _ = estimate_migration_years(
        _asset(location="tax-portal/a.py:1", recommendation="do something")
    )
    legacy, basis = estimate_migration_years(
        _asset(location="legacy-mainframe/a.py:1", recommendation="do something")
    )
    assert legacy > plain and "legacy" in basis

    discounted, basis = estimate_migration_years(
        _asset(recommendation="Migrate to the 'hybrid' suite."),
        live_suites={"hybrid"},
    )
    assert discounted < plain and "drop-in" in basis


def test_migration_cost_is_clamped():
    y, _ = estimate_migration_years(
        _asset(kind=AssetKind.LIBRARY_CALL, location="legacy-mainframe/deep/a.py:1")
    )
    assert 0.1 <= y <= 10.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score(asset, *, x=10, y=1.0, blast=1, year=2026):
    cfg = MoscaConfig(active_preset="likely", presets={"likely": 2035})
    m = assess(x, y, cfg, year)
    return score_asset(asset, m, blast_radius=blast,
                       shelf_life_basis="t", migration_basis="t")


def test_quantum_safe_asset_scores_near_zero():
    rs = _score(_asset(exposure=Exposure.QUANTUM_SAFE, primitive="ML-KEM"))
    assert rs.score <= 3.0
    assert rs.band is PriorityBand.P4


def test_classically_broken_outscores_weakened():
    broken = _score(_asset(exposure=Exposure.CLASSICALLY_BROKEN, primitive="MD5"))
    weak = _score(_asset(exposure=Exposure.QUANTUM_WEAKENED, primitive="AES",
                         key_bits=128))
    assert broken.score > weak.score


def test_longer_shelf_life_raises_score():
    short = _score(_asset(), x=5)
    long = _score(_asset(), x=30)
    assert long.score > short.score


def test_blast_radius_raises_score():
    lonely = _score(_asset(), blast=1)
    everywhere = _score(_asset(), blast=8)
    assert everywhere.score > lonely.score


def test_too_late_broken_primitive_is_forced_to_p1():
    rs = _score(_asset(exposure=Exposure.QUANTUM_BROKEN), x=30, y=3, year=2026)
    assert rs.mosca.is_too_late
    assert rs.band is PriorityBand.P1


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def report():
    return prioritise(scan_estate(), assessment_year=2026)


def test_report_scores_every_asset_and_sorts_descending(report):
    cbom = scan_estate()
    assert len(report.scores) == len(cbom.assets)
    values = [s.score for s in report.scores]
    assert values == sorted(values, reverse=True)


def test_report_bands_have_spread(report):
    counts = report.band_counts()
    assert counts["P1"] > 0
    assert counts["P2"] > 0
    # not everything is P1
    assert counts["P1"] < report.summary()["assets_scored"]


def test_land_registry_rsa_outranks_a_weakened_aes_config(report):
    def rank(pred):
        return next(i for i, s in enumerate(report.scores) if pred(s))

    rsa = rank(lambda s: s.asset.detail == "RSA-2048"
               and "records_service.py" in s.asset.location)
    aes = rank(lambda s: s.asset.primitive == "AES" and s.asset.key_bits == 128)
    assert rsa < aes  # lower index == higher priority


def test_quantum_safe_assets_are_scored_but_excluded_from_packages(report):
    safe = [s for s in report.scores if s.asset.exposure is Exposure.QUANTUM_SAFE]
    assert safe  # they are present in the ranking
    packaged = {id(s.asset) for wp in report.work_packages for s in wp.scores}
    assert not any(id(s.asset) in packaged for s in safe)


def test_work_packages_partition_the_backlog(report):
    backlog = [s for s in report.scores
               if s.asset.exposure is not Exposure.QUANTUM_SAFE]
    packaged = [s for wp in report.work_packages for s in wp.scores]
    assert len(packaged) == len(backlog)
    assert {s.asset.asset_id for s in packaged} == {s.asset.asset_id for s in backlog}


def test_work_packages_ordered_by_urgency(report):
    maxes = [wp.max_score for wp in report.work_packages]
    assert maxes == sorted(maxes, reverse=True)
    assert all(wp.id == f"wp-{i:02d}"
               for i, wp in enumerate(report.work_packages, start=1))


def test_too_late_count_grows_as_the_horizon_nears():
    near = prioritise(scan_estate(), assessment_year=2033)  # Z = 2
    far = prioritise(scan_estate(), assessment_year=2026)   # Z = 9
    assert len(near.too_late()) >= len(far.too_late())


def test_prioritise_is_deterministic():
    a = prioritise(scan_estate(), assessment_year=2026)
    b = prioritise(scan_estate(), assessment_year=2026)
    assert [(s.asset.asset_id, s.score, s.band.value) for s in a.scores] == \
           [(s.asset.asset_id, s.score, s.band.value) for s in b.scores]
    assert [(wp.id, wp.title, [m.asset.asset_id for m in wp.scores])
            for wp in a.work_packages] == \
           [(wp.id, wp.title, [m.asset.asset_id for m in wp.scores])
            for wp in b.work_packages]


def test_report_json_round_trips(report):
    payload = json.loads(report.to_json())
    assert payload["summary"]["assets_scored"] == len(report.scores)
    assert len(payload["scores"]) == len(report.scores)
    assert len(payload["work_packages"]) == len(report.work_packages)
    assert {"score", "band", "system", "mosca"} <= set(payload["scores"][0])


def test_renderers_produce_output(report):
    assert "SCORE" in render_table(report)
    assert "START BY" in render_table(report, top=5)
    md = render_markdown(report)
    assert md.startswith("# Post-quantum migration priorities")
    assert "## Work packages" in md
    assert render(report, "json") == report.to_json()


def test_policy_yaml_carries_data_classes():
    policy = load_policy()
    assert policy.mosca.data_classes.get("land-registry") == 30
    assert policy.mosca.crqc_year() == policy.mosca.presets[policy.mosca.active_preset]


def test_cli_entrypoint_runs_and_flags_p1():
    from app.risk.__main__ import main

    assert main(["--format", "json"]) == 0
    assert main(["--assessment-year", "2026", "--fail-on-p1"]) == 1
