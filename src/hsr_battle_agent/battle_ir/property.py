# -*- coding: utf-8 -*-
"""Generic Property IR for Handoffs 09/10/11.

This module contains only canonical persistent representations and neutral
semantic labels:

* ``PropertyEntry`` mirrors the native PropertyEntry slots proven by Handoff
  10 (``data/semantics/4.4.54/generic_property_materialization_10.json``).
* ``ModifierPropertyContribution`` is the Handoff 09 modifier-owned record,
  with Handoff 10's stable ``source_index`` replacing the early opaque
  ``contribution_key`` abstraction.  There is deliberately **one** key system.
* ``PropertyChangeBoundary`` is an internal deterministic
  old-materialized -> rebuild -> new-materialized record.  It is not an event
  dispatch and does not model listeners.
* The post-materialization fields (``post_hook_context`` /
  ``post_transform_a`` / ``post_transform_b``) are opaque JSON-safe values.
  Their gameplay meaning is UNKNOWN and they keep neutral names.
* Materialization kinds use neutral ``MaterializationKind`` names; gameplay
  labels are deliberately not invented here.

Runtime semantics live in ``hsr_battle_agent.battle_runtime.property`` and are
bound to the semantic artifacts through the catalog/registry path.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.modifiers import ModifierRef, ModifierState
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet

JSON_SCHEMA = "battle_ir_property/1"
CONTRIBUTION_JSON_SCHEMA = "battle_ir_property_contribution/1"

_QWORD_MIN = -(2**63)
_QWORD_MAX = 0xFFFFFFFFFFFFFFFF

# Handoff 11 native special property-ID branch set.  CurrentHP is property 10
# and MUST NOT use the generic source-0 mutation path.
CURRENT_HP_PROPERTY_ID = 10
SPECIAL_PROPERTY_IDS = frozenset(
    {10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32}
)


class PropertyModifyFunction(IntEnum):
    """Handoff 11 ``ApplyPropertyModifyFunction`` ids (native arithmetic proven).

    Out-of-range ids are not enum members; the native helper uses the Set
    fallthrough for them.
    """

    SET = 1
    ADD = 2
    MUL = 3
    MIN_SET = 4
    MAX_SET = 5


class MaterializationKind(IntEnum):
    """Neutral labels for the seven native PropertyEntry materialization modes.

    Names describe control flow / recovered callee identities only.  They are
    intentionally not gameplay labels (SUM/MULTIPLY/MIN/MAX are not asserted
    unless the machine artifacts prove the exact operation).
    """

    KIND_1_SOURCE_ZERO_SELECTION = 1
    KIND_2_LAST_CHANGED_SOURCE_SELECTION = 2
    KIND_3_ACTIVE_FOLD_ADD_CALLEE = 3
    KIND_4_ACTIVE_FOLD_MULTIPLY_CALLEE = 4
    KIND_5_ACTIVE_FOLD_SUBTRACT_MULTIPLY_CALLEES = 5
    KIND_6_ACTIVE_EXTREMUM_DIRECTION_A = 6
    KIND_7_ACTIVE_EXTREMUM_DIRECTION_B = 7


def property_entry_key(entity: EntityRef, property_id: int) -> str:
    """Canonical persistent key for ``BattleState.entity_property_entries``."""
    if not isinstance(entity, EntityRef):
        raise TypeError(
            f"entity must be EntityRef, got {type(entity).__name__}"
        )
    _require_int(property_id, "property_id")
    return f"property_entry:{entity.runtime_id}:{property_id}"


def parse_property_entry_key(key: str) -> tuple[int, int]:
    """Parse a canonical property-entry key back to ``(runtime_id, property_id)``."""
    if not isinstance(key, str):
        raise TypeError(f"key must be str, got {type(key).__name__}")
    prefix, raw_entity, raw_property = key.split(":")
    if prefix != "property_entry":
        raise ValueError(f"not a property_entry key: {key!r}")
    return int(raw_entity), int(raw_property)


def modifier_contribution_key(modifier: ModifierRef) -> str:
    """Canonical persistent key for ``BattleState.modifier_property_contributions``."""
    if not isinstance(modifier, ModifierRef):
        raise TypeError(
            f"modifier must be ModifierRef, got {type(modifier).__name__}"
        )
    return (
        f"modifier_property:{modifier.owner_entity.runtime_id}:"
        f"{modifier.instance_ordinal}:{modifier.name}"
    )


def _require_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")


def _require_qword_raw(value: int, name: str) -> None:
    _require_int(value, name)
    if not (_QWORD_MIN <= value <= _QWORD_MAX):
        raise ValueError(
            f"{name} out of qword raw range [{_QWORD_MIN}, {_QWORD_MAX}]: "
            f"{value}"
        )


def _validate_json_value(value: Any, where: str) -> None:
    """Same strict JSON model as BattleState, duplicated to keep IR standalone."""
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{where} float values must be finite")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{where} mapping keys must be strings, got {type(key).__name__}"
                )
            _validate_json_value(item, f"{where}.{key}")
        return
    if isinstance(value, tuple):
        raise TypeError(
            f"{where} tuples are forbidden by the strict JSON model; use a list"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{where}[{index}]")
        return
    raise TypeError(
        f"{where} must be JSON-safe "
        "(None/bool/int/finite float/str/list/dict with str keys), "
        f"got {type(value).__name__}"
    )


def _copy_json_value(value: Any) -> Any:
    _validate_json_value(value, "value")
    if isinstance(value, dict):
        return {key: _copy_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json_value(item) for item in value]
    return value


@dataclass
class PropertyEntry:
    """Canonical persistent PropertyEntry (Handoff 10 slot model).

    ``source_generation``, ``source_active`` and ``source_value`` are parallel
    arrays indexed by stable ``source_index``.  A generation of zero disables
    the slot; stale ``source_value`` entries are retained when a slot is
    removed.  Slot ``0`` is reserved for the native mutable/base source-0 path
    (Handoff 11); modifier-owned contributions are allocated from index 1+.
    """

    source_generation: list[int]
    source_active: list[bool]
    source_value: list[int]
    post_hook_context: Any = None
    post_transform_a: Any = None
    post_transform_b: Any = None
    materialization_kind: int = int(MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION)
    generation_counter: int = 0
    active_source_extent: int = 0
    last_changed_source: int = 0
    base_or_fallback: int = 0
    materialized: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.source_generation, list):
            raise TypeError("source_generation must be a list")
        if not isinstance(self.source_active, list):
            raise TypeError("source_active must be a list")
        if not isinstance(self.source_value, list):
            raise TypeError("source_value must be a list")
        if not (
            len(self.source_generation)
            == len(self.source_active)
            == len(self.source_value)
        ):
            raise ValueError(
                "source_generation/source_active/source_value must have equal lengths"
            )
        for index in range(len(self.source_generation)):
            _require_int(self.source_generation[index], f"source_generation[{index}]")
            if self.source_generation[index] < 0:
                raise ValueError(f"source_generation[{index}] must be >= 0")
            if not isinstance(self.source_active[index], bool):
                raise TypeError(
                    f"source_active[{index}] must be bool, "
                    f"got {type(self.source_active[index]).__name__}"
                )
            _require_qword_raw(
                self.source_value[index], f"source_value[{index}]"
            )
        for name in (
            "post_hook_context",
            "post_transform_a",
            "post_transform_b",
        ):
            _validate_json_value(getattr(self, name), name)
        _require_int(self.materialization_kind, "materialization_kind")
        if self.materialization_kind < 0:
            raise ValueError("materialization_kind must be >= 0")
        _require_int(self.generation_counter, "generation_counter")
        if self.generation_counter < 0:
            raise ValueError("generation_counter must be >= 0")
        _require_int(self.active_source_extent, "active_source_extent")
        if self.active_source_extent < 0:
            raise ValueError("active_source_extent must be >= 0")
        _require_int(self.last_changed_source, "last_changed_source")
        if self.last_changed_source < 0:
            raise ValueError("last_changed_source must be >= 0")
        _require_qword_raw(self.base_or_fallback, "base_or_fallback")
        _require_qword_raw(self.materialized, "materialized")

        # Defensive copy: caller-owned containers can never alias the entry.
        self.source_generation = list(self.source_generation)
        self.source_active = list(self.source_active)
        self.source_value = list(self.source_value)
        self.post_hook_context = _copy_json_value(self.post_hook_context)
        self.post_transform_a = _copy_json_value(self.post_transform_a)
        self.post_transform_b = _copy_json_value(self.post_transform_b)

    @classmethod
    def create_empty(
        cls,
        *,
        materialization_kind: int = int(
            MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
        ),
        base_or_fallback: int = 0,
    ) -> "PropertyEntry":
        """Create an entry with source slot 0 reserved and inactive.

        This keeps Handoff 11's mutable source-0 base path available without
        ever handing source 0 to modifier contribution allocation.
        """
        return cls(
            source_generation=[0],
            source_active=[False],
            source_value=[0],
            materialization_kind=materialization_kind,
            base_or_fallback=base_or_fallback,
            materialized=base_or_fallback,
        )

    @property
    def post_transform_context(self) -> Any:
        """Handoff 11 name for entry[+0x40]; Handoff 10 calls it post_hook_context.

        One neutral storage field, two evidence-era names.  Runtime semantics
        treat this opaque slot identically under either name.
        """
        return self.post_hook_context

    @post_transform_context.setter
    def post_transform_context(self, value: Any) -> None:
        _validate_json_value(value, "post_transform_context")
        self.post_hook_context = _copy_json_value(value)

    def clone(self) -> "PropertyEntry":
        return PropertyEntry(
            source_generation=list(self.source_generation),
            source_active=list(self.source_active),
            source_value=list(self.source_value),
            post_hook_context=_copy_json_value(self.post_hook_context),
            post_transform_a=_copy_json_value(self.post_transform_a),
            post_transform_b=_copy_json_value(self.post_transform_b),
            materialization_kind=self.materialization_kind,
            generation_counter=self.generation_counter,
            active_source_extent=self.active_source_extent,
            last_changed_source=self.last_changed_source,
            base_or_fallback=self.base_or_fallback,
            materialized=self.materialized,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JSON_SCHEMA,
            "kind": "PropertyEntry",
            "source_generation": list(self.source_generation),
            "source_active": list(self.source_active),
            "source_value": list(self.source_value),
            "post_hook_context": _copy_json_value(self.post_hook_context),
            "post_transform_a": _copy_json_value(self.post_transform_a),
            "post_transform_b": _copy_json_value(self.post_transform_b),
            "materialization_kind": self.materialization_kind,
            "generation_counter": self.generation_counter,
            "active_source_extent": self.active_source_extent,
            "last_changed_source": self.last_changed_source,
            "base_or_fallback": self.base_or_fallback,
            "materialized": self.materialized,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PropertyEntry":
        if not isinstance(data, Mapping):
            raise TypeError("PropertyEntry dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "PropertyEntry":
            raise ValueError(f"unsupported PropertyEntry dict: {data!r}")
        return cls(
            source_generation=list(data["source_generation"]),
            source_active=list(data["source_active"]),
            source_value=list(data["source_value"]),
            post_hook_context=data.get("post_hook_context"),
            post_transform_a=data.get("post_transform_a"),
            post_transform_b=data.get("post_transform_b"),
            materialization_kind=int(data.get("materialization_kind", 1)),
            generation_counter=int(data.get("generation_counter", 0)),
            active_source_extent=int(data.get("active_source_extent", 0)),
            last_changed_source=int(data.get("last_changed_source", 0)),
            base_or_fallback=int(data.get("base_or_fallback", 0)),
            materialized=int(data.get("materialized", 0)),
        )

    def trace_summary(self) -> str:
        return (
            f"property_entry:kind:{self.materialization_kind}:"
            f"sources:{len(self.source_value)}:active:{self.active_source_extent}:"
            f"materialized:0x{self.materialized & _QWORD_MAX:X}"
        )


@dataclass(frozen=True)
class ModifierPropertyContribution:
    """Ordered modifier-owned property contribution record (Handoffs 09/10).

    ``source_index`` is the stable PropertyEntry source-slot index; it is never
    an opaque separate key system.
    """

    modifier: ModifierRef
    target: EntityRef
    property_id: int
    source_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.modifier, ModifierRef):
            raise TypeError(
                f"modifier must be ModifierRef, got {type(self.modifier).__name__}"
            )
        if not isinstance(self.target, EntityRef):
            raise TypeError(
                f"target must be EntityRef, got {type(self.target).__name__}"
            )
        _require_int(self.property_id, "property_id")
        _require_int(self.source_index, "source_index")
        if self.source_index < 0:
            raise ValueError("source_index must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CONTRIBUTION_JSON_SCHEMA,
            "kind": "ModifierPropertyContribution",
            "modifier": self.modifier.to_dict(),
            "target": self.target.to_dict(),
            "property_id": self.property_id,
            "source_index": self.source_index,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierPropertyContribution":
        if not isinstance(data, Mapping):
            raise TypeError("ModifierPropertyContribution dict must be a mapping")
        if (
            data.get("schema") != CONTRIBUTION_JSON_SCHEMA
            or data.get("kind") != "ModifierPropertyContribution"
        ):
            raise ValueError(
                f"unsupported ModifierPropertyContribution dict: {data!r}"
            )
        return cls(
            modifier=ModifierRef.from_dict(data["modifier"]),
            target=EntityRef.from_dict(data["target"]),
            property_id=int(data["property_id"]),
            source_index=int(data["source_index"]),
        )

    def trace_summary(self) -> str:
        return (
            f"modifier_property_contribution:{self.modifier.trace_summary()}:"
            f"target:{self.target.runtime_id}:property:{self.property_id}:"
            f"source:{self.source_index}"
        )


@dataclass(frozen=True)
class PropertyChangeBoundary:
    """Deterministic post-materialization change boundary record.

    This is the observable boundary of ``_AfterPropertyChanged`` for sandbox
    scope: old materialized value, the source-slot mutation, rebuild, and the
    new materialized value.  Listener/event consumers remain UNKNOWN and are
    deliberately absent.
    """

    operation: str
    entity: EntityRef
    property_id: int
    source_index: int | None
    old_materialized: int
    new_materialized: int

    def __post_init__(self) -> None:
        if not isinstance(self.operation, str) or not self.operation:
            raise ValueError("operation must be a non-empty string")
        if not isinstance(self.entity, EntityRef):
            raise TypeError(
                f"entity must be EntityRef, got {type(self.entity).__name__}"
            )
        _require_int(self.property_id, "property_id")
        if self.source_index is not None:
            _require_int(self.source_index, "source_index")
            if self.source_index < 0:
                raise ValueError("source_index must be >= 0")
        _require_qword_raw(self.old_materialized, "old_materialized")
        _require_qword_raw(self.new_materialized, "new_materialized")

    def trace_summary(self) -> str:
        return (
            f"property_change_boundary:{self.operation}:"
            f"entity:{self.entity.runtime_id}:property:{self.property_id}:"
            f"source:{self.source_index}:"
            f"old:0x{self.old_materialized & _QWORD_MAX:X}:"
            f"new:0x{self.new_materialized & _QWORD_MAX:X}"
        )


# Handoff 10 / Handoff 11 neutral operation tags used by boundary records.
PROPERTY_BOUNDARY_SOURCE_ALLOCATED = "source_allocated"
PROPERTY_BOUNDARY_SOURCE_UPDATED = "source_updated"
PROPERTY_BOUNDARY_SOURCE_REMOVED = "source_removed"
PROPERTY_BOUNDARY_AFTER_PROPERTY_CHANGED = "after_property_changed"


@dataclass(frozen=True)
class StackPropertyTaskContext:
    """Opaque task-context projection needed by the StackProperty executor.

    Only the proven ``modifier_source`` dependency is materialized; the rest of
    the native TaskContext remains opaque.
    """

    modifier: ModifierState

    def __post_init__(self) -> None:
        if not isinstance(self.modifier, ModifierState):
            raise TypeError(
                f"modifier must be ModifierState, got {type(self.modifier).__name__}"
            )

    def trace_summary(self) -> str:
        return f"stack_property_task_context:{self.modifier.trace_summary()}"


@dataclass(frozen=True)
class StackPropertyTaskConfig:
    """StackProperty config projection consumed by the executor primitive.

    Target selection and DynamicValue payloads are evaluated before the
    executor primitive by the proven M506082 chain; this canonical config
    therefore only carries the property identity plus opaque payload slots.
    """

    property_id: int
    target_payload: Any = None
    dynamic_value_payload: Any = None

    def __post_init__(self) -> None:
        _require_int(self.property_id, "property_id")
        _validate_json_value(self.target_payload, "target_payload")
        _validate_json_value(self.dynamic_value_payload, "dynamic_value_payload")
        object.__setattr__(
            self, "target_payload", _copy_json_value(self.target_payload)
        )
        object.__setattr__(
            self, "dynamic_value_payload", _copy_json_value(self.dynamic_value_payload)
        )

    def trace_summary(self) -> str:
        return f"stack_property_task_config:property:{self.property_id}"


@dataclass(frozen=True)
class StackPropertyExecutor:
    """Canonical StackProperty generated-executor projection (M506081/M506082)."""

    task_context: StackPropertyTaskContext
    task_config: StackPropertyTaskConfig
    kind_marker: int = 0x7777

    def __post_init__(self) -> None:
        if not isinstance(self.task_context, StackPropertyTaskContext):
            raise TypeError(
                "task_context must be StackPropertyTaskContext, "
                f"got {type(self.task_context).__name__}"
            )
        if not isinstance(self.task_config, StackPropertyTaskConfig):
            raise TypeError(
                f"task_config must be StackPropertyTaskConfig, got {type(self.task_config).__name__}"
            )
        _require_int(self.kind_marker, "kind_marker")

    def trace_summary(self) -> str:
        return (
            f"stack_property_executor:marker:0x{self.kind_marker:X}:"
            f"{self.task_context.trace_summary()}:{self.task_config.trace_summary()}"
        )


@dataclass(frozen=True)
class StackPropertyTaskResult:
    """Ordered per-target StackProperty contribution projection."""

    task_completion: str
    applied_targets: tuple[EntityRef, ...]
    applied_source_indices: tuple[int | None, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.task_completion, str) or not self.task_completion:
            raise ValueError("task_completion must be a non-empty string")
        if not isinstance(self.applied_targets, tuple):
            raise TypeError("applied_targets must be a tuple")
        if not isinstance(self.applied_source_indices, tuple):
            raise TypeError("applied_source_indices must be a tuple")
        if len(self.applied_targets) != len(self.applied_source_indices):
            raise ValueError(
                "applied_targets and applied_source_indices must have equal lengths"
            )
        for target in self.applied_targets:
            if not isinstance(target, EntityRef):
                raise TypeError("applied_targets items must be EntityRef")
        for source_index in self.applied_source_indices:
            if source_index is not None:
                _require_int(source_index, "applied_source_indices item")
                if source_index < 0:
                    raise ValueError("applied source index must be >= 0")

    def trace_summary(self) -> str:
        return (
            f"stack_property_task_result:{self.task_completion}:"
            f"targets:{len(self.applied_targets)}:"
            f"sources:{self.applied_source_indices}"
        )


# A resolved target sequence from the Batch 05 selector is canonically a
# TargetSet.  Handoff 09 calls it a resolved_target_sequence; keep the alias
# explicit without introducing a second collection type.
ResolvedTargetSequence = TargetSet
