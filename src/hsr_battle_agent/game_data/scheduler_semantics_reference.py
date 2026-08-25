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
