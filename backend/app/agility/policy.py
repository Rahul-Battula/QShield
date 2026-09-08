"""Loading, validation and mutation of ``policy.yaml``.

A malformed policy fails here, at load time, with a clear message — never later
at crypto time with an obscure one.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, model_validator

from ..config import policy_path
from .errors import PolicyError


class Suite(BaseModel):
    """One named cryptographic configuration: a KEM and a signature algorithm."""

    kem: str
    sig: str


class MoscaConfig(BaseModel):
    """CRQC-arrival horizon presets, and inputs for Phase 3 risk scoring.

    ``presets`` maps a name to the calendar year a cryptographically relevant
    quantum computer is assumed to exist; ``active_preset`` selects one. The two
    optional fields feed Mosca's inequality (X + Y > Z):

    * ``assessment_year`` — the year "now" is taken to be. Defaults to the
      current year; pin it to make a risk report reproducible.
    * ``data_classes`` — how many years each part of the estate's data must stay
      confidential (the "X"), keyed by a leading path fragment of an asset's
      location. Longest match wins; unmatched assets use a built-in default.
    """

    active_preset: str
    presets: dict[str, int]
    assessment_year: int | None = None
    data_classes: dict[str, int] = {}

    @model_validator(mode="after")
    def _active_preset_exists(self) -> MoscaConfig:
        if self.active_preset not in self.presets:
            raise ValueError(
                f"mosca.active_preset {self.active_preset!r} is not one of "
                f"{sorted(self.presets)}"
            )
        return self

    def crqc_year(self) -> int:
        """The assumed CRQC arrival year for the active preset."""
        return self.presets[self.active_preset]


class Policy(BaseModel):
    """The whole of ``policy.yaml``."""

    version: int
    active_suite: str
    suites: dict[str, Suite]
    mosca: MoscaConfig

    @model_validator(mode="after")
    def _active_suite_exists(self) -> Policy:
        if self.active_suite not in self.suites:
            raise ValueError(
                f"active_suite {self.active_suite!r} is not defined under "
                f"suites: {sorted(self.suites)}"
            )
        return self

    def active(self) -> Suite:
        """Return the currently selected :class:`Suite`."""
        return self.suites[self.active_suite]


def load_policy(path: Path | None = None) -> Policy:
    """Read, parse and validate the policy file.

    Every failure mode is re-raised as :class:`PolicyError` with a message an
    operator can act on.
    """
    p = path or policy_path()
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PolicyError(f"policy file not found: {p}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyError(f"policy file is not valid YAML ({p}): {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyError(f"policy file must be a YAML mapping ({p})")

    try:
        return Policy.model_validate(raw)
    except ValidationError as exc:
        raise PolicyError(f"policy failed validation ({p}):\n{exc}") from exc


def write_active_suite(suite: str, path: Path | None = None) -> None:
    """Rewrite only the ``active_suite:`` line of the policy file.

    This is the single mutation that performs a migration. It is used by the
    hot-swap acceptance test and, from Phase 5, by the ``/api/agility`` endpoint
    that drives the live demo. The rest of the file is preserved and key order
    is kept so diffs stay readable.
    """
    p = path or policy_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if suite not in raw.get("suites", {}):
        raise PolicyError(
            f"cannot set active_suite to {suite!r}: not defined under suites: "
            f"{sorted(raw.get('suites', {}))}"
        )
    raw["active_suite"] = suite
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
