# -*- coding: utf-8 -*-
"""Machine-readable, deterministic execution trace.

Kernel 01 supports exactly two event kinds:

* ``PrimitiveStarted``
* ``PrimitiveFinished``

Events carry summaries only (primitive id, input tags, result value).  They
must never dump whole object graphs.  Future event kinds (ValueResolved,
PredicateEvaluated, TargetSelected, ModifierApplied, DamageCalculated,
EventEmitted) are explicitly deferred until their semantics are recovered.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from hsr_battle_agent.battle_ir.actions import TaskExecutionState, TaskState
from hsr_battle_agent.battle_ir.modifiers import (
    ModifierConfigRef,
    ModifierContainer,
    ModifierLifecycleResult,
    ModifierMatchKey,
    ModifierRef,
    ModifierState,
    ModifierTaskApplication,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_ir.values import EvaluatorSpec

TRACE_SCHEMA = "battle_sandbox_trace/1"
TRACE_JSON_RESULT_TYPES = (bool, int, float, str, type(None))


class TraceSink(Protocol):
    def started(
        self,
        primitive_id: str,
        input_tags: tuple[str, ...],
        semantic_provenance_ref: str | None,
    ) -> "PrimitiveStarted": ...

    def finished(
        self,
        started: "PrimitiveStarted",
        result: Any,
    ) -> "PrimitiveFinished": ...


@dataclass(frozen=True)
class PrimitiveStarted:
    event: str
    event_id: int
    primitive_id: str
    input_tags: tuple[str, ...]
    semantic_provenance_ref: str | None = None

    @classmethod
    def create(
        cls,
        event_id: int,
        primitive_id: str,
        input_tags: tuple[str, ...],
        semantic_provenance_ref: str | None,
    ) -> "PrimitiveStarted":
        return cls(
            event="PrimitiveStarted",
            event_id=event_id,
            primitive_id=primitive_id,
            input_tags=input_tags,
            semantic_provenance_ref=semantic_provenance_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "event_id": self.event_id,
            "primitive_id": self.primitive_id,
            "input_tags": list(self.input_tags),
            "semantic_provenance_ref": self.semantic_provenance_ref,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PrimitiveStarted":
        return cls(
            event=str(data["event"]),
            event_id=int(data["event_id"]),
            primitive_id=str(data["primitive_id"]),
            input_tags=tuple(str(item) for item in data["input_tags"]),
            semantic_provenance_ref=(
                None if data.get("semantic_provenance_ref") is None
                else str(data["semantic_provenance_ref"])
            ),
        )


@dataclass(frozen=True)
class PrimitiveFinished:
    event: str
    event_id: int
    primitive_event_id: int
    primitive_id: str
    result: Any
    result_type: str
    semantic_provenance_ref: str | None = None

    @classmethod
    def create(
        cls,
        event_id: int,
        started: PrimitiveStarted,
        result: Any,
    ) -> "PrimitiveFinished":
        summary = _trace_result_summary(result)
        return cls(
            event="PrimitiveFinished",
            event_id=event_id,
            primitive_event_id=started.event_id,
            primitive_id=started.primitive_id,
            result=summary,
            result_type=type(result).__name__,
            semantic_provenance_ref=started.semantic_provenance_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "event_id": self.event_id,
            "primitive_event_id": self.primitive_event_id,
            "primitive_id": self.primitive_id,
            "result": self.result,
            "result_type": self.result_type,
            "semantic_provenance_ref": self.semantic_provenance_ref,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PrimitiveFinished":
        result = data["result"]
        _validate_trace_result(result)
        return cls(
            event=str(data["event"]),
            event_id=int(data["event_id"]),
            primitive_event_id=int(data["primitive_event_id"]),
            primitive_id=str(data["primitive_id"]),
            result=result,
            result_type=str(data["result_type"]),
            semantic_provenance_ref=(
                None if data.get("semantic_provenance_ref") is None
                else str(data["semantic_provenance_ref"])
            ),
        )


def _validate_trace_result(value: Any) -> None:
    if not isinstance(value, TRACE_JSON_RESULT_TYPES):
        raise TypeError(
            "trace results must be JSON-safe scalar (None/bool/int/float/str), "
            f"got {type(value).__name__}; never dump whole objects into traces"
        )


def _trace_result_summary(value: Any) -> Any:
    """Return the trace-stored result.

    Scalar primitives keep their value.  ``EvaluatorSpec``, ``EntityRef`` and
    ``TargetSet`` are non-scalar primitive results; the trace stores
    deterministic compact summaries and never dumps object graphs.
    ``PrimitiveResult`` still carries the real object for callers.
    """
    if isinstance(value, EvaluatorSpec):
        return f"EvaluatorSpec(fixpoint_raw=0x{value.fixpoint_raw & 0xFFFFFFFFFFFFFFFF:X})"
    if isinstance(value, EntityRef):
        return value.trace_summary()
    if isinstance(value, TargetSet):
        return value.trace_summary()
    if isinstance(value, TaskState):
        return value.trace_summary()
    if isinstance(value, TaskExecutionState):
        return value.trace_summary()
    if isinstance(value, (ModifierConfigRef, ModifierRef, ModifierState)):
        return value.trace_summary()
    if isinstance(value, ModifierContainer):
        return value.trace_summary()
    if isinstance(value, ModifierTaskApplication):
        return value.trace_summary()
    if isinstance(value, (ModifierMatchKey, ModifierLifecycleResult)):
        return value.trace_summary()
    _validate_trace_result(value)
    return value


class ExecutionTrace:
    """Deterministic event list implementing ``TraceSink``."""

    def __init__(self, events: list[PrimitiveStarted | PrimitiveFinished] | None = None) -> None:
        self._events: list[PrimitiveStarted | PrimitiveFinished] = list(events or ())
        self._next_event_id = max(
            (event.event_id for event in self._events),
            default=0,
        ) + 1

    @property
    def events(self) -> tuple[PrimitiveStarted | PrimitiveFinished, ...]:
        return tuple(self._events)

    def started(
        self,
        primitive_id: str,
        input_tags: tuple[str, ...],
        semantic_provenance_ref: str | None,
    ) -> PrimitiveStarted:
        event = PrimitiveStarted.create(
            event_id=self._next_event_id,
            primitive_id=primitive_id,
            input_tags=tuple(input_tags),
            semantic_provenance_ref=semantic_provenance_ref,
        )
        self._next_event_id += 1
        self._events.append(event)
        return event

    def finished(self, started: PrimitiveStarted, result: Any) -> PrimitiveFinished:
        event = PrimitiveFinished.create(
            event_id=self._next_event_id,
            started=started,
            result=result,
        )
        self._next_event_id += 1
        self._events.append(event)
        return event

    def record(self, event: PrimitiveStarted | PrimitiveFinished) -> None:
        """Append an already-built event (advanced/foreign sinks only)."""
        if not isinstance(event, (PrimitiveStarted, PrimitiveFinished)):
            raise TypeError(
                "trace event must be PrimitiveStarted or PrimitiveFinished, "
                f"got {type(event).__name__}"
            )
        self._events.append(event)
        self._next_event_id = max(self._next_event_id, event.event_id + 1)

    def clone(self) -> "ExecutionTrace":
        return ExecutionTrace(events=list(self._events))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TRACE_SCHEMA,
            "events": [event.to_dict() for event in self._events],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionTrace":
        if not isinstance(data, Mapping):
            raise TypeError("trace dict must be a mapping")
        if data.get("schema") != TRACE_SCHEMA:
            raise ValueError(f"unsupported trace schema: {data.get('schema')!r}")
        raw_events = data.get("events")
        if not isinstance(raw_events, list):
            raise TypeError("trace events must be a list")
        events: list[PrimitiveStarted | PrimitiveFinished] = []
        for raw in raw_events:
            if not isinstance(raw, Mapping):
                raise TypeError("trace event must be a mapping")
            event_name = raw.get("event")
            if event_name == "PrimitiveStarted":
                events.append(PrimitiveStarted.from_dict(raw))
            elif event_name == "PrimitiveFinished":
                events.append(PrimitiveFinished.from_dict(raw))
            else:
                raise ValueError(f"unknown trace event: {event_name!r}")
        return cls(events=events)

    def __len__(self) -> int:
        return len(self._events)
