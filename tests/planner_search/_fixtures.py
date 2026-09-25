from __future__ import annotations

from decimal import Decimal

from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario, CustomTerminalRule, EmptySidePolicy, ResultPolicy,
    ScenarioParticipant, SimultaneousExhaustionPolicy,
)
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxActionRule, SandboxResourceContract, initialize_sandbox_resource_state,
)
from hsr_battle_agent.planner_search.objective import (
    AT_HORIZON, MIN_STEPS, REACH, PlannerObjective,
)
from hsr_battle_agent.planner_search.policy import PlannerSearchPolicy
from tests.battle_sandbox.test_transaction_plan import make_state
from tests.planner._fixtures import scenario_and_contract


def fixture(amount: str = "10"):
    return scenario_and_contract(amount)


def blocked_fixture():
    from tests.planner._fixtures import blocked_scenario_and_contract
    return blocked_scenario_and_contract()


def tied_fixture():
    contract = SandboxResourceContract(
        "tests.m9", "1", "source-order-tie", "actor-left", "energy",
        (
            SandboxActionRule("Z", "candidate-z", "actor-left", ("target",), Decimal("1")),
            SandboxActionRule("A", "candidate-a", "actor-left", ("target",), Decimal("1")),
        ),
    )
    state = initialize_sandbox_resource_state(make_state(), contract, amount="10", maximum="10")
    scenario = CustomScenario(
        stage_id=None,
        participants=(ScenarioParticipant("left", "left", 0), ScenarioParticipant("right", "right", 0)),
        initial_state=state,
        terminal_rule=CustomTerminalRule(
            "tests.m9", "1", "declared-local-terminal", EmptySidePolicy.TERMINAL,
            SimultaneousExhaustionPolicy.DRAW, ResultPolicy.REPORT_CUSTOM_OUTCOME,
        ),
    )
    return scenario, contract


def policy(depth: int = 2, nodes: int = 100, plans: int = 1):
    return PlannerSearchPolicy("tests.m9", "1", depth, nodes, plans)


def horizon(contract, comparison="MAXIMIZE"):
    return PlannerObjective("tests.m9", "1", AT_HORIZON, contract.resource_key, comparison=comparison)


def reach(contract, operator="LE", threshold="8", *, minimum_steps=False):
    return PlannerObjective(
        "tests.m9", "1", MIN_STEPS if minimum_steps else REACH,
        contract.resource_key, operator=operator, threshold=Decimal(threshold),
    )
