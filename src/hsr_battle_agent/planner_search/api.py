"""Read-only Python entry point for local objective planning."""
from __future__ import annotations

from dataclasses import dataclass

from hsr_battle_agent.battle_sandbox.custom_scenario import CustomScenario
from hsr_battle_agent.battle_sandbox.sandbox_transition import SandboxResourceContract
from hsr_battle_agent.planner_search.objective import PlannerObjective
from hsr_battle_agent.planner_search.policy import PlannerSearchPolicy
from hsr_battle_agent.planner_search.result import PlannerResult
from hsr_battle_agent.planner_search.search import search_resource_plans


@dataclass(frozen=True)
class PlannerRequest:
    scenario: CustomScenario
    contract: SandboxResourceContract
    objective: PlannerObjective
    policy: PlannerSearchPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, CustomScenario) or not isinstance(self.contract, SandboxResourceContract):
            raise TypeError("PlannerRequest requires a custom scenario and sandbox resource contract")
        if not isinstance(self.objective, PlannerObjective) or not isinstance(self.policy, PlannerSearchPolicy):
            raise TypeError("PlannerRequest requires versioned objective and policy")


def plan(request: PlannerRequest) -> PlannerResult:
    if not isinstance(request, PlannerRequest):
        raise TypeError("plan requires PlannerRequest")
    return search_resource_plans(request.scenario, request.contract, request.objective, request.policy)
