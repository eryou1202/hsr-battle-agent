# -*- coding: utf-8 -*-
"""Lossless local trajectory, step and exclusion representations."""
from __future__ import annotations

import copy
import hashlib
from enum import Enum
from typing import Any, Mapping, NoReturn, Sequence

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.legal_actions import (
    LegalActionsView,
    PlayerLegalAction,
)
from hsr_battle_agent.battle_sandbox.sandbox_transition import SandboxResourcePlan
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2

TRAJECTORY_STEP_SCHEMA = "terra_planner_trajectory_step/1"
TRAJECTORY_SCHEMA = "terra_planner_trajectory/1"
EXCLUSION_SCHEMA = "terra_planner_exclusion/1"
VALIDATION_VOCABULARY_VERSION = "1"
GENERATION_POLICY_SCHEMA = "terra_planner_generation_policy/1"


class TrajectoryError(ValueError):
    pass


class TrajectoryValidationLabel(Enum):
    """Local validation strength, deliberately separate from EvidenceMode."""

    DETERMINISTIC_REPLAY_ONLY = "DETERMINISTIC_REPLAY_ONLY"

    def __bool__(self) -> NoReturn:
        raise TrajectoryError("trajectory validation is a label, not permission")


class TrajectoryTerminationReason(Enum):
    GENERATION_HORIZON_REACHED = "GENERATION_HORIZON_REACHED"
    CUSTOM_TERMINAL = "CUSTOM_TERMINAL"


class ExclusionClassification(Enum):
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    UNSUPPORTED = "UNSUPPORTED"


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TrajectoryError(f"{label} must be a non-empty trimmed string")
    return value


