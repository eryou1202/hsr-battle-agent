"""Deterministic reference semantics for scheduler/action boundary operations.

This is the SCHEDULER-001 semantics companion.  It is a reconstruction
reference, not the production battle runtime.  It anchors:

- TaskState raw values (E4 action_execution_bridge_06),
- action/damage completion markers,
- IncludeTaskListTemplate expansion (corpus template_definitions),
- fixed LoopExecuteTaskListWithInterval,
- ConditionalLoopExecuteTaskListWithInterval with an explicit predicate hook,
- delay set/add/reset transitions,
- inserted-action configuration records.

Turn consumption, AV recomputation and priority-queue arbitration between
candidate actions remain in the future global scheduler packet.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import IntEnum
from typing import Any, Callable, Iterable, Mapping, Sequence

from .dynamic_value_reference import DynamicValueSemanticError, DynamicValueSpec, value_spec_from_payload


class SchedulerSemanticError(DynamicValueSemanticError):
    """A scheduler operation cannot be reconstructed safely."""


class TaskState(IntEnum):
    READY = 0x7777
    EXECUTING = 0x8888
    SUCCESS = 0x9999
    FAIL = 0xAAAA


PredicateEvaluator = Callable[[Mapping[str, Any]], bool]


@dataclass(frozen=True)
class TaskStep:
    task_id: str
    state: TaskState
    owner_id: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "state": self.state.name, "owner_id": self.owner_id}


@dataclass(frozen=True)
class ActionDelayState:
    normalized_value: Decimal
    skip_target_turn: bool = False

    def clamp(self) -> "ActionDelayState":
        if self.normalized_value < 0:
            return replace(self, normalized_value=Decimal("0"))
        return self

    def set(self, value: Decimal, *, skip_target_turn: bool = False) -> "ActionDelayState":
        return ActionDelayState(normalized_value=value, skip_target_turn=skip_target_turn)

    def add(self, delta: Decimal, *, skip_target_turn: bool = False) -> "ActionDelayState":
        return ActionDelayState(
            normalized_value=self.normalized_value + delta,
            skip_target_turn=skip_target_turn or self.skip_target_turn,
        ).clamp()


@dataclass(frozen=True)
class OrdinaryTurnTimeline:
    """Reference state for the closed ordinary property-38 scheduler scope.

    This is deliberately distinct from ``ActionDelayState``.  The latter is a
    behavior-level delay operation holder, while this timeline represents the
    standard-MVP remaining action-delay/action-list model recovered as
    property 38.  Inserted actions, Advance/Delay composition, special turns,
    and priority arbitration are not represented here.
    """

    action_order: tuple[str, ...]
    remaining_delays: Mapping[str, Decimal]
    current_actor_id: str | None = None
    elapsed_action_delay: Decimal = Decimal("0")
    turn_index: int = 0

    def __post_init__(self) -> None:
        if not self.action_order or len(set(self.action_order)) != len(self.action_order):
            raise SchedulerSemanticError("ordinary action order must contain unique entities")
        if set(self.remaining_delays) != set(self.action_order):
            raise SchedulerSemanticError("ordinary remaining-delay keys must exactly match action order")
        if any(value < 0 for value in self.remaining_delays.values()):
            raise SchedulerSemanticError("ordinary remaining delays must be non-negative")
        if self.current_actor_id is not None and self.current_actor_id not in self.remaining_delays:
            raise SchedulerSemanticError("ordinary current actor is absent from action order")
        if self.elapsed_action_delay < 0 or self.turn_index < 0:
            raise SchedulerSemanticError("ordinary timeline counters must be non-negative")

    def as_json(self) -> dict[str, Any]:
        return {
            "action_order": list(self.action_order),
            "remaining_delays": {key: str(value) for key, value in sorted(self.remaining_delays.items())},
            "current_actor_id": self.current_actor_id,
            "elapsed_action_delay": str(self.elapsed_action_delay),
            "turn_index": self.turn_index,
        }


@dataclass(frozen=True)
class OrdinaryTurnTransition:
    """One ordinary candidate-selection or post-action advance result."""

    timeline: OrdinaryTurnTimeline
    selected_actor_id: str
    selected_delay: Decimal
    ordered_candidates_before_advance: tuple[str, ...]
    recharged_actor_id: str | None = None
    recharged_delay: Decimal | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "selected_actor_id": self.selected_actor_id,
            "selected_delay": str(self.selected_delay),
            "ordered_candidates_before_advance": list(self.ordered_candidates_before_advance),
            "recharged_actor_id": self.recharged_actor_id,
            "recharged_delay": None if self.recharged_delay is None else str(self.recharged_delay),
            "timeline": self.timeline.as_json(),
        }


def _ordinary_candidates(timeline: OrdinaryTurnTimeline, eligible_ids: Iterable[str]) -> tuple[str, ...]:
    eligible = set(eligible_ids)
    ordered = tuple(entity_id for entity_id in timeline.action_order if entity_id in eligible)
    if not ordered:
        raise SchedulerSemanticError("ordinary scheduler requires at least one eligible actor")
    if len(ordered) != len(eligible):
        missing = sorted(eligible - set(ordered))
        raise SchedulerSemanticError(f"ordinary scheduler eligible actor is absent from action order: {missing!r}")
    positions = {entity_id: index for index, entity_id in enumerate(ordered)}
    return tuple(sorted(ordered, key=lambda entity_id: (timeline.remaining_delays[entity_id], positions[entity_id])))


def _advance_ordinary_candidates(
    timeline: OrdinaryTurnTimeline,
    eligible_ids: Iterable[str],
    *,
    recharged_actor_id: str | None = None,
    recharged_delay: Decimal | None = None,
) -> OrdinaryTurnTransition:
    candidates = _ordinary_candidates(timeline, eligible_ids)
    selected_actor_id = candidates[0]
    selected_delay = timeline.remaining_delays[selected_actor_id]
    remaining = {
        entity_id: max(Decimal("0"), timeline.remaining_delays[entity_id] - selected_delay)
        for entity_id in candidates
    }
    advanced = OrdinaryTurnTimeline(
        action_order=candidates,
        remaining_delays=remaining,
        current_actor_id=selected_actor_id,
        elapsed_action_delay=timeline.elapsed_action_delay + selected_delay,
        turn_index=timeline.turn_index + 1,
    )
    return OrdinaryTurnTransition(
        timeline=advanced,
        selected_actor_id=selected_actor_id,
        selected_delay=selected_delay,
        ordered_candidates_before_advance=candidates,
        recharged_actor_id=recharged_actor_id,
        recharged_delay=recharged_delay,
    )


def select_initial_ordinary_actor(
    timeline: OrdinaryTurnTimeline,
    eligible_ids: Iterable[str],
) -> OrdinaryTurnTransition:
    """Select and advance to one ordinary actor without a prior completion."""
    if timeline.current_actor_id is not None:
        raise SchedulerSemanticError("ordinary timeline already has an active actor")
    return _advance_ordinary_candidates(timeline, eligible_ids)


def complete_ordinary_action(
    timeline: OrdinaryTurnTimeline,
    *,
    actor_id: str,
    eligible_ids: Iterable[str],
    speeds: Mapping[str, Decimal],
    action_delay_distance: Decimal = Decimal("10000"),
) -> OrdinaryTurnTransition:
    """Recharge one completed ordinary actor, then select the next actor.

    This is the bounded DYN-MVP-AV-001 model: the completing actor receives
    ``ActionDelayDistance / speed``; eligible ordinary actors are stably
    ordered by remaining delay and prior action-list position; the selected
    delay advances every candidate.  Callers own eligibility filtering and
    must not pass special/inserted action candidates into this scope.
    """
    if timeline.current_actor_id != actor_id:
        raise SchedulerSemanticError("ordinary completion actor must match the active ordinary actor")
    eligible = tuple(eligible_ids)
    if actor_id not in eligible:
        raise SchedulerSemanticError("ordinary completion actor is not eligible")
    if action_delay_distance <= 0:
        raise SchedulerSemanticError("ordinary action-delay distance must be positive")
    speed = speeds.get(actor_id)
    if speed is None or speed <= 0:
        raise SchedulerSemanticError("ordinary completion actor requires positive explicit speed")
    recharge = action_delay_distance / speed
    delays = dict(timeline.remaining_delays)
    delays[actor_id] = recharge
    recharged = OrdinaryTurnTimeline(
        action_order=timeline.action_order,
        remaining_delays=delays,
        current_actor_id=None,
        elapsed_action_delay=timeline.elapsed_action_delay,
        turn_index=timeline.turn_index,
    )
    return _advance_ordinary_candidates(
        recharged,
        eligible,
        recharged_actor_id=actor_id,
        recharged_delay=recharge,
    )


@dataclass(frozen=True)
class LoopSpec:
    max_loop_count: int
    body_operations: tuple[Mapping[str, Any], ...]
    raw_payload: Mapping[str, Any]

    @staticmethod
    def from_operation(operation: Mapping[str, Any]) -> "LoopSpec":
        arguments = operation.get("arguments") if isinstance(operation.get("arguments"), Mapping) else {}
        spec = value_spec_from_payload(arguments.get("MaxLoopCount"))
        if spec.is_dynamic:
            raise SchedulerSemanticError("LoopExecuteTaskListWithInterval with a dynamic MaxLoopCount is outside SCHEDULER-001")
        if spec.fixed_value is None or spec.fixed_value < 0 or spec.fixed_value != spec.fixed_value.to_integral_value():
            raise SchedulerSemanticError(f"invalid loop count {spec.fixed_value}")
        body = []
        for group in operation.get("children", []):
            if isinstance(group, Mapping) and group.get("field_path") == "TaskList":
                body.extend(item for item in group.get("operations", []) if isinstance(item, Mapping))
        return LoopSpec(int(spec.fixed_value), tuple(body), arguments)

    def expand(self) -> tuple[Mapping[str, Any], ...]:
        return self.body_operations * self.max_loop_count


@dataclass(frozen=True)
class InsertedActionSpec:
    ability_name: str | None
    ability_target: Mapping[str, Any] | None
    auto_cast: bool
    auto_cast_target: Mapping[str, Any] | None
    insert_priority: str | None
    show_in_action_bar: bool
    can_run_on_unselectable_target: bool
    can_run_after_fight_finish: bool
    custom_tags: tuple[str, ...]
    raw_payload: Mapping[str, Any]

    @staticmethod
    def _text(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, Mapping) and isinstance(value.get("Value"), str):
            return str(value["Value"])
        return None

    @staticmethod
    def from_operation(operation: Mapping[str, Any]) -> "InsertedActionSpec":
        arguments = operation.get("arguments") if isinstance(operation.get("arguments"), Mapping) else {}
        tags = arguments.get("CustomTags", [])
        if isinstance(tags, list):
            tag_texts = tuple(str(tag.get("Value")) for tag in tags if isinstance(tag, Mapping) and isinstance(tag.get("Value"), str))
        else:
            tag_texts = ()
        return InsertedActionSpec(
            ability_name=InsertedActionSpec._text(arguments.get("AbilityName")),
            ability_target=arguments.get("AbilityTarget") if isinstance(arguments.get("AbilityTarget"), Mapping) else None,
            auto_cast=bool(arguments.get("AutoCast", False)),
            auto_cast_target=arguments.get("AutoCastTargetType") if isinstance(arguments.get("AutoCastTargetType"), Mapping) else None,
            insert_priority=InsertedActionSpec._text(arguments.get("InsertAbilityPriority") or arguments.get("InsertActionPriority")),
            show_in_action_bar=bool(arguments.get("ShowInActionBar", False)),
            can_run_on_unselectable_target=bool(arguments.get("CanRunOnUnselectableTarget", False)),
            can_run_after_fight_finish=bool(arguments.get("CanRunAfterFightFinish", False)),
            custom_tags=tag_texts,
            raw_payload=arguments,
        )


@dataclass(frozen=True)
class DelayTransition:
    delay: ActionDelayState
    action: str

    def as_json(self) -> dict[str, Any]:
        return {"action": self.action, "normalized_value": str(self.delay.normalized_value), "skip_target_turn": self.delay.skip_target_turn}


def apply_delay_operation(operation: Mapping[str, Any], current: ActionDelayState | None = None, dynamic_resolver=None) -> DelayTransition:
    """Apply SetActionDelay / ModifyActionDelay / ResetActionDelay.

    ``dynamic_resolver`` is required only for dynamic Value specs.  The
    selected model clamps negative normalized delays to zero.
    """
    arguments = operation.get("arguments") if isinstance(operation.get("arguments"), Mapping) else {}
    kind = str(operation.get("kind"))
    current = current or ActionDelayState(Decimal("0"))
    source_type = str(operation.get("source_type"))
    if kind == "RESET_ACTION_DELAY" or source_type == "RPG.GameCore.ResetActionDelay":
        return DelayTransition(current.set(Decimal("0"), skip_target_turn=bool(arguments.get("SkipTargetTurn", False))), "RESET")
    value = arguments.get("Value") if source_type == "RPG.GameCore.SetActionDelay" else None
    if value is not None:
        spec = value_spec_from_payload(value)
        if spec.is_dynamic:
            if dynamic_resolver is None:
                raise SchedulerSemanticError("dynamic SetActionDelay requires a dynamic resolver")
            evaluated = spec.evaluate(dynamic_resolver)
        else:
            evaluated = spec.fixed_value
            if evaluated is None:
                raise SchedulerSemanticError("SetActionDelay Value is missing")
        return DelayTransition(current.set(evaluated), "SET")
    add_value = arguments.get("AddNormalizedValue")
    if add_value is not None:
        spec = value_spec_from_payload(add_value)
        if spec.is_dynamic:
            if dynamic_resolver is None:
                raise SchedulerSemanticError("dynamic ModifyActionDelay requires a dynamic resolver")
            delta = spec.evaluate(dynamic_resolver)
        else:
            delta = spec.fixed_value
            if delta is None:
                raise SchedulerSemanticError("ModifyActionDelay AddNormalizedValue is missing")
        return DelayTransition(current.add(delta), "ADD")
    raise SchedulerSemanticError(f"unsupported delay payload for {source_type}")


def find_template(record: Mapping[str, Any], template_ref: str | None) -> Mapping[str, Any] | None:
    if not template_ref:
        return None
    for template in record.get("template_definitions", []):
        if isinstance(template, Mapping) and template.get("template_id") == template_ref:
            return template
    return None


def expand_template_invocation(record: Mapping[str, Any], operation: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Expand IncludeTaskListTemplate at its invocation point.

    Template argument substitution into template operation arguments is
    preserved in ``invocation_arguments`` but is not evaluated here; the
    formula/dynamic-value resolver owns that step.
    """
    template = find_template(record, operation.get("template_ref"))
    if template is None:
        raise SchedulerSemanticError(f"unresolved template invocation: {operation.get('template_ref')}")
    expanded = []
    for child in template.get("operations", []):
        if not isinstance(child, Mapping):
            continue
        expanded_child = dict(child)
        expanded_child["invocation_arguments"] = operation.get("arguments")
        expanded.append(expanded_child)
    return tuple(expanded)


