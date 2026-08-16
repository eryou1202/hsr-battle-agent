# -*- coding: utf-8 -*-
"""Deterministic snapshot / serialization for sandbox kernel state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.hash import logical_battle_hash
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.state import BattleState
from hsr_battle_agent.battle_sandbox.trace import TRACE_SCHEMA, ExecutionTrace

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SandboxSnapshot:
    schema_version: int
    battle_state: dict[str, Any]
    rng_state: dict[str, Any]
    trace_events: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported snapshot schema_version: {self.schema_version!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "battle_state": self.battle_state,
            "rng_state": self.rng_state,
            "trace": list(self.trace_events),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SandboxSnapshot":
        if not isinstance(data, Mapping):
            raise TypeError("snapshot dict must be a mapping")
        if data.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported snapshot schema_version: {data.get('schema_version')!r}"
            )
        battle_state = data.get("battle_state")
        rng_state = data.get("rng_state")
        trace = data.get("trace", [])
        if not isinstance(battle_state, Mapping):
            raise TypeError("snapshot battle_state must be a mapping")
        if not isinstance(rng_state, Mapping):
            raise TypeError("snapshot rng_state must be a mapping")
        if not isinstance(trace, list):
            raise TypeError("snapshot trace must be a list")
        return cls(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            battle_state=dict(battle_state),
            rng_state=dict(rng_state),
            trace_events=tuple(dict(item) for item in trace),
        )

    def state_hash(self) -> str:
        """Hash logical state only (state + RNG); trace is observational."""
        return logical_battle_hash(self.battle_state, self.rng_state)

    def restore_context(self) -> ExecutionContext:
        return ExecutionContext(
            state=BattleState.from_dict(self.battle_state),
            rng=SandboxRng.from_dict(self.rng_state),
            trace=ExecutionTrace.from_dict(
                {"schema": TRACE_SCHEMA, "events": list(self.trace_events)}
            ),
        )


def capture_snapshot(context: ExecutionContext) -> SandboxSnapshot:
    if not isinstance(context, ExecutionContext):
        raise TypeError(
            f"context must be ExecutionContext, got {type(context).__name__}"
        )
    return SandboxSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        battle_state=context.state.to_dict(),
        rng_state=context.rng.to_dict(),
        trace_events=tuple(event.to_dict() for event in context.trace.events),
    )
