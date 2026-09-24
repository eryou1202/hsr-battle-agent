# -*- coding: utf-8 -*-
"""Private transaction planning and staged state deltas.

These are local strict-execution integrity objects.  They do not encode
client-native operation semantics and expose no publication surface.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

from hsr_battle_agent.battle_ir.evidence import EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.gate_certificate import GateCertificate
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.identity import (
    IdentityAllocator,
    IdentityFamily,
    TypedIdentity,
    require_declared_family,
)
from hsr_battle_agent.battle_sandbox.opaque import OpaqueUnresolvedStore
from hsr_battle_agent.battle_sandbox.preflight import ObligationAccess
from hsr_battle_agent.battle_sandbox.revision import StateRevision
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state import F01StateEnvelope
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.stores.core import TypedStore

__all__ = [
    "TransactionError",
    "TransactionOperation",
    "TransactionPlan",
    "StagedWrite",
    "StagedDelta",
    "transaction_plan_identity",
    "plan_transaction",
]


class TransactionError(ValueError):
    """Raised when a local transaction boundary is violated."""


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TransactionError(f"{label} must be a non-empty trimmed string")
    return value


def _envelope(value: Any, label: str) -> F01StateEnvelope:
    try:
        return F01StateEnvelope(value)
    except (TypeError, ValueError) as exc:
        raise TransactionError(f"invalid {label}: {exc}") from exc


def _access_copy(value: ObligationAccess) -> ObligationAccess:
    if not isinstance(value, ObligationAccess):
        raise TransactionError("transaction footprints require ObligationAccess")
    return ObligationAccess.from_dict(value.to_dict())


@dataclass(frozen=True, init=False, eq=False)
class TransactionOperation:
    """One ordered, representation-only operation occurrence."""

    _operation_id: str
    _payload: F01StateEnvelope

    def __init__(self, operation_id: str, payload: Any) -> None:
        object.__setattr__(self, "_operation_id", _token(operation_id, "operation_id"))
        object.__setattr__(self, "_payload", _envelope(payload, "operation payload"))

    @property
    def operation_id(self) -> str:
        return self._operation_id

    @property
    def payload(self) -> Any:
        return self._payload.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_transaction_operation/1",
            "operation_id": self._operation_id,
            "payload": self._payload.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TransactionOperation":
        if not isinstance(data, Mapping) or set(data) != {
            "schema", "operation_id", "payload"
        }:
            raise TransactionError("invalid transaction operation document")
        if data["schema"] != "terra_transaction_operation/1":
            raise TransactionError("unknown transaction operation schema")
        return cls(data["operation_id"], F01StateEnvelope.from_dict(data["payload"]).value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TransactionOperation):
            return NotImplemented
        return self.to_dict() == other.to_dict()


def _operations(values: Sequence[TransactionOperation]) -> tuple[TransactionOperation, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise TransactionError("operations must be an ordered tuple or list")
    result: list[TransactionOperation] = []
    for item in values:
        if not isinstance(item, TransactionOperation):
            raise TransactionError("every operation must be TransactionOperation")
        result.append(TransactionOperation.from_dict(item.to_dict()))
    return tuple(result)


def transaction_plan_identity(operations: Sequence[TransactionOperation]) -> str:
    """Return the lossless identity of an ordered operation sequence."""
    owned = _operations(operations)
    document = F01StateEnvelope([item.to_dict() for item in owned]).to_dict()
    encoded = json.dumps(document, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":"))
    return "terra-plan-sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class TransactionPlan:
    """Immutable plan bound exactly to one sealed native certificate."""

    __slots__ = (
        "_operations", "_certificate", "_certificate_identity",
        "_source_revision", "_source_state_hash", "_reads", "_writes",
    )

    def __init__(
        self,
        operations: Sequence[TransactionOperation],
        certificate: GateCertificate,
        source_revision: StateRevision,
        source_state_hash: str,
    ) -> None:
        if not isinstance(certificate, GateCertificate):
            raise TransactionError("TransactionPlan requires a GateCertificate")
        if certificate.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
            raise TransactionError("only a native-evidenced certificate may plan")
        owned = _operations(operations)
        if transaction_plan_identity(owned) != certificate.plan_identity:
            raise TransactionError("operation sequence does not match certificate plan identity")
        if not isinstance(source_revision, StateRevision):
            raise TransactionError("source_revision must be StateRevision")
        if source_revision.to_dict() != certificate.state_revision.to_dict():
            raise TransactionError("source revision does not match certificate")
        self._operations = owned
        self._certificate = certificate
        self._certificate_identity = certificate.identity()
        self._source_revision = StateRevision.from_dict(source_revision.to_dict())
        self._source_state_hash = _token(source_state_hash, "source_state_hash")
        self._reads = tuple(_access_copy(item) for item in certificate.allowed_reads)
        self._writes = tuple(_access_copy(item) for item in certificate.allowed_writes)

    def __bool__(self) -> NoReturn:
        raise TransactionError("TransactionPlan has no truthiness and is not permission")

    @property
    def operations(self) -> tuple[TransactionOperation, ...]:
        return tuple(TransactionOperation.from_dict(item.to_dict()) for item in self._operations)

    @property
    def certificate(self) -> GateCertificate:
        return self._certificate

    @property
    def certificate_identity(self) -> str:
        return self._certificate_identity

    @property
    def source_revision(self) -> StateRevision:
        return StateRevision.from_dict(self._source_revision.to_dict())

    @property
    def source_state_hash(self) -> str:
        return self._source_state_hash

    @property
    def allowed_reads(self) -> tuple[ObligationAccess, ...]:
        return tuple(_access_copy(item) for item in self._reads)

    @property
    def allowed_writes(self) -> tuple[ObligationAccess, ...]:
        return tuple(_access_copy(item) for item in self._writes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_transaction_plan/1",
            "operations": [item.to_dict() for item in self._operations],
            "certificate_identity": self._certificate_identity,
            "source_revision": self._source_revision.to_dict(),
            "source_state_hash": self._source_state_hash,
            "allowed_reads": [item.to_dict() for item in self._reads],
            "allowed_writes": [item.to_dict() for item in self._writes],
        }


def plan_transaction(
    state: TerraBattleState,
    certificate: GateCertificate,
    operations: Sequence[TransactionOperation],
) -> TransactionPlan:
    """Read published state and produce a pure plan; never touch staged state."""
    if not isinstance(state, TerraBattleState):
        raise TransactionError("planning requires TerraBattleState")
    if not isinstance(certificate, GateCertificate):
        raise TransactionError("planning requires a sealed GateCertificate")
    if state.revision.to_dict() != certificate.state_revision.to_dict():
        raise TransactionError("live state revision does not match certificate")
    snapshot = TerraSnapshotV2(state=state, policy_identity=certificate.policy_identity)
    return TransactionPlan(
        operations, certificate, state.revision, semantic_hash_v2(snapshot)
    )


@dataclass(frozen=True, init=False, eq=False)
class StagedWrite:
    """One explicit staged write occurrence."""

    _kind: str
    _target: str
    _payload: F01StateEnvelope

    def __init__(self, kind: str, target: str, payload: Any) -> None:
        object.__setattr__(self, "_kind", _token(kind, "write kind"))
        object.__setattr__(self, "_target", _token(target, "write target"))
        object.__setattr__(self, "_payload", _envelope(payload, "write payload"))

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def target(self) -> str:
        return self._target

    @property
    def payload(self) -> Any:
        return self._payload.value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self._kind, "target": self._target, "payload": self._payload.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StagedWrite":
        return cls(data["kind"], data["target"], F01StateEnvelope.from_dict(data["payload"]).value)


def _presence_copy(value: PresenceValue) -> PresenceValue:
    if not isinstance(value, PresenceValue):
        value = PresenceValue.present(value)
    return PresenceValue.from_dict(value.to_dict())


class StagedDelta:
    """Private replacement material; no method can publish it to live state."""

    __slots__ = (
        "_plan_identity", "_certificate_identity", "_source_revision",
        "_source_state_hash", "_allowed_writes", "_stores", "_opaque",
        "_allocator", "_writes",
    )

    def __init__(self, plan: TransactionPlan, state: TerraBattleState) -> None:
        if not isinstance(plan, TransactionPlan) or not isinstance(state, TerraBattleState):
            raise TransactionError("StagedDelta requires a plan and TerraBattleState")
        if state.revision.to_dict() != plan.source_revision.to_dict():
            raise TransactionError("staged delta source revision is stale")
        actual = semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=plan.certificate.policy_identity))
        if actual != plan.source_state_hash:
            raise TransactionError("staged delta source state does not match plan")
        self._plan_identity = transaction_plan_identity(plan.operations)
        self._certificate_identity = plan.certificate_identity
        self._source_revision = plan.source_revision
        self._source_state_hash = plan.source_state_hash
        self._allowed_writes = tuple(_access_copy(x) for x in plan.allowed_writes)
        self._stores = {k: TypedStore.from_dict(v.to_dict()) for k, v in state.stores.items()}
        self._opaque = {k: OpaqueUnresolvedStore.from_dict(v.to_dict()) for k, v in state.opaque_stores.items()}
        self._allocator = state.allocator
        self._writes: tuple[StagedWrite, ...] = ()

    @classmethod
    def _copy_from(cls, value: "StagedDelta") -> "StagedDelta":
        result = object.__new__(cls)
        result._plan_identity = value._plan_identity
        result._certificate_identity = value._certificate_identity
        result._source_revision = StateRevision.from_dict(value._source_revision.to_dict())
        result._source_state_hash = value._source_state_hash
        result._allowed_writes = tuple(_access_copy(x) for x in value._allowed_writes)
        result._stores = {k: TypedStore.from_dict(v.to_dict()) for k, v in value._stores.items()}
        result._opaque = {k: OpaqueUnresolvedStore.from_dict(v.to_dict()) for k, v in value._opaque.items()}
        result._allocator = value._allocator.clone()
        result._writes = tuple(StagedWrite.from_dict(x.to_dict()) for x in value._writes)
        return result

    def detached_copy(self) -> "StagedDelta":
        return self._copy_from(self)

    def _require_write(self, target: str, extent: PresenceValue) -> None:
        requested = ObligationAccess(target, extent)
        if not any(requested == allowed for allowed in self._allowed_writes):
            raise TransactionError(f"write {target!r} with the requested exact extent is not certified")

    def stage_store_append(self, family: str, key: str, value: PresenceValue | Any) -> "StagedDelta":
        if family not in self._stores:
            raise TransactionError(f"undeclared typed store {family!r}")
        presence = _presence_copy(value)
        target = f"store:{family}:{_token(key, 'store key')}"
        self._require_write(target, presence)
        result = self.detached_copy()
        result._stores[family] = result._stores[family].append(key, presence)
        result._writes += (StagedWrite("STORE_APPEND", target, presence),)
        return result

    def stage_opaque_handle(self, family: str, handle: UnknownHandle) -> "StagedDelta":
        if family not in self._opaque or not isinstance(handle, UnknownHandle):
            raise TransactionError("opaque staging requires a declared family and UnknownHandle")
        payload = PresenceValue.present(handle.to_dict())
        target = f"opaque:{family}:{handle.blocker_id}"
        self._require_write(target, payload)
        result = self.detached_copy()
        result._opaque[family] = result._opaque[family].with_handle(UnknownHandle.from_dict(handle.to_dict()))
        result._writes += (StagedWrite("OPAQUE_HANDLE", target, handle.to_dict()),)
        return result

    def stage_allocation(self, family: IdentityFamily, namespace: str) -> tuple["StagedDelta", TypedIdentity]:
        resolved = require_declared_family(family)
        target = f"allocator:{_token(namespace, 'allocator namespace')}"
        extent = PresenceValue.present({"family": resolved.name})
        self._require_write(target, extent)
        result = self.detached_copy()
        identity = result._allocator.allocate(resolved, namespace)
        result._writes += (StagedWrite("ALLOCATE", target, identity.to_dict()),)
        return result, identity

    @property
    def writes(self) -> tuple[StagedWrite, ...]:
        return tuple(StagedWrite.from_dict(x.to_dict()) for x in self._writes)

    @property
    def stores(self) -> Mapping[str, TypedStore]:
        return {k: TypedStore.from_dict(v.to_dict()) for k, v in self._stores.items()}

    @property
    def opaque_stores(self) -> Mapping[str, OpaqueUnresolvedStore]:
        return {k: OpaqueUnresolvedStore.from_dict(v.to_dict()) for k, v in self._opaque.items()}

    @property
    def allocator(self) -> IdentityAllocator:
        return self._allocator.clone()

    @property
    def source_revision(self) -> StateRevision:
        return StateRevision.from_dict(self._source_revision.to_dict())

    @property
    def source_state_hash(self) -> str:
        return self._source_state_hash

    @property
    def certificate_identity(self) -> str:
        return self._certificate_identity

    @property
    def plan_identity(self) -> str:
        return self._plan_identity

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_staged_delta/1",
            "plan_identity": self._plan_identity,
            "certificate_identity": self._certificate_identity,
            "source_revision": self._source_revision.to_dict(),
            "source_state_hash": self._source_state_hash,
            "allowed_writes": [x.to_dict() for x in self._allowed_writes],
            "stores": [self._stores[k].to_dict() for k in self._stores],
            "opaque_stores": [self._opaque[k].to_dict() for k in self._opaque],
            "allocator": self._allocator.to_dict(),
            "writes": [x.to_dict() for x in self._writes],
        }
