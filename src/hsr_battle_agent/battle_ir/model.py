# -*- coding: utf-8 -*-
"""Battle IR model: primitive specifications and execution nodes.

Runtime semantics (``PrimitiveSpec`` / ``PrimitiveCall``) are deliberately
separate from source provenance.  Nothing in this module knows about method
indices or native RVAs; those live in ``provenance.py`` and are evidence-only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DETERMINISM_DETERMINISTIC = "DETERMINISTIC"
RESULT_BOOLEAN = "boolean"

DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID = "battle.ir.value.dynamic_value_equals"
DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID = "battle.ir.value.dynamic_value_to_int"
DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID = "battle.ir.value.dynamic_value_to_uint"
DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID = "battle.ir.value.dynamic_value_to_long"
DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID = "battle.ir.value.dynamic_value_to_float"
DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID = "battle.ir.value.dynamic_value_to_double"
DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID = "battle.ir.value.dynamic_value_to_bool"
DYNAMIC_VALUE_TYPE_PRIMITIVE_ID = "battle.ir.value.dynamic_value_type"
DYNAMIC_VALUE_STRING_PRIMITIVE_ID = "battle.ir.value.dynamic_value_string"
DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID = "battle.ir.value.dynamic_value_is_array"
DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID = "battle.ir.value.dynamic_value_is_map"
DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID = "battle.ir.value.dynamic_value_is_null"

FIXPOINT_FROM_INT32_PRIMITIVE_ID = "battle.ir.value.fixpoint_from_int32"
FIXPOINT_EQUAL_PRIMITIVE_ID = "battle.ir.compare.fixpoint_equal"
FIXPOINT_NOT_EQUAL_PRIMITIVE_ID = "battle.ir.compare.fixpoint_not_equal"
FIXPOINT_LESS_PRIMITIVE_ID = "battle.ir.compare.fixpoint_less"
FIXPOINT_LESS_EQUAL_PRIMITIVE_ID = "battle.ir.compare.fixpoint_less_equal"
FIXPOINT_GREATER_PRIMITIVE_ID = "battle.ir.compare.fixpoint_greater"
FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID = "battle.ir.compare.fixpoint_greater_equal"
FIXPOINT_IS_ZERO_PRIMITIVE_ID = "battle.ir.predicate.fixpoint_is_zero"
FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID = "battle.ir.predicate.fixpoint_is_negative"
FIXPOINT_IS_POSITIVE_PRIMITIVE_ID = "battle.ir.predicate.fixpoint_is_positive"

EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID = (
    "battle.ir.predicate.evaluator_spec_from_int32"
)
EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID = (
    "battle.ir.predicate.evaluator_spec_from_fixpoint_raw"
)
EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID = (
    "battle.ir.predicate.evaluator_spec_fixpoint_equal_int32"
)
EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID = (
    "battle.ir.predicate.evaluator_spec_fixpoint_equal_raw"
)
EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID = (
    "battle.ir.predicate.evaluator_spec_fixpoint_not_equal_raw"
)

TARGET_CONTEXT_TASK_ACTION_TARGET_PRIMITIVE_ID = (
    "battle.ir.target.context_task_action_target"
)
TARGET_CONTEXT_OWNER_ENTITY_PRIMITIVE_ID = "battle.ir.target.context_owner_entity"
TARGET_SELECT_TASK_ACTION_TARGET_PRIMITIVE_ID = (
    "battle.ir.target.select_task_action_target"
)
TARGET_SELECT_CASTER_PRIMITIVE_ID = "battle.ir.target.select_caster"
TARGET_SELECT_NONE_PRIMITIVE_ID = "battle.ir.target.select_none"
TARGET_COLLAPSE_SINGLE_OR_NULL_PRIMITIVE_ID = (
    "battle.ir.target.collapse_single_or_null"
)
TARGET_COLLAPSE_REQUIRED_SINGLE_OR_NULL_PRIMITIVE_ID = (
    "battle.ir.target.collapse_required_single_or_null"
)
ENTITY_GAME_ENTITY_RUNTIME_ID_PRIMITIVE_ID = "battle.ir.entity.game_entity_runtime_id"


@dataclass(frozen=True)
class PrimitiveInputSpec:
    name: str
    type: str


@dataclass(frozen=True)
class PrimitiveSpec:
    """Semantic specification of one canonical Battle IR primitive.

    This is the runtime-facing description: id, name, inputs, read/write set,
    result type and determinism.  Source provenance is attached separately by
    the semantic-artifact layer.
    """

    primitive_id: str
    semantic_name: str
    description: str
    inputs: tuple[PrimitiveInputSpec, ...]
    context_reads: tuple[str, ...] = ()
    context_writes: tuple[str, ...] = ()
    result: str = RESULT_BOOLEAN
    determinism: str = DETERMINISM_DETERMINISTIC

    def __post_init__(self) -> None:
        if not isinstance(self.primitive_id, str) or not self.primitive_id:
            raise ValueError("primitive_id must be a non-empty string")
        if not isinstance(self.semantic_name, str) or not self.semantic_name:
            raise ValueError("semantic_name must be a non-empty string")
        names = [item.name for item in self.inputs]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate primitive input names: {names}")
        if any(not name for name in names):
            raise ValueError("primitive input names must be non-empty")

    @property
    def input_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.inputs)

    def validate_and_order_inputs(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Validate names and return values ordered by spec input order."""
        unknown = set(inputs) - set(self.input_names)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(
                f"primitive {self.primitive_id} got unknown inputs: {names}"
            )
        missing = set(self.input_names) - set(inputs)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(
                f"primitive {self.primitive_id} is missing inputs: {names}"
            )
        return {name: inputs[name] for name in self.input_names}

    def to_dict(self) -> dict[str, Any]:
        return {
            "primitive_id": self.primitive_id,
            "semantic_name": self.semantic_name,
            "description": self.description,
            "inputs": [{"name": item.name, "type": item.type} for item in self.inputs],
            "context_reads": list(self.context_reads),
            "context_writes": list(self.context_writes),
            "result": self.result,
            "determinism": self.determinism,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PrimitiveSpec":
        try:
            return cls(
                primitive_id=data["primitive_id"],
                semantic_name=data["semantic_name"],
                description=data["description"],
                inputs=tuple(
                    PrimitiveInputSpec(name=item["name"], type=item["type"])
                    for item in data["inputs"]
                ),
                context_reads=tuple(data.get("context_reads", ())),
                context_writes=tuple(data.get("context_writes", ())),
                result=data["result"],
                determinism=data["determinism"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid PrimitiveSpec dict: {exc}") from exc


@dataclass(frozen=True)
class PrimitiveArgument:
    name: str
    value: Any

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("PrimitiveArgument.name must be a non-empty string")


@dataclass(frozen=True)
class PrimitiveCall:
    """An executable IR node.

    ``arguments`` order is normalized by the executor against the registered
    ``PrimitiveSpec``, so callers may pass them in any order without changing
    execution semantics.
    """

    primitive_id: str
    arguments: tuple[PrimitiveArgument, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.primitive_id, str) or not self.primitive_id:
            raise ValueError("primitive_id must be a non-empty string")
        if not isinstance(self.arguments, tuple):
            raise TypeError("arguments must be a tuple of PrimitiveArgument")
        seen: set[str] = set()
        for argument in self.arguments:
            if not isinstance(argument, PrimitiveArgument):
                raise TypeError(
                    f"arguments must contain PrimitiveArgument, "
                    f"got {type(argument).__name__}"
                )
            if argument.name in seen:
                raise ValueError(
                    f"duplicate argument name in PrimitiveCall: {argument.name!r}"
                )
            seen.add(argument.name)

    @classmethod
    def create(cls, primitive_id: str, **inputs: Any) -> "PrimitiveCall":
        return cls(
            primitive_id=primitive_id,
            arguments=tuple(PrimitiveArgument(name, value) for name, value in inputs.items()),
        )

    def as_input_mapping(self) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for argument in self.arguments:
            if argument.name in mapping:
                # Defense-in-depth: PrimitiveCall construction already rejects
                # duplicates; as_input_mapping must never silently overwrite.
                raise ValueError(
                    f"duplicate argument name in PrimitiveCall: {argument.name!r}"
                )
            mapping[argument.name] = argument.value
        return mapping


@dataclass(frozen=True)
class PrimitiveResult:
    """Result of one primitive execution.

    ``semantic_result_type`` is the canonical IR result type declared by the
    registered ``PrimitiveSpec`` (for DynamicValueEquals: ``"boolean"``).
    ``runtime_result_type`` is optional Python debug metadata (``"bool"``) and
    must never be used as the canonical type.
    """

    primitive_id: str
    value: Any
    semantic_result_type: str
    runtime_result_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.primitive_id, str) or not self.primitive_id:
            raise ValueError("primitive_id must be a non-empty string")
        if not isinstance(self.semantic_result_type, str) or not self.semantic_result_type:
            raise ValueError("semantic_result_type must be a non-empty string")
        if self.runtime_result_type is not None:
            if not isinstance(self.runtime_result_type, str) or not self.runtime_result_type:
                raise ValueError("runtime_result_type must be a non-empty string or None")
