# -*- coding: utf-8 -*-
"""Evidence-mode boundary: native/reference type separation (guard rails only).

This module installs *types and checks*, not execution.  It implements the
``REFERENCE_QUARANTINE_DECISION`` rule set:

  * ``ReferenceProfile`` / ``ReferenceDescriptor`` / ``ReferenceResult`` cannot
    satisfy ``NativeContract`` or ``GateCertificate`` APIs;
  * ``ReferenceRegistry`` and ``NativeContractRegistry`` are separate types;
  * a reference object can never be re-labelled as native evidence.

Design constraints taken from the frozen Astra authority:

  * the four evidence modes are spelled exactly as the Astra semantic freeze
    records them, and are never renamed or reinterpreted here;
  * "reuse never changes evidence class" -- consuming a reference object must
    not upgrade it.

Honesty note on strength of enforcement.  These are structural *guard rails*
for a typed codebase, not a security sandbox.  ``NativeContract`` and
``GateCertificate`` are sealed with a module-private token so that ordinary
construction and reference objects cannot satisfy them; a caller who
deliberately reaches for the private module attribute could still forge one.
The AST/import guard in ``reference_boundary`` plus the tests in
``tests/battle_sandbox/test_reference_quarantine.py`` cover accidental and
casual violations, which is the scope this task was given.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.errors import BattleSandboxError

__all__ = [
    "EVIDENCE_MODE_NAMES",
    "NATIVE_EVIDENCE_MODE",
    "NON_NATIVE_EVIDENCE_MODES",
    "EvidenceBoundaryError",
    "EvidenceMode",
    "GateCertificate",
    "NativeContract",
    "NativeContractRegistry",
    "ReferenceDescriptor",
    "ReferenceProfile",
    "ReferenceRegistry",
    "ReferenceResult",
    "certify_native_contract",
    "evidence_mode_of",
    "is_native_evidenced",
    "is_reference_wrapper",
    "issue_gate_certificate",
    "require_native_contract",
]


class EvidenceBoundaryError(BattleSandboxError):
    """Raised when an evidence-mode or native/reference boundary is violated."""


class EvidenceMode(str, Enum):
    """The evidence modes recorded by the Astra semantic freeze.

    The member names and values are the frozen spellings.  Do not rename them
    and do not add modes here.
    """

    NATIVE_EVIDENCED = "NATIVE_EVIDENCED"
    REFERENCE_MODEL = "REFERENCE_MODEL"
    SANDBOX_EXTENSION = "SANDBOX_EXTENSION"
    UNSUPPORTED = "UNSUPPORTED"


#: Frozen spellings, exposed for callers that must compare raw strings.
EVIDENCE_MODE_NAMES = tuple(mode.value for mode in EvidenceMode)

NATIVE_EVIDENCE_MODE = EvidenceMode.NATIVE_EVIDENCED

#: Modes that can never issue or satisfy a native gate certificate.
NON_NATIVE_EVIDENCE_MODES = frozenset(
    {
        EvidenceMode.REFERENCE_MODEL,
        EvidenceMode.SANDBOX_EXTENSION,
        EvidenceMode.UNSUPPORTED,
    }
)


class _NativeSealToken:
    """Module-private seal placed on native contracts and gate certificates."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return "<native-evidence-seal>"


_NATIVE_SEAL = _NativeSealToken()


def _coerce_mode(value: Any, *, owner: str) -> EvidenceMode:
    if isinstance(value, EvidenceMode):
        return value
    if isinstance(value, str):
        try:
            return EvidenceMode(value)
        except ValueError:
            pass
    raise EvidenceBoundaryError(
        f"{owner}: {value!r} is not one of the frozen evidence modes "
        f"{EVIDENCE_MODE_NAMES!r}"
    )


def _require_reference_mode(value: Any, *, owner: str) -> EvidenceMode:
    mode = _coerce_mode(value, owner=owner)
    if mode is NATIVE_EVIDENCE_MODE:
        raise EvidenceBoundaryError(
            f"{owner} cannot carry {NATIVE_EVIDENCE_MODE.value}: a reference "
            "object may never claim native evidence (REUSE_NEVER_CHANGES_"
            "EVIDENCE_CLASS)"
        )
    return mode


