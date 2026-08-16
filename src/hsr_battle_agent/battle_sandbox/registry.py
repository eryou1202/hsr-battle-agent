# -*- coding: utf-8 -*-
"""Small primitive registry: primitive_id -> implementation."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from hsr_battle_agent.battle_ir.model import DYNAMIC_VALUE_EQUALS_SPEC, PrimitiveSpec
from hsr_battle_agent.battle_sandbox.errors import (
    DuplicatePrimitiveError,
    FrozenRegistryError,
    UnsupportedPrimitiveError,
)
from hsr_battle_agent.battle_sandbox.context import ExecutionContext

PrimitiveImplementation = Callable[[ExecutionContext, Mapping[str, Any]], Any]

DYNAMIC_VALUE_EQUALS_PROVENANCE_REF = "4.4.54:RPG.GameCore.DynamicValue.Equals:74632"


def _dynamic_value_equals_impl(
    context: ExecutionContext, inputs: Mapping[str, Any]
) -> Any:
    del context  # no state reads/writes in this primitive
    # Imported lazily only as a documentation of the dispatch boundary; the
    # module import itself is cheap and the registry is built once.
    from hsr_battle_agent.battle_runtime.values import dynamic_value_equals

    return dynamic_value_equals(inputs["lhs"], inputs["rhs"])


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
    def create_default(cls) -> "PrimitiveRegistry":
        """Build the Kernel 01 registry (no disk access; hot-path safe)."""
        registry = cls()
        registry.register(
            spec=DYNAMIC_VALUE_EQUALS_SPEC,
            implementation=_dynamic_value_equals_impl,
            provenance_ref=DYNAMIC_VALUE_EQUALS_PROVENANCE_REF,
        )
        registry.freeze()
        return registry
