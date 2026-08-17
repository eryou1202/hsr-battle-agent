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
    ENTITY_GAME_ENTITY_RUNTIME_ID_PRIMITIVE_ID,
    TARGET_COLLAPSE_REQUIRED_SINGLE_OR_NULL_PRIMITIVE_ID,
    TARGET_COLLAPSE_SINGLE_OR_NULL_PRIMITIVE_ID,
    TARGET_CONTEXT_OWNER_ENTITY_PRIMITIVE_ID,
    TARGET_CONTEXT_TASK_ACTION_TARGET_PRIMITIVE_ID,
    TARGET_SELECT_CASTER_PRIMITIVE_ID,
    TARGET_SELECT_NONE_PRIMITIVE_ID,
    TARGET_SELECT_TASK_ACTION_TARGET_PRIMITIVE_ID,
    TASK_BEGIN_IMMEDIATE_SUCCESS_PRIMITIVE_ID,
    TASK_BEGIN_SELECT_SINGLE_TARGET_PRIMITIVE_ID,
    TASK_EXECUTOR_BASE_READY_INIT_PRIMITIVE_ID,
    TASK_EXECUTOR_INIT_PRIMITIVE_ID,
    TASK_RESET_READY_CLEAR_SELECTED_TARGET_PRIMITIVE_ID,
    TASK_RESET_READY_PRIMITIVE_ID,
    TASK_STATE_READ_PRIMITIVE_ID,
    ADD_MODIFIER_EXECUTOR_INIT_PRIMITIVE_ID,
    MODIFIER_TASK_BEGIN_APPLY_PRIMITIVE_ID,
    MODIFIER_APPLY_INSTANCE_PRIMITIVE_ID,
    MODIFIER_CONTAINER_GET_BY_INDEX_PRIMITIVE_ID,
    MODIFIER_CONTAINER_INDEX_OF_PRIMITIVE_ID,
    MODIFIER_CONTAINER_HAS_MODIFIER_BY_NAME_PRIMITIVE_ID,
    MODIFIER_CONTAINER_COUNT_PRIMITIVE_ID,
    MODIFIER_STATE_NAME_PRIMITIVE_ID,
    MODIFIER_STATE_COUNT_PRIMITIVE_ID,
    MODIFIER_STATE_STATE_RAW_PRIMITIVE_ID,
    MODIFIER_STATE_STACKING_FLAG_RAW_PRIMITIVE_ID,
    MODIFIER_STATE_CASTER_ENTITY_PRIMITIVE_ID,
    MODIFIER_STATE_LAYER_PRIMITIVE_ID,
    MODIFIER_STATE_MAX_LAYER_PRIMITIVE_ID,
    MODIFIER_STATE_CURRENT_LIFE_PRIMITIVE_ID,
    MODIFIER_STATE_SOURCE_ENTITY_PRIMITIVE_ID,
    MODIFIER_TRY_ADD_INSTANCE_PRIMITIVE_ID,
    MODIFIER_CONTAINER_FIND_INSTANCE_PRIMITIVE_ID,
    MODIFIER_MATCH_SEARCH_PRIMITIVE_ID,
    MODIFIER_LIFECYCLE_DESTROY_PRIMITIVE_ID,
    MODIFIER_CONTAINER_REMOVE_DIRTY_PRIMITIVE_ID,
    MODIFIER_LIFECYCLE_PROCESS_REDD_PRIMITIVE_ID,
    MODIFIER_LIFECYCLE_ON_ADDED_PRIMITIVE_ID,
    MODIFIER_LIFECYCLE_ON_ACTIVATE_PRIMITIVE_ID,
    STACK_PROPERTY_EXECUTOR_INIT_PRIMITIVE_ID,
    STACK_PROPERTY_EXECUTE_PRIMITIVE_ID,
    MODIFIER_STACK_PROPERTY_CONTRIBUTION_PRIMITIVE_ID,
    MODIFIER_POP_PROPERTY_CONTRIBUTIONS_PRIMITIVE_ID,
    COMPONENT_STACK_BOUNDARY_PRIMITIVE_ID,
    COMPONENT_UNSTACK_BOUNDARY_PRIMITIVE_ID,
    COMPONENT_STACK_SOURCE_PRIMITIVE_ID,
    UPDATE_CONTRIBUTION_SOURCE_PRIMITIVE_ID,
    REMOVE_CONTRIBUTION_SOURCE_PRIMITIVE_ID,
    ALLOCATE_SOURCE_SLOT_PRIMITIVE_ID,
    UPDATE_SOURCE_SLOT_PRIMITIVE_ID,
    REMOVE_SOURCE_SLOT_PRIMITIVE_ID,
    REBUILD_MATERIALIZED_PRIMITIVE_ID,
    MATERIALIZE_KIND_3_PRIMITIVE_ID,
    MATERIALIZE_KIND_4_PRIMITIVE_ID,
    MATERIALIZE_KIND_5_PRIMITIVE_ID,
    MATERIALIZE_KIND_6_PRIMITIVE_ID,
    MATERIALIZE_KIND_7_PRIMITIVE_ID,
    FIXPOINT_ADD_PRIMITIVE_ID,
    FIXPOINT_SUBTRACT_PRIMITIVE_ID,
    FIXPOINT_MULTIPLY_PRIMITIVE_ID,
    PROPERTY_APPLY_MODIFY_FUNCTION_PRIMITIVE_ID,
    PROPERTY_MODIFY_SOURCE_ZERO_UNTRANSFORMED_PRIMITIVE_ID,
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (
    RecoveredPrimitive,
)
from hsr_battle_agent.battle_runtime import actions as action_runtime
from hsr_battle_agent.battle_runtime import modifiers as modifier_runtime
from hsr_battle_agent.battle_runtime import predicates as predicate_runtime
from hsr_battle_agent.battle_runtime import property as property_runtime
from hsr_battle_agent.battle_runtime import targets as target_runtime
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
    return _named_unary_impl("value", function)


