# -*- coding: utf-8 -*-
"""Small primitive registry: primitive_id -> implementation.

Bootstrap path (source of truth is the explicit semantic catalog):

    catalog.json
      -> artifact validation (schema + sha256 + enabled)
      -> validated RecoveredPrimitive(spec, provenance) list
      -> explicit implementation binding by primitive_id
      -> frozen PrimitiveRegistry

``create_default`` performs this bootstrap exactly once (cached).  Execution
paths never read the catalog or artifact files and never touch bootstrap code.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from hsr_battle_agent.battle_ir.catalog import load_catalog_primitives
from hsr_battle_agent.battle_ir.model import (
    DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID,
    DYNAMIC_VALUE_STRING_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TYPE_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_EQUAL_PRIMITIVE_ID,
    FIXPOINT_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID,
    FIXPOINT_GREATER_PRIMITIVE_ID,
    FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID,
    FIXPOINT_IS_POSITIVE_PRIMITIVE_ID,
    FIXPOINT_IS_ZERO_PRIMITIVE_ID,
    FIXPOINT_LESS_EQUAL_PRIMITIVE_ID,
    FIXPOINT_LESS_PRIMITIVE_ID,
    FIXPOINT_NOT_EQUAL_PRIMITIVE_ID,
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (
    RecoveredPrimitive,
)
from hsr_battle_agent.battle_runtime import predicates as predicate_runtime
from hsr_battle_agent.battle_runtime import values as dynamic_value_runtime
from hsr_battle_agent.battle_sandbox.errors import (
    DuplicatePrimitiveError,
    FrozenRegistryError,
    UnsupportedPrimitiveError,
)
from hsr_battle_agent.battle_sandbox.context import ExecutionContext

PrimitiveImplementation = Callable[[ExecutionContext, Mapping[str, Any]], Any]


def _binary_impl(function: Callable[[Any, Any], Any]) -> PrimitiveImplementation:
    return _named_binary_impl(("lhs", "rhs"), function)


def _named_binary_impl(
    names: tuple[str, str], function: Callable[[Any, Any], Any]
) -> PrimitiveImplementation:
    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        del context  # no state reads/writes in this primitive
        first_name, second_name = names
        return function(inputs[first_name], inputs[second_name])

    return impl


def _unary_impl(function: Callable[[Any], Any]) -> PrimitiveImplementation:
    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        del context  # no state reads/writes in this primitive
        return function(inputs["value"])

    return impl


# Explicit implementation bindings.  This mapping contains no semantic spec and
# no provenance: those come exclusively from the validated semantic artifacts.
DEFAULT_IMPLEMENTATION_BINDINGS: Mapping[str, PrimitiveImplementation] = {
    DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID: _binary_impl(
        dynamic_value_runtime.dynamic_value_equals
    ),
    DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_to_int
    ),
    DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_to_uint
    ),
    DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_to_long
    ),
    DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_to_float
    ),
    DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_to_double
    ),
    DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_to_bool
    ),
    DYNAMIC_VALUE_TYPE_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_type
    ),
    DYNAMIC_VALUE_STRING_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_string
    ),
    DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_is_array
    ),
    DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_is_map
    ),
    DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID: _unary_impl(
        dynamic_value_runtime.dynamic_value_is_null
    ),
    FIXPOINT_FROM_INT32_PRIMITIVE_ID: _unary_impl(
        predicate_runtime.fixpoint_from_int32
    ),
    FIXPOINT_EQUAL_PRIMITIVE_ID: _binary_impl(predicate_runtime.fixpoint_equal),
    FIXPOINT_NOT_EQUAL_PRIMITIVE_ID: _binary_impl(
        predicate_runtime.fixpoint_not_equal
    ),
    FIXPOINT_LESS_PRIMITIVE_ID: _binary_impl(predicate_runtime.fixpoint_less),
    FIXPOINT_LESS_EQUAL_PRIMITIVE_ID: _binary_impl(
        predicate_runtime.fixpoint_less_equal
    ),
    FIXPOINT_GREATER_PRIMITIVE_ID: _binary_impl(
        predicate_runtime.fixpoint_greater
    ),
    FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID: _binary_impl(
        predicate_runtime.fixpoint_greater_equal
    ),
    FIXPOINT_IS_ZERO_PRIMITIVE_ID: _unary_impl(
        predicate_runtime.fixpoint_is_zero
    ),
    FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID: _unary_impl(
        predicate_runtime.fixpoint_is_negative
    ),
    FIXPOINT_IS_POSITIVE_PRIMITIVE_ID: _unary_impl(
        predicate_runtime.fixpoint_is_positive
    ),
    EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID: _unary_impl(
        predicate_runtime.evaluator_spec_from_int32
    ),
    EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID: _unary_impl(
        predicate_runtime.evaluator_spec_from_fixpoint_raw
    ),
    EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID: _named_binary_impl(
        ("evaluator_spec", "rhs"),
        predicate_runtime.evaluator_spec_fixpoint_equal_int32,
    ),
    EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID: _named_binary_impl(
        ("evaluator_spec", "rhs"),
        predicate_runtime.evaluator_spec_fixpoint_equal_raw,
    ),
    EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID: _named_binary_impl(
        ("evaluator_spec", "rhs"),
        predicate_runtime.evaluator_spec_fixpoint_not_equal_raw,
    ),
}


@dataclass(frozen=True)
class RegisteredPrimitive:
    spec: PrimitiveSpec
    implementation: PrimitiveImplementation
    provenance_ref: str | None = None


class PrimitiveRegistry:
    """Explicit-failure registry.

    Unknown primitive ids raise ``UnsupportedPrimitiveError``; the sandbox
    never silently no-ops.
    """

    def __init__(self) -> None:
        self._entries: dict[str, RegisteredPrimitive] = {}
        self._frozen = False

    @property
    def frozen(self) -> bool:
        return self._frozen

    def register(
        self,
        spec: PrimitiveSpec,
        implementation: PrimitiveImplementation,
        provenance_ref: str | None = None,
    ) -> None:
        if self._frozen:
            raise FrozenRegistryError()
        if not isinstance(spec, PrimitiveSpec):
            raise TypeError(f"spec must be PrimitiveSpec, got {type(spec).__name__}")
        if not callable(implementation):
            raise TypeError("implementation must be callable")
        if spec.primitive_id in self._entries:
            raise DuplicatePrimitiveError(spec.primitive_id)
        self._entries[spec.primitive_id] = RegisteredPrimitive(
            spec=spec,
            implementation=implementation,
            provenance_ref=provenance_ref,
        )

    def bind_recovered_primitive(
        self,
        recovered: RecoveredPrimitive,
        implementation: PrimitiveImplementation,
    ) -> None:
        """Register an artifact-validated primitive with its real provenance.

        The semantic spec and provenance reference are taken from
        ``RecoveredPrimitive``; no caller-supplied copies are used.
        """
        if not isinstance(recovered, RecoveredPrimitive):
            raise TypeError(
                f"recovered must be RecoveredPrimitive, got {type(recovered).__name__}"
            )
        self.register(
            spec=recovered.spec,
            implementation=implementation,
            provenance_ref=recovered.provenance.source_reference(),
        )

    def freeze(self) -> None:
        self._frozen = True

    def resolve(self, primitive_id: str) -> RegisteredPrimitive:
        try:
            return self._entries[primitive_id]
        except KeyError:
            raise UnsupportedPrimitiveError(primitive_id) from None

    def get_spec(self, primitive_id: str) -> PrimitiveSpec:
        return self.resolve(primitive_id).spec

    @property
    def known_primitive_ids(self) -> tuple[str, ...]:
        return tuple(self._entries)

    @classmethod
    @lru_cache(maxsize=1)
    def create_default(cls) -> "PrimitiveRegistry":
        """Bootstrap the runtime from the validated semantic catalog.

        Disk access happens only here, at registry setup time, and the returned
        frozen registry is cached so the catalog/artifacts are loaded once per
        process.  Execution never re-reads the catalog.
        """
        recovered_primitives = load_catalog_primitives()
        if not recovered_primitives:
            raise UnsupportedPrimitiveError("<empty semantic catalog>")
        registry = cls()
        for recovered in recovered_primitives:
            primitive_id = recovered.spec.primitive_id
            try:
                implementation = DEFAULT_IMPLEMENTATION_BINDINGS[primitive_id]
            except KeyError:
                raise UnsupportedPrimitiveError(primitive_id) from None
            registry.bind_recovered_primitive(recovered, implementation)
        registry.freeze()
        return registry