def _uint(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TrajectoryError(f"{label} must be an explicit non-negative int")
    return value


def _identity(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_v2_bytes(document)).hexdigest()


def _exact(data: Mapping[str, Any], expected: set[str], label: str) -> None:
    if not isinstance(data, Mapping) or set(data) != expected:
        raise TrajectoryError(f"{label} has missing or unknown fields")


def _validate_generation_policy(data: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "namespace", "version", "strategy_id", "max_depth",
        "branch_ordering", "stochastic_sampling", "rng_draws_for_branching",
    }
    _exact(data, expected, "generation policy")
    owned = copy.deepcopy(dict(data))
    if owned["schema"] != GENERATION_POLICY_SCHEMA:
        raise TrajectoryError("unknown generation-policy schema")
    for name in ("namespace", "version", "strategy_id"):
        _token(owned[name], f"generation policy {name}")
    if _uint(owned["max_depth"], "generation policy max_depth") == 0:
        raise TrajectoryError("generation policy max_depth must be positive")
    if owned["branch_ordering"] != "SOURCE_ORDER_EXHAUSTIVE":
        raise TrajectoryError("unknown generation-policy branch ordering")
    if owned["stochastic_sampling"] is not False:
        raise TrajectoryError("current generation policy cannot sample stochastically")
    if owned["rng_draws_for_branching"] != 0:
        raise TrajectoryError("branch enumeration must consume zero RNG draws")
    return owned


def action_document(action: PlayerLegalAction) -> dict[str, Any]:
    if not isinstance(action, PlayerLegalAction):
        raise TrajectoryError("selected action must be PlayerLegalAction")
    if action.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
        raise TrajectoryError("planner action must remain REFERENCE_MODEL")
    if not isinstance(action.target_ids, tuple):
        raise TrajectoryError("action target_ids must retain canonical tuple ownership")
    return {
        "action_id": _token(action.action_id, "action_id"),
        "candidate_occurrence_id": _token(
            action.candidate_occurrence_id, "candidate_occurrence_id"
        ),
        "actor_id": _token(action.actor_id, "actor_id"),
        "target_ids": list(action.target_ids),
        "resource_cost": str(action.resource_cost),
        "evidence_mode": action.evidence_mode.value,
    }


def legal_view_document(view: LegalActionsView) -> dict[str, Any]:
    if not isinstance(view, LegalActionsView):
        raise TrajectoryError("legal-actions view is required")
    return {
        "status": view.status.value,
        "actions": [action_document(item) for item in view.actions],
        "blockers": list(view.blockers),
        "evidence_mode": view.evidence_mode.value,
    }


def snapshot_facts(snapshot: TerraSnapshotV2) -> dict[str, Any]:
    if not isinstance(snapshot, TerraSnapshotV2):
        raise TrajectoryError("snapshot must be TerraSnapshotV2")
    document = snapshot.to_dict()
    state = document["state"]
    return {
        "snapshot": document,
        "semantic_hash": semantic_hash_v2(snapshot),
        "revision": copy.deepcopy(
            state["revision_and_transaction_sequence"]["published_revision"]
        ),
        "revision_sequence": copy.deepcopy(
            state["revision_and_transaction_sequence"]
        ),
        "rng": copy.deepcopy(state["rng_state"]),
    }


class TrajectoryStep:
    """One fully committed state-bearing planner observation."""

    __slots__ = ("_document",)

    _FIELDS = {
        "schema", "step_id", "step_index", "path", "state_before",
        "decision", "scenario", "transition", "state_after", "result",
        "validation_label", "validation_vocabulary_version",
    }

    def __init__(self, document: Mapping[str, Any]) -> None:
        _exact(document, self._FIELDS, "trajectory step")
        owned = copy.deepcopy(dict(document))
        if owned["schema"] != TRAJECTORY_STEP_SCHEMA:
            raise TrajectoryError("unknown trajectory-step schema")
        _uint(owned["step_index"], "step_index")
        if not isinstance(owned["path"], list) or not all(
            isinstance(item, str) for item in owned["path"]
        ):
            raise TrajectoryError("step path must be an ordered action-id list")
        if len(owned["path"]) != owned["step_index"] + 1:
            raise TrajectoryError("step path depth differs from step index")
        try:
            label = TrajectoryValidationLabel(owned["validation_label"])
        except (TypeError, ValueError) as exc:
            raise TrajectoryError("unknown trajectory validation label") from exc
        if label is not TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY:
            raise TrajectoryError("current local trajectories are replay-only")
        if owned["validation_vocabulary_version"] != VALIDATION_VOCABULARY_VERSION:
            raise TrajectoryError("unknown validation vocabulary version")
        before = self._validate_state_facts(owned["state_before"], "state_before")
        after = self._validate_state_facts(owned["state_after"], "state_after")
        decision = owned["decision"]
        _exact(
            decision,
            {"legal_actions", "selected_action_id", "selected_action_evidence_mode"},
            "decision",
        )
        if decision["selected_action_evidence_mode"] != EvidenceMode.REFERENCE_MODEL.value:
            raise TrajectoryError("selected action evidence mode must remain REFERENCE_MODEL")
        legal = decision["legal_actions"]
        _exact(legal, {"status", "actions", "blockers", "evidence_mode"}, "legal actions")
        if (
            legal["status"] != "COMPLETE_FOR_SUPPORTED_SCOPE"
            or legal["blockers"] != []
            or legal["evidence_mode"] != EvidenceMode.REFERENCE_MODEL.value
            or not isinstance(legal["actions"], list)
        ):
            raise TrajectoryError("committed step requires a complete unblocked reference action set")
        action_ids: list[str] = []
        for action in legal["actions"]:
            _exact(
                action,
                {"action_id", "candidate_occurrence_id", "actor_id", "target_ids", "resource_cost", "evidence_mode"},
                "legal action",
            )
            if action["evidence_mode"] != EvidenceMode.REFERENCE_MODEL.value:
                raise TrajectoryError("legal action evidence mode changed")
            if not isinstance(action["target_ids"], list):
                raise TrajectoryError("serialized target_ids must remain an ordered list")
            action_ids.append(_token(action["action_id"], "legal action id"))
        if action_ids.count(decision["selected_action_id"]) != 1:
            raise TrajectoryError("selected action is absent or ambiguous in complete action set")
        if owned["path"][-1] != decision["selected_action_id"]:
            raise TrajectoryError("step path does not end with selected action")
        transition = owned["transition"]
        _exact(
            transition,
            {"evidence_mode", "plan_identity", "contract_identity", "declared_reads", "declared_writes"},
            "transition",
        )
        if transition["evidence_mode"] != EvidenceMode.SANDBOX_EXTENSION.value:
            raise TrajectoryError("transition evidence mode must remain SANDBOX_EXTENSION")
        result = owned["result"]
        _exact(result, {"outcome", "native_success_claimed"}, "step result")
        if result != {"outcome": "COMMITTED", "native_success_claimed": False}:
            raise TrajectoryError("trajectory steps may contain committed local results only")
        scenario = owned["scenario"]
        _exact(
            scenario,
            {"scenario_identity", "terminal_rule_identity", "policy_identity", "resource_contract_identity"},
            "step scenario",
        )
        if scenario["policy_identity"] != before["snapshot"]["policy_identity"]:
            raise TrajectoryError("step policy identity differs from state-before snapshot")
        if scenario["policy_identity"] != after["snapshot"]["policy_identity"]:
            raise TrajectoryError("step policy identity differs from state-after snapshot")
        identity_payload = copy.deepcopy(owned)
        supplied = _token(identity_payload.pop("step_id"), "step_id")
        if supplied != _identity(identity_payload):
            raise TrajectoryError("trajectory step identity mismatch")
        self._document = owned

    @staticmethod
    def _validate_state_facts(data: Mapping[str, Any], label: str) -> dict[str, Any]:
        _exact(data, {"snapshot", "semantic_hash", "revision", "revision_sequence", "rng"}, label)
        snapshot = TerraSnapshotV2.from_dict(data["snapshot"])
        expected = snapshot_facts(snapshot)
        if dict(data) != expected:
            raise TrajectoryError(f"{label} facts do not match the complete snapshot")
        return expected

    @classmethod
    def create(
        cls,
        *,
        step_index: int,
        path: Sequence[str],
        before: TerraSnapshotV2,
        after: TerraSnapshotV2,
        legal_actions: LegalActionsView,
        selected_action: PlayerLegalAction,
        scenario_identity: str,
        terminal_rule_identity: str,
        resource_contract_identity: str,
        plan: SandboxResourcePlan,
    ) -> "TrajectoryStep":
        if plan.evidence_mode is not EvidenceMode.SANDBOX_EXTENSION:
            raise TrajectoryError("plan evidence changed")
        document: dict[str, Any] = {
            "schema": TRAJECTORY_STEP_SCHEMA,
            "step_index": _uint(step_index, "step_index"),
            "path": list(path),
            "state_before": snapshot_facts(before),
            "decision": {
                "legal_actions": legal_view_document(legal_actions),
                "selected_action_id": selected_action.action_id,
                "selected_action_evidence_mode": selected_action.evidence_mode.value,
            },
            "scenario": {
                "scenario_identity": _token(scenario_identity, "scenario_identity"),
                "terminal_rule_identity": _token(terminal_rule_identity, "terminal_rule_identity"),
                "policy_identity": plan.policy_identity.to_dict(),
                "resource_contract_identity": _token(
                    resource_contract_identity, "resource_contract_identity"
                ),
            },
            "transition": {
                "evidence_mode": plan.evidence_mode.value,
                "plan_identity": plan.identity,
                "contract_identity": plan.contract_identity,
                "declared_reads": list(plan.declared_reads),
                "declared_writes": list(plan.declared_writes),
            },
            "state_after": snapshot_facts(after),
            "result": {"outcome": "COMMITTED", "native_success_claimed": False},
            "validation_label": TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value,
            "validation_vocabulary_version": VALIDATION_VOCABULARY_VERSION,
        }
        document["step_id"] = _identity(document)
        return cls(document)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TrajectoryStep":
        return cls(data)

    @property
    def step_id(self) -> str:
        return self._document["step_id"]

    @property
    def step_index(self) -> int:
        return self._document["step_index"]

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)


