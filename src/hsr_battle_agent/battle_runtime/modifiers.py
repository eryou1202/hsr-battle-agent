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
    MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED,
    ModifierContainer,
    ModifierLifecycleResult,
    ModifierMatchKey,
    ModifierStacking,
    ModifierState,
    ModifierStateValue,
    ModifierTaskApplication,
    same_modifier_instance,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_ir.values import ObjectRef

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


def _next_instance_ordinal(container: ModifierContainer) -> int:
    """Deterministic logical instance ordinal, never reused after removal.

    Batch 07 anchored identity on ordered-append ordinals.  Once removal is
    possible, ``container.count`` can collide with a surviving tail ordinal,
    so the canonical extension is ``max(existing ordinals) + 1``.  This is
    deterministic state, not ``id()`` and not a UUID.
    """
    if container.count == 0:
        return 0
    return max(item.instance_ordinal for item in container.items) + 1


def apply_modifier_instance(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
) -> ModifierContainer:
    """Canonical AbilityComponent.AddModifierInstance persistent write.

    Native leaf appends to ``_ModifierList`` without any duplicate check.
    The canonical write keys the list by the proven owner entity id and
    assigns a deterministic, non-reused tail instance ordinal.
    """
    _require_modifier(modifier)
    container = _container_from_battle_state(state, target)
    instance = dataclasses.replace(
        modifier,
        owner_entity=target,
        instance_ordinal=_next_instance_ordinal(container),
    )
    updated = container.append(instance)
    _write_container_to_battle_state(state, target, updated)
    return updated


def _require_match_key(match_key: ModifierMatchKey) -> None:
    if not isinstance(match_key, ModifierMatchKey):
        raise TypeError(
            f"match_key must be ModifierMatchKey, got {type(match_key).__name__}"
        )


def _require_entity_or_none(value: EntityRef | None, name: str) -> None:
    if value is not None and not isinstance(value, EntityRef):
        raise TypeError(f"{name} must be EntityRef or None, got {type(value).__name__}")


def _require_object_ref_or_none(value: ObjectRef | None, name: str) -> None:
    if value is not None and not isinstance(value, ObjectRef):
        raise TypeError(
            f"{name} must be ObjectRef or None, got {type(value).__name__}"
        )


def modifier_match_search(
    modifier: ModifierState,
    match_key: ModifierMatchKey,
    state_filter: int,
) -> bool:
    """AbilityComponent._IsModifierMatchSearch E4 projection.

    The native predicate checks, in order:

    * name pointer/ordinal equality,
    * State filter (0 -> State 0..1; 1 -> State == 1; other -> none),
    * StackingFlag equality (100 -> wildcard),
    * optional caster RuntimeID (0/-1 -> wildcard),
    * optional source-provider object identity.
    """
    _require_modifier(modifier)
    _require_match_key(match_key)
    if isinstance(state_filter, bool) or not isinstance(state_filter, int):
        raise TypeError(f"state_filter must be an int, got {type(state_filter).__name__}")
    if modifier.name != match_key.name:
        return False
    if state_filter == MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED:
        if modifier.state_raw > ModifierStateValue.ALIVE:
            return False
    elif state_filter == 1:
        if modifier.state_raw != ModifierStateValue.ALIVE:
            return False
    if match_key.stacking_flag != 100:
        if modifier.stacking_flag_raw != match_key.stacking_flag:
            return False
    if match_key.caster_entity is not None:
        if modifier.caster_entity is None:
            return False
        if modifier.caster_entity.runtime_id != match_key.caster_entity.runtime_id:
            return False
    if match_key.source_provider_ref is not None:
        if modifier.source_provider_ref != match_key.source_provider_ref:
            return False
    return True


def modifier_container_find(
    container: ModifierContainer,
    match_key: ModifierMatchKey,
    state_filter: int,
) -> ModifierState | None:
    """AbilityComponent.FindModifierInstance forward scan projection."""
    _require_container(container)
    _require_match_key(match_key)
    for item in container.items:
        if modifier_match_search(item, match_key, state_filter):
            return item
    return None


def _index_of_ref(container: ModifierContainer, modifier: ModifierState) -> int:
    _require_modifier(modifier)
    return container.index_of(modifier)


