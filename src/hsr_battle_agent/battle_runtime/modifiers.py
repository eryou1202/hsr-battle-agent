# -*- coding: utf-8 -*-
"""Modifier Application Bridge 07 runtime implementations.

Every function mirrors a bounded E4 native body / accepted boundary from
``data/semantics/4.4.54/modifier_application_bridge_07.json``.

Client-faithful details preserved:

* ``AbilityComponent.AddModifierInstance``: ordered tail append; duplicates
  are never checked by this leaf.  The two native post-append virtual
  dispatches are lifecycle/event side effects and are intentionally deferred.
* ``GetModifierByIndex``: positional index read; out-of-range returns null.
* ``GetIndexByModifier``: forward linear logical-ref scan -> first ordinal.
* ``HasModifier``: only raw state ``1`` instances are considered.
* ``get_Name`` / state getters: the proven native slots are materialized on
  the immutable canonical ``ModifierState``.
* The AddModifier OnTaskBegin primitive is an explicit normal-path boundary
  projection: ordered targets -> per-target append -> TaskState.SUCCESS.
  Stack/lifetime/effect branches are not simulated.
"""
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from hsr_battle_agent.battle_ir.actions import TaskExecutionState, TaskState
from hsr_battle_agent.battle_ir.modifiers import (
    ModifierContainer,
    ModifierState,
    ModifierTaskApplication,
    same_modifier_instance,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet

if TYPE_CHECKING:  # pragma: no cover - annotation-only, avoids sandbox import cycle
    from hsr_battle_agent.battle_sandbox.state import BattleState


def _require_modifier(modifier: ModifierState) -> None:
    if not isinstance(modifier, ModifierState):
        raise TypeError(
            f"modifier must be ModifierState, got {type(modifier).__name__}"
        )


def _require_container(container: ModifierContainer) -> None:
    if not isinstance(container, ModifierContainer):
        raise TypeError(
            f"container must be ModifierContainer, got {type(container).__name__}"
        )


def modifier_state_name(modifier: ModifierState) -> str:
    """BaseModifierInstance.get_Name: return the name slot materialization."""
    _require_modifier(modifier)
    return modifier.name


def modifier_state_count(modifier: ModifierState) -> int:
    """BaseModifierInstance.get_Count: return the count slot."""
    _require_modifier(modifier)
    return modifier.count


def modifier_state_state_raw(modifier: ModifierState) -> int:
    """BaseModifierInstance.get_State: raw enum slot (members UNKNOWN)."""
    _require_modifier(modifier)
    return modifier.state_raw


def modifier_state_stacking_flag_raw(modifier: ModifierState) -> int:
    """BaseModifierInstance.get_StackingFlag: raw enum slot (members UNKNOWN)."""
    _require_modifier(modifier)
    return modifier.stacking_flag_raw


def modifier_state_caster_entity(modifier: ModifierState) -> EntityRef | None:
    """BaseModifierInstance.get_CasterEntity materialization."""
    _require_modifier(modifier)
    return modifier.caster_entity


def modifier_state_layer(modifier: ModifierState) -> int:
    """TurnBasedModifierInstance.get_Layer slot materialization."""
    _require_modifier(modifier)
    return modifier.layer


def modifier_state_max_layer(modifier: ModifierState) -> int:
    """TurnBasedModifierInstance.get_MaxLayer: max(1, slot + slot)."""
    _require_modifier(modifier)
    return modifier.max_layer


def modifier_state_current_life(modifier: ModifierState) -> int:
    """TurnBasedModifierInstance.get_CurrentLife slot materialization."""
    _require_modifier(modifier)
    return modifier.current_life


def modifier_state_source_entity(modifier: ModifierState) -> EntityRef | None:
    """TurnBasedModifierInstance.get_SourceEntity materialization."""
    _require_modifier(modifier)
    return modifier.source_entity


def modifier_container_count(container: ModifierContainer) -> int:
    """AbilityComponent.get_ModifierCount: list count field."""
    _require_container(container)
    return container.count


def modifier_container_get_by_index(
    container: ModifierContainer,
    index: int,
) -> ModifierState | None:
    """AbilityComponent.GetModifierByIndex: positional ordered read."""
    _require_container(container)
    return container.get_by_index(index)


def modifier_container_index_of(
    container: ModifierContainer,
    modifier: ModifierState,
) -> int:
    """AbilityComponent.GetIndexByModifier: first logical-ref match or -1."""
    _require_container(container)
    _require_modifier(modifier)
    return container.index_of(modifier)


def modifier_container_has_modifier_by_name(
    container: ModifierContainer,
    name: str | None,
) -> bool:
    """AbilityComponent.HasModifier: active (state_raw == 1) name scan."""
    _require_container(container)
    return container.has_modifier_by_name(name)


def _container_from_battle_state(state: Any, target: EntityRef) -> ModifierContainer:
    if not isinstance(target, EntityRef):
        raise TypeError(f"target must be EntityRef, got {type(target).__name__}")
    raw = state.modifier_state_by_entity.get(str(target.runtime_id), [])
    if not isinstance(raw, list):
        raise TypeError("BattleState modifier collection must be a list")
    items = tuple(ModifierState.from_dict(item) for item in raw)
    return ModifierContainer(items)


def _write_container_to_battle_state(
    state: Any,
    target: EntityRef,
    container: ModifierContainer,
) -> None:
    _require_container(container)
    state.modifier_state_by_entity[str(target.runtime_id)] = [
        item.to_dict() for item in container.items
    ]


def apply_modifier_instance(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
) -> ModifierContainer:
    """Canonical AbilityComponent.AddModifierInstance persistent write.

    Native leaf appends to ``_ModifierList`` without any duplicate check.
    The canonical write keys the list by the proven owner entity id and
    assigns the tail instance ordinal.
    """
    _require_modifier(modifier)
    container = _container_from_battle_state(state, target)
    instance = dataclasses.replace(
        modifier,
        owner_entity=target,
        instance_ordinal=container.count,
    )
    updated = container.append(instance)
    _write_container_to_battle_state(state, target, updated)
    return updated


def add_modifier_task_begin_apply(
    state: Any,
    execution: TaskExecutionState,
    targets: TargetSet,
    modifier: ModifierState,
) -> ModifierTaskApplication:
    """Boundary projection of JAJPDPAHFOA.OnTaskBegin (AddModifier).

    Native normal path: iterate the ordered target list and call
    ``TryAddModifierInstance`` for every target, then write TaskState Success.
    The canonical boundary applies the proven append leaf per target in order
    and returns the deterministic Success projection.  Stack/lifetime/effect
    branches inside the 6592-byte native body remain out of scope.
    """
    if not isinstance(execution, TaskExecutionState):
        raise TypeError(
            f"execution must be TaskExecutionState, got {type(execution).__name__}"
        )
    if not isinstance(targets, TargetSet):
        raise TypeError(f"targets must be TargetSet, got {type(targets).__name__}")
    _require_modifier(modifier)
    applied_refs = []
    for target in targets.items:
        if target is None:
            raise ValueError(
                "AddModifier OnTaskBegin canonical boundary received a null "
                "target element; native path would dereference the entity"
            )
        container = apply_modifier_instance(state, target, modifier)
        applied_refs.append(container.items[-1].ref)
    return ModifierTaskApplication(
        task_state=TaskState.SUCCESS,
        applied_refs=tuple(applied_refs),
    )
