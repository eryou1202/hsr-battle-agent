# -*- coding: utf-8 -*-
"""Battle runtime implementations over canonical Battle IR values.

Dependency direction:

    IR primitive -> executor dispatch -> battle_runtime implementation

Runtime functions must not import battle_sandbox or provenance decision logic.
"""
from __future__ import annotations

from hsr_battle_agent.battle_runtime.predicates import (
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
]