# ---------------------------------------------------------------------------
# Reference side (quarantined)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceProfile:
    """A caller-selected reference packet plus its explicit assumptions.

    The mode is restricted to a non-native evidence mode at construction time,
    so a profile cannot be used to smuggle native evidence.
    """

    reference_id: str
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reference_id, str) or not self.reference_id:
            raise EvidenceBoundaryError(
                "ReferenceProfile.reference_id must be a non-empty string"
            )
        object.__setattr__(
            self,
            "evidence_mode",
            _require_reference_mode(self.evidence_mode, owner="ReferenceProfile"),
        )


@dataclass(frozen=True)
class ReferenceDescriptor:
    """A description of quarantined reference material.  Never native."""

    descriptor_id: str
    profile: ReferenceProfile
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ReferenceProfile):
            raise EvidenceBoundaryError(
                "ReferenceDescriptor.profile must be a ReferenceProfile"
            )

    @property
    def evidence_mode(self) -> EvidenceMode:
        # Derived, never independently settable: the mode travels with the
        # profile so it cannot drift.
        return self.profile.evidence_mode


@dataclass(frozen=True)
class ReferenceResult:
    """The outcome of a reference computation, still labelled reference."""

    profile: ReferenceProfile
    payload: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ReferenceProfile):
            raise EvidenceBoundaryError(
                "ReferenceResult.profile must be a ReferenceProfile"
            )

    @property
    def evidence_mode(self) -> EvidenceMode:
        return self.profile.evidence_mode


class ReferenceRegistry:
    """Inert registry marker for reference profiles.

    It stores profiles and their evidence modes.  It has no execution entry
    point and cannot yield native contracts: the two registry roles are
    deliberately separate types.
    """

    __slots__ = ("_profiles",)

    def __init__(self) -> None:
        self._profiles: list[ReferenceProfile] = []

    def register(self, profile: ReferenceProfile) -> ReferenceProfile:
        if not isinstance(profile, ReferenceProfile):
            raise EvidenceBoundaryError(
                "ReferenceRegistry accepts ReferenceProfile values only; got "
                f"{type(profile).__name__}"
            )
        self._profiles.append(profile)
        return profile

    @property
    def profiles(self) -> tuple[ReferenceProfile, ...]:
        return tuple(self._profiles)

    def native_contracts(self) -> tuple[NativeContract, ...]:
        raise EvidenceBoundaryError(
            "ReferenceRegistry cannot yield native contracts; use "
            "NativeContractRegistry for native-evidenced contracts"
        )

    def __len__(self) -> int:
        return len(self._profiles)

    def __contains__(self, profile: object) -> bool:
        return profile in self._profiles


# ---------------------------------------------------------------------------
# Native side
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NativeContract:
    """A native-evidenced contract.

    Sealed: ordinary construction fails unless the caller holds the private
    module seal, which only ``certify_native_contract`` passes.
    """

    contract_id: str
    evidence_mode: EvidenceMode
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, str) or not self.contract_id:
            raise EvidenceBoundaryError(
                "NativeContract.contract_id must be a non-empty string"
            )
        mode = _coerce_mode(self.evidence_mode, owner="NativeContract")
        if mode is not NATIVE_EVIDENCE_MODE:
            raise EvidenceBoundaryError(
                f"NativeContract requires {NATIVE_EVIDENCE_MODE.value}; got "
                f"{mode.value}"
            )
        if self._seal is not _NATIVE_SEAL:
            raise EvidenceBoundaryError(
                "NativeContract must be produced by certify_native_contract"
            )
        object.__setattr__(self, "evidence_mode", mode)

    @property
    def is_native_evidenced(self) -> bool:
        return (
            self.evidence_mode is NATIVE_EVIDENCE_MODE
            and self._seal is _NATIVE_SEAL
        )


@dataclass(frozen=True)
class GateCertificate:
    """Proof that a native-evidenced contract satisfied a named gate."""

    gate_id: str
    contract_id: str
    evidence_mode: EvidenceMode
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        mode = _coerce_mode(self.evidence_mode, owner="GateCertificate")
        if mode is not NATIVE_EVIDENCE_MODE:
            raise EvidenceBoundaryError(
                f"GateCertificate requires {NATIVE_EVIDENCE_MODE.value}; got "
                f"{mode.value} (a gate certificate is native-evidence proof only)"
            )
        if self._seal is not _NATIVE_SEAL:
            raise EvidenceBoundaryError(
                "GateCertificate must be produced by issue_gate_certificate"
            )
        object.__setattr__(self, "evidence_mode", mode)