class Trajectory:
    __slots__ = ("_document", "_steps")

    _FIELDS = {
        "schema", "trajectory_id", "scenario_identity", "generation_policy",
        "validation_label", "validation_vocabulary_version", "evidence_summary",
        "initial_state", "steps", "termination",
    }

    def __init__(self, document: Mapping[str, Any]) -> None:
        _exact(document, self._FIELDS, "trajectory")
        owned = copy.deepcopy(dict(document))
        if owned["schema"] != TRAJECTORY_SCHEMA:
            raise TrajectoryError("unknown trajectory schema")
        if owned["validation_label"] != TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value:
            raise TrajectoryError("trajectory validation label is not replay-only")
        if owned["validation_vocabulary_version"] != VALIDATION_VOCABULARY_VERSION:
            raise TrajectoryError("unknown validation vocabulary version")
        scenario_identity = _token(owned["scenario_identity"], "scenario_identity")
        policy = _validate_generation_policy(owned["generation_policy"])
        evidence = owned["evidence_summary"]
        _exact(evidence, {"decision", "transition", "native_trace", "golden"}, "evidence summary")
        if evidence != {
            "decision": EvidenceMode.REFERENCE_MODEL.value,
            "transition": EvidenceMode.SANDBOX_EXTENSION.value,
            "native_trace": False,
            "golden": False,
        }:
            raise TrajectoryError("trajectory evidence summary changed")
        initial = TrajectoryStep._validate_state_facts(owned["initial_state"], "initial_state")
        if not isinstance(owned["steps"], list) or not owned["steps"]:
            raise TrajectoryError("complete trajectory requires committed steps")
        steps = [TrajectoryStep.from_dict(item) for item in owned["steps"]]
        for index, step in enumerate(steps):
            if step.step_index != index:
                raise TrajectoryError("trajectory step indexes are not contiguous")
        if steps[0].to_dict()["state_before"] != initial:
            raise TrajectoryError("first step does not begin at trajectory initial state")
        for prior, current in zip(steps, steps[1:]):
            if prior.to_dict()["state_after"] != current.to_dict()["state_before"]:
                raise TrajectoryError("trajectory state continuity mismatch")
        for index, step in enumerate(steps):
            step_document = step.to_dict()
            if step_document["path"] != [
                item.to_dict()["decision"]["selected_action_id"]
                for item in steps[: index + 1]
            ]:
                raise TrajectoryError("trajectory path continuity mismatch")
            if step_document["scenario"]["scenario_identity"] != scenario_identity:
                raise TrajectoryError("trajectory and step scenario identities differ")
        term = owned["termination"]
        _exact(term, {"reason", "depth", "custom_terminal_result"}, "termination")
        try:
            TrajectoryTerminationReason(term["reason"])
        except (TypeError, ValueError) as exc:
            raise TrajectoryError("unknown trajectory termination reason") from exc
        PresenceValue.from_dict(term["custom_terminal_result"])
        if _uint(term["depth"], "termination depth") != len(steps):
            raise TrajectoryError("termination depth differs from step count")
        if policy["max_depth"] != len(steps):
            raise TrajectoryError("complete trajectory does not reach generation horizon")
        identity_payload = copy.deepcopy(owned)
        supplied = _token(identity_payload.pop("trajectory_id"), "trajectory_id")
        if supplied != _identity(identity_payload):
            raise TrajectoryError("trajectory identity mismatch")
        self._document = owned
        self._steps = tuple(steps)

    @classmethod
    def create(
        cls,
        *,
        scenario_identity: str,
        generation_policy: Mapping[str, Any],
        initial_snapshot: TerraSnapshotV2,
        steps: Sequence[TrajectoryStep],
    ) -> "Trajectory":
        document: dict[str, Any] = {
            "schema": TRAJECTORY_SCHEMA,
            "scenario_identity": _token(scenario_identity, "scenario_identity"),
            "generation_policy": copy.deepcopy(dict(generation_policy)),
            "validation_label": TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY.value,
            "validation_vocabulary_version": VALIDATION_VOCABULARY_VERSION,
            "evidence_summary": {
                "decision": EvidenceMode.REFERENCE_MODEL.value,
                "transition": EvidenceMode.SANDBOX_EXTENSION.value,
                "native_trace": False,
                "golden": False,
            },
            "initial_state": snapshot_facts(initial_snapshot),
            "steps": [item.to_dict() for item in steps],
            "termination": {
                "reason": TrajectoryTerminationReason.GENERATION_HORIZON_REACHED.value,
                "depth": len(steps),
                "custom_terminal_result": PresenceValue.absent().to_dict(),
            },
        }
        document["trajectory_id"] = _identity(document)
        return cls(document)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Trajectory":
        return cls(data)

    @property
    def trajectory_id(self) -> str:
        return self._document["trajectory_id"]

    @property
    def steps(self) -> tuple[TrajectoryStep, ...]:
        return self._steps

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)


