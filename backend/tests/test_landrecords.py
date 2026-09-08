"""The demo land-records application (Phase 5 subject).

The application must be a faithful crypto-agility client: it seals and opens
records through the ``kem``/``sig`` facades, records the algorithm names it was
handed, and detects tampering — all without naming an algorithm itself.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.agility import reload
from app.agility.policy import write_active_suite
from app.landrecords import (
    IntegrityError,
    LandRegistry,
    NotRekeyed,
    RecordNotFound,
    TitleRecord,
    demo_registry,
    sample_titles,
)


def _title(**kw) -> TitleRecord:
    base = dict(parcel_id="AP-VZM-2026-000042", owner="A. Rao", area_sqm=250.0,
                survey_note="test parcel", valuation_gbp=120_000)
    base.update(kw)
    return TitleRecord(**base)


def test_register_and_open_round_trips(policy_file):
    reg = LandRegistry()
    reg.rekey()
    rid = reg.register(_title(owner="S. Devi", valuation_gbp=815_000))
    got = reg.open(rid)
    assert got.owner == "S. Devi"
    assert got.valuation_gbp == 815_000


def test_registry_requires_rekey_first(policy_file):
    with pytest.raises(NotRekeyed):
        LandRegistry().register(_title())


def test_default_suite_algorithms_are_recorded(policy_file):
    reg = demo_registry(4)
    assert reg.current_suite == "hybrid"
    assert reg.algorithms_in_use() == {
        ("X25519+ML-KEM-768", "ECDSA-P256+ML-DSA-65"): 4
    }
    for rid in reg.record_ids():
        sealed = reg.sealed(rid)
        assert sealed.kem_algorithm == "X25519+ML-KEM-768"
        assert sealed.sig_algorithm == "ECDSA-P256+ML-DSA-65"


def test_all_sample_records_verify(policy_file):
    reg = demo_registry(12, seed=3)
    assert all(reg.verify_all().values())
    assert len(reg) == 12


def test_confidential_field_is_not_in_the_sealed_record(policy_file):
    reg = demo_registry(1)
    sealed = reg.sealed(reg.record_ids()[0])
    plaintext = reg.open(reg.record_ids()[0])
    assert str(plaintext.valuation_gbp).encode() not in sealed.blob
    assert plaintext.survey_note.encode() not in sealed.blob


def test_tampering_with_owner_breaks_the_signature(policy_file):
    reg = demo_registry(2)
    rid = reg.record_ids()[0]
    reg._records[rid] = dataclasses.replace(reg.sealed(rid), owner="Mallory")
    assert reg.verify(rid) is False
    with pytest.raises(IntegrityError):
        reg.open(rid)


def test_tampering_with_ciphertext_breaks_aead(policy_file):
    reg = demo_registry(2)
    rid = reg.record_ids()[0]
    sealed = reg.sealed(rid)
    flipped = bytes([sealed.blob[0] ^ 0x01]) + sealed.blob[1:]
    reg._records[rid] = dataclasses.replace(sealed, blob=flipped)
    # re-sign so the signature is not the thing that fails
    from app.agility import sig
    epoch = reg.current_epoch
    resigned = sig.sign(epoch.sig_private, reg._records[rid].signing_message())
    reg._records[rid] = dataclasses.replace(reg._records[rid], signature=resigned.signature)
    with pytest.raises(IntegrityError):
        reg.open(rid)


def test_missing_record_raises(policy_file):
    reg = demo_registry(1)
    with pytest.raises(RecordNotFound):
        reg.open("TR-999999")


def test_replace_reseals_in_place(policy_file):
    reg = demo_registry(1)
    rid = reg.record_ids()[0]
    before = reg.sealed(rid)
    reg.replace(rid, _title(owner="New Owner"))
    after = reg.sealed(rid)
    assert after.record_id == rid
    assert after.kem_ciphertext != before.kem_ciphertext
    assert reg.open(rid).owner == "New Owner"


def test_records_sealed_on_a_stale_suite_do_not_verify(policy_file):
    reg = demo_registry(2)
    write_active_suite("classical", policy_file)
    reload()
    # keys/ciphertext are still hybrid, policy is now classical
    assert not any(reg.verify_all().values())


def test_application_module_names_no_algorithm():
    import pathlib

    import app.landrecords as pkg

    root = pathlib.Path(pkg.__file__).parent
    banned = ("ML-KEM", "ML_KEM", "ML-DSA", "RSA", "X25519", "ECDSA", "AES-256",
              "Kyber", "Dilithium")
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("#")
        )
        # AESGCM is a construction, not an agile choice; allow the import name.
        code = code.replace("AESGCM", "")
        for token in banned:
            assert token not in code, f"{path.name} names {token!r}"


def test_sample_titles_are_deterministic():
    a = sample_titles(5, seed=1)
    b = sample_titles(5, seed=1)
    assert a == b
    assert len({t.parcel_id for t in sample_titles(50, seed=0)}) > 40