def _replace_item(
    state: Any,
    target: EntityRef,
    index: int,
    updated: ModifierState,
) -> ModifierContainer:
    container = _container_from_battle_state(state, target)
    container = container.replace_at(index, updated)
    _write_container_to_battle_state(state, target, container)
    return container


def destroy_modifier_instance(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
    destroy_arg: int,
) -> ModifierState:
    """TurnBasedModifierInstance.Destroy bounded State transition.

    Native: State > 1 returns immediately (idempotent); otherwise
    ``State [+0x80] = 2 (ToBeRemoved)``.  Cleanup callbacks and the eventual
    RemoveDirtyModifiers list mutation are deferred; this primitive writes
    only the proven persistent State transition.
    """
    _require_modifier(modifier)
    if isinstance(destroy_arg, bool) or not isinstance(destroy_arg, int):
        raise TypeError(f"destroy_arg must be an int, got {type(destroy_arg).__name__}")
    container = _container_from_battle_state(state, target)
    index = _index_of_ref(container, modifier)
    if index < 0:
        raise ValueError(
            f"modifier {modifier.ref.trace_summary()} not present for {target}"
        )
    existing = container.items[index]
    if existing.state_raw > ModifierStateValue.ALIVE:
        return existing
    updated = dataclasses.replace(
        existing,
        state_raw=int(ModifierStateValue.TO_BE_REMOVED),
    )
    _replace_item(state, target, index, updated)
    return updated


def remove_dirty_modifiers(state: Any, target: EntityRef) -> ModifierContainer:
    """AbilityComponent.RemoveDirtyModifiers E4 shift-left removal.

    Native scans backwards; items with ``State == Alive(1)`` or
    ``destroy_guard > 0`` are kept, everything else is removed.  Each removal
    is count-- + shift-left + tail clear + version++, which is
    ``List<T>.RemoveAt`` equivalent, so the canonical tuple preserves the
    exact remaining order.
    """
    container = _container_from_battle_state(state, target)
    index = container.count - 1
    while index >= 0:
        item = container.items[index]
        if item.state_raw == ModifierStateValue.ALIVE or item.destroy_guard > 0:
            index -= 1
            continue
        container = container.remove_at(index)
        index -= 1
    _write_container_to_battle_state(state, target, container)
    return container


def _apply_redd_life_core(
    existing: ModifierState,
    stacking: int,
    new_count: int,
    new_life: int,
) -> ModifierState:
    """Recovered _ProcessModifierRedd deterministic life/count core.

    OnReplace / _OnModifierValueChanged / UI refresh / config-byte copies are
    deferred; only the directly proven persistent integer transitions are
    materialized.
    """
    if isinstance(new_count, bool) or not isinstance(new_count, int):
        raise TypeError(f"new_count must be an int, got {type(new_count).__name__}")
    if isinstance(new_life, bool) or not isinstance(new_life, int):
        raise TypeError(f"new_life must be an int, got {type(new_life).__name__}")
    if new_count < 0:
        raise ValueError("new_count must be >= 0")
    current_life = existing.current_life
    previous_life = existing.previous_life
    count = existing.count
    if stacking in (
        ModifierStacking.REFRESH,
        ModifierStacking.REPLACE,
        ModifierStacking.REPLACE_BY_CASTER,
        ModifierStacking.REPLACE_BY_CASTER_OR_UNSTACK,
        ModifierStacking.REPLACE_BY_CASTER_ABILITY,
    ):
        current_life = new_life
        count = new_count
        previous_life = current_life
    elif stacking == ModifierStacking.PROLONG:
        if new_life != -1 and existing.previous_life != -1:
            current_life = existing.current_life + new_life
        else:
            current_life = -1
        previous_life = current_life
    elif stacking == ModifierStacking.MERGE:
        if new_life != -1 and existing.previous_life != -1:
            current_life = max(existing.current_life, new_life)
        else:
            current_life = -1
        previous_life = current_life
    elif stacking == ModifierStacking.REPLACE_BUT_KEEP_LIFETIME:
        count = new_count
    # Multiple/EntityUnique/RetainGlobalLatest-family: config-only branch;
    # life/count/previous-life are untouched in the recovered core.
    return dataclasses.replace(
        existing,
        count=count,
        current_life=current_life,
        previous_life=previous_life,
        is_max_layer=existing.layer >= max(1, existing.max_layer),
    )


