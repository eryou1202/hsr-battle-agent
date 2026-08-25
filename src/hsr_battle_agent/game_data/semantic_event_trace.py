"""Deterministic reference tracing for reconstructed BehaviorRecord events.

This is deliberately *not* the production battle runtime.  It makes the
KERNEL-EVENT-001 ordering contract executable and inspectable before a future
compiler binds individual operations to battle primitives.  In particular,
an opaque operation is surfaced as a hard diagnostic and never interpreted as
a semantic no-op.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


def canonical_event_name(value: str) -> str:
    """Use one comparison key while retaining the source event in trace data."""
    return value.strip().upper()


@dataclass(frozen=True)
class EventRegistration:
    event: str
    registration_id: str
    owner_instance_id: str
    behavior_id: str
    entrypoint_id: str
    priority: int
    registration_sequence: int
    operations: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class EventTraceStep:
    event_sequence: int
    event: str
    registration_id: str
    priority: int
    operation_id: str
    source_type: str | None
    kind: str
    semantic_status: str
    node_role: str
    trace_disposition: str
    commit_boundary: str


@dataclass(frozen=True)
class EventTraceResult:
    trace: tuple[EventTraceStep, ...]
    blocked_operation_ids: tuple[str, ...]
    queued_events: tuple[str, ...]

    @property
    def executable(self) -> bool:
        return not self.blocked_operation_ids

    def as_json(self) -> dict[str, Any]:
        return {
            "trace": [asdict(step) for step in self.trace],
            "blocked_operation_ids": list(self.blocked_operation_ids),
            "queued_events": list(self.queued_events),
            "executable": self.executable,
        }


class UnsupportedSemanticOperation(RuntimeError):
    """Raised when strict tracing encounters uncompiled or opaque behavior."""


class DeterministicEventTracer:
    """Reference implementation of the selected KERNEL-EVENT-001 model.

    Event registrations are stable by activation order.  A dispatch uses
    numeric priority ascending followed by registration sequence.  Children
    are emitted depth-first.  An event requested by an operation is appended
    to the FIFO queue immediately in emission order, but dispatch of queued
    events only begins after every matching registration of the currently
    dispatching event has completed.  This selected model prevents reentrant
    listener mutation of an in-progress dispatch; the native immediate-vs-
    deferred distinction remains an explicit ambiguity until a local packet
    resolves it.
    """

    def __init__(self) -> None:
        self._registrations: list[EventRegistration] = []
        self._next_sequence = 0

    @property
    def registrations(self) -> tuple[EventRegistration, ...]:
        return tuple(self._registrations)

    def register(
        self,
        *,
        event: str,
        owner_instance_id: str,
        behavior_id: str,
        entrypoint_id: str,
        operations: Sequence[Mapping[str, Any]],
        priority: int | None = None,
        registration_id: str | None = None,
    ) -> EventRegistration:
        event_key = canonical_event_name(event)
        sequence = self._next_sequence
        self._next_sequence += 1
        identifier = registration_id or f"{owner_instance_id}:{behavior_id}:{entrypoint_id}:{sequence}"
        if any(existing.registration_id == identifier for existing in self._registrations):
            raise ValueError(f"duplicate event registration: {identifier}")
        registration = EventRegistration(
            event=event_key,
            registration_id=identifier,
            owner_instance_id=owner_instance_id,
            behavior_id=behavior_id,
            entrypoint_id=entrypoint_id,
            priority=int(priority) if priority is not None else 0,
            registration_sequence=sequence,
            operations=tuple(operations),
        )
        self._registrations.append(registration)
        return registration

    def register_behavior_record(self, record: Mapping[str, Any], *, owner_instance_id: str) -> tuple[EventRegistration, ...]:
        """Register root entrypoints and Modifier callback entrypoints.

        Modifier callback dispatch keys come from ``callback_metadata.event``;
        the verbose callback path remains the stable entrypoint identifier.
        """
        behavior_id = str(record["behavior_id"])
        registered: list[EventRegistration] = []
        for entrypoint in record.get("entrypoints", []):
            if not isinstance(entrypoint, Mapping):
                continue
            metadata = entrypoint.get("callback_metadata")
            callback = metadata if isinstance(metadata, Mapping) else {}
            event = callback.get("event") or entrypoint.get("source_event") or entrypoint.get("event")
            if not isinstance(event, str) or not event:
                continue
            raw_priority = callback.get("priority")
            priority = raw_priority if isinstance(raw_priority, int) else 0
            registered.append(
                self.register(
                    event=event,
                    owner_instance_id=owner_instance_id,
                    behavior_id=behavior_id,
                    entrypoint_id=str(entrypoint.get("event", event)),
                    operations=tuple(item for item in entrypoint.get("operations", []) if isinstance(item, Mapping)),
                    priority=priority,
                )
            )
        return tuple(registered)

    def trace(
        self,
        emitted_events: Iterable[str],
        *,
        nested_events_after_operation: Mapping[str, Sequence[str]] | None = None,
        strict_semantics: bool = False,
    ) -> EventTraceResult:
        """Trace dispatch order without pretending to execute uncompiled ops.

        ``nested_events_after_operation`` is an explicit probe hook.  It
        models an already-compiled operation emitting an event; the emitted
        events enter the FIFO queue in emission order, but the queue is not
        drained until the current event's entire registration pass has
        completed.
        """
        pending = deque(canonical_event_name(event) for event in emitted_events)
        trace: list[EventTraceStep] = []
        blocked: list[str] = []
        queued: list[str] = list(pending)
        event_sequence = 0
        nested = nested_events_after_operation or {}

        while pending:
            event = pending.popleft()
            matching = sorted(
                (registration for registration in self._registrations if registration.event == event),
                key=lambda registration: (registration.priority, registration.registration_sequence),
            )
            emitted_after_current_event: list[str] = []
            for registration in matching:
                for operation in registration.operations:
                    self._trace_operation(
                        operation,
                        event=event,
                        event_sequence=event_sequence,
                        registration=registration,
                        trace=trace,
                        blocked=blocked,
                        nested=nested,
                        emitted_after_current_event=emitted_after_current_event,
                        strict_semantics=strict_semantics,
                    )
            for nested_event in emitted_after_current_event:
                pending.append(nested_event)
                queued.append(nested_event)
            event_sequence += 1
        return EventTraceResult(tuple(trace), tuple(blocked), tuple(queued))

    def _trace_operation(
        self,
        operation: Mapping[str, Any],
        *,
        event: str,
        event_sequence: int,
        registration: EventRegistration,
        trace: list[EventTraceStep],
        blocked: list[str],
        nested: Mapping[str, Sequence[str]],
        emitted_after_current_event: list[str],
        strict_semantics: bool,
    ) -> None:
        operation_id = str(operation.get("operation_id", "UNKNOWN_OPERATION"))
        status = str(operation.get("semantic_status", "OPAQUE"))
        risk = str(operation.get("gating_risk", "UNKNOWN"))
        kind = str(operation.get("kind", "OPAQUE"))
        behavior_affecting = status == "OPAQUE" or (status == "PRESENTATION" and risk != "NONE")
        requires_packet = status == "REQUIRES_PACKET"
        if behavior_affecting:
            disposition = "OPAQUE_BLOCKS_EXECUTION"
            blocked.append(operation_id)
        elif requires_packet:
            disposition = "REQUIRES_PACKET_UNCOMPILED"
            blocked.append(operation_id)
        elif status == "PRESENTATION":
            disposition = "PRESENTATION_IGNORED_HEADLESS"
        else:
            disposition = "ORDER_ONLY_MODELLED"
        trace.append(
            EventTraceStep(
                event_sequence=event_sequence,
                event=event,
                registration_id=registration.registration_id,
                priority=registration.priority,
                operation_id=operation_id,
                source_type=operation.get("source_type") if isinstance(operation.get("source_type"), str) else None,
                kind=kind,
                semantic_status=status,
                node_role=str(operation.get("node_role", "OPERATION")),
                trace_disposition=disposition,
                commit_boundary="PRIMITIVE_OWNED_IMMEDIATE" if risk == "KNOWN_STATE_COMMIT" else "NO_COMMIT_CLAIM",
            )
        )
        if strict_semantics and (behavior_affecting or requires_packet):
            raise UnsupportedSemanticOperation(f"{operation_id}: {disposition}")
        for group in operation.get("children", []):
            if not isinstance(group, Mapping):
                continue
            for child in group.get("operations", []):
                if isinstance(child, Mapping):
                    self._trace_operation(
                        child,
                        event=event,
                        event_sequence=event_sequence,
                        registration=registration,
                        trace=trace,
                        blocked=blocked,
                        nested=nested,
                        emitted_after_current_event=emitted_after_current_event,
                        strict_semantics=strict_semantics,
                    )
        for nested_event in nested.get(operation_id, ()):
            emitted_after_current_event.append(canonical_event_name(nested_event))

