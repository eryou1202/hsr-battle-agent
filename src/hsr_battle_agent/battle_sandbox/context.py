# -*- coding: utf-8 -*-
"""Minimal execution context for battle IR primitives."""
from __future__ import annotations

from dataclasses import dataclass, field

from hsr_battle_agent.battle_sandbox.hash import logical_battle_hash
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.state import BattleState
from hsr_battle_agent.battle_sandbox.trace import ExecutionTrace


@dataclass
class ExecutionContext:
    """Carries state, RNG and trace sink for one sandbox branch.

    Deliberately no caster / target / skill / modifier / event fields yet:
    those enter only when a recovered semantic slice proves they are needed.
    """

    state: BattleState = field(default_factory=BattleState)
    rng: SandboxRng = field(default_factory=SandboxRng)
    trace: ExecutionTrace = field(default_factory=ExecutionTrace)

    def clone(self, *, copy_trace: bool = False) -> "ExecutionContext":
        """Clone an isolated branch.

        State and RNG are deep-copied.  Trace starts fresh by default so
        branches do not share observational output; pass ``copy_trace=True``
        to fork an existing trace (useful for debugging).
        """
        return ExecutionContext(
            state=self.state.clone(),
            rng=self.rng.clone(),
            trace=self.trace.clone() if copy_trace else ExecutionTrace(),
        )

    def state_hash(self) -> str:
        return logical_battle_hash(self.state.to_dict(), self.rng.to_dict())
