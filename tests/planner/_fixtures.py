from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario,
    CustomTerminalRule,
    EmptySidePolicy,
    ResultPolicy,
    ScenarioParticipant,
    SimultaneousExhaustionPolicy,
)
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxActionRule,
    SandboxResourceContract,
    initialize_sandbox_resource_state,
)
from hsr_battle_agent.planner.dataset import PlannerDataset
from hsr_battle_agent.planner.generator import GenerationPolicy, generate_trajectories
from tests.battle_sandbox.test_transaction_plan import make_state


@lru_cache(maxsize=None)
def contract() -> SandboxResourceContract:
    return SandboxResourceContract(
        "tests.m8",
        "1",
        "planner-resource-actions",
        "actor-left",
        "declared-energy",
        (
            SandboxActionRule("A", "candidate-a", "actor-left", ("target", None, "target"), Decimal("1")),
            SandboxActionRule("B", "candidate-b", "actor-left", ("target",), Decimal("2")),
            SandboxActionRule("C", "candidate-c", "actor-left", ("target",), Decimal("3")),
            SandboxActionRule("D", "candidate-d", "actor-left", ("target",), Decimal("4")),
        ),
    )


@lru_cache(maxsize=None)
def scenario_and_contract(amount: str = "10"):
    resource_contract = contract()
    state = initialize_sandbox_resource_state(
        make_state(), resource_contract, amount=amount, maximum="10"
    )
    scenario = CustomScenario(
        stage_id=None,
        participants=(
            ScenarioParticipant("left", "left", 0),
            ScenarioParticipant("right", "right", 0),
        ),
        initial_state=state,
        terminal_rule=CustomTerminalRule(
            "tests.m8",
            "1",
            "local-horizon-terminal",
            EmptySidePolicy.TERMINAL,
            SimultaneousExhaustionPolicy.DRAW,
            ResultPolicy.REPORT_CUSTOM_OUTCOME,
        ),
    )
    return scenario, resource_contract


@lru_cache(maxsize=None)
def generation_policy(max_depth: int = 2) -> GenerationPolicy:
    return GenerationPolicy(
        "terra.planner.local",
        "1",
        "source-order-exhaustive",
        max_depth,
    )


@lru_cache(maxsize=None)
def blocked_scenario_and_contract():
    resource_contract = SandboxResourceContract(
        "tests.m8",
        "1",
        "planner-blocked-resource-action",
        "actor-left",
        "declared-energy",
        (
            SandboxActionRule(
                "BLOCKED-A",
                "candidate-blocked-a",
                "actor-left",
                ("unsupported-target",),
                Decimal("1"),
                target_supported=False,
                terminal_supported=True,
            ),
        ),
    )
    state = initialize_sandbox_resource_state(
        make_state(), resource_contract, amount="10", maximum="10"
    )
    scenario = CustomScenario(
        stage_id=None,
        participants=(
            ScenarioParticipant("left", "left", 0),
            ScenarioParticipant("right", "right", 0),
        ),
        initial_state=state,
        terminal_rule=CustomTerminalRule(
            "tests.m8",
            "1",
            "local-horizon-terminal",
            EmptySidePolicy.TERMINAL,
            SimultaneousExhaustionPolicy.DRAW,
            ResultPolicy.REPORT_CUSTOM_OUTCOME,
        ),
    )
    return scenario, resource_contract


@lru_cache(maxsize=None)
def blocked_generated():
    scenario, resource_contract = blocked_scenario_and_contract()
    result = generate_trajectories(
        scenario, resource_contract, generation_policy(2)
    )
    return scenario, resource_contract, result


@lru_cache(maxsize=None)
def generated(max_depth: int = 2, amount: str = "10"):
    scenario, resource_contract = scenario_and_contract(amount)
    result = generate_trajectories(
        scenario, resource_contract, generation_policy(max_depth)
    )
    return scenario, resource_contract, result


@lru_cache(maxsize=None)
def dataset(max_depth: int = 2, amount: str = "10"):
    scenario, resource_contract, result = generated(max_depth, amount)
    return scenario, resource_contract, PlannerDataset.from_generation(result)
