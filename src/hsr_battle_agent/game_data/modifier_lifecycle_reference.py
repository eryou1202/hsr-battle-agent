"""Pure reference transitions for the locally-supported Modifier lifecycle.

This module is a semantic executable specification for
PRIM-MODIFIER-001.  It intentionally excludes callback execution, source
formula resolution and global modifier lookup; those require their own
compiler/kernel packets.  It must not be mistaken for a production runtime.

The v2 reference aligns with the packet boundary model:

- an appended instance enters ``TO_BE_ADDED`` and is not dispatchable;
- ``activate`` represents the OnAdded -> OnActivate boundary and moves the
  instance to ``ALIVE`` (callback registration keys become eligible for the
  event kernel only from this point);
- ``mark_destroy`` moves to ``TO_BE_REMOVED`` but keeps the registration keys
  attached until the explicit dirty-removal boundary;
- ``remove_dirty`` removes non-ALIVE instances without a destroy guard,
  preserves survivor order, and returns the callback/property-contribution
  keys that must be deregistered at the same boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Iterable


class ModifierState(IntEnum):
    TO_BE_ADDED = 0
    ALIVE = 1
    TO_BE_REMOVED = 2
    REMOVED = 3


class StackingPolicy(IntEnum):
    REPLACE = 2
    PROLONG = 3
    MULTIPLE = 4
    REPLACE_ALT_5 = 5
    MERGE = 6
    REPLACE_ALT_7 = 7
    REPLACE_ALT_8 = 8
    REPLACE_KEEP_LIFETIME = 10
    RETAIN_GLOBAL_LATEST = 11
    REPLACE_ALT_12 = 12
    RETAIN_GLOBAL_LATEST_UNIQUE = 13


@dataclass(frozen=True)
class ModifierInstance:
    instance_id: str
    name: str
    stacking: int
    caster_runtime_id: int | None
    source_provider_id: str | None
    current_life: int | None
    count: int | None
    state: ModifierState = ModifierState.TO_BE_ADDED
    destroy_guard: int = 0
    destroy_reason: int | None = None
    callback_registration_keys: tuple[str, ...] = ()
    property_contribution_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModifierTransition:
    instances: tuple[ModifierInstance, ...]
    action: str
    affected_instance_id: str
    deregistered_callback_keys: tuple[str, ...] = ()
    removed_property_contribution_keys: tuple[str, ...] = ()


def _matches(existing: ModifierInstance, incoming: ModifierInstance) -> bool:
    """The proven local lookup identity, with no implicit Python equality."""
    if existing.name != incoming.name or existing.stacking != incoming.stacking:
        return False
    if existing.state not in {ModifierState.TO_BE_ADDED, ModifierState.ALIVE}:
        return False
    if incoming.caster_runtime_id not in {None, 0, -1} and existing.caster_runtime_id != incoming.caster_runtime_id:
        return False
    return incoming.source_provider_id is None or existing.source_provider_id == incoming.source_provider_id


def add_or_refresh(instances: Iterable[ModifierInstance], incoming: ModifierInstance) -> ModifierTransition:
    """Apply the bounded E4 add/refresh state transition.

    Appended instances remain ``TO_BE_ADDED`` until ``activate`` is called at
    the OnAdded -> OnActivate boundary.  Policies without a complete
    local/global resolution contract are rejected, rather than silently
    approximated.
    """
    current = tuple(instances)
    policy = int(incoming.stacking)
    if policy == StackingPolicy.MULTIPLE:
        pending = replace(incoming, state=ModifierState.TO_BE_ADDED)
        return ModifierTransition(current + (pending,), "APPEND_MULTIPLE_PENDING", pending.instance_id)
    existing_index = next((index for index, existing in enumerate(current) if _matches(existing, incoming)), None)
    if existing_index is None:
        pending = replace(incoming, state=ModifierState.TO_BE_ADDED)
        return ModifierTransition(current + (pending,), "APPEND_NEW_PENDING", pending.instance_id)
    existing = current[existing_index]
    if policy in {2, 5, 7, 8, 12}:
        updated = replace(existing, current_life=incoming.current_life, count=incoming.count)
        action = "REFRESH_REPLACE"
    elif policy == StackingPolicy.PROLONG:
        if existing.current_life is None or incoming.current_life is None:
            raise ValueError("PROLONG requires explicit current_life values")
        updated = replace(existing, current_life=existing.current_life + incoming.current_life)
        action = "REFRESH_PROLONG"
    elif policy == StackingPolicy.MERGE:
        if existing.current_life is None or incoming.current_life is None:
            raise ValueError("MERGE requires explicit current_life values")
        updated = replace(existing, current_life=max(existing.current_life, incoming.current_life))
        action = "REFRESH_MERGE"
    elif policy == StackingPolicy.REPLACE_KEEP_LIFETIME:
        updated = replace(existing, count=incoming.count)
        action = "REFRESH_KEEP_LIFETIME"
    elif policy in {StackingPolicy.RETAIN_GLOBAL_LATEST, StackingPolicy.RETAIN_GLOBAL_LATEST_UNIQUE}:
        raise NotImplementedError("global modifier lookup is explicitly outside PRIM-MODIFIER-001")
    else:
        raise NotImplementedError(f"unsupported stacking policy {policy}")
    return ModifierTransition(current[:existing_index] + (updated,) + current[existing_index + 1 :], action, updated.instance_id)


def activate(instances: Iterable[ModifierInstance], instance_id: str) -> ModifierTransition:
    """OnAdded has completed; OnActivate makes exactly one pending instance ALIVE."""
    current = tuple(instances)
    index = next((index for index, item in enumerate(current) if item.instance_id == instance_id), None)
    if index is None:
        raise KeyError(instance_id)
    pending = current[index]
    if pending.state != ModifierState.TO_BE_ADDED:
        raise ValueError(f"instance {instance_id} is not TO_BE_ADDED: {pending.state.name}")
    activated = replace(pending, state=ModifierState.ALIVE)
    return ModifierTransition(current[:index] + (activated,) + current[index + 1 :], "ACTIVATE_ALIVE", instance_id)


def active_callback_keys(instances: Iterable[ModifierInstance]) -> tuple[str, ...]:
    """Only ALIVE modifiers contribute callbacks to KERNEL-EVENT-001."""
    return tuple(
        key
        for instance in instances
        if instance.state == ModifierState.ALIVE
        for key in instance.callback_registration_keys
    )


def mark_destroy(instances: Iterable[ModifierInstance], instance_id: str, *, reason: int) -> ModifierTransition:
    current = tuple(instances)
    index = next((index for index, item in enumerate(current) if item.instance_id == instance_id), None)
    if index is None:
        raise KeyError(instance_id)
    existing = current[index]
    if existing.state > ModifierState.ALIVE:
        return ModifierTransition(current, "DESTROY_ALREADY_PENDING", existing.instance_id)
    pending = replace(existing, state=ModifierState.TO_BE_REMOVED, destroy_reason=reason)
    return ModifierTransition(current[:index] + (pending,) + current[index + 1 :], "MARK_TO_BE_REMOVED", pending.instance_id)


def remove_dirty(instances: Iterable[ModifierInstance]) -> ModifierTransition:
    """Commit native dirty removal while preserving the survivors' order.

    Callback registrations and property-contribution keys of removed
    instances are returned on the transition so the same lifecycle boundary
    deregisters them atomically.
    """
    current = tuple(instances)
    survivors = tuple(item for item in current if item.state == ModifierState.ALIVE or item.destroy_guard > 0)
    removed = tuple(item for item in current if item not in survivors)
    return ModifierTransition(
        survivors,
        "REMOVE_DIRTY",
        removed[0].instance_id if removed else "NONE",
        deregistered_callback_keys=tuple(key for item in removed for key in item.callback_registration_keys),
        removed_property_contribution_keys=tuple(key for item in removed for key in item.property_contribution_keys),
    )
