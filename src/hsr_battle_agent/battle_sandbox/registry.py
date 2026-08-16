# -*- coding: utf-8 -*-
"""Small primitive registry: primitive_id -> implementation.

Bootstrap path (source of truth is the semantic artifact):

    semantic artifact JSON
      -> validated RecoveredPrimitive(spec, provenance)
      -> explicit implementation binding by primitive_id
      -> frozen PrimitiveRegistry

``create_default`` performs this bootstrap exactly once (cached).  Execution
paths never read the artifact file and never touch this bootstrap code.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from hsr_battle_agent.battle_ir.model import (
    DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (
    RecoveredPrimitive,
    load_vertical_slice_01,
)
from hsr_battle_agent.battle_sandbox.errors import (
    DuplicatePrimitiveError,
    FrozenRegistryError,
    UnsupportedPrimitiveError,
)
from hsr_battle_agent.battle_sandbox.context import ExecutionContext

PrimitiveImplementation = Callable[[ExecutionContext, Mapping[str, Any]], Any]


def _dynamic_value_equals_impl(
    context: ExecutionContext, inputs: Mapping[str, Any]
) -> Any:
    del context  # no state reads/writes in this primitive
    # Imported lazily only as a documentation of the dispatch boundary; the
    # module import itself is cheap and the registry is built once.
    from hsr_battle_agent.battle_runtime.values import dynamic_value_equals

    return dynamic_value_equals(inputs["lhs"], inputs["rhs"])


# Explicit implementation bindings.  This mapping contains no semantic spec and
# no provenance: those come exclusively from the semantic artifact.
DEFAULT_IMPLEMENTATION_BINDINGS: Mapping[str, PrimitiveImplementation] = {
    DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID: _dynamic_value_equals_impl,
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
        """Bootstrap Kernel 01 from the validated semantic artifact.

        Disk access happens only here, at registry setup time, and the returned
        frozen registry is cached so the artifact is loaded once per process.
        """
        recovered = load_vertical_slice_01()
        primitive_id = recovered.spec.primitive_id
        try:
            implementation = DEFAULT_IMPLEMENTATION_BINDINGS[primitive_id]
        except KeyError:
            raise UnsupportedPrimitiveError(primitive_id) from None
        registry = cls()
        registry.bind_recovered_primitive(recovered, implementation)
        registry.freeze()
        return registry
