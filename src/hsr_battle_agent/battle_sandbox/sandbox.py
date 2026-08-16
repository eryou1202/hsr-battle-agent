# -*- coding: utf-8 -*-
"""Top-level sandbox API v0."""
from __future__ import annotations

from typing import Any

from hsr_battle_agent.battle_ir.model import PrimitiveCall, PrimitiveResult
from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.errors import StubNotImplementedError
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.snapshot import SandboxSnapshot, capture_snapshot
from hsr_battle_agent.battle_sandbox.state import BattleState
from hsr_battle_agent.battle_sandbox.trace import ExecutionTrace


class Sandbox:
    """Minimal Kernel 01 sandbox facade.

    Planner / MCTS style consumers depend on this API and the
    ``PrimitiveExecutor``, not on individual runtime Python functions.
    """

    def __init__(
        self,
        registry: PrimitiveRegistry | None = None,
        seed: int | None = None,
    ) -> None:
        self._registry = registry if registry is not None else PrimitiveRegistry.create_default()
        self._executor = PrimitiveExecutor(self._registry)
        self._context = ExecutionContext(
            state=BattleState(),
            rng=SandboxRng(seed=seed),
            trace=ExecutionTrace(),
        )

    @property
    def registry(self) -> PrimitiveRegistry:
        return self._registry

    @property
    def context(self) -> ExecutionContext:
        return self._context

    def reset(self, seed: int | None = None) -> None:
        self._context = ExecutionContext(
            state=BattleState(),
            rng=SandboxRng(seed=seed),
            trace=ExecutionTrace(),
        )

    def clone(self) -> "Sandbox":
        branch = object.__new__(type(self))
        branch._registry = self._registry
        branch._executor = PrimitiveExecutor(self._registry)
        branch._context = self._context.clone()
        return branch

    def execute(self, primitive: str | PrimitiveCall, **inputs: Any) -> PrimitiveResult:
        """Execute one IR primitive.

        Accepts either ``PrimitiveCall`` or ``("primitive_id", lhs=..., rhs=...)``.
        """
        if isinstance(primitive, str):
            call = PrimitiveCall.create(primitive, **inputs)
        elif isinstance(primitive, PrimitiveCall):
            if inputs:
                raise ValueError(
                    "inputs keyword arguments are only allowed with a primitive_id string"
                )
            call = primitive
        else:
            raise TypeError(
                "primitive must be a primitive_id str or PrimitiveCall, "
                f"got {type(primitive).__name__}"
            )
        return self._executor.execute(call, self._context)

    def snapshot(self) -> SandboxSnapshot:
        return capture_snapshot(self._context)

    def restore(self, snapshot: SandboxSnapshot) -> None:
        if not isinstance(snapshot, SandboxSnapshot):
            raise TypeError(
                f"snapshot must be SandboxSnapshot, got {type(snapshot).__name__}"
            )
        self._context = snapshot.restore_context()

    def state_hash(self) -> str:
        return self._context.state_hash()

    def legal_actions(self) -> None:
        """Future surface.  Explicitly NOT_IMPLEMENTED in Kernel 01."""
        raise StubNotImplementedError("NOT_IMPLEMENTED: legal_actions needs recovered action semantics")

    def step(self, action: Any) -> None:
        """Future surface.  Explicitly NOT_IMPLEMENTED in Kernel 01."""
        del action
        raise StubNotImplementedError("NOT_IMPLEMENTED: step needs recovered battle state transitions")

    def is_terminal(self) -> None:
        """Future surface.  Explicitly NOT_IMPLEMENTED in Kernel 01."""
        raise StubNotImplementedError("NOT_IMPLEMENTED: is_terminal needs recovered terminal conditions")
