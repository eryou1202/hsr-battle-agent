# -*- coding: utf-8 -*-
"""Private ordered trace, event and queue staging for G01-008."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hsr_battle_agent.battle_sandbox.state import F01StateEnvelope
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.preflight import ObligationAccess
from hsr_battle_agent.battle_sandbox.transaction import TransactionError, TransactionPlan

__all__ = ["StagedRecord", "StagedTrace"]


@dataclass(frozen=True, init=False, eq=False)
class StagedRecord:
    _channel: str
    _kind: str
    _payload: F01StateEnvelope

    def __init__(self, channel: str, kind: str, payload: Any) -> None:
        if channel not in {"TRACE", "EVENT", "QUEUE"}:
            raise TransactionError(f"unknown staged record channel {channel!r}")
        if not isinstance(kind, str) or not kind or kind != kind.strip():
            raise TransactionError("staged record kind must be non-empty and trimmed")
        object.__setattr__(self, "_channel", channel)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_payload", F01StateEnvelope(payload))

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def payload(self) -> Any:
        return self._payload.value

    def to_dict(self) -> dict[str, Any]:
        return {"channel": self._channel, "kind": self._kind, "payload": self._payload.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StagedRecord":
        return cls(data["channel"], data["kind"], F01StateEnvelope.from_dict(data["payload"]).value)


class StagedTrace:
    """Functional private buffer.  It neither invokes nor stores callbacks."""

    __slots__ = (
        "_plan_identity", "_certificate_identity", "_source_state_hash",
        "_allowed_writes", "_records", "_discarded",
    )

    def __init__(self, plan: TransactionPlan, state: TerraBattleState) -> None:
        if not isinstance(plan, TransactionPlan) or not isinstance(state, TerraBattleState):
            raise TransactionError("StagedTrace requires a plan and TerraBattleState")
        if state.revision.to_dict() != plan.source_revision.to_dict():
            raise TransactionError("staged trace source revision is stale")
        actual_hash = semantic_hash_v2(
            TerraSnapshotV2(
                state=state, policy_identity=plan.certificate.policy_identity
            )
        )
        if actual_hash != plan.source_state_hash:
            raise TransactionError("staged trace source state does not match the plan")
        self._plan_identity = plan.certificate.plan_identity
        self._certificate_identity = plan.certificate_identity
        self._source_state_hash = plan.source_state_hash
        self._allowed_writes = tuple(
            ObligationAccess.from_dict(item.to_dict())
            for item in plan.allowed_writes
        )
        self._records: tuple[StagedRecord, ...] = ()
        self._discarded = False

    @classmethod
    def _copy(cls, value: "StagedTrace") -> "StagedTrace":
        result = object.__new__(cls)
        result._plan_identity = value._plan_identity
        result._certificate_identity = value._certificate_identity
        result._source_state_hash = value._source_state_hash
        result._allowed_writes = tuple(
            ObligationAccess.from_dict(item.to_dict())
            for item in value._allowed_writes
        )
        result._records = tuple(StagedRecord.from_dict(x.to_dict()) for x in value._records)
        result._discarded = value._discarded
        return result

    def detached_copy(self) -> "StagedTrace":
        return self._copy(self)

    def _append(self, channel: str, kind: str, payload: Any) -> "StagedTrace":
        if self._discarded:
            raise TransactionError("discarded staged output cannot accept records")
        target = f"{channel.lower()}:{kind}"
        extent = PresenceValue.null() if payload is None else PresenceValue.present(payload)
        requested = ObligationAccess(target, extent)
        if not any(requested == allowed for allowed in self._allowed_writes):
            raise TransactionError(
                f"staged output {target!r} with the requested exact extent is not certified"
            )
        result = self.detached_copy()
        result._records += (StagedRecord(channel, kind, payload),)
        return result

    def stage_trace(self, kind: str, payload: Any) -> "StagedTrace":
        return self._append("TRACE", kind, payload)

    def stage_event(self, kind: str, payload: Any) -> "StagedTrace":
        return self._append("EVENT", kind, payload)

    def stage_queue_write(self, kind: str, payload: Any) -> "StagedTrace":
        return self._append("QUEUE", kind, payload)

    def discard(self) -> "StagedTrace":
        result = self.detached_copy()
        result._records = ()
        result._discarded = True
        return result

    @property
    def records(self) -> tuple[StagedRecord, ...]:
        return tuple(StagedRecord.from_dict(x.to_dict()) for x in self._records)

    @property
    def trace(self) -> tuple[StagedRecord, ...]:
        return tuple(x for x in self.records if x.channel == "TRACE")

    @property
    def events(self) -> tuple[StagedRecord, ...]:
        return tuple(x for x in self.records if x.channel == "EVENT")

    @property
    def queue_writes(self) -> tuple[StagedRecord, ...]:
        return tuple(x for x in self.records if x.channel == "QUEUE")

    @property
    def discarded(self) -> bool:
        return self._discarded

    @property
    def plan_identity(self) -> str:
        return self._plan_identity

    @property
    def certificate_identity(self) -> str:
        return self._certificate_identity

    @property
    def source_state_hash(self) -> str:
        return self._source_state_hash

    @property
    def allowed_writes(self) -> tuple[ObligationAccess, ...]:
        return tuple(
            ObligationAccess.from_dict(item.to_dict())
            for item in self._allowed_writes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_staged_trace/1",
            "plan_identity": self._plan_identity,
            "certificate_identity": self._certificate_identity,
            "source_state_hash": self._source_state_hash,
            "allowed_writes": [item.to_dict() for item in self._allowed_writes],
            "records": [x.to_dict() for x in self._records],
            "discarded": self._discarded,
        }
