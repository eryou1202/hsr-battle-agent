# -*- coding: utf-8 -*-
"""Modifier Application Bridge 07 canonical IR.

Recovered runtime shape (see
``data/semantics/4.4.54/modifier_application_bridge_07.json``, E4):

* ``RPG.GameCore.AddModifier`` is a TaskConfig DSL config.
* Its generated executor ``JAJPDPAHFOA`` evaluates targets and calls
  ``TurnBasedAbilityComponent.TryAddModifierInstance`` per target.
* ``RPG.GameCore.AbilityComponent`` owns the persistent ordered
  ``_ModifierList`` at native slot ``[+0x38]``.
* ``BaseModifierInstance`` / ``TurnBasedModifierInstance`` expose the accepted
  state slots below.

Only fields with E4 native reads/writes are represented here.  There are
deliberately **no** hp/atk/def/dot/listener fields and no guessed stack /
duration semantics: stack policy and expiration triggers stay UNKNOWN in the
artifact until native evidence resolves them.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.actions import TaskState
from hsr_battle_agent.battle_ir.targets import EntityRef
from hsr_battle_agent.battle_ir.values import ObjectRef

JSON_SCHEMA = "battle_ir_modifiers/1"
OBJECT_REF_JSON_SCHEMA = "battle_ir_object_ref/1"

MATCH_STACKING_FLAG_WILDCARD = 100
MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED = 0
MATCH_STATE_FILTER_ALIVE_ONLY = 1
MATCH_STATE_FILTER_NONE = -1
MATCH_CASTER_WILDCARD_IDS = (None, 0, -1)


class ModifierStacking(IntEnum):
    """Recovered ``RPG.GameCore.ModifierStacking`` ordinals.

    E3 member order + E4 consumers: ModifierConfig parser stores the field at
    ``[+0x18]``; ``TryAddModifierInstance`` switches ordinals 7..13 and
    ``_ProcessModifierRedd`` switches ordinals 2..12.
    """

    UNKNOW = 0
    UNIQUE = 1
    REFRESH = 2
    PROLONG = 3
    MULTIPLE = 4
    REPLACE = 5
    MERGE = 6
    REPLACE_BY_CASTER = 7
    REPLACE_BY_CASTER_OR_UNSTACK = 8
    ENTITY_UNIQUE = 9
    REPLACE_BUT_KEEP_LIFETIME = 10
    RETAIN_GLOBAL_LATEST = 11
    REPLACE_BY_CASTER_ABILITY = 12
    RETAIN_GLOBAL_LATEST_UNIQUE = 13


def modifier_stacking_name(value: int) -> str:
    try:
        return ModifierStacking(value).name
    except ValueError:
        return f"UNKNOWN_STACKING_{value}"


class ModifierStateValue(IntEnum):
    """Recovered ``RPG.GameCore.ModifierState`` ordinals.

    E3 member order + E4 consumers: Base ctor writes 1, HasModifier filters 1,
    TryAdd branches on 0, Destroy writes 2 and guards state > 1.
    """

    TO_BE_ADDED = 0
    ALIVE = 1
    TO_BE_REMOVED = 2
    REMOVED = 3


def modifier_state_name(value: int) -> str:
    try:
        return ModifierStateValue(value).name
    except ValueError:
        return f"UNKNOWN_STATE_{value}"


class ModifierStackingFlag(IntEnum):
    """Recovered ``RPG.GameCore.ModifierStackingFlag`` ordinals (E3)."""

    DEFAULT = 0
    CHARACTER_SKILL = 1
    EQUIPMENT = 2
    RELIC = 3
    LEVEL = 4
    ROGUE = 5
    ANY = 6


def modifier_stacking_flag_name(value: int) -> str:
    try:
        return ModifierStackingFlag(value).name
    except ValueError:
        return f"UNKNOWN_STACKING_FLAG_{value}"


def _require_entity(value: EntityRef | None, name: str) -> None:
    if value is not None and not isinstance(value, EntityRef):
        raise TypeError(f"{name} must be EntityRef or None, got {type(value).__name__}")


def _require_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")


@dataclass(frozen=True)
class ModifierConfigRef:
    """Minimal serialized/config identity proven this round.

    The only stable recovered config identity is the modifier name string
    (``BaseModifierInstance.Name`` at native ``[+0x60]``).  No numeric config
    id / runtime id is claimed here.
    """

    name: str
    stacking: int = ModifierStacking.UNKNOW

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                f"ModifierConfigRef.name must be str, got {type(self.name).__name__}"
            )
        _require_int(self.stacking, "stacking")
        if int(self.stacking) not in set(int(v) for v in ModifierStacking):
            raise ValueError(
                f"ModifierConfigRef.stacking must be a ModifierStacking "
                f"ordinal, got {self.stacking}"
            )

    def clone(self) -> "ModifierConfigRef":
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JSON_SCHEMA,
            "kind": "ModifierConfigRef",
            "name": self.name,
            "stacking": int(self.stacking),
            "stacking_name": modifier_stacking_name(int(self.stacking)),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierConfigRef":
        if not isinstance(data, Mapping):
            raise TypeError("ModifierConfigRef dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "ModifierConfigRef":
            raise ValueError(f"unsupported ModifierConfigRef dict: {data!r}")
        return cls(
            name=str(data["name"]),
            stacking=int(data.get("stacking", ModifierStacking.UNKNOW)),
        )

    def trace_summary(self) -> str:
        return (
            f"modifier_config_ref:{self.name}:"
            f"stacking:{modifier_stacking_name(int(self.stacking))}"
        )


@dataclass(frozen=True)
class ModifierRef:
    """Immutable logical modifier instance reference.

    Identity coverage (E4): config name string + owner entity + ordered-list
    instance ordinal.  A native object handle / runtime instance id was not
    recovered, so it is intentionally absent.
    """

    name: str
    owner_entity: EntityRef
    instance_ordinal: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"name must be str, got {type(self.name).__name__}")
        if not isinstance(self.owner_entity, EntityRef):
            raise TypeError(
                "owner_entity must be EntityRef, "
                f"got {type(self.owner_entity).__name__}"
            )
        _require_int(self.instance_ordinal, "instance_ordinal")
        if self.instance_ordinal < 0:
            raise ValueError("instance_ordinal must be >= 0")

    def clone(self) -> "ModifierRef":
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JSON_SCHEMA,
            "kind": "ModifierRef",
            "name": self.name,
            "owner_entity": self.owner_entity.to_dict(),
            "instance_ordinal": self.instance_ordinal,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierRef":
        if not isinstance(data, Mapping):
            raise TypeError("ModifierRef dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "ModifierRef":
            raise ValueError(f"unsupported ModifierRef dict: {data!r}")
        return cls(
            name=str(data["name"]),
            owner_entity=EntityRef.from_dict(data["owner_entity"]),
            instance_ordinal=int(data["instance_ordinal"]),
        )

    def trace_summary(self) -> str:
        return (
            f"modifier_ref:{self.name}:entity:{self.owner_entity.runtime_id}"
            f":ordinal:{self.instance_ordinal}"
        )


def _object_ref_to_dict(value: ObjectRef | None) -> Any:
    if value is None:
        return None
    return {
        "schema": OBJECT_REF_JSON_SCHEMA,
        "kind": "ObjectRef",
        "ref_id": value.ref_id,
    }


def _object_ref_from_dict(data: Any) -> ObjectRef | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise TypeError("ObjectRef dict must be a mapping")
    if (
        data.get("schema") != OBJECT_REF_JSON_SCHEMA
        or data.get("kind") != "ObjectRef"
    ):
        raise ValueError(f"unsupported ObjectRef dict: {data!r}")
    return ObjectRef(ref_id=int(data["ref_id"]))


@dataclass(frozen=True)
class ModifierMatchKey:
    """Client duplicate-match identity, kept separate from instance identity.

    Native predicate ``_IsModifierMatchSearch`` checks: name (ordinal string),
    StackingFlag, optional caster entity RuntimeID, optional source-provider
    object identity.  The source-provider native object id is UNKNOWN; the
    sandbox materializes it as a caller-supplied deterministic ``ObjectRef``.
    """

    name: str
    stacking_flag: int = ModifierStackingFlag.DEFAULT
    caster_entity: EntityRef | None = None
    source_provider_ref: ObjectRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"name must be str, got {type(self.name).__name__}")
        _require_int(self.stacking_flag, "stacking_flag")
        _require_entity(self.caster_entity, "caster_entity")
        if self.source_provider_ref is not None and not isinstance(
            self.source_provider_ref, ObjectRef
        ):
            raise TypeError(
                "source_provider_ref must be ObjectRef or None, "
                f"got {type(self.source_provider_ref).__name__}"
            )

    def clone(self) -> "ModifierMatchKey":
        return self

    def trace_summary(self) -> str:
        caster = (
            "any"
            if self.caster_entity is None
            else str(self.caster_entity.runtime_id)
        )
        source = (
            "any"
            if self.source_provider_ref is None
            else f"object:{self.source_provider_ref.ref_id}"
        )
        return (
            f"modifier_match:{self.name}:flag:{self.stacking_flag}:"
            f"caster:{caster}:source:{source}"
        )


@dataclass(frozen=True)
class ModifierLifecycleResult:
    """Deterministic outcome of TryAddModifierInstance projection."""

    disposition: str
    modifier: ModifierState
    before_count: int
    after_count: int
    destroyed_ref: ModifierRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, str) or not self.disposition:
            raise ValueError("disposition must be a non-empty string")
        if not isinstance(self.modifier, ModifierState):
            raise TypeError("modifier must be ModifierState")
        _require_int(self.before_count, "before_count")
        _require_int(self.after_count, "after_count")
        if self.before_count < 0 or self.after_count < 0:
            raise ValueError("before_count/after_count must be >= 0")
        if self.destroyed_ref is not None and not isinstance(
            self.destroyed_ref, ModifierRef
        ):
            raise TypeError("destroyed_ref must be ModifierRef or None")

    def clone(self) -> "ModifierLifecycleResult":
        return self

    def trace_summary(self) -> str:
        return (
            f"modifier_lifecycle:{self.disposition}:"
            f"{self.modifier.ref.trace_summary()}:"
            f"count:{self.before_count}->{self.after_count}"
        )


@dataclass(frozen=True)
class ModifierState:
    """Canonical persistent modifier instance state.

    Batch 07 fields: name ``[+0x60]``, count ``[+0x7c]``, state ``[+0x80]``,
    stacking_flag ``[+0x88]``, layer ``[+0x288]``, max_layer
    ``max(1, [+0x2e0] + [+0x270])``, source ``[+0x100]`` and caster
    ``[+0x58]``.  Batch 08 E4 lifecycle fields: previous_life ``[+0x2e4]``,
    is_max_layer ``[+0x8e]``, destroy_guard ``[+0x94]``, and the sandbox
    logical materialization of the native source-provider object identity.

    ``owner_entity`` / ``instance_ordinal`` remain the proven container
    identity (component owner + ordered-list ordinal).
    """

    name: str
    owner_entity: EntityRef
    instance_ordinal: int = 0
    state_raw: int = 0
    stacking_flag_raw: int = 0
    count: int = 0
    layer: int = 0
    max_layer: int = 1
    current_life: int = 0
    source_entity: EntityRef | None = None
    caster_entity: EntityRef | None = None
    previous_life: int = -1
    is_max_layer: bool = False
    destroy_guard: int = 0
    source_provider_ref: ObjectRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"name must be str, got {type(self.name).__name__}")
        if not isinstance(self.owner_entity, EntityRef):
            raise TypeError(
                "owner_entity must be EntityRef, "
                f"got {type(self.owner_entity).__name__}"
            )
        for field_name in (
            "instance_ordinal",
            "state_raw",
            "stacking_flag_raw",
            "count",
            "layer",
            "max_layer",
            "current_life",
            "previous_life",
            "destroy_guard",
        ):
            _require_int(getattr(self, field_name), field_name)
        if self.instance_ordinal < 0:
            raise ValueError("instance_ordinal must be >= 0")
        if self.count < 0:
            raise ValueError("count must be >= 0")
        if self.destroy_guard < 0:
            raise ValueError("destroy_guard must be >= 0")
        if not isinstance(self.is_max_layer, bool):
            raise TypeError(
                f"is_max_layer must be bool, got {type(self.is_max_layer).__name__}"
            )
        _require_entity(self.source_entity, "source_entity")
        _require_entity(self.caster_entity, "caster_entity")
        if self.source_provider_ref is not None and not isinstance(
            self.source_provider_ref, ObjectRef
        ):
            raise TypeError(
                "source_provider_ref must be ObjectRef or None, "
                f"got {type(self.source_provider_ref).__name__}"
            )

    @property
    def config(self) -> ModifierConfigRef:
        return ModifierConfigRef(self.name)

    @property
    def state_name(self) -> str:
        return modifier_state_name(self.state_raw)

    @property
    def stacking_flag_name(self) -> str:
        return modifier_stacking_flag_name(self.stacking_flag_raw)

    @property
    def ref(self) -> ModifierRef:
        return ModifierRef(
            name=self.name,
            owner_entity=self.owner_entity,
            instance_ordinal=self.instance_ordinal,
        )

    def clone(self) -> "ModifierState":
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JSON_SCHEMA,
            "kind": "ModifierState",
            "name": self.name,
            "owner_entity": self.owner_entity.to_dict(),
            "instance_ordinal": self.instance_ordinal,
            "state_raw": self.state_raw,
            "state_name": self.state_name,
            "stacking_flag_raw": self.stacking_flag_raw,
            "stacking_flag_name": self.stacking_flag_name,
            "count": self.count,
            "layer": self.layer,
            "max_layer": self.max_layer,
            "current_life": self.current_life,
            "previous_life": self.previous_life,
            "is_max_layer": self.is_max_layer,
            "destroy_guard": self.destroy_guard,
            "source_entity": (
                None if self.source_entity is None else self.source_entity.to_dict()
            ),
            "caster_entity": (
                None if self.caster_entity is None else self.caster_entity.to_dict()
            ),
            "source_provider_ref": _object_ref_to_dict(self.source_provider_ref),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierState":
        if not isinstance(data, Mapping):
            raise TypeError("ModifierState dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "ModifierState":
            raise ValueError(f"unsupported ModifierState dict: {data!r}")
        return cls(
            name=str(data["name"]),
            owner_entity=EntityRef.from_dict(data["owner_entity"]),
            instance_ordinal=int(data.get("instance_ordinal", 0)),
            state_raw=int(data.get("state_raw", 0)),
            stacking_flag_raw=int(data.get("stacking_flag_raw", 0)),
            count=int(data.get("count", 0)),
            layer=int(data.get("layer", 0)),
            max_layer=int(data.get("max_layer", 1)),
            current_life=int(data.get("current_life", 0)),
            previous_life=int(data.get("previous_life", -1)),
            is_max_layer=bool(data.get("is_max_layer", False)),
            destroy_guard=int(data.get("destroy_guard", 0)),
            source_entity=(
                None
                if data.get("source_entity") is None
                else EntityRef.from_dict(data["source_entity"])
            ),
            caster_entity=(
                None
                if data.get("caster_entity") is None
                else EntityRef.from_dict(data["caster_entity"])
            ),
            source_provider_ref=_object_ref_from_dict(data.get("source_provider_ref")),
        )

    def trace_summary(self) -> str:
        return self.ref.trace_summary()


@dataclass(frozen=True)
class ModifierTaskApplication:
    """Canonical AddModifier OnTaskBegin normal-path projection result.

    ``task_state`` is the proven native Success store (0x9999) on the observed
    normal application path.  ``applied_refs`` preserves target-loop apply
    order; effects/lifetime branches beyond the boundary are not represented.
    """

    task_state: TaskState = TaskState.SUCCESS
    applied_refs: tuple[ModifierRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task_state, TaskState):
            raise TypeError(
                f"task_state must be TaskState, got {type(self.task_state).__name__}"
            )
        if not isinstance(self.applied_refs, tuple):
            raise TypeError("applied_refs must be a tuple")
        for ref in self.applied_refs:
            if not isinstance(ref, ModifierRef):
                raise TypeError(
                    f"applied_refs items must be ModifierRef, got {type(ref).__name__}"
                )

    def trace_summary(self) -> str:
        return (
            f"ModifierTaskApplication(task_state={self.task_state.name}, "
            f"applied={len(self.applied_refs)})"
        )


@dataclass(frozen=True)
class ModifierContainer:
    """Ordered tuple-backed modifier collection (never an unordered set).

    Native layout / semantics proven by AbilityComponent leaf bodies:

    * order = append order (``ORDERED_APPEND``),
    * duplicates are preserved by the append leaf,
    * index reads are positional,
    * ``GetIndexByModifier`` is a forward linear reference scan.
    """

    items: tuple[ModifierState, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise TypeError("ModifierContainer.items must be a tuple")
        for item in self.items:
            if not isinstance(item, ModifierState):
                raise TypeError(
                    "ModifierContainer items must be ModifierState, "
                    f"got {type(item).__name__}"
                )

    @classmethod
    def of(cls, *items: ModifierState) -> "ModifierContainer":
        return cls(tuple(items))

    def append(self, modifier: ModifierState) -> "ModifierContainer":
        if not isinstance(modifier, ModifierState):
            raise TypeError(
                f"modifier must be ModifierState, got {type(modifier).__name__}"
            )
        return ModifierContainer(self.items + (modifier,))

    def replace_at(self, index: int, modifier: ModifierState) -> "ModifierContainer":
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"index must be an int, got {type(index).__name__}")
        if index < 0 or index >= len(self.items):
            raise IndexError(index)
        if not isinstance(modifier, ModifierState):
            raise TypeError(
                f"modifier must be ModifierState, got {type(modifier).__name__}"
            )
        items = list(self.items)
        items[index] = modifier
        return ModifierContainer(tuple(items))

    def remove_at(self, index: int) -> "ModifierContainer":
        """Native RemoveDirtyModifiers shift-left removal (E4).

        Remaining items keep their relative order; the freed tail slot is
        dropped from the canonical tuple.  This is exactly the observable
        state after the native ``List<T>.RemoveAt``-equivalent mutation.
        """
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"index must be an int, got {type(index).__name__}")
        if index < 0 or index >= len(self.items):
            raise IndexError(index)
        items = list(self.items)
        del items[index]
        return ModifierContainer(tuple(items))

    def get_by_index(self, index: int) -> ModifierState | None:
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"index must be an int, got {type(index).__name__}")
        if index < 0 or index >= len(self.items):
            return None
        return self.items[index]

    def index_of(self, modifier: ModifierState) -> int:
        if not isinstance(modifier, ModifierState):
            raise TypeError(
                f"modifier must be ModifierState, got {type(modifier).__name__}"
            )
        wanted = modifier.ref
        for index, item in enumerate(self.items):
            if item.ref == wanted:
                return index
        return -1

    def has_modifier_by_name(self, name: str | None) -> bool:
        """AbilityComponent.HasModifier projection.

        Native body only considers instances whose raw state ``[+0x80] == 1``
        and compares the string name slot ``[+0x60]``.
        """
        if name is not None and not isinstance(name, str):
            raise TypeError(f"name must be str or None, got {type(name).__name__}")
        for item in self.items:
            if item.state_raw == 1 and item.name == name:
                return True
        return False

    @property
    def count(self) -> int:
        return len(self.items)

    def clone(self) -> "ModifierContainer":
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JSON_SCHEMA,
            "kind": "ModifierContainer",
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierContainer":
        if not isinstance(data, Mapping):
            raise TypeError("ModifierContainer dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "ModifierContainer":
            raise ValueError(f"unsupported ModifierContainer dict: {data!r}")
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            raise TypeError("ModifierContainer.items must be a list in dict form")
        return cls(tuple(ModifierState.from_dict(item) for item in raw_items))

    def trace_summary(self) -> str:
        return f"modifier_count:{self.count}"


def same_modifier_instance(a: ModifierState, b: ModifierState) -> bool:
    """Canonical instance equality: logical ref equality, not deep equality."""
    if not isinstance(a, ModifierState) or not isinstance(b, ModifierState):
        raise TypeError("same_modifier_instance requires ModifierState values")
    return a.ref == b.ref