def _named_unary_impl(
    name: str, function: Callable[[Any], Any]
) -> PrimitiveImplementation:
    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        del context  # no state reads/writes in this primitive
        return function(inputs[name])

    return impl


def _context_impl(function: Callable[[ExecutionContext], Any]) -> PrimitiveImplementation:
    """Implementation whose only input is the executor's ExecutionContext."""

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        if inputs:
            raise ValueError("context primitives take no explicit inputs")
        return function(context)

    return impl


def _context_target_set_impl(
    function: Callable[[ExecutionContext], Any]
) -> PrimitiveImplementation:
    return _context_impl(function)


def _no_input_impl(function: Callable[[], Any]) -> PrimitiveImplementation:
    """Implementation that takes no explicit inputs and no context reads."""

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        del context
        if inputs:
            raise ValueError("no-input primitives take no explicit inputs")
        return function()

    return impl


def _modifier_state_write_impl(
    function: Callable[[Any, Any, Any], Any],
) -> PrimitiveImplementation:
    """Implementation that writes BattleState.modifier_state_by_entity.

    The function signature is ``(state, target, modifier)``.  The executor
    passes the live isolated branch state; the primitive returns the updated
    canonical container.
    """

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        return function(context.state, inputs["target"], inputs["modifier"])

    return impl


def _modifier_task_begin_impl(
    function: Callable[[Any, Any, Any, Any], Any],
) -> PrimitiveImplementation:
    """AddModifier OnTaskBegin boundary: ``(state, execution, targets, modifier)``."""

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        return function(
            context.state,
            inputs["execution"],
            inputs["targets"],
            inputs["modifier"],
        )

    return impl


def _modifier_lifecycle_impl(
    function: Callable[..., Any],
    input_names: tuple[str, ...],
) -> PrimitiveImplementation:
    """Lifecycle implementation that reads/writes BattleState.

    The implementation receives ``(context.state, *named_inputs)``.
    """

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        return function(context.state, *(inputs[name] for name in input_names))

    return impl


def _modifier_lifecycle_no_state_impl(
    function: Callable[..., Any],
    input_names: tuple[str, ...],
) -> PrimitiveImplementation:
    """Lifecycle implementation that does not touch BattleState."""

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        del context
        return function(*(inputs[name] for name in input_names))

    return impl


