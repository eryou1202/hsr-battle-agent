# -*- coding: utf-8 -*-
"""Battle IR model: primitive specifications and execution nodes.

Runtime semantics (``PrimitiveSpec`` / ``PrimitiveCall``) are deliberately
separate from source provenance.  Nothing in this module knows about method
indices or native RVAs; those live in ``provenance.py`` and are evidence-only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

DETERMINISM_DETERMINISTIC = "DETERMINISTIC"
RESULT_BOOLEAN = "boolean"

DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID = "battle.ir.value.dynamic_value_equals"


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


DYNAMIC_VALUE_EQUALS_SPEC = PrimitiveSpec(
    primitive_id=DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
    semantic_name="DynamicValueEquals",
    description=(
        "Tag-aware equality over two RPG.GameCore.DynamicValue cells"
    ),
    inputs=(
        PrimitiveInputSpec(name="lhs", type="DynamicValue"),
        PrimitiveInputSpec(name="rhs", type="DynamicValue"),
    ),
    context_reads=("lhs", "rhs"),
    context_writes=(),
    result=RESULT_BOOLEAN,
    determinism=DETERMINISM_DETERMINISTIC,
)


@dataclass(frozen=True)
class PrimitiveArgument:
    name: str
    value: Any


@dataclass(frozen=True)
class PrimitiveCall:
    """An executable IR node.

    ``arguments`` order is normalized by the executor against the registered
    ``PrimitiveSpec``, so callers may pass them in any order without changing
    execution semantics.
    """

    primitive_id: str
    arguments: tuple[PrimitiveArgument, ...] = ()

    @classmethod
    def create(cls, primitive_id: str, **inputs: Any) -> "PrimitiveCall":
        if not isinstance(primitive_id, str) or not primitive_id:
            raise ValueError("primitive_id must be a non-empty string")
        return cls(
            primitive_id=primitive_id,
            arguments=tuple(PrimitiveArgument(name, value) for name, value in inputs.items()),
        )

    def as_input_mapping(self) -> dict[str, Any]:
        return {item.name: item.value for item in self.arguments}


@dataclass(frozen=True)
class PrimitiveResult:
    primitive_id: str
    value: Any
    result_type: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_type", type(self.value).__name__)
