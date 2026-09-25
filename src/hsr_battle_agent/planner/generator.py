# -*- coding: utf-8 -*-
"""Bounded source-order trajectory generation over the M5 local transition."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
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
from hsr_battle_agent.planner.trajectory import (
    ExclusionClassification,
    ExclusionRecord,
    Trajectory,
    TrajectoryStep,
)

GENERATION_POLICY_SCHEMA = "terra_planner_generation_policy/1"


class GenerationError(ValueError):
    pass


class BranchOrderingRule(Enum):
    SOURCE_ORDER_EXHAUSTIVE = "SOURCE_ORDER_EXHAUSTIVE"


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GenerationError(f"{label} must be a non-empty trimmed string")
    return value


@dataclass(frozen=True)
class GenerationPolicy:
    namespace: str
    version: str
    strategy_id: str
    max_depth: int
    branch_ordering: BranchOrderingRule = BranchOrderingRule.SOURCE_ORDER_EXHAUSTIVE

    def __post_init__(self) -> None:
        for name in ("namespace", "version", "strategy_id"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        if isinstance(self.max_depth, bool) or not isinstance(self.max_depth, int):
            raise GenerationError("max_depth must be an explicit int")
        if self.max_depth <= 0:
            raise GenerationError("max_depth must be positive")
        if self.branch_ordering is not BranchOrderingRule.SOURCE_ORDER_EXHAUSTIVE:
            raise GenerationError("only deterministic source-order enumeration is supported")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": GENERATION_POLICY_SCHEMA,
            "namespace": self.namespace,
            "version": self.version,
            "strategy_id": self.strategy_id,
            "max_depth": self.max_depth,
            "branch_ordering": self.branch_ordering.value,
            "stochastic_sampling": False,
            "rng_draws_for_branching": 0,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "GenerationPolicy":
        if not isinstance(data, dict) or set(data) != {
            "schema", "namespace", "version", "strategy_id", "max_depth",
            "branch_ordering", "stochastic_sampling", "rng_draws_for_branching",
        }:
            raise GenerationError("generation policy has missing or unknown fields")
        if data["schema"] != GENERATION_POLICY_SCHEMA:
            raise GenerationError("unknown generation-policy schema")
        if data["stochastic_sampling"] is not False or data["rng_draws_for_branching"] != 0:
            raise GenerationError("first M8 policy must enumerate without RNG sampling")
        try:
            ordering = BranchOrderingRule(data["branch_ordering"])
        except (TypeError, ValueError) as exc:
            raise GenerationError("unknown branch-ordering rule") from exc
        return cls(
            data["namespace"], data["version"], data["strategy_id"],
            data["max_depth"], ordering,
        )

    @property
    def identity(self) -> str:
        return hashlib.sha256(canonical_v2_bytes(self.to_dict())).hexdigest()


@dataclass(frozen=True)
class GenerationResult:
    trajectories: tuple[Trajectory, ...]
    exclusions: tuple[ExclusionRecord, ...]
    policy: GenerationPolicy
    scenario_identity: str
    resource_contract_identity: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trajectories", tuple(self.trajectories))
        object.__setattr__(self, "exclusions", tuple(self.exclusions))
        if any(not isinstance(item, Trajectory) for item in self.trajectories):
            raise GenerationError("trajectories must be validated Trajectory values")
        if any(not isinstance(item, ExclusionRecord) for item in self.exclusions):
            raise GenerationError("exclusions must be validated ExclusionRecord values")


def scenario_identity(scenario: CustomScenario) -> str:
    if not isinstance(scenario, CustomScenario):
        raise GenerationError("scenario must be CustomScenario")
    return hashlib.sha256(canonical_v2_bytes(scenario.to_dict())).hexdigest()


def _snapshot(state: TerraBattleState, scenario: CustomScenario) -> TerraSnapshotV2:
    return TerraSnapshotV2(state=state, policy_identity=scenario.policy_identity())


def generate_trajectories(
    scenario: CustomScenario,
    contract: SandboxResourceContract,
    policy: GenerationPolicy,
) -> GenerationResult:
    """Enumerate every committed path up to the explicit dataset horizon.

    Invalid continuations become exclusion records.  A prefix that cannot
    reach the horizon is never emitted as a successful trajectory.
    """
    if not isinstance(scenario, CustomScenario):
        raise GenerationError("scenario must be CustomScenario")
    if not isinstance(contract, SandboxResourceContract):
        raise GenerationError("contract must be SandboxResourceContract")
    if not isinstance(policy, GenerationPolicy):
        raise GenerationError("policy must be GenerationPolicy")
    initial = scenario.initial_state
    scenario_id = scenario_identity(scenario)
    terminal_rule_id = scenario.terminal_rule.content_sha256
    initial_snapshot = _snapshot(initial, scenario)
    candidate_scope = tuple(item.candidate_occurrence_id for item in contract.actions)
    trajectories: list[Trajectory] = []
    exclusions: list[ExclusionRecord] = []

    def exclude(
        state: TerraBattleState,
        path: tuple[str, ...],
        action_id: str,
        classification: ExclusionClassification,
        reason: str,
    ) -> None:
        before = copy.deepcopy(state.to_dict())
        snapshot = _snapshot(state, scenario)
        state_doc = snapshot.to_dict()["state"]
        record = ExclusionRecord.create(
            source_path=path,
            source_state_hash=semantic_hash_v2(snapshot),
            attempted_action_id=action_id,
            depth=len(path),
            classification=classification,
            reason=reason,
            evidence_mode=EvidenceMode.SANDBOX_EXTENSION,
            source_revision=state_doc["revision_and_transaction_sequence"]["published_revision"],
            source_rng=state_doc["rng_state"],
        )
        if state.to_dict() != before:
            raise GenerationError("excluded branch mutated its source state")
        exclusions.append(record)

    def visit(
        state: TerraBattleState,
        path: tuple[str, ...],
        steps: tuple[TrajectoryStep, ...],
    ) -> None:
        if len(steps) == policy.max_depth:
            trajectories.append(
                Trajectory.create(
                    scenario_identity=scenario_id,
                    generation_policy=policy.to_dict(),
                    initial_snapshot=initial_snapshot,
                    steps=steps,
                )
            )
            return
        view = query_sandbox_legal_actions(contract, candidate_scope)
        if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
            exclude(
                state,
                path,
                "decision-context",
                ExclusionClassification.BLOCKED,
                ";".join(view.blockers) or "LEGAL_ACTIONS_BLOCKED",
            )
            return
        for action in view.actions:
            before_document = copy.deepcopy(state.to_dict())
            try:
                plan = plan_sandbox_resource_transition(
                    state,
                    scenario.policy_identity(),
                    contract,
                    view,
                    action.action_id,
                )
            except SandboxTransitionError as exc:
                if state.to_dict() != before_document:
                    raise GenerationError("planning rejection mutated source state") from exc
                exclude(
                    state,
                    path,
                    action.action_id,
                    ExclusionClassification.REJECTED,
                    str(exc),
                )
                continue
            result = SandboxResourceTransaction(contract, plan).commit(state)
            if result.outcome is not SandboxTransitionOutcome.COMMITTED:
                if state.to_dict() != before_document:
                    raise GenerationError("transaction rejection mutated source state")
                exclude(
                    state,
                    path,
                    action.action_id,
                    ExclusionClassification.REJECTED,
                    result.reason or "TRANSITION_REJECTED",
                )
                continue
            next_state = result.committed_state
            if next_state is None:
                raise GenerationError("committed transition omitted state")
            next_path = path + (action.action_id,)
            step = TrajectoryStep.create(
                step_index=len(steps),
                path=next_path,
                before=_snapshot(state, scenario),
                after=_snapshot(next_state, scenario),
                legal_actions=view,
                selected_action=action,
                scenario_identity=scenario_id,
                terminal_rule_identity=terminal_rule_id,
                resource_contract_identity=contract.identity,
                plan=plan,
            )
            if state.to_dict() != before_document:
                raise GenerationError("committed branch mutated shared source state")
            visit(next_state, next_path, steps + (step,))

    visit(initial, (), ())
    return GenerationResult(
        tuple(trajectories),
        tuple(exclusions),
        policy,
        scenario_id,
        contract.identity,
    )
