# -*- coding: utf-8 -*-
"""Sealed strict-preflight permission certificate (G01-004).

This is the first *strict execution* permission object.  It is local integrity
infrastructure, not a recovered native-client certificate.  Construction is
possible only through :func:`certify_closed_preflight`, which requires a fully
closed native-evidenced preflight result and a sealed native contract.  The
function performs no execution, mutation, RNG draw, allocation or commit.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NoReturn

from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode
from hsr_battle_agent.battle_sandbox.evidence_boundary import (
    NativeContract,
    require_native_contract,
)
from hsr_battle_agent.battle_sandbox.errors import BattleSandboxError
from hsr_battle_agent.battle_sandbox.preflight import (
    ObligationAccess,
    PreflightResult,
)
from hsr_battle_agent.battle_sandbox.revision import StateRevision
from hsr_battle_agent.battle_sandbox.snapshot_v2 import SnapshotPolicyIdentity

__all__ = [
    "GATE_CERTIFICATE_SCHEMA",
    "GateCertificate",
    "GateCertificateError",
    "certify_closed_preflight",
]

GATE_CERTIFICATE_SCHEMA = "terra_gate_certificate/1"


class GateCertificateError(BattleSandboxError):
    """Raised when strict certificate construction or validation fails."""


class _CertificateSeal:
    __slots__ = ()


_CERTIFICATE_SEAL = _CertificateSeal()


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GateCertificateError(f"{label} must be a non-empty trimmed string")
    return value


def _contract_copy(value: ContractRef) -> ContractRef:
    if not isinstance(value, ContractRef):
        raise GateCertificateError("contract_ref must be a ContractRef")
    return ContractRef.from_dict(value.to_dict())


def _policy_copy(value: SnapshotPolicyIdentity) -> SnapshotPolicyIdentity:
    if not isinstance(value, SnapshotPolicyIdentity):
        raise GateCertificateError(
            "policy_identity must be a SnapshotPolicyIdentity"
        )
    return SnapshotPolicyIdentity.from_dict(value.to_dict())


def _revision_copy(value: StateRevision) -> StateRevision:
    if not isinstance(value, StateRevision):
        raise GateCertificateError("state_revision must be a StateRevision")
    return StateRevision.from_dict(value.to_dict())


def _access_copy(value: ObligationAccess) -> ObligationAccess:
    if not isinstance(value, ObligationAccess):
        raise GateCertificateError("certificate access must be ObligationAccess")
    return ObligationAccess.from_dict(value.to_dict())


def _identity_node(value: Any, where: str = "binding") -> Any:
    """Type-tag a binding so tuple/list and scalar categories cannot collide."""
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GateCertificateError(f"{where} contains a non-finite number")
        return ["float", value.hex()]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, list):
        return [
            "list",
            [_identity_node(item, f"{where}[{index}]") for index, item in enumerate(value)],
        ]
    if isinstance(value, tuple):
        return [
            "tuple",
            [_identity_node(item, f"{where}[{index}]") for index, item in enumerate(value)],
        ]
    if isinstance(value, Mapping):
        keys = tuple(value.keys())
        if any(not isinstance(key, str) for key in keys):
            raise GateCertificateError(f"{where} has a non-string mapping key")
        return [
            "mapping",
            [
                [key, _identity_node(value[key], f"{where}.{key}")]
                for key in sorted(keys, key=lambda item: item.encode("utf-8"))
            ],
        ]
    raise GateCertificateError(
        f"{where} contains unsupported identity value {type(value).__name__}"
    )


def _identity_hash(document: Mapping[str, Any], *, domain: str) -> str:
    text = json.dumps(
        [domain, _identity_node(document)],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _closure_identity(result: PreflightResult) -> str:
    return _identity_hash(
        result.closure.to_dict(), domain="terra-gate-closure/1"
    )


@dataclass(frozen=True, init=False, eq=False, repr=False)
class GateCertificate:
    """Immutable bindings authorising only one completely closed input.

    The class is sealed.  A caller cannot construct it directly, deserialize a
    document into it, or add permissions after preflight.  Equality and
    :meth:`matches` cover every binding, including the complete closure digest
    and ordered repeated access occurrences.
    """

    _plan_identity: str
    _evidence_mode: EvidenceMode
    _policy_identity: SnapshotPolicyIdentity
    _input_identity: str
    _input_revision: str
    _state_revision: StateRevision
    _contract_ref: ContractRef
    _contract_revision: str
    _closure_identity: str
    _allowed_reads: tuple[ObligationAccess, ...]
    _allowed_writes: tuple[ObligationAccess, ...]
    _seal: object

    def __init__(
        self,
        *,
        plan_identity: str,
        evidence_mode: EvidenceMode,
        policy_identity: SnapshotPolicyIdentity,
        input_identity: str,
        input_revision: str,
        state_revision: StateRevision,
        contract_ref: ContractRef,
        contract_revision: str,
        closure_identity: str,
        allowed_reads: tuple[ObligationAccess, ...],
        allowed_writes: tuple[ObligationAccess, ...],
        _seal: object = None,
    ) -> None:
        if _seal is not _CERTIFICATE_SEAL:
            raise GateCertificateError(
                "GateCertificate must be produced by certify_closed_preflight"
            )
        if evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
            raise GateCertificateError(
                "strict GateCertificate requires NATIVE_EVIDENCED; reference, "
                "extension and unsupported material cannot be promoted"
            )
        if isinstance(allowed_reads, (str, bytes)) or not isinstance(
            allowed_reads, tuple
        ):
            raise GateCertificateError("allowed_reads must be an ordered tuple")
        if isinstance(allowed_writes, (str, bytes)) or not isinstance(
            allowed_writes, tuple
        ):
            raise GateCertificateError("allowed_writes must be an ordered tuple")
        owned_policy = _policy_copy(policy_identity)
        owned_contract = _contract_copy(contract_ref)
        if owned_policy.evidence_mode is not evidence_mode:
            raise GateCertificateError(
                "policy evidence mode must equal the certificate evidence mode"
            )
        if owned_contract.evidence_mode is not evidence_mode:
            raise GateCertificateError(
                "contract evidence mode must equal the certificate evidence mode"
            )
        object.__setattr__(self, "_plan_identity", _token(plan_identity, "plan_identity"))
        object.__setattr__(self, "_evidence_mode", evidence_mode)
        object.__setattr__(self, "_policy_identity", owned_policy)
        object.__setattr__(self, "_input_identity", _token(input_identity, "input_identity"))
        object.__setattr__(self, "_input_revision", _token(input_revision, "input_revision"))
        object.__setattr__(self, "_state_revision", _revision_copy(state_revision))
        object.__setattr__(self, "_contract_ref", owned_contract)
        object.__setattr__(
            self, "_contract_revision", _token(contract_revision, "contract_revision")
        )
        object.__setattr__(
            self, "_closure_identity", _token(closure_identity, "closure_identity")
        )
        object.__setattr__(
            self, "_allowed_reads", tuple(_access_copy(item) for item in allowed_reads)
        )
        object.__setattr__(
            self,
            "_allowed_writes",
            tuple(_access_copy(item) for item in allowed_writes),
        )
        object.__setattr__(self, "_seal", _seal)

    def __bool__(self) -> NoReturn:
        raise GateCertificateError(
            "GateCertificate has no truthiness; validate exact bindings explicitly"
        )

    @property
    def plan_identity(self) -> str:
        return self._plan_identity

    @property
    def evidence_mode(self) -> EvidenceMode:
        return self._evidence_mode

    @property
    def policy_identity(self) -> SnapshotPolicyIdentity:
        return _policy_copy(self._policy_identity)

    @property
    def input_identity(self) -> str:
        return self._input_identity

    @property
    def input_revision(self) -> str:
        return self._input_revision

    @property
    def state_revision(self) -> StateRevision:
        return _revision_copy(self._state_revision)

    @property
    def contract_ref(self) -> ContractRef:
        return _contract_copy(self._contract_ref)

    @property
    def contract_revision(self) -> str:
        return self._contract_revision

    @property
    def closure_identity(self) -> str:
        return self._closure_identity

    @property
    def allowed_reads(self) -> tuple[ObligationAccess, ...]:
        return tuple(_access_copy(item) for item in self._allowed_reads)

    @property
    def allowed_writes(self) -> tuple[ObligationAccess, ...]:
        return tuple(_access_copy(item) for item in self._allowed_writes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": GATE_CERTIFICATE_SCHEMA,
            "plan_identity": self._plan_identity,
            "evidence_mode": self._evidence_mode.value,
            "policy_identity": self._policy_identity.to_dict(),
            "input_identity": self._input_identity,
            "input_revision": self._input_revision,
            "state_revision": self._state_revision.to_dict(),
            "contract_ref": self._contract_ref.to_dict(),
            "contract_revision": self._contract_revision,
            "closure_identity": self._closure_identity,
            "allowed_reads": [item.to_dict() for item in self._allowed_reads],
            "allowed_writes": [item.to_dict() for item in self._allowed_writes],
        }

    def identity(self) -> str:
        return _identity_hash(
            self.to_dict(), domain="terra-gate-certificate/1"
        )

    def matches(
        self,
        result: PreflightResult,
        *,
        native_contract: NativeContract,
        plan_identity: str,
        evidence_mode: EvidenceMode,
        policy_identity: SnapshotPolicyIdentity,
        input_identity: str,
        input_revision: str,
        state_revision: StateRevision,
        contract_ref: ContractRef,
        contract_revision: str,
    ) -> bool:
        """Return whether every supplied binding recreates this certificate."""
        try:
            candidate = certify_closed_preflight(
                result,
                native_contract=native_contract,
                plan_identity=plan_identity,
                evidence_mode=evidence_mode,
                policy_identity=policy_identity,
                input_identity=input_identity,
                input_revision=input_revision,
                state_revision=state_revision,
                contract_ref=contract_ref,
                contract_revision=contract_revision,
            )
        except (GateCertificateError, BattleSandboxError, ValueError, TypeError):
            return False
        return self.identity() == candidate.identity()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GateCertificate):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return int(self.identity()[:16], 16)


def certify_closed_preflight(
    result: PreflightResult,
    *,
    native_contract: NativeContract,
    plan_identity: str,
    evidence_mode: EvidenceMode,
    policy_identity: SnapshotPolicyIdentity,
    input_identity: str,
    input_revision: str,
    state_revision: StateRevision,
    contract_ref: ContractRef,
    contract_revision: str,
) -> GateCertificate:
    """Seal exact native bindings after complete conservative closure."""
    if not isinstance(result, PreflightResult) or not result.is_closed():
        raise GateCertificateError(
            "certificate construction requires a CLOSED PreflightResult"
        )
    native = require_native_contract(native_contract, role="strict preflight")
    if evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
        raise GateCertificateError(
            "certificate evidence mode must be exactly NATIVE_EVIDENCED"
        )
    owned_contract = _contract_copy(contract_ref)
    if owned_contract.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
        raise GateCertificateError("reference/non-native ContractRef cannot certify")
    if native.contract_id != owned_contract.contract_id:
        raise GateCertificateError(
            "sealed NativeContract and bound ContractRef identify different contracts"
        )

    closure = result.closure
    for obligation in closure.obligations:
        if obligation.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
            raise GateCertificateError(
                "every closed obligation must be NATIVE_EVIDENCED; closure does "
                "not promote reference or extension evidence"
            )
        if not obligation.is_satisfied():
            raise GateCertificateError(
                "every certified obligation must be explicitly RESOLVED"
            )

    return GateCertificate(
        plan_identity=plan_identity,
        evidence_mode=evidence_mode,
        policy_identity=policy_identity,
        input_identity=input_identity,
        input_revision=input_revision,
        state_revision=state_revision,
        contract_ref=owned_contract,
        contract_revision=contract_revision,
        closure_identity=_closure_identity(result),
        allowed_reads=closure.allowed_reads,
        allowed_writes=closure.allowed_writes,
        _seal=_CERTIFICATE_SEAL,
    )
