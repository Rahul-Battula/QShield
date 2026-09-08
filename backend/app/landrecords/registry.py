"""The demo land registry — an application built on the crypto-agility layer.

Every cryptographic operation goes through the ``kem`` and ``sig`` facades from
:mod:`app.agility`. This module contains no algorithm name, no backend
import, and no ``if`` on a suite. Which primitives run is entirely a function of
``policy.yaml`` at the moment :meth:`LandRegistry.rekey` and
:meth:`LandRegistry.register` are called.

Keys are held per :class:`KeyEpoch`: one KEM keypair and one signing keypair for
the suite that was active when :meth:`rekey` ran. A record records the epoch
that sealed it, so migration (:mod:`app.migration`) can open every record
under the keys that created it before re-sealing it under new ones.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..agility import kem, sig
from ..agility.policy import load_policy
from .models import SealedRecord, TitleRecord


class RegistryError(RuntimeError):
    """Base class for land-registry failures."""


class NotRekeyed(RegistryError):
    """An operation needed keys but :meth:`LandRegistry.rekey` was never called."""


class RecordNotFound(RegistryError):
    pass


class IntegrityError(RegistryError):
    """A stored record failed signature or AEAD verification."""


@dataclass(frozen=True, slots=True)
class KeyEpoch:
    """One generation of registry keys, tied to the suite that produced them."""

    epoch_id: int
    suite: str
    kem_algorithm: str
    sig_algorithm: str
    kem_public: bytes
    kem_private: bytes
    sig_public: bytes
    sig_private: bytes


@dataclass
class LandRegistry:
    """An in-memory register of sealed land titles."""

    _records: dict[str, SealedRecord] = field(default_factory=dict)
    _epochs: dict[int, KeyEpoch] = field(default_factory=dict)
    _current_epoch: int | None = None
    _seq: int = 0

    # -- key management ------------------------------------------------

    def rekey(self) -> KeyEpoch:
        """Generate a fresh key epoch for the *currently active* policy suite."""
        suite = load_policy().active_suite
        kem_kp = kem.generate_keypair()
        sig_kp = sig.generate_keypair()
        epoch = KeyEpoch(
            epoch_id=len(self._epochs) + 1,
            suite=suite,
            kem_algorithm=kem_kp.algorithm,
            sig_algorithm=sig_kp.algorithm,
            kem_public=kem_kp.public_key,
            kem_private=kem_kp.private_key,
            sig_public=sig_kp.public_key,
            sig_private=sig_kp.private_key,
        )
        self._epochs[epoch.epoch_id] = epoch
        self._current_epoch = epoch.epoch_id
        return epoch

    @property
    def current_epoch(self) -> KeyEpoch:
        if self._current_epoch is None:
            raise NotRekeyed("call rekey() before using the registry")
        return self._epochs[self._current_epoch]

    @property
    def current_suite(self) -> str:
        return self.current_epoch.suite

    # -- record lifecycle -------------------------------------------

    def register(self, record: TitleRecord) -> str:
        """Seal ``record`` under the current epoch and store it. Returns the id."""
        self._seq += 1
        record_id = f"TR-{self._seq:06d}"
        self._records[record_id] = self._seal(record_id, record)
        return record_id

    def replace(self, record_id: str, record: TitleRecord) -> SealedRecord:
        """Re-seal an existing record under the current epoch (used by migration
        and by key rotation)."""
        if record_id not in self._records:
            raise RecordNotFound(record_id)
        sealed = self._seal(record_id, record)
        self._records[record_id] = sealed
        return sealed

    def open(self, record_id: str) -> TitleRecord:
        """Verify and decrypt a stored record back to plaintext."""
        if record_id not in self._records:
            raise RecordNotFound(record_id)
        return self._open(self._records[record_id])

    def verify(self, record_id: str) -> bool:
        try:
            self._open(self._records[record_id])
            return True
        except (IntegrityError, KeyError):
            return False

    def verify_all(self) -> dict[str, bool]:
        return {rid: self.verify(rid) for rid in self._records}

    # -- introspection --------------------------------------------

    def record_ids(self) -> list[str]:
        return list(self._records)

    def sealed(self, record_id: str) -> SealedRecord:
        return self._records[record_id]

    def algorithms_in_use(self) -> dict[tuple[str, str], int]:
        out: dict[tuple[str, str], int] = {}
        for sr in self._records.values():
            key = (sr.kem_algorithm, sr.sig_algorithm)
            out[key] = out.get(key, 0) + 1
        return out

    def __len__(self) -> int:
        return len(self._records)

    # -- crypto (facade only) -----------------------------------

    def _seal(self, record_id: str, record: TitleRecord) -> SealedRecord:
        epoch = self.current_epoch
        enc = kem.encapsulate(epoch.kem_public)
        nonce = os.urandom(12)
        blob = AESGCM(enc.shared_secret).encrypt(
            nonce, record.canonical_bytes(), record_id.encode()
        )
        draft = SealedRecord(
            record_id=record_id,
            parcel_id=record.parcel_id,
            owner=record.owner,
            kem_algorithm=enc.algorithm,
            sig_algorithm="",
            suite=epoch.suite,
            epoch_id=epoch.epoch_id,
            kem_ciphertext=enc.ciphertext,
            nonce=nonce,
            blob=blob,
            signature=b"",
        )
        signed = sig.sign(epoch.sig_private, draft.signing_message())
        return SealedRecord(
            record_id=draft.record_id,
            parcel_id=draft.parcel_id,
            owner=draft.owner,
            kem_algorithm=draft.kem_algorithm,
            sig_algorithm=signed.algorithm,
            suite=draft.suite,
            epoch_id=draft.epoch_id,
            kem_ciphertext=draft.kem_ciphertext,
            nonce=draft.nonce,
            blob=draft.blob,
            signature=signed.signature,
            sealed_at=draft.sealed_at,
        )

    def _open(self, sealed: SealedRecord) -> TitleRecord:
        epoch = self._epochs.get(sealed.epoch_id)
        if epoch is None:
            raise IntegrityError(f"no key epoch {sealed.epoch_id} for {sealed.record_id}")
        active = load_policy().active_suite
        if epoch.suite != active:
            raise IntegrityError(
                f"{sealed.record_id} is sealed under suite '{epoch.suite}' but "
                f"policy is now on '{active}'; run a migration to re-seal it"
            )
        if not sig.verify(epoch.sig_public, sealed.signing_message(), sealed.signature):
            raise IntegrityError(f"signature check failed for {sealed.record_id}")
        shared = kem.decapsulate(epoch.kem_private, sealed.kem_ciphertext)
        try:
            raw = AESGCM(shared).decrypt(sealed.nonce, sealed.blob, sealed.record_id.encode())
        except InvalidTag as exc:
            raise IntegrityError(f"AEAD check failed for {sealed.record_id}") from exc
        return TitleRecord.from_json(raw)
