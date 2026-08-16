# -*- coding: utf-8 -*-
"""Target Selector Batch 05 runtime implementations.

Every function mirrors a bounded native body from
``data/semantics/4.4.54/target_selector_batch_05.json`` (E4).  The sandbox
models the recovered TaskContext fields canonically; it does not simulate
IL2CPP list memory or the caster getter's vtable chain.

Client-faithful details preserved:

* ``select_task_action_target``: null TaskContext field -> empty TargetSet.
* ``select_caster``: null caster result -> one-element TargetSet containing
  ``None`` (the native list really receives a null element).
* ``select_none``: always empty TargetSet.
* ``collapse_single_or_null`` (AbilityStatic.GetTaskSingleTarget): first
  element, null when empty.
* ``collapse_required_single_or_null`` (TaskContext.EvaluateSingleTarget):
  only element, null when count is 0 or >= 2.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checkers
    from hsr_battle_agent.battle_sandbox.context import ExecutionContext


def context_task_action_target(context: "ExecutionContext") -> EntityRef | None:
    """TaskContext.get_TaskActionTarget: raw [+0x48] field read."""
    return context.task_action_target


def context_owner_entity(context: "ExecutionContext") -> EntityRef | None:
    """TaskContext.get_OwnerEntity: raw [+0x70] field read."""
    return context.owner_entity


def select_task_action_target(context: "ExecutionContext") -> TargetSet:
    """TargetFetchTaskActionTarget evaluator: append only a non-null field."""
    entity = context.task_action_target
    if entity is None:
        return TargetSet()
    return TargetSet.of(entity)


def select_caster(context: "ExecutionContext") -> TargetSet:
    """TargetFetchCaster evaluator: append the caster result unconditionally."""
    return TargetSet.of(context.caster_entity)


def select_none(context: "ExecutionContext") -> TargetSet:
    """TargetFetchNone evaluator: no context field is read."""
    del context  # proven no-read leaf
    return TargetSet()


def collapse_single_or_null(targets: TargetSet) -> EntityRef | None:
    """AbilityStatic.GetTaskSingleTarget: first element, null when empty."""
    if targets.count == 0:
        return None
    return targets.items[0]


def collapse_required_single_or_null(targets: TargetSet) -> EntityRef | None:
    """TaskContext.EvaluateSingleTarget: exactly one element, else null."""
    if targets.count != 1:
        return None
    return targets.items[0]


def game_entity_runtime_id(entity: EntityRef) -> int:
    """GameEntity.get_RuntimeID: canonical EntityRef id is the runtime id."""
    return entity.runtime_id
