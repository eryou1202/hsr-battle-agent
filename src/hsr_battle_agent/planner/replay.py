# -*- coding: utf-8 -*-
"""Independent replay validation for exported local planner records."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.custom_scenario import CustomScenario
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.legal_actions import LegalActionsStatus
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceContract,
    SandboxResourceTransaction,
    SandboxTransitionError,
    SandboxTransitionOutcome,
    plan_sandbox_resource_transition,
    query_sandbox_legal_actions,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.planner.dataset import PlannerDataset
from hsr_battle_agent.planner.generator import scenario_identity
from hsr_battle_agent.planner.trajectory import (
    ExclusionClassification,
    ExclusionRecord,
    Trajectory,
    TrajectoryError,
    legal_view_document,
    snapshot_facts,
)


class ReplayValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ReplayValidationResult:
    dataset_id: str
    trajectories_validated: int
    exclusions_validated: int
    deterministic_replay_only: bool = True
    native_validated: bool = False


def _view(contract: SandboxResourceContract):
    return query_sandbox_legal_actions(
        contract, tuple(item.candidate_occurrence_id for item in contract.actions)
    )


def _step(
    state: TerraBattleState,
    scenario: CustomScenario,
    contract: SandboxResourceContract,
    action_id: str,
):
    view = _view(contract)
    plan = plan_sandbox_resource_transition(
        state, scenario.policy_identity(), contract, view, action_id
    )
    result = SandboxResourceTransaction(contract, plan).commit(state)
    if result.outcome is not SandboxTransitionOutcome.COMMITTED:
        raise ReplayValidationError(f"replay transition rejected: {result.reason}")
    if result.committed_state is None:
        raise ReplayValidationError("replay transition omitted committed state")
    return view, plan, result.committed_state


def replay_trajectory(
    record: Mapping[str, Any] | Trajectory,
    scenario: CustomScenario,
    contract: SandboxResourceContract,
) -> TerraBattleState:
    try:
        trajectory = record if isinstance(record, Trajectory) else Trajectory.from_dict(record)
    except (TrajectoryError, TypeError, ValueError) as exc:
        raise ReplayValidationError(f"trajectory representation rejected: {exc}") from exc
    data = trajectory.to_dict()
    if data["scenario_identity"] != scenario_identity(scenario):
        raise ReplayValidationError("scenario/rule identity mismatch")
    if data["initial_state"]["snapshot"]["policy_identity"] != scenario.policy_identity().to_dict():
        raise ReplayValidationError("profile/rule policy identity mismatch")
    current = TerraSnapshotV2.from_dict(data["initial_state"]["snapshot"]).restore_state()
    if current.to_dict() != scenario.initial_state.to_dict():
        raise ReplayValidationError("trajectory initial state differs from scenario")
    path: list[str] = []
    for index, step in enumerate(data["steps"]):
        expected_before = snapshot_facts(
            TerraSnapshotV2(state=current, policy_identity=scenario.policy_identity())
        )
        if step["state_before"] != expected_before:
            raise ReplayValidationError("state-before hash/revision/RNG mismatch")
        view = _view(contract)
        if step["decision"]["legal_actions"] != legal_view_document(view):
            raise ReplayValidationError("legal-action completeness/order mismatch")
        if step["scenario"]["scenario_identity"] != scenario_identity(scenario):
            raise ReplayValidationError("step scenario identity mismatch")
        if step["scenario"]["terminal_rule_identity"] != scenario.terminal_rule.content_sha256:
            raise ReplayValidationError("step terminal-rule identity mismatch")
        if step["scenario"]["policy_identity"] != scenario.policy_identity().to_dict():
            raise ReplayValidationError("step policy/profile identity mismatch")
        action_id = step["decision"]["selected_action_id"]
        matches = tuple(item for item in view.actions if item.action_id == action_id)
        if len(matches) != 1:
            raise ReplayValidationError("selected action is unavailable or ambiguous")
        try:
            replay_view, plan, after = _step(current, scenario, contract, action_id)
        except (SandboxTransitionError, ReplayValidationError) as exc:
            raise ReplayValidationError(f"step {index} cannot replay: {exc}") from exc
        transition = step["transition"]
        if transition["plan_identity"] != plan.identity:
            raise ReplayValidationError("plan identity mismatch")
        if transition["contract_identity"] != contract.identity:
            raise ReplayValidationError("resource contract identity mismatch")
        if transition["declared_reads"] != list(plan.declared_reads):
            raise ReplayValidationError("declared read footprint mismatch")
        if transition["declared_writes"] != list(plan.declared_writes):
            raise ReplayValidationError("declared write footprint mismatch")
        if legal_view_document(replay_view) != step["decision"]["legal_actions"]:
            raise ReplayValidationError("replayed legal actions changed")
        expected_after = snapshot_facts(
            TerraSnapshotV2(state=after, policy_identity=scenario.policy_identity())
        )
        if step["state_after"] != expected_after:
            raise ReplayValidationError("state-after hash/revision/RNG mismatch")
        path.append(action_id)
        if step["path"] != path:
            raise ReplayValidationError("step path identity mismatch")
        current = after
    return current


def _state_at_path(
    scenario: CustomScenario,
    contract: SandboxResourceContract,
    path: list[str],
) -> TerraBattleState:
    state = scenario.initial_state
    for action_id in path:
        _view_value, _plan_value, state = _step(state, scenario, contract, action_id)
    return state


def validate_exclusion_replay(
    record: Mapping[str, Any] | ExclusionRecord,
    scenario: CustomScenario,
    contract: SandboxResourceContract,
) -> None:
    """Reproduce one current-generator exclusion without publishing state.

    BLOCKED is a decision-context result and is therefore validated only by
    reconstructing the complete legal-actions view.  REJECTED is an action
    transition result and is validated through the exact plan/commit path.
    UNSUPPORTED remains representable for schema compatibility but has no
    producer in the bounded M5 resource generator.
    """
    try:
        exclusion = (
            record if isinstance(record, ExclusionRecord)
            else ExclusionRecord.from_dict(record)
        )
    except (TrajectoryError, TypeError, ValueError) as exc:
        raise ReplayValidationError(f"exclusion representation rejected: {exc}") from exc
    data = exclusion.to_dict()
    source = _state_at_path(scenario, contract, data["source_path"])
    before = copy.deepcopy(source.to_dict())
    snapshot = TerraSnapshotV2(state=source, policy_identity=scenario.policy_identity())
    if semantic_hash_v2(snapshot) != data["source_state_hash"]:
        raise ReplayValidationError("exclusion source-state hash mismatch")
    state_doc = snapshot.to_dict()["state"]
    if state_doc["revision_and_transaction_sequence"]["published_revision"] != data["source_revision"]:
        raise ReplayValidationError("exclusion source revision mismatch")
    if state_doc["rng_state"] != data["source_rng"]:
        raise ReplayValidationError("exclusion source RNG mismatch")

    classification = ExclusionClassification(data["classification"])
    actual_reason: str | None = None
    if classification is ExclusionClassification.BLOCKED:
        if data["attempted_action_id"] != "decision-context":
            raise ReplayValidationError("BLOCKED exclusion must identify decision-context")
        view = _view(contract)
        if view.status is not LegalActionsStatus.BLOCKED:
            raise ReplayValidationError("BLOCKED exclusion decision context is now complete")
        actual_reason = ";".join(view.blockers) or "LEGAL_ACTIONS_BLOCKED"
    elif classification is ExclusionClassification.REJECTED:
        view = _view(contract)
        if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
            raise ReplayValidationError(
                "REJECTED exclusion cannot substitute for a BLOCKED decision context"
            )
        action_id = data["attempted_action_id"]
        rejected = False
        try:
            plan = plan_sandbox_resource_transition(
                source, scenario.policy_identity(), contract, view, action_id
            )
            result = SandboxResourceTransaction(contract, plan).commit(source)
            rejected = result.outcome is not SandboxTransitionOutcome.COMMITTED
            actual_reason = result.reason
        except SandboxTransitionError as exc:
            rejected = True
            actual_reason = str(exc)
        if not rejected:
            raise ReplayValidationError("exclusion action unexpectedly committed")
    else:
        raise ReplayValidationError(
            "UNSUPPORTED is representable but not produced by the current M5 generator"
        )

    if data["reason"] != actual_reason:
        raise ReplayValidationError("exclusion rejection reason mismatch")
    if source.to_dict() != before:
        raise ReplayValidationError("exclusion replay mutated source state")


def validate_dataset_replay(
    dataset: PlannerDataset,
    scenario: CustomScenario,
    contract: SandboxResourceContract,
) -> ReplayValidationResult:
    if not isinstance(dataset, PlannerDataset):
        raise ReplayValidationError("dataset must be PlannerDataset")
    if dataset.to_dict()["scenario_identity"] != scenario_identity(scenario):
        raise ReplayValidationError("dataset scenario identity mismatch")
    for trajectory in dataset.trajectories:
        replay_trajectory(trajectory, scenario, contract)
    for exclusion in dataset.exclusions:
        validate_exclusion_replay(exclusion, scenario, contract)
    return ReplayValidationResult(
        dataset.dataset_id,
        len(dataset.trajectories),
        len(dataset.exclusions),
    )