def process_modifier_redd(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
    stacking: int,
    new_count: int,
    new_life: int,
) -> ModifierState:
    """_ProcessModifierRedd bounded existing-instance refresh projection."""
    _require_modifier(modifier)
    if isinstance(stacking, bool) or not isinstance(stacking, int):
        raise TypeError(f"stacking must be an int, got {type(stacking).__name__}")
    if int(stacking) not in set(int(v) for v in ModifierStacking):
        raise ValueError(f"unknown ModifierStacking ordinal: {stacking}")
    container = _container_from_battle_state(state, target)
    index = _index_of_ref(container, modifier)
    if index < 0:
        raise ValueError(
            f"modifier {modifier.ref.trace_summary()} not present for {target}"
        )
    updated = _apply_redd_life_core(
        container.items[index],
        int(stacking),
        new_count,
        new_life,
    )
    _replace_item(state, target, index, updated)
    return updated


def on_added_modifier(modifier: ModifierState) -> ModifierState:
    """OnAdded canonical projection: sequence-state effects deferred."""
    _require_modifier(modifier)
    return modifier


def on_activate_modifier(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
) -> ModifierState:
    """OnActivate State transition: State [+0x80] = Alive(1)."""
    _require_modifier(modifier)
    container = _container_from_battle_state(state, target)
    index = _index_of_ref(container, modifier)
    if index < 0:
        raise ValueError(
            f"modifier {modifier.ref.trace_summary()} not present for {target}"
        )
    existing = container.items[index]
    if existing.state_raw == ModifierStateValue.ALIVE:
        return existing
    updated = dataclasses.replace(
        existing,
        state_raw=int(ModifierStateValue.ALIVE),
    )
    _replace_item(state, target, index, updated)
    return updated


def _global_targets_with_containers(state: Any) -> list[tuple[EntityRef, ModifierContainer]]:
    out: list[tuple[EntityRef, ModifierContainer]] = []
    for raw_id in sorted(state.modifier_state_by_entity, key=int):
        target = EntityRef(int(raw_id))
        out.append((target, _container_from_battle_state(state, target)))
    return out


def _append_new_instance(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
    stacking_flag: int,
    caster_entity: EntityRef | None,
    source_provider_ref: ObjectRef | None,
) -> tuple[ModifierState, ModifierContainer]:
    container = _container_from_battle_state(state, target)
    instance = dataclasses.replace(
        modifier,
        owner_entity=target,
        instance_ordinal=_next_instance_ordinal(container),
        state_raw=int(ModifierStateValue.ALIVE),
        stacking_flag_raw=int(stacking_flag),
        caster_entity=caster_entity,
        source_provider_ref=source_provider_ref,
        is_max_layer=False,
    )
    updated = container.append(instance)
    _write_container_to_battle_state(state, target, updated)
    return instance, updated


