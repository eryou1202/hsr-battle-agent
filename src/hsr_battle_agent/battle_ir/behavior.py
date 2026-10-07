"""Canonical Behavior IR v1; independent of frozen primitive/admission contracts.

Nodes own canonical JSON payloads, rather than mutable caller-owned containers.
Semantic children are nodes too, so authority is never lost during round trips.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import ClassVar


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


EVIDENCE_LEVELS = frozenset({"NATIVE_EVIDENCED", "REAL_CONTENT_RECONSTRUCTED",
    "STATIC_DATA", "REFERENCE_MODEL", "SANDBOX_EXTENSION", "RUNTIME_ORACLE_PENDING"})
SEMANTIC_STATUSES = frozenset({"NATIVE_EVIDENCED", "REAL_CONTENT_RECONSTRUCTED",
    "REFERENCE_MODEL", "CONDITIONAL_REFERENCE", "STRUCTURE_ONLY",
    "RUNTIME_ORACLE_PENDING", "UNSUPPORTED"})


@dataclass(frozen=True)
class Authority:
    evidence_level: str
    source_version: str
    source_artifact: str
    source_sha256: str
    native_method_refs: tuple[str, ...] = ()
    semantic_status: str = "STRUCTURE_ONLY"
    oracle_status: str = "RUNTIME_ORACLE_PENDING"
    source_pointer: str = ""
    ledger_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"unknown evidence level: {self.evidence_level}")
        if self.semantic_status not in SEMANTIC_STATUSES:
            raise ValueError(f"unknown semantic status: {self.semantic_status}")
        object.__setattr__(self, "native_method_refs", tuple(self.native_method_refs))
        object.__setattr__(self, "ledger_refs", tuple(self.ledger_refs))

    def to_dict(self) -> dict:
        return json.loads(canonical_json(asdict(self)))


def encode(value: object) -> object:
    if isinstance(value, IRNode):
        return value.to_dict()
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise TypeError("IR maps require string keys")
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    return value


def decode(value: object) -> object:
    if isinstance(value, dict):
        if set(value) == {"kind", "node_id", "op", "authority", "payload"}:
            return IRNode.from_dict(value)
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


@dataclass(frozen=True, init=False)
class IRNode:
    node_id: str
    op: str
    authority: Authority
    _payload_json: str
    kind: ClassVar[str] = "IRNode"

    def __init__(self, node_id: str, op: str, authority: Authority, payload: dict | None = None):
        if not node_id or not op or not isinstance(authority, Authority):
            raise ValueError("node identity, operation and authority are required")
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("IR payload must be a mapping")
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "op", op)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "_payload_json", canonical_json(encode(payload or {})))

    @property
    def payload(self) -> dict:
        return decode(json.loads(self._payload_json))

    def to_dict(self) -> dict:
        return {"kind": self.kind, "node_id": self.node_id, "op": self.op,
                "authority": self.authority.to_dict(), "payload": json.loads(self._payload_json)}

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def stable_hash(self) -> str:
        return stable_hash(self.to_dict())

    @classmethod
    def from_dict(cls, document: dict) -> IRNode:
        if set(document) != {"kind", "node_id", "op", "authority", "payload"}:
            raise ValueError("invalid IR node envelope")
        node_type = NODE_TYPES.get(document["kind"])
        if node_type is None:
            raise ValueError("unknown IR node kind")
        return node_type(document["node_id"], document["op"],
                         Authority(**document["authority"]), decode(document["payload"]))


class AbilityIR(IRNode):
    kind = "AbilityIR"


class TaskIR(IRNode):
    kind = "TaskIR"


class TaskSequenceIR(IRNode):
    kind = "TaskSequenceIR"


class PredicateIR(IRNode):
    kind = "PredicateIR"


class TargetSelectorIR(IRNode):
    kind = "TargetSelectorIR"


class ExpressionIR(IRNode):
    kind = "ExpressionIR"


class PropertyMutationIR(IRNode):
    kind = "PropertyMutationIR"


class ResourceMutationIR(IRNode):
    kind = "ResourceMutationIR"


class ModifierApplyIR(IRNode):
    kind = "ModifierApplyIR"


class ModifierRemoveIR(IRNode):
    kind = "ModifierRemoveIR"


class EventDispatchIR(IRNode):
    kind = "EventDispatchIR"


class SchedulerBarrierIR(IRNode):
    kind = "SchedulerBarrierIR"


class RandomChoiceIR(IRNode):
    kind = "RandomChoiceIR"


class CompletionIR(IRNode):
    kind = "CompletionIR"


class UnsupportedSemanticIR(IRNode):
    kind = "UnsupportedSemanticIR"


NODE_TYPES = {c.kind: c for c in (AbilityIR, TaskIR, TaskSequenceIR, PredicateIR,
    TargetSelectorIR, ExpressionIR, PropertyMutationIR, ResourceMutationIR,
    ModifierApplyIR, ModifierRemoveIR, EventDispatchIR, SchedulerBarrierIR,
    RandomChoiceIR, CompletionIR, UnsupportedSemanticIR)}


def walk_nodes(value: object):
    if isinstance(value, IRNode):
        yield value
        yield from walk_nodes(value.payload)
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from walk_nodes(value[key])
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk_nodes(item)
