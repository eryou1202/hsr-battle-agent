# -*- coding: utf-8 -*-
"""Battle runtime implementations over canonical Battle IR values.

Dependency direction:

    IR primitive -> executor dispatch -> battle_runtime implementation

Runtime functions must not import battle_sandbox or provenance decision logic.
"""
from __future__ import annotations

from hsr_battle_agent.battle_runtime.predicates import (
    evaluator_spec_fixpoint_equal_int32,
    evaluator_spec_fixpoint_equal_raw,
    evaluator_spec_fixpoint_not_equal_raw,
    evaluator_spec_from_fixpoint_raw,
    evaluator_spec_from_int32,
    fixpoint_equal,
    fixpoint_from_int32,
    fixpoint_greater,
    fixpoint_greater_equal,
    fixpoint_is_negative,
    fixpoint_is_positive,
    fixpoint_is_zero,
    fixpoint_less,
    fixpoint_less_equal,
    fixpoint_not_equal,
)
from hsr_battle_agent.battle_runtime.values import (
    dynamic_value_equals,
    dynamic_value_is_array,
    dynamic_value_is_map,
    dynamic_value_is_null,
    dynamic_value_string,
    dynamic_value_to_bool,
    dynamic_value_to_double,
    dynamic_value_to_float,
    dynamic_value_to_int,
    dynamic_value_to_long,
    dynamic_value_to_uint,
    dynamic_value_type,
)
from hsr_battle_agent.battle_runtime.targets import (
    collapse_required_single_or_null,
    collapse_single_or_null,
    context_owner_entity,
    context_task_action_target,
    game_entity_runtime_id,
    select_caster,
    select_none,
    select_task_action_target,
)
from hsr_battle_agent.battle_runtime.actions import (
    task_begin_immediate_success,
    task_begin_select_single_target,
    task_executor_base_ready_init,
    task_executor_init,
    task_reset_ready,
    task_reset_ready_clear_selected_target,
    task_state_read,
)

__all__ = [
    "dynamic_value_equals",
    "dynamic_value_is_array",
    "dynamic_value_is_map",
    "dynamic_value_is_null",
    "dynamic_value_string",
    "dynamic_value_to_bool",
    "dynamic_value_to_double",
    "dynamic_value_to_float",
    "dynamic_value_to_int",
    "dynamic_value_to_long",
    "dynamic_value_to_uint",
    "dynamic_value_type",
    "evaluator_spec_fixpoint_equal_int32",
    "evaluator_spec_fixpoint_equal_raw",
    "evaluator_spec_fixpoint_not_equal_raw",
    "evaluator_spec_from_fixpoint_raw",
    "evaluator_spec_from_int32",
    "fixpoint_equal",
    "fixpoint_from_int32",
    "fixpoint_greater",
    "fixpoint_greater_equal",
    "fixpoint_is_negative",
    "fixpoint_is_positive",
    "fixpoint_is_zero",
    "fixpoint_less",
    "fixpoint_less_equal",
    "fixpoint_not_equal",
    "collapse_required_single_or_null",
    "collapse_single_or_null",
    "context_owner_entity",
    "context_task_action_target",
    "game_entity_runtime_id",
    "select_caster",
    "select_none",
    "select_task_action_target",
    "task_begin_immediate_success",
    "task_begin_select_single_target",
    "task_executor_base_ready_init",
    "task_executor_init",
    "task_reset_ready",
    "task_reset_ready_clear_selected_target",
    "task_state_read",
]
