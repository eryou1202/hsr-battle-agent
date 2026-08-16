# -*- coding: utf-8 -*-
"""Deterministic snapshot / serialization for sandbox kernel state.

Defensive-copy boundary:

* ``capture_snapshot`` never keeps references into the context;
* ``SandboxSnapshot.__init__`` deep-copies every input container;
* ``from_dict`` deep-copies the input mapping before any use;
* ``to_dict`` and every public state property return fresh deep copies.

Mutating a caller-owned dict/list or a returned view therefore can never
change a snapshot's logical content.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.hash import logical_battle_hash
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.state import (
    BattleState,
    deep_copy_json_value,
)
from hsr_battle_agent.battle_sandbox.trace import TRACE_SCHEMA, ExecutionTrace

SNAPSHOT_SCHEMA_VERSION = 1


class SandboxSnapshot:
    """Immutable logical snapshot with private, defensively copied storage."""

    __slots__ = (
        "_schema_version",
        "_battle_state",
        "_rng_state",
        "_trace_events",
    )

    def __init__(
        self,
        schema_version: int,
        battle_state: Mapping[str, Any],
        rng_state: Mapping[str, Any],
        trace_events: tuple[Mapping[str, Any], ...] = (),
    ) -> None:
        if schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported snapshot schema_version: {schema_version!r}"
            )
        if not isinstance(battle_state, Mapping):
            raise TypeError("snapshot battle_state must be a mapping")
        if not isinstance(rng_state, Mapping):
            raise TypeError("snapshot rng_state must be a mapping")
        if not isinstance(trace_events, tuple):
            raise TypeError("snapshot trace_events must be a tuple of mappings")
        for index, event in enumerate(trace_events):
            if not isinstance(event, Mapping):
                raise TypeError(
                    f"snapshot trace_events[{index}] must be a mapping, "
                    f"got {type(event).__name__}"
                )

        self._schema_version = SNAPSHOT_SCHEMA_VERSION
        self._battle_state = deep_copy_json_value(dict(battle_state))
        self._rng_state = deep_copy_json_value(dict(rng_state))
        self._trace_events = tuple(
            deep_copy_json_value(dict(event)) for event in trace_events
        )

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def battle_state(self) -> dict[str, Any]:
        return deep_copy_json_value(self._battle_state)

    @property
    def rng_state(self) -> dict[str, Any]:
        return deep_copy_json_value(self._rng_state)

    @property
    def trace_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(deep_copy_json_value(event) for event in self._trace_events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self._schema_version,
            "battle_state": deep_copy_json_value(self._battle_state),
            "rng_state": deep_copy_json_value(self._rng_state),
            "trace": [
                deep_copy_json_value(event) for event in self._trace_events
            ],
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
        for index, event in enumerate(trace):
            if not isinstance(event, Mapping):
                raise TypeError(
                    f"snapshot trace[{index}] must be a mapping, "
                    f"got {type(event).__name__}"
                )
        return cls(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            battle_state=battle_state,
            rng_state=rng_state,
            trace_events=tuple(trace),
        )

    def state_hash(self) -> str:
        """Hash logical state only (state + RNG); trace is observational."""
        return logical_battle_hash(self._battle_state, self._rng_state)

    def restore_context(self) -> ExecutionContext:
        return ExecutionContext(
            state=BattleState.from_dict(
                deep_copy_json_value(self._battle_state)
            ),
            rng=SandboxRng.from_dict(
                deep_copy_json_value(self._rng_state)
            ),
            trace=ExecutionTrace.from_dict(
                {
                    "schema": TRACE_SCHEMA,
                    "events": [
                        deep_copy_json_value(event)
                        for event in self._trace_events
                    ],
                }
            ),
        )

    def __repr__(self) -> str:
        return (
            f"SandboxSnapshot(schema_version={self._schema_version}, "
            f"trace_events={len(self._trace_events)})"
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
