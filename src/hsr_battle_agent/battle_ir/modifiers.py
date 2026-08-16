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
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.actions import TaskState
from hsr_battle_agent.battle_ir.targets import EntityRef

JSON_SCHEMA = "battle_ir_modifiers/1"


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

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                f"ModifierConfigRef.name must be str, got {type(self.name).__name__}"
            )

    def clone(self) -> "ModifierConfigRef":
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"schema": JSON_SCHEMA, "kind": "ModifierConfigRef", "name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierConfigRef":
        if not isinstance(data, Mapping):
            raise TypeError("ModifierConfigRef dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "ModifierConfigRef":
            raise ValueError(f"unsupported ModifierConfigRef dict: {data!r}")
        return cls(name=str(data["name"]))

    def trace_summary(self) -> str:
        return f"modifier_config_ref:{self.name}"


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


@dataclass(frozen=True)
class ModifierState:
    """Canonical persistent modifier instance state.

    Every field corresponds to one E4 native slot accepted in Batch 07:
    name ``[+0x60]``, count ``[+0x7c]``, state ``[+0x80]``,
    stacking_flag ``[+0x88]``, layer ``[+0x288]``, current_life ``[+0x2c4]``,
    max_layer ``max(1, [+0x2e0] + [+0x270])``, source ``[+0x100]`` and caster
    ``[+0x58]``.  ``owner_entity`` / ``instance_ordinal`` are the proven
    container identity (component owner + ordered-list ordinal), not instance
    object fields.
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
        ):
            _require_int(getattr(self, field_name), field_name)
        if self.instance_ordinal < 0:
            raise ValueError("instance_ordinal must be >= 0")
        if self.count < 0:
            raise ValueError("count must be >= 0")
        _require_entity(self.source_entity, "source_entity")
        _require_entity(self.caster_entity, "caster_entity")

    @property
    def config(self) -> ModifierConfigRef:
        return ModifierConfigRef(self.name)

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
            "stacking_flag_raw": self.stacking_flag_raw,
            "count": self.count,
            "layer": self.layer,
            "max_layer": self.max_layer,
            "current_life": self.current_life,
            "source_entity": (
                None if self.source_entity is None else self.source_entity.to_dict()
            ),
            "caster_entity": (
                None if self.caster_entity is None else self.caster_entity.to_dict()
            ),
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