def _property_entry_impl(
    function: Callable[..., Any],
    input_names: tuple[str, ...],
) -> PrimitiveImplementation:
    """Pure PropertyEntry helper (no BattleState, no boundary sink)."""

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        del context
        return function(*(inputs[name] for name in input_names))

    return impl


def _property_state_impl(
    function: Callable[..., Any],
    input_names: tuple[str, ...],
    *,
    with_boundary: bool = True,
) -> PrimitiveImplementation:
    """Property primitive that reads/writes BattleState.

    The implementation receives ``(context.state, *named_inputs)``.  For
    mutating primitives a boundary sink is attached so exactly one
    ``PropertyChangeBoundary`` is recorded per accepted mutation.
    """

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        boundary_sink = (
            context.trace.record_property_change_boundary if with_boundary else None
        )
        return function(
            context.state,
            *(inputs[name] for name in input_names),
            boundary_sink=boundary_sink,
        )

    return impl


def _property_state_no_boundary_impl(
    function: Callable[..., Any],
    input_names: tuple[str, ...],
) -> PrimitiveImplementation:
    """Property state primitive whose native body has no change boundary."""

    def impl(context: ExecutionContext, inputs: Mapping[str, Any]) -> Any:
        return function(context.state, *(inputs[name] for name in input_names))

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
    TARGET_CONTEXT_TASK_ACTION_TARGET_PRIMITIVE_ID: _context_impl(
        target_runtime.context_task_action_target
    ),
    TARGET_CONTEXT_OWNER_ENTITY_PRIMITIVE_ID: _context_impl(
        target_runtime.context_owner_entity
    ),
    TARGET_SELECT_TASK_ACTION_TARGET_PRIMITIVE_ID: _context_target_set_impl(
        target_runtime.select_task_action_target
    ),
    TARGET_SELECT_CASTER_PRIMITIVE_ID: _context_target_set_impl(
        target_runtime.select_caster
    ),
    TARGET_SELECT_NONE_PRIMITIVE_ID: _context_target_set_impl(
        target_runtime.select_none
    ),
    TARGET_COLLAPSE_SINGLE_OR_NULL_PRIMITIVE_ID: _named_unary_impl(
        "targets", target_runtime.collapse_single_or_null
    ),
    TARGET_COLLAPSE_REQUIRED_SINGLE_OR_NULL_PRIMITIVE_ID: _named_unary_impl(
        "targets", target_runtime.collapse_required_single_or_null
    ),
    ENTITY_GAME_ENTITY_RUNTIME_ID_PRIMITIVE_ID: _named_unary_impl(
        "entity", target_runtime.game_entity_runtime_id
    ),
    TASK_EXECUTOR_INIT_PRIMITIVE_ID: _named_unary_impl(
        "config", action_runtime.task_executor_init
    ),
    TASK_BEGIN_IMMEDIATE_SUCCESS_PRIMITIVE_ID: _named_unary_impl(
        "execution", action_runtime.task_begin_immediate_success
    ),
    TASK_RESET_READY_PRIMITIVE_ID: _named_unary_impl(
        "execution", action_runtime.task_reset_ready
    ),
    TASK_STATE_READ_PRIMITIVE_ID: _named_unary_impl(
        "execution", action_runtime.task_state_read
    ),
    TASK_EXECUTOR_BASE_READY_INIT_PRIMITIVE_ID: _no_input_impl(
        action_runtime.task_executor_base_ready_init
    ),
    TASK_BEGIN_SELECT_SINGLE_TARGET_PRIMITIVE_ID: _named_binary_impl(
        ("execution", "targets"),
        action_runtime.task_begin_select_single_target,
    ),
    TASK_RESET_READY_CLEAR_SELECTED_TARGET_PRIMITIVE_ID: _named_unary_impl(
        "execution", action_runtime.task_reset_ready_clear_selected_target
    ),
    ADD_MODIFIER_EXECUTOR_INIT_PRIMITIVE_ID: _named_unary_impl(
        "config", action_runtime.task_executor_init
    ),
    MODIFIER_TASK_BEGIN_APPLY_PRIMITIVE_ID: _modifier_task_begin_impl(
        modifier_runtime.add_modifier_task_begin_apply
    ),
    MODIFIER_APPLY_INSTANCE_PRIMITIVE_ID: _modifier_state_write_impl(
        modifier_runtime.apply_modifier_instance
    ),
    MODIFIER_CONTAINER_GET_BY_INDEX_PRIMITIVE_ID: _named_binary_impl(
        ("container", "index"),
        modifier_runtime.modifier_container_get_by_index,
    ),
    MODIFIER_CONTAINER_INDEX_OF_PRIMITIVE_ID: _named_binary_impl(
        ("container", "modifier"),
        modifier_runtime.modifier_container_index_of,
    ),
    MODIFIER_CONTAINER_HAS_MODIFIER_BY_NAME_PRIMITIVE_ID: _named_binary_impl(
        ("container", "name"),
        modifier_runtime.modifier_container_has_modifier_by_name,
    ),
    MODIFIER_CONTAINER_COUNT_PRIMITIVE_ID: _named_unary_impl(
        "container", modifier_runtime.modifier_container_count
    ),
    MODIFIER_STATE_NAME_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_name
    ),
    MODIFIER_STATE_COUNT_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_count
    ),
    MODIFIER_STATE_STATE_RAW_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_state_raw
    ),
    MODIFIER_STATE_STACKING_FLAG_RAW_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_stacking_flag_raw
    ),
    MODIFIER_STATE_CASTER_ENTITY_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_caster_entity
    ),
    MODIFIER_STATE_LAYER_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_layer
    ),
    MODIFIER_STATE_MAX_LAYER_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_max_layer
    ),
    MODIFIER_STATE_CURRENT_LIFE_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_current_life
    ),
    MODIFIER_STATE_SOURCE_ENTITY_PRIMITIVE_ID: _named_unary_impl(
        "modifier", modifier_runtime.modifier_state_source_entity
    ),
    MODIFIER_TRY_ADD_INSTANCE_PRIMITIVE_ID: _modifier_lifecycle_impl(
        modifier_runtime.try_add_modifier_instance,
        (
            "target",
            "modifier",
            "stacking",
            "stacking_flag",
            "caster_entity",
            "source_provider_ref",
            "activate",
        ),
    ),
    MODIFIER_CONTAINER_FIND_INSTANCE_PRIMITIVE_ID: _modifier_lifecycle_no_state_impl(
        modifier_runtime.modifier_container_find,
        ("container", "match_key", "state_filter"),
    ),
    MODIFIER_MATCH_SEARCH_PRIMITIVE_ID: _modifier_lifecycle_no_state_impl(
        modifier_runtime.modifier_match_search,
        ("modifier", "match_key", "state_filter"),
    ),
    MODIFIER_LIFECYCLE_DESTROY_PRIMITIVE_ID: _modifier_lifecycle_impl(
        modifier_runtime.destroy_modifier_instance,
        ("target", "modifier", "destroy_arg"),
    ),
    MODIFIER_CONTAINER_REMOVE_DIRTY_PRIMITIVE_ID: _modifier_lifecycle_impl(
        modifier_runtime.remove_dirty_modifiers,
        ("target",),
    ),
    MODIFIER_LIFECYCLE_PROCESS_REDD_PRIMITIVE_ID: _modifier_lifecycle_impl(
        modifier_runtime.process_modifier_redd,
        ("target", "modifier", "stacking", "new_count", "new_life"),
    ),
    MODIFIER_LIFECYCLE_ON_ADDED_PRIMITIVE_ID: _modifier_lifecycle_no_state_impl(
        modifier_runtime.on_added_modifier,
        ("modifier",),
    ),
    MODIFIER_LIFECYCLE_ON_ACTIVATE_PRIMITIVE_ID: _modifier_lifecycle_impl(
        modifier_runtime.on_activate_modifier,
        ("target", "modifier"),
    ),
    # Handoff 09 + 10 modifier-owned property contribution lifecycle.
    STACK_PROPERTY_EXECUTOR_INIT_PRIMITIVE_ID: _modifier_lifecycle_no_state_impl(
        property_runtime.stack_property_executor_init,
        ("task_context", "task_config"),
    ),
    STACK_PROPERTY_EXECUTE_PRIMITIVE_ID: _property_state_impl(
        property_runtime.stack_property_execute,
        ("executor", "selected_targets", "evaluated_property_value"),
    ),
    MODIFIER_STACK_PROPERTY_CONTRIBUTION_PRIMITIVE_ID: _property_state_impl(
        property_runtime.stack_property_contribution,
        (
            "modifier",
            "property_id",
            "value",
            "target_component",
            "context_token",
            "is_refresh",
        ),
    ),
    MODIFIER_POP_PROPERTY_CONTRIBUTIONS_PRIMITIVE_ID: _property_state_impl(
        property_runtime.pop_property_contributions,
        ("modifier",),
    ),
    COMPONENT_STACK_BOUNDARY_PRIMITIVE_ID: _property_state_impl(
        property_runtime.component_stack_boundary,
        ("component", "property_id", "value", "context_token"),
    ),
    COMPONENT_UNSTACK_BOUNDARY_PRIMITIVE_ID: _property_state_impl(
        property_runtime.component_unstack_boundary,
        ("component", "property_id", "contribution_key", "owner_modifier"),
    ),
    # Handoff 10 source-slot/materialization runtime.
    COMPONENT_STACK_SOURCE_PRIMITIVE_ID: _property_state_impl(
        property_runtime.component_stack_source,
        ("component", "property_id", "runtime_value", "context_token"),
    ),
    UPDATE_CONTRIBUTION_SOURCE_PRIMITIVE_ID: _property_state_impl(
        property_runtime.update_contribution_source,
        (
            "component",
            "property_id",
            "source_index",
            "new_source_value",
            "context_token",
        ),
    ),
    REMOVE_CONTRIBUTION_SOURCE_PRIMITIVE_ID: _property_state_impl(
        property_runtime.remove_contribution_source,
        ("component", "property_id", "source_index", "context_token"),
    ),
    ALLOCATE_SOURCE_SLOT_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.allocate_source_slot,
        ("property_entry", "source_value"),
    ),
    UPDATE_SOURCE_SLOT_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.update_source_slot,
        ("property_entry", "source_index", "source_value"),
    ),
    REMOVE_SOURCE_SLOT_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.remove_source_slot,
        ("property_entry", "source_index"),
    ),
    REBUILD_MATERIALIZED_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.rebuild_materialized,
        ("property_entry",),
    ),
    MATERIALIZE_KIND_3_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.materialize_kind_3,
        ("property_entry",),
    ),
    MATERIALIZE_KIND_4_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.materialize_kind_4,
        ("property_entry",),
    ),
    MATERIALIZE_KIND_5_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.materialize_kind_5,
        ("property_entry",),
    ),
    MATERIALIZE_KIND_6_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.materialize_kind_6,
        ("property_entry",),
    ),
    MATERIALIZE_KIND_7_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.materialize_kind_7,
        ("property_entry",),
    ),
    # Handoff 11 fixed-point mutation runtime.
    FIXPOINT_ADD_PRIMITIVE_ID: _named_binary_impl(
        ("left", "right"), property_runtime.fixedpoint_add
    ),
    FIXPOINT_SUBTRACT_PRIMITIVE_ID: _named_binary_impl(
        ("left", "right"), property_runtime.fixedpoint_subtract
    ),
    FIXPOINT_MULTIPLY_PRIMITIVE_ID: _named_binary_impl(
        ("left", "right"), property_runtime.fixedpoint_multiply
    ),
    PROPERTY_APPLY_MODIFY_FUNCTION_PRIMITIVE_ID: _property_entry_impl(
        property_runtime.apply_modify_function,
        ("function_id", "old_materialized_value", "operand"),
    ),
    PROPERTY_MODIFY_SOURCE_ZERO_UNTRANSFORMED_PRIMITIVE_ID: _property_state_impl(
        property_runtime.modify_source_zero_untransformed,
        ("component", "property_id", "function_id", "operand", "context_token"),
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
