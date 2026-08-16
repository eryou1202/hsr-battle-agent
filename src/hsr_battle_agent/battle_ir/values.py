# -*- coding: utf-8 -*-
"""Canonical DynamicValue representation for Battle IR.

The representation is deliberately *not* an IL2CPP union-layout clone.  It is a
tagged, frozen, clone-friendly value cell:

* ValueType is the strict seven-value enum recovered from the 4.4.54 client.
* INT / FLOAT / BOOL keep their canonical scalar payload.
* ARRAY / MAP keep an ``ObjectRef`` whose equality is reference identity only.
* STRING keeps ``str | None``; game equality is ordinal UTF-16 content
  equality, implemented in ``hsr_battle_agent.battle_runtime.values``.
* NULL keeps ``None``.

``DynamicValue`` intentionally does **not** define Python ``__eq__`` because
Python container equality is deep equality, which would silently contradict the
E4 reference-identity semantics of ARRAY / MAP (and NULL != NULL).  Callers
must use the battle runtime primitive ``DynamicValueEquals``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


class DynamicValueType(IntEnum):
    """Recovered ``RPG.GameCore.DynamicValueType`` ordinals (4.4.54).

    Do not extend this enum without a new semantic recovery slice.
    """

    INT = 0
    FLOAT = 1
    BOOL = 2
    ARRAY = 3
    MAP = 4
    STRING = 5
    NULL = 6


@dataclass(frozen=True, eq=False)
class ObjectRef:
    """Stable object-identity handle.

    ARRAY / MAP equality is pointer/reference identity in the client.  This
    class is that identity made explicit.  Two ``ObjectRef`` values are equal
    iff their ``ref_id`` is equal; ``contents`` (optional future-heap
    metadata) never participates in equality or hashing.  Future Entity /
    Modifier / Array / Map heap models can use the same handle and move
    ``contents`` into a heap keyed by ``ref_id``.
    """

    ref_id: int
    contents: object = None

    def __post_init__(self) -> None:
        if isinstance(self.ref_id, bool) or not isinstance(self.ref_id, int):
            raise TypeError(f"ObjectRef.ref_id must be an int, got {type(self.ref_id).__name__}")
        if self.ref_id < 0:
            raise ValueError(f"ObjectRef.ref_id must be >= 0, got {self.ref_id}")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ObjectRef) and self.ref_id == other.ref_id

    def __hash__(self) -> int:
        return hash(("hsr.battle_ir.object_ref", self.ref_id))

    def __repr__(self) -> str:
        return f"ObjectRef(ref_id={self.ref_id})"


@dataclass(frozen=True)
class EvaluatorSpec:
    """Minimal predicate/evaluator operand representation (Batch 04).

    The 4.4.54 native bodies recover exactly one field for the runtime operand
    class behind ``type_reference 23221`` / class-pointer global
    ``0x95E2B08``: an 8-byte FixPoint raw qword at object offset +0x20.

    No other field is modeled and no ``__eq__`` is defined, because only the
    FixPoint comparison semantics are proven.  The object is immutable and
    clone-friendly so it can travel through ``PrimitiveCall`` inputs safely.
    """

    fixpoint_raw: int

    def __post_init__(self) -> None:
        if isinstance(self.fixpoint_raw, bool) or not isinstance(self.fixpoint_raw, int):
            raise TypeError(
                f"EvaluatorSpec.fixpoint_raw must be int, "
                f"got {type(self.fixpoint_raw).__name__}"
            )
        if not (-(2**63) <= self.fixpoint_raw <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError(
                f"EvaluatorSpec.fixpoint_raw out of qword raw range: {self.fixpoint_raw}"
            )

    def clone(self) -> "EvaluatorSpec":
        return EvaluatorSpec(self.fixpoint_raw)


@dataclass(frozen=True, eq=False)
class DynamicValue:
    """A canonical battle DynamicValue cell.

    ``payload`` meaning by tag:

    * INT   -> signed 64-bit ``int``
    * FLOAT -> IEEE-754 double ``float`` (NaN and +/-0.0 preserved)
    * BOOL  -> raw 8-byte union payload as signed 64-bit ``int``
    * ARRAY -> ``ObjectRef``
    * MAP   -> ``ObjectRef``
    * STRING-> ``str | None``
    * NULL  -> ``None``
    """

    value_type: DynamicValueType
    payload: object = None

    def __post_init__(self) -> None:
        value_type = self.value_type
        if not isinstance(value_type, DynamicValueType):
            if isinstance(value_type, bool) or not isinstance(value_type, int):
                raise TypeError(
                    f"value_type must be DynamicValueType or int 0..6, "
                    f"got {type(value_type).__name__}"
                )
            try:
                value_type = DynamicValueType(value_type)
            except ValueError as exc:
                raise ValueError(
                    f"unknown DynamicValueType tag {value_type}; "
                    "only 0..6 (INT..NULL) are recovered"
                ) from exc
            object.__setattr__(self, "value_type", value_type)

        payload = self.payload
        if value_type is DynamicValueType.INT:
            if isinstance(payload, bool) or not isinstance(payload, int):
                raise TypeError(f"INT payload must be int, got {type(payload).__name__}")
            if not (_INT64_MIN <= payload <= _INT64_MAX):
                raise ValueError(f"INT payload out of int64 range: {payload}")
        elif value_type is DynamicValueType.FLOAT:
            if not isinstance(payload, float):
                raise TypeError(f"FLOAT payload must be float, got {type(payload).__name__}")
        elif value_type is DynamicValueType.BOOL:
            if isinstance(payload, bool) or not isinstance(payload, int):
                raise TypeError(f"BOOL payload must be int (raw union value), got {type(payload).__name__}")
            if not (_INT64_MIN <= payload <= _INT64_MAX):
                raise ValueError(f"BOOL payload out of int64 range: {payload}")
        elif value_type in (DynamicValueType.ARRAY, DynamicValueType.MAP):
            if not isinstance(payload, ObjectRef):
                raise TypeError(
                    f"{value_type.name} payload must be ObjectRef (reference identity), "
                    f"got {type(payload).__name__}"
                )
        elif value_type is DynamicValueType.STRING:
            if payload is not None and not isinstance(payload, str):
                raise TypeError(f"STRING payload must be str or None, got {type(payload).__name__}")
        elif value_type is DynamicValueType.NULL:
            if payload is not None:
                raise TypeError(f"NULL payload must be None, got {type(payload).__name__}")
        else:  # pragma: no cover - enum is exhaustive
            raise AssertionError(f"unreachable value_type: {value_type!r}")

    @classmethod
    def int_value(cls, value: int) -> "DynamicValue":
        return cls(DynamicValueType.INT, value)

    @classmethod
    def float_value(cls, value: float) -> "DynamicValue":
        return cls(DynamicValueType.FLOAT, value)

    @classmethod
    def bool_value(cls, raw_union_value: int = 1) -> "DynamicValue":
        """Create a BOOL cell.

        The client compares ``(unionValue == 1)`` on both sides, so any raw
        union payload is representable here even though normal constructors
        write 0 or 1.
        """
        return cls(DynamicValueType.BOOL, raw_union_value)

    @classmethod
    def array_ref(cls, ref: ObjectRef) -> "DynamicValue":
        return cls(DynamicValueType.ARRAY, ref)

    @classmethod
    def map_ref(cls, ref: ObjectRef) -> "DynamicValue":
        return cls(DynamicValueType.MAP, ref)

    @classmethod
    def string_value(cls, value: str | None) -> "DynamicValue":
        return cls(DynamicValueType.STRING, value)

    @classmethod
    def null_value(cls) -> "DynamicValue":
        return cls(DynamicValueType.NULL, None)

    def clone(self) -> "DynamicValue":
        """Return an equal cell that preserves reference identity semantics."""
        return DynamicValue(self.value_type, self.payload)

    @property
    def tag(self) -> int:
        return self.value_type.value

    @property
    def tag_name(self) -> str:
        return self.value_type.name

    def __hash__(self) -> None:  # type: ignore[override]
        raise TypeError(f"{type(self).__name__} is intentionally unhashable")

    def __repr__(self) -> str:
        return f"DynamicValue({self.value_type.name}, {self.payload!r})"
