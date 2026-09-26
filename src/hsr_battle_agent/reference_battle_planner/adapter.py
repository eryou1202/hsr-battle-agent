"""Explicit transition families; M9 remains byte-for-byte owned by its v1 API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from hsr_battle_agent.battle_sandbox.custom_scenario import CustomScenario
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceContract, SandboxResourceTransaction, SandboxTransitionOutcome,
    plan_sandbox_resource_transition, query_sandbox_legal_actions,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.planner.generator import scenario_identity
from hsr_battle_agent.planner_search.api import PlannerRequest, plan as plan_resource
from hsr_battle_agent.planner_search.objective import PlannerObjective
from hsr_battle_agent.planner_search.policy import PlannerSearchPolicy, SCOPE as RESOURCE_SCOPE
from hsr_battle_agent.reference_sandbox import ReferenceBattleSession, ReferenceStepResult, SCOPE as BATTLE_SCOPE


class TransitionAdapter(Protocol):
    """Small scope-specific boundary, not a universal game executor."""

    @property
    def scope(self) -> str: ...

    def initial_identity(self) -> str: ...

    def snapshot(self) -> dict[str, Any]: ...

    def legal_actions(self) -> Any: ...

    def step(self, action_id: str) -> Any: ...

    def terminal_status(self) -> str: ...


@dataclass(frozen=True)
class ReferenceBattleAdapter:
    session: ReferenceBattleSession

    @property
    def scope(self) -> str:
        return BATTLE_SCOPE

    def initial_identity(self) -> str:
        return self.session.spec.identity

    def snapshot(self) -> dict[str, Any]:
        return self.session.snapshot().to_dict()

    def legal_actions(self) -> Any:
        return self.session.legal_actions()

    def commit(self, action_id: str) -> ReferenceStepResult:
        """Keep the exact M10 record available to planner replay."""
        return self.session.step(action_id)

    def step(self, action_id: str) -> "ReferenceBattleAdapter":
        return type(self)(self.commit(action_id).session)

    def terminal_status(self) -> str:
        return self.session.terminal_status()


@dataclass(frozen=True)
class ResourceV1Boundary:
    """M9 transition adapter using only the existing resource transaction API."""

    scenario: CustomScenario
    contract: SandboxResourceContract
    state: TerraBattleState | None = None

    @property
    def scope(self) -> str:
        return RESOURCE_SCOPE

    def initial_identity(self) -> str:
        return f"{scenario_identity(self.scenario)}:{self.contract.identity}"

    def snapshot(self) -> dict[str, Any]:
        return TerraSnapshotV2(state=self.state or self.scenario.initial_state,
                               policy_identity=self.scenario.policy_identity()).to_dict()

    def legal_actions(self) -> Any:
        return query_sandbox_legal_actions(
            self.contract, tuple(item.candidate_occurrence_id for item in self.contract.actions))

    def step(self, action_id: str) -> "ResourceV1Boundary":
        source = self.state or self.scenario.initial_state
        planned = plan_sandbox_resource_transition(
            source, self.scenario.policy_identity(), self.contract, self.legal_actions(), action_id)
        committed = SandboxResourceTransaction(self.contract, planned).commit(source)
        if committed.outcome is not SandboxTransitionOutcome.COMMITTED or committed.committed_state is None:
            raise ValueError(committed.reason or "resource transition rejected")
        return type(self)(self.scenario, self.contract, committed.committed_state)

    def terminal_status(self) -> str:
        return "UNDECLARED_IN_M9_SCOPE"

    def search(self, objective: PlannerObjective, policy: PlannerSearchPolicy) -> Any:
        if self.state is not None:
            raise ValueError("M9 public search starts only from its declared scenario initial state")
        return plan_resource(PlannerRequest(self.scenario, self.contract, objective, policy))
