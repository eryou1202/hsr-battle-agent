"""Independent selected-prefix replay over the frozen resource seam."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.custom_scenario import CustomScenario
from hsr_battle_agent.battle_sandbox.legal_actions import LegalActionsStatus
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceContract, SandboxResourceTransaction, SandboxTransitionOutcome,
    plan_sandbox_resource_transition, query_sandbox_legal_actions,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.planner.generator import scenario_identity
from hsr_battle_agent.planner.replay import validate_exclusion_replay
from hsr_battle_agent.planner.trajectory import legal_view_document, snapshot_facts
from hsr_battle_agent.planner_search.objective import AT_HORIZON, PlannerObjective
from hsr_battle_agent.planner_search.policy import PlannerSearchPolicy, SCOPE
from hsr_battle_agent.planner_search.result import PlannerPlan, PlannerResult


class PlannerReplayError(ValueError):
    pass


@dataclass(frozen=True)
class PlannerValidationResult:
    plan_id: str
    steps_validated: int
    deterministic_replay_only: bool = True
    native_validated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "PlannerValidationResult/1",
            "plan_id": self.plan_id,
            "steps_validated": self.steps_validated,
            "deterministic_replay_only": self.deterministic_replay_only,
            "native_validated": self.native_validated,
        }


def validate_plan(
    plan: PlannerPlan | Mapping[str, Any], scenario: CustomScenario,
    contract: SandboxResourceContract, objective: PlannerObjective,
    policy: PlannerSearchPolicy,
) -> PlannerValidationResult:
    try:
        checked = plan if isinstance(plan, PlannerPlan) else PlannerPlan.from_dict(plan)
        doc = checked.to_dict()
        if not all((isinstance(scenario, CustomScenario), isinstance(contract, SandboxResourceContract),
                    isinstance(objective, PlannerObjective), isinstance(policy, PlannerSearchPolicy))):
            raise PlannerReplayError("versioned scenario/contract/objective/policy required")
        if doc["scope"] != SCOPE or doc["scenario_identity"] != scenario_identity(scenario):
            raise PlannerReplayError("plan scope or scenario mismatch")
        if doc["resource_contract_identity"] != contract.identity:
            raise PlannerReplayError("plan resource contract mismatch")
        if doc["objective_identity"] != objective.identity or doc["search_policy_identity"] != policy.identity:
            raise PlannerReplayError("plan objective or policy identity mismatch")
        if not objective.supports(contract):
            raise PlannerReplayError("objective resource is unsupported")
        state = TerraSnapshotV2.from_dict(doc["initial_state"]["snapshot"]).restore_state()
        if state.to_dict() != scenario.initial_state.to_dict():
            raise PlannerReplayError("plan initial state differs from scenario")
        if doc["initial_state"] != snapshot_facts(TerraSnapshotV2(state=state, policy_identity=scenario.policy_identity())):
            raise PlannerReplayError("initial state policy/hash/revision/RNG mismatch")
        candidate_scope = tuple(item.candidate_occurrence_id for item in contract.actions)
        for index, step in enumerate(checked.steps):
            step_doc = step.to_dict()
            satisfied_before, _ = objective.evaluate(state, contract, index, policy.max_depth)
            if satisfied_before:
                raise PlannerReplayError("objective was satisfied before recorded plan continuation")
            before = snapshot_facts(TerraSnapshotV2(state=state, policy_identity=scenario.policy_identity()))
            if step_doc["state_before"] != before:
                raise PlannerReplayError("step source hash/revision/RNG mismatch")
            view = query_sandbox_legal_actions(contract, candidate_scope)
            if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
                raise PlannerReplayError("recorded step has blocked decision context")
            if step_doc["decision"]["legal_actions"] != legal_view_document(view):
                raise PlannerReplayError("legal action completeness/order mismatch")
            ordinal = doc["action_ordinals"][index]
            if ordinal >= len(view.actions) or view.actions[ordinal].action_id != doc["action_ids"][index]:
                raise PlannerReplayError("selected action ordinal mismatch")
            if step_doc["scenario"]["terminal_rule_identity"] != scenario.terminal_rule.content_sha256:
                raise PlannerReplayError("terminal rule identity mismatch")
            if step_doc["scenario"]["policy_identity"] != scenario.policy_identity().to_dict():
                raise PlannerReplayError("snapshot policy identity mismatch")
            transition_plan = plan_sandbox_resource_transition(
                state, scenario.policy_identity(), contract, view, doc["action_ids"][index]
            )
            transition = step_doc["transition"]
            if transition != {
                "evidence_mode": "SANDBOX_EXTENSION",
                "plan_identity": transition_plan.identity,
                "contract_identity": contract.identity,
                "declared_reads": list(transition_plan.declared_reads),
                "declared_writes": list(transition_plan.declared_writes),
            }:
                raise PlannerReplayError("transition plan/contract/footprint mismatch")
            committed = SandboxResourceTransaction(contract, transition_plan).commit(state)
            if committed.outcome is not SandboxTransitionOutcome.COMMITTED or committed.committed_state is None:
                raise PlannerReplayError("recorded transition cannot commit")
            state = committed.committed_state
            after = snapshot_facts(TerraSnapshotV2(state=state, policy_identity=scenario.policy_identity()))
            if step_doc["state_after"] != after:
                raise PlannerReplayError("step result hash/revision/RNG mismatch")
        depth = len(checked.steps)
        satisfied, value = objective.evaluate(state, contract, depth, policy.max_depth)
        if not satisfied or doc["objective_value"] != value:
            raise PlannerReplayError("final objective value or satisfaction mismatch")
        expected_reason = "HORIZON_REACHED" if objective.kind == AT_HORIZON else "OBJECTIVE_SATISFIED"
        if doc["termination_reason"] != expected_reason:
            raise PlannerReplayError("plan termination semantics mismatch")
        return PlannerValidationResult(checked.plan_id, depth)
    except PlannerReplayError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise PlannerReplayError(f"plan replay rejected: {exc}") from exc


def validate_result(
    result: PlannerResult | Mapping[str, Any], scenario: CustomScenario,
    contract: SandboxResourceContract, objective: PlannerObjective,
    policy: PlannerSearchPolicy,
) -> tuple[PlannerValidationResult, ...]:
    checked = result if isinstance(result, PlannerResult) else PlannerResult.from_dict(result)
    doc = checked.to_dict()
    if doc["scenario_identity"] != scenario_identity(scenario) or doc["resource_contract_identity"] != contract.identity:
        raise PlannerReplayError("result scenario/contract mismatch")
    if doc["objective_identity"] != objective.identity or doc["search_policy_identity"] != policy.identity:
        raise PlannerReplayError("result objective/policy mismatch")
    for exclusion in checked.exclusions:
        validate_exclusion_replay(exclusion, scenario, contract)
    return tuple(validate_plan(plan, scenario, contract, objective, policy) for plan in checked.plans)
