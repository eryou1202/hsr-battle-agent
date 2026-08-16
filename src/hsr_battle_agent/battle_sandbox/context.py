# -*- coding: utf-8 -*-
"""Minimal execution context for battle IR primitives."""
from __future__ import annotations

from dataclasses import dataclass, field

from hsr_battle_agent.battle_ir.targets import EntityRef
from hsr_battle_agent.battle_sandbox.hash import logical_battle_hash
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.state import BattleState
from hsr_battle_agent.battle_sandbox.trace import ExecutionTrace


@dataclass
class ExecutionContext:
    """Carries state, RNG and trace sink for one sandbox branch.

    Target Selector Batch 05 adds exactly the transient context entities whose
    native reads were proven (E4): ``task_action_target`` (TaskContext +0x48),
    ``owner_entity`` (TaskContext +0x70) and ``caster_entity`` (canonical
    materialization of TaskContext.get_CasterEntity).  These are single-frame
    execution inputs: they are copied by ``clone()`` for isolated branches but
    are intentionally **not** part of BattleState and not included in the
    logical state hash / snapshot.
    """

    state: BattleState = field(default_factory=BattleState)
    rng: SandboxRng = field(default_factory=SandboxRng)
    trace: ExecutionTrace = field(default_factory=ExecutionTrace)
    task_action_target: EntityRef | None = None
    owner_entity: EntityRef | None = None
    caster_entity: EntityRef | None = None

    def clone(self, *, copy_trace: bool = False) -> "ExecutionContext":
        """Clone an isolated branch.

        State and RNG are deep-copied; the transient target context entities
        are immutable values and are copied as values.  Trace starts fresh by
        default so branches do not share observational output; pass
        ``copy_trace=True`` to fork an existing trace (useful for debugging).
        """
        return ExecutionContext(
            state=self.state.clone(),
            rng=self.rng.clone(),
            trace=self.trace.clone() if copy_trace else ExecutionTrace(),
            task_action_target=self.task_action_target,
            owner_entity=self.owner_entity,
            caster_entity=self.caster_entity,
        )

    def state_hash(self) -> str:
        return logical_battle_hash(self.state.to_dict(), self.rng.to_dict())