def try_add_modifier_instance(
    state: Any,
    target: EntityRef,
    modifier: ModifierState,
    stacking: int,
    stacking_flag: int,
    caster_entity: EntityRef | None,
    source_provider_ref: ObjectRef | None,
    activate: bool,
) -> ModifierLifecycleResult:
    """TryAddModifierInstance E4 duplicate/lifecycle decision tree.

    See the Batch 08 semantic artifact for the native branch evidence.
    Source-provider identity is only required by Stacking 7/8/12, exactly
    like the native lookup; those branches fail explicitly when the caller
    cannot supply the deterministic ObjectRef materialization.
    """
    _require_modifier(modifier)
    _require_entity_or_none(caster_entity, "caster_entity")
    _require_object_ref_or_none(source_provider_ref, "source_provider_ref")
    if isinstance(stacking, bool) or not isinstance(stacking, int):
        raise TypeError(f"stacking must be an int, got {type(stacking).__name__}")
    if int(stacking) not in set(int(v) for v in ModifierStacking):
        raise ValueError(f"unknown ModifierStacking ordinal: {stacking}")
    if isinstance(stacking_flag, bool) or not isinstance(stacking_flag, int):
        raise TypeError(f"stacking_flag must be an int, got {type(stacking_flag).__name__}")
    if not isinstance(activate, bool):
        raise TypeError(f"activate must be bool, got {type(activate).__name__}")
    stacking = int(stacking)
    source_required = stacking in (
        ModifierStacking.REPLACE_BY_CASTER,
        ModifierStacking.REPLACE_BY_CASTER_OR_UNSTACK,
        ModifierStacking.REPLACE_BY_CASTER_ABILITY,
    )
    if source_required and source_provider_ref is None:
        raise ValueError(
            "ModifierStacking "
            f"{ModifierStacking(stacking).name} requires source-provider "
            "identity; native match predicate compares the source provider "
            "object pointer"
        )

    match_key = ModifierMatchKey(
        name=modifier.name,
        stacking_flag=stacking_flag,
        caster_entity=caster_entity,
        source_provider_ref=source_provider_ref,
    )
    state_filter = MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED

    if stacking in (
        ModifierStacking.RETAIN_GLOBAL_LATEST,
        ModifierStacking.RETAIN_GLOBAL_LATEST_UNIQUE,
    ):
        search_targets = _global_targets_with_containers(state)
    else:
        search_targets = [(target, _container_from_battle_state(state, target))]

    existing: ModifierState | None = None
    existing_owner: EntityRef | None = None
    for owner, container in search_targets:
        found = modifier_container_find(container, match_key, state_filter)
        if found is not None:
            existing = found
            existing_owner = owner
            break

    local_before = _container_from_battle_state(state, target).count

    if existing is None:
        instance, updated = _append_new_instance(
            state, target, modifier, stacking_flag, caster_entity, source_provider_ref
        )
        return ModifierLifecycleResult(
            disposition="APPENDED",
            modifier=instance,
            before_count=local_before,
            after_count=updated.count,
        )

    if stacking == ModifierStacking.MULTIPLE:
        instance, updated = _append_new_instance(
            state, target, modifier, stacking_flag, caster_entity, source_provider_ref
        )
        return ModifierLifecycleResult(
            disposition="DUPLICATE_APPENDED",
            modifier=instance,
            before_count=local_before,
            after_count=updated.count,
        )

    destroyed_ref = None
    if stacking == ModifierStacking.RETAIN_GLOBAL_LATEST:
        assert existing_owner is not None
        destroyed_ref = existing.ref
        destroy_modifier_instance(state, existing_owner, existing, 0)
        instance, updated = _append_new_instance(
            state, target, modifier, stacking_flag, caster_entity, source_provider_ref
        )
        return ModifierLifecycleResult(
            disposition="DESTROYED_AND_APPENDED",
            modifier=instance,
            before_count=local_before,
            after_count=updated.count,
            destroyed_ref=destroyed_ref,
        )

    if stacking == ModifierStacking.RETAIN_GLOBAL_LATEST_UNIQUE:
        caster_is_owner = (
            existing.caster_entity is not None
            and existing.caster_entity.runtime_id == target.runtime_id
        )
        if not caster_is_owner:
            assert existing_owner is not None
            destroyed_ref = existing.ref
            destroy_modifier_instance(state, existing_owner, existing, 0)
            instance, updated = _append_new_instance(
                state, target, modifier, stacking_flag, caster_entity, source_provider_ref
            )
            return ModifierLifecycleResult(
                disposition="DESTROYED_AND_APPENDED",
                modifier=instance,
                before_count=local_before,
                after_count=updated.count,
                destroyed_ref=destroyed_ref,
            )

    # Process the existing instance in place.
    if existing.state_raw == ModifierStateValue.TO_BE_ADDED:
        # Native path appends to the delayed-add queue; queue internals are
        # deferred and the persistent ModifierList is unchanged.
        return ModifierLifecycleResult(
            disposition="DELAYED_EXISTING",
            modifier=existing,
            before_count=local_before,
            after_count=local_before,
        )
    updated = process_modifier_redd(
        state,
        existing_owner if existing_owner is not None else target,
        existing,
        stacking,
        new_count=modifier.count,
        new_life=modifier.current_life,
    )
    return ModifierLifecycleResult(
        disposition="EXISTING_PROCESSED",
        modifier=updated,
        before_count=local_before,
        after_count=local_before,
    )


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