class ExclusionRecord:
    __slots__ = ("_document",)

    _FIELDS = {
        "schema", "exclusion_id", "source_path", "source_path_identity",
        "source_state_hash", "attempted_action_id", "depth", "classification",
        "reason", "evidence_mode", "source_revision", "source_rng",
        "source_unchanged",
    }

    def __init__(self, document: Mapping[str, Any]) -> None:
        _exact(document, self._FIELDS, "exclusion")
        owned = copy.deepcopy(dict(document))
        if owned["schema"] != EXCLUSION_SCHEMA:
            raise TrajectoryError("unknown exclusion schema")
        classification = ExclusionClassification(owned["classification"])
        mode = EvidenceMode(owned["evidence_mode"])
        if mode is not EvidenceMode.SANDBOX_EXTENSION:
            raise TrajectoryError("exclusion evidence must remain SANDBOX_EXTENSION")
        if not isinstance(owned["source_path"], list) or not all(
            isinstance(item, str) for item in owned["source_path"]
        ):
            raise TrajectoryError("exclusion source path must be an ordered action-id list")
        if owned["source_path_identity"] != _identity({"path": owned["source_path"]}):
            raise TrajectoryError("exclusion source-path identity mismatch")
        _token(owned["reason"], "exclusion reason")
        if owned["source_unchanged"] is not True:
            raise TrajectoryError("excluded branch must prove its source unchanged")
        _uint(owned["depth"], "exclusion depth")
        identity_payload = copy.deepcopy(owned)
        supplied = _token(identity_payload.pop("exclusion_id"), "exclusion_id")
        if supplied != _identity(identity_payload):
            raise TrajectoryError("exclusion identity mismatch")
        self._document = owned

    @classmethod
    def create(
        cls,
        *,
        source_path: Sequence[str],
        source_state_hash: str,
        attempted_action_id: str,
        depth: int,
        classification: ExclusionClassification,
        reason: str,
        evidence_mode: EvidenceMode,
        source_revision: Mapping[str, Any],
        source_rng: Mapping[str, Any],
    ) -> "ExclusionRecord":
        path = list(source_path)
        document: dict[str, Any] = {
            "schema": EXCLUSION_SCHEMA,
            "source_path": path,
            "source_path_identity": _identity({"path": path}),
            "source_state_hash": _token(source_state_hash, "source_state_hash"),
            "attempted_action_id": _token(attempted_action_id, "attempted_action_id"),
            "depth": _uint(depth, "depth"),
            "classification": classification.value,
            "reason": _token(reason, "reason"),
            "evidence_mode": evidence_mode.value,
            "source_revision": copy.deepcopy(dict(source_revision)),
            "source_rng": copy.deepcopy(dict(source_rng)),
            "source_unchanged": True,
        }
        document["exclusion_id"] = _identity(document)
        return cls(document)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExclusionRecord":
        return cls(data)

    @property
    def exclusion_id(self) -> str:
        return self._document["exclusion_id"]

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)
