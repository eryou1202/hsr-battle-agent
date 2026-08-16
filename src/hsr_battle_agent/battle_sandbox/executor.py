# -*- coding: utf-8 -*-
"""Primitive executor: stable IR -> dispatch -> runtime -> result + trace."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hsr_battle_agent.battle_ir.model import PrimitiveCall, PrimitiveResult
from hsr_battle_agent.battle_ir.modifiers import (
    ModifierContainer,
    ModifierState,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_ir.values import DynamicValue
from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.errors import InvalidPrimitiveInputError
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry


class PrimitiveExecutor:
    def __init__(self, registry: PrimitiveRegistry) -> None:
        if not isinstance(registry, PrimitiveRegistry):
            raise TypeError(
                f"registry must be PrimitiveRegistry, got {type(registry).__name__}"
            )
        self._registry = registry

    @property
    def registry(self) -> PrimitiveRegistry:
        return self._registry

    def execute(
        self,
        primitive: PrimitiveCall,
        context: ExecutionContext,
    ) -> PrimitiveResult:
        if not isinstance(primitive, PrimitiveCall):
            raise TypeError(
                f"primitive must be PrimitiveCall, got {type(primitive).__name__}"
            )
        if not isinstance(context, ExecutionContext):
            raise TypeError(
                f"context must be ExecutionContext, got {type(context).__name__}"
            )

        registered = self._registry.resolve(primitive.primitive_id)
        try:
            ordered_inputs = registered.spec.validate_and_order_inputs(
                primitive.as_input_mapping()
            )
        except ValueError as exc:
            raise InvalidPrimitiveInputError(str(exc)) from exc

        input_tags = tuple(_input_tag(value) for value in ordered_inputs.values())
        started = context.trace.started(
            primitive_id=primitive.primitive_id,
            input_tags=input_tags,
            semantic_provenance_ref=registered.provenance_ref,
        )
        value = registered.implementation(context, ordered_inputs)
        context.trace.finished(started=started, result=value)
        return PrimitiveResult(
            primitive_id=primitive.primitive_id,
            value=value,
            semantic_result_type=registered.spec.result,
            runtime_result_type=type(value).__name__,
        )


def _input_tag(value: Any) -> str:
    if isinstance(value, DynamicValue):
        return f"DynamicValue:{value.tag_name}"
    if isinstance(value, EntityRef):
        return value.trace_summary()
    if isinstance(value, TargetSet):
        return value.trace_summary()
    if isinstance(value, ModifierState):
        return value.trace_summary()
    if isinstance(value, ModifierContainer):
        return value.trace_summary()
    return type(value).__name__