class NativeContractRegistry:
    """Inert registry marker for native contracts.

    Separate type from ``ReferenceRegistry``; it accepts only sealed native
    contracts and never accepts reference objects.
    """

    __slots__ = ("_contracts",)

    def __init__(self) -> None:
        self._contracts: list[NativeContract] = []

    def register(self, contract: Any) -> NativeContract:
        native = require_native_contract(contract, role="NativeContractRegistry")
        self._contracts.append(native)
        return native

    @property
    def contracts(self) -> tuple[NativeContract, ...]:
        return tuple(self._contracts)

    def issue(self, gate_id: str, contract: Any) -> GateCertificate:
        return issue_gate_certificate(gate_id, contract)

    def __len__(self) -> int:
        return len(self._contracts)

    def __contains__(self, contract: object) -> bool:
        return contract in self._contracts


# ---------------------------------------------------------------------------
# Boundary API
# ---------------------------------------------------------------------------

_REFERENCE_WRAPPER_TYPES = (
    ReferenceProfile,
    ReferenceDescriptor,
    ReferenceResult,
    ReferenceRegistry,
)


def is_reference_wrapper(candidate: Any) -> bool:
    """True when the value is a quarantined reference-side object."""
    return isinstance(candidate, _REFERENCE_WRAPPER_TYPES)


def evidence_mode_of(candidate: Any) -> EvidenceMode | None:
    """Return the declared evidence mode of a boundary object, else ``None``."""
    if isinstance(candidate, ReferenceRegistry):
        return EvidenceMode.REFERENCE_MODEL
    mode = getattr(candidate, "evidence_mode", None)
    if isinstance(mode, EvidenceMode):
        return mode
    if isinstance(mode, str):
        try:
            return EvidenceMode(mode)
        except ValueError:
            return None
    return None


def certify_native_contract(
    contract_id: str,
    *,
    evidence_mode: EvidenceMode = NATIVE_EVIDENCE_MODE,
) -> NativeContract:
    """Seal a native-evidenced contract.

    This is the only producer of ``NativeContract``.  A non-native mode is
    rejected outright: a native contract cannot be used to carry reference
    material.
    """
    mode = _coerce_mode(evidence_mode, owner="certify_native_contract")
    if mode is not NATIVE_EVIDENCE_MODE:
        raise EvidenceBoundaryError(
            f"certify_native_contract requires {NATIVE_EVIDENCE_MODE.value}; "
            f"got {mode.value}"
        )
    return NativeContract(
        contract_id=contract_id, evidence_mode=mode, _seal=_NATIVE_SEAL
    )


def require_native_contract(candidate: Any, *, role: str = "value") -> NativeContract:
    """Return ``candidate`` if it is a sealed native contract, else raise."""
    if is_reference_wrapper(candidate):
        raise EvidenceBoundaryError(
            f"{role}: {type(candidate).__name__} is reference-quarantined and "
            "can never satisfy a native API"
        )
    if not isinstance(candidate, NativeContract):
        raise EvidenceBoundaryError(
            f"{role}: expected a sealed NativeContract, got "
            f"{type(candidate).__name__}"
        )
    if not candidate.is_native_evidenced:
        raise EvidenceBoundaryError(
            f"{role}: NativeContract {candidate.contract_id!r} is not sealed "
            f"native evidence (mode {candidate.evidence_mode.value})"
        )
    return candidate


def is_native_evidenced(candidate: Any) -> bool:
    """True only for a properly sealed native-evidenced contract."""
    return (
        isinstance(candidate, NativeContract)
        and candidate.is_native_evidenced
        and not is_reference_wrapper(candidate)
    )


def issue_gate_certificate(gate_id: str, contract: Any) -> GateCertificate:
    """Issue a native gate certificate for a sealed native contract.

    Reference wrappers, registries and forged contracts are rejected before any
    certificate is produced.
    """
    native = require_native_contract(contract, role=f"gate {gate_id!r}")
    return GateCertificate(
        gate_id=gate_id,
        contract_id=native.contract_id,
        evidence_mode=NATIVE_EVIDENCE_MODE,
        _seal=_NATIVE_SEAL,
    )