def trace_completion_marker(operation: Mapping[str, Any], *, task_id: str) -> TaskStep:
    """Markers transition their owning task at the boundary.

    Action start marks EXECUTING; action/damage completion marks SUCCESS.
    """
    kind = str(operation.get("kind"))
    if kind == "ACTION_START_MARKER":
        return TaskStep(task_id, TaskState.EXECUTING)
    if kind in {"ACTION_COMPLETION_MARKER", "DAMAGE_COMPLETION_MARKER"}:
        return TaskStep(task_id, TaskState.SUCCESS)
    raise SchedulerSemanticError(f"{kind} is not a completion marker")


def conditional_loop_expand(operation: Mapping[str, Any], predicate: PredicateEvaluator, max_iterations: int = 1000) -> tuple[Mapping[str, Any], ...]:
    """Expand a ConditionalLoop until the predicate hook returns false.

    The predicate hook receives the loop operation's raw Predicate payload;
    implementing a predicate evaluator is COMPILER-PREDICATE-001 work.
    """
    arguments = operation.get("arguments") if isinstance(operation.get("arguments"), Mapping) else {}
    body = []
    for group in operation.get("children", []):
        if isinstance(group, Mapping) and group.get("field_path") == "TaskList":
            body.extend(item for item in group.get("operations", []) if isinstance(item, Mapping))
    iterations = 0
    expanded = []
    while predicate(arguments) and iterations < max_iterations:
        expanded.extend(body)
        iterations += 1
    if iterations >= max_iterations:
        raise SchedulerSemanticError("conditional loop exceeded selected recursion guard")
    return tuple(expanded)
