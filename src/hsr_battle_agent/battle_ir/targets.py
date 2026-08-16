# -*- coding: utf-8 -*-
"""Target Batch 05 canonical entity / target-list representations.

Recovered native identity (see data/semantics/4.4.54/target_selector_batch_05.json):

* A target-selection result is an entity object pointer (runtime
  type_reference ``202024``).  Its stable logical identity is the signed
  int32 ``GameEntity.RuntimeID`` read at native offset ``+0xD0``
  (method_index 499138, RVA ``0xE61B860``, E4).
* The runtime target container is an ordered IL2CPP list:
  ``+0x10`` items array, ``+0x18`` count, ``+0x1c`` version, items at
  ``[array + index*8 + 0x20]``.  Append order is proven, duplicates are never
  deduplicated, and individual elements may be null (the caster selector
  appends null; the task-action-target selector skips null).
* Therefore the canonical representation is a **tuple-backed ordered list**,
  deliberately named ``TargetSet`` for compatibility with the batch naming.
  It is never a Python ``set``: order, duplicates and nulls are semantic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

JSON_SCHEMA = "battle_ir_targets/1"


@dataclass(frozen=True)
class EntityRef:
    """Minimal immutable entity reference.

    Equality and hash use only ``runtime_id`` (the proven stable logical id).
    There is intentionally no Python object identity semantics and no full
    entity state model.
    """

    runtime_id: int

    def __post_init__(self) -> None:
        if isinstance(self.runtime_id, bool) or not isinstance(self.runtime_id, int):
            raise TypeError("EntityRef.runtime_id must be an int")

    def clone(self) -> "EntityRef":
        """Clone-friendly: frozen value returns itself."""
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"schema": JSON_SCHEMA, "kind": "EntityRef", "runtime_id": self.runtime_id}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EntityRef":
        if not isinstance(data, Mapping):
            raise TypeError("EntityRef dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "EntityRef":
            raise ValueError(f"unsupported EntityRef dict: {data!r}")
        return cls(runtime_id=int(data["runtime_id"]))

    def trace_summary(self) -> str:
        return f"entity_ref:{self.runtime_id}"


@dataclass(frozen=True)
class TargetSet:
    """Ordered tuple-backed target collection (never Python ``set``).

    Order is append order.  Duplicates are preserved.  Elements are
    ``EntityRef`` or ``None``; null elements are allowed only where the
    recovered selector appends them.
    """

    items: tuple[EntityRef | None, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise TypeError("TargetSet.items must be a tuple")
        for item in self.items:
            if item is not None and not isinstance(item, EntityRef):
                raise TypeError(
                    f"TargetSet items must be EntityRef or None, got {type(item).__name__}"
                )

    @classmethod
    def of(cls, *items: EntityRef | None) -> "TargetSet":
        return cls(tuple(items))

    @classmethod
    def from_iterable(cls, items: Iterable[EntityRef | None]) -> "TargetSet":
        return cls(tuple(items))

    @property
    def count(self) -> int:
        return len(self.items)

    def clone(self) -> "TargetSet":
        """Clone-friendly: frozen value returns itself."""
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JSON_SCHEMA,
            "kind": "TargetSet",
            "items": [
                None if item is None else item.to_dict() for item in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TargetSet":
        if not isinstance(data, Mapping):
            raise TypeError("TargetSet dict must be a mapping")
        if data.get("schema") != JSON_SCHEMA or data.get("kind") != "TargetSet":
            raise ValueError(f"unsupported TargetSet dict: {data!r}")
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            raise TypeError("TargetSet.items must be a list in dict form")
        items = tuple(
            None if item is None else EntityRef.from_dict(item) for item in raw_items
        )
        return cls(items)

    def trace_summary(self) -> str:
        return f"target_count:{self.count}"
