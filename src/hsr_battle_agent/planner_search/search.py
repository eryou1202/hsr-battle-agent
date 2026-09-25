"""Bounded source-order DFS over SANDBOX_RESOURCE_V1."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.custom_scenario import CustomScenario
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.legal_actions import LegalActionsStatus, LegalActionsView
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceContract, SandboxResourceTransaction, SandboxTransitionError,
    SandboxTransitionOutcome, plan_sandbox_resource_transition,
    query_sandbox_legal_actions, read_sandbox_resource_state,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.planner.generator import scenario_identity
from hsr_battle_agent.planner.trajectory import (
    ExclusionClassification, ExclusionRecord, TrajectoryStep, snapshot_facts,
)
from hsr_battle_agent.planner_search.objective import AT_HORIZON, PlannerObjective
from hsr_battle_agent.planner_search.policy import PlannerSearchPolicy, SCOPE
from hsr_battle_agent.planner_search.result import EVIDENCE, CONTENT_TARGET, PlannerPlan, PlannerResult


class PlannerSearchError(ValueError):
    pass


@dataclass
class _Frame:
    state: TerraBattleState
    path: tuple[str, ...]
    ordinals: tuple[int, ...]
    steps: tuple[TrajectoryStep, ...]
    view: LegalActionsView | None = None
    next_index: int = 0
    entered: bool = False


def _snapshot(state: TerraBattleState, scenario: CustomScenario) -> TerraSnapshotV2:
    return TerraSnapshotV2(state=state, policy_identity=scenario.policy_identity())


def search_resource_plans(
    scenario: CustomScenario,
    contract: SandboxResourceContract,
    objective: PlannerObjective,
    policy: PlannerSearchPolicy,
) -> PlannerResult:
    if not isinstance(scenario, CustomScenario) or not isinstance(contract, SandboxResourceContract):
        raise PlannerSearchError("scenario and local resource contract are required")
    if not isinstance(objective, PlannerObjective) or not isinstance(policy, PlannerSearchPolicy):
        raise PlannerSearchError("versioned objective and search policy are required")
    initial = scenario.initial_state
    initial_document = copy.deepcopy(initial.to_dict())
    initial_facts = snapshot_facts(_snapshot(initial, scenario))
    scenario_id = scenario_identity(scenario)
    contract_id = contract.identity
    policy_id = policy.identity
    objective_id = objective.identity
    exclusions: list[ExclusionRecord] = []
    candidates: list[tuple[tuple[str, ...], tuple[int, ...], tuple[TrajectoryStep, ...], dict[str, Any], str]] = []
    counts = {"explored_node_count": 0, "committed_edge_count": 0,
              "rejected_edge_count": 0, "blocked_node_count": 0,
              "repeated_state_count": 0}
    reasons: set[str] = set()
    seen: dict[tuple[str, str, str, str, int, str], list[dict[str, Any]]] = {}
    limit_reached = False

    def result(status: str, complete: bool) -> PlannerResult:
        ranked = sorted(candidates, key=lambda item: objective.rank_key(item[3], item[1]))
        selected: list[PlannerPlan] = []
        for path, ordinals, steps, value, termination in ranked[:policy.max_plans]:
            related = [record.exclusion_id for record in exclusions
                       if path[:len(record.to_dict()["source_path"])] == tuple(record.to_dict()["source_path"])]
            selected.append(PlannerPlan.create(
                scope=SCOPE, objective_identity=objective_id,
                search_policy_identity=policy_id, scenario_identity=scenario_id,
                resource_contract_identity=contract_id, initial_state=initial_facts,
                action_ids=list(path), action_ordinals=list(ordinals),
                steps=[step.to_dict() for step in steps], objective_value=value,
                termination_reason=termination,
                validation_label=EVIDENCE["validation"],
                evidence_summary=EVIDENCE, related_exclusion_ids=related,
            ))
        return PlannerResult.create(
            content_target=CONTENT_TARGET, scope=SCOPE,
            scenario_identity=scenario_id, resource_contract_identity=contract_id,
            search_policy=policy.to_dict(), search_policy_identity=policy_id,
            objective=objective.to_dict(), objective_identity=objective_id,
            initial_state=initial_facts, status=status, search_complete=complete,
            plans=[item.to_dict() for item in selected],
            candidate_plan_count=len(candidates), **counts,
            exclusions=[item.to_dict() for item in exclusions],
            termination_reasons=[name for name in (
                "OBJECTIVE_SATISFIED", "HORIZON_REACHED", "BLOCKED_DECISION_CONTEXT",
                "NODE_LIMIT", "EXHAUSTED_SUPPORTED_BRANCHES", "UNSUPPORTED_OBJECTIVE_RESOURCE",
            ) if name in reasons],
            evidence_summary=EVIDENCE,
        )

    if not objective.supports(contract):
        reasons.add("UNSUPPORTED_OBJECTIVE_RESOURCE")
        return result("UNSUPPORTED", False)
    try:
        read_sandbox_resource_state(initial, contract)
    except SandboxTransitionError:
        reasons.add("UNSUPPORTED_OBJECTIVE_RESOURCE")
        return result("UNSUPPORTED", False)

    def exclude(frame: _Frame, action_id: str, classification: ExclusionClassification, reason: str) -> None:
        before = frame.state.to_dict()
        snap = _snapshot(frame.state, scenario)
        state_doc = snap.to_dict()["state"]
        exclusions.append(ExclusionRecord.create(
            source_path=frame.path,
            source_state_hash=semantic_hash_v2(snap),
            attempted_action_id=action_id,
            depth=len(frame.path), classification=classification,
            reason=reason, evidence_mode=EvidenceMode.SANDBOX_EXTENSION,
            source_revision=state_doc["revision_and_transaction_sequence"]["published_revision"],
            source_rng=state_doc["rng_state"],
        ))
        if frame.state.to_dict() != before:
            raise PlannerSearchError("excluded branch mutated source state")
        if classification is ExclusionClassification.BLOCKED:
            counts["blocked_node_count"] += 1
            reasons.add("BLOCKED_DECISION_CONTEXT")
        else:
            counts["rejected_edge_count"] += 1

    stack = [_Frame(initial, (), (), ())]
    candidate_scope = tuple(item.candidate_occurrence_id for item in contract.actions)
    while stack:
        frame = stack[-1]
        if not frame.entered:
            # The root and every successfully committed successor are counted once
            # on entry. Rejected actions never create frames.
            counts["explored_node_count"] += 1
            frame.entered = True
            snapshot = _snapshot(frame.state, scenario)
            key = (scenario_id, contract_id, objective_id, policy_id,
                   policy.max_depth - len(frame.path), semantic_hash_v2(snapshot))
            document = snapshot.to_dict()
            bucket = seen.setdefault(key, [])
            if document in bucket:
                counts["repeated_state_count"] += 1
            else:
                bucket.append(document)
            satisfied, value = objective.evaluate(
                frame.state, contract, len(frame.path), policy.max_depth
            )
            if satisfied:
                termination = "HORIZON_REACHED" if objective.kind == AT_HORIZON else "OBJECTIVE_SATISFIED"
                candidates.append((frame.path, frame.ordinals, frame.steps, value, termination))
                reasons.add(termination)
                stack.pop()
                continue
            if len(frame.path) == policy.max_depth:
                reasons.add("HORIZON_REACHED")
                stack.pop()
                continue
            view = query_sandbox_legal_actions(contract, candidate_scope)
            if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
                exclude(frame, "decision-context", ExclusionClassification.BLOCKED,
                        ";".join(view.blockers) or "LEGAL_ACTIONS_BLOCKED")
                stack.pop()
                continue
            frame.view = view
        assert frame.view is not None
        if frame.next_index == len(frame.view.actions):
            stack.pop()
            continue
        ordinal = frame.next_index
        action = frame.view.actions[ordinal]
        frame.next_index += 1
        before = frame.state.to_dict()
        try:
            transition_plan = plan_sandbox_resource_transition(
                frame.state, scenario.policy_identity(), contract, frame.view, action.action_id
            )
        except SandboxTransitionError as exc:
            if frame.state.to_dict() != before:
                raise PlannerSearchError("planning rejection mutated source state") from exc
            exclude(frame, action.action_id, ExclusionClassification.REJECTED, str(exc))
            continue
        transition = SandboxResourceTransaction(contract, transition_plan).commit(frame.state)
        if transition.outcome is not SandboxTransitionOutcome.COMMITTED:
            if frame.state.to_dict() != before:
                raise PlannerSearchError("transaction rejection mutated source state")
            exclude(frame, action.action_id, ExclusionClassification.REJECTED,
                    transition.reason or "TRANSITION_REJECTED")
            continue
        counts["committed_edge_count"] += 1
        successor = transition.committed_state
        if successor is None:
            raise PlannerSearchError("committed transition omitted state")
        if frame.state.to_dict() != before:
            raise PlannerSearchError("committed branch mutated source state")
        # A committed edge may be counted without visiting its successor when
        # the limit has been reached. No objective claim is made for that node.
        if counts["explored_node_count"] >= policy.node_limit:
            limit_reached = True
            reasons.add("NODE_LIMIT")
            break
        next_path = frame.path + (action.action_id,)
        step = TrajectoryStep.create(
            step_index=len(frame.steps), path=next_path,
            before=_snapshot(frame.state, scenario), after=_snapshot(successor, scenario),
            legal_actions=frame.view, selected_action=action,
            scenario_identity=scenario_id,
            terminal_rule_identity=scenario.terminal_rule.content_sha256,
            resource_contract_identity=contract_id, plan=transition_plan,
        )
        stack.append(_Frame(successor, next_path, frame.ordinals + (ordinal,), frame.steps + (step,)))

    if scenario.initial_state.to_dict() != initial_document:
        raise PlannerSearchError("search mutated caller scenario")
    complete = not limit_reached and counts["blocked_node_count"] == 0
    if not limit_reached:
        reasons.add("EXHAUSTED_SUPPORTED_BRANCHES")
    if candidates:
        status = "FOUND"
    elif limit_reached:
        status = "LIMIT_REACHED"
    elif counts["blocked_node_count"]:
        status = "BLOCKED"
    else:
        status = "NO_PLAN_WITHIN_HORIZON"
    return result(status, complete)
