"""Canonical plans and search results, distinct from M8 datasets."""
from __future__ import annotations

import copy
import json
from decimal import Decimal
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.planner.trajectory import (
    ExclusionRecord, TrajectoryStep, snapshot_facts,
)
from hsr_battle_agent.planner_search.objective import PlannerObjective, decimal_text
from hsr_battle_agent.planner_search.policy import PlannerSearchPolicy, SCOPE, identity

PLAN_SCHEMA = "PlannerPlan/1"
RESULT_SCHEMA = "PlannerResult/1"
CONTENT_TARGET = "HSR-4.4.54"
EVIDENCE = {
    "decision": "REFERENCE_MODEL",
    "transition": "SANDBOX_EXTENSION",
    "validation": "DETERMINISTIC_REPLAY_ONLY",
    "native_trace": False,
    "golden": False,
}
STATUSES = frozenset((
    "FOUND", "NO_PLAN_WITHIN_HORIZON", "BLOCKED", "LIMIT_REACHED", "UNSUPPORTED",
))
REASONS = frozenset((
    "OBJECTIVE_SATISFIED", "HORIZON_REACHED", "EXHAUSTED_SUPPORTED_BRANCHES",
    "BLOCKED_DECISION_CONTEXT", "NODE_LIMIT", "UNSUPPORTED_OBJECTIVE_RESOURCE",
))


class PlannerResultError(ValueError):
    pass


def _exact(data: Mapping[str, Any], fields: set[str], name: str) -> None:
    if not isinstance(data, Mapping) or set(data) != fields:
        raise PlannerResultError(f"{name} has missing or unknown fields")


def _facts(data: Mapping[str, Any]) -> dict[str, Any]:
    _exact(data, {"snapshot", "semantic_hash", "revision", "revision_sequence", "rng"}, "state facts")
    expected = snapshot_facts(TerraSnapshotV2.from_dict(data["snapshot"]))
    if dict(data) != expected:
        raise PlannerResultError("state facts differ from complete snapshot")
    return expected


def _value(data: Mapping[str, Any]) -> None:
    _exact(data, {"resource_amount", "committed_steps"}, "objective value")
    amount = data["resource_amount"]
    if not isinstance(amount, str):
        raise PlannerResultError("resource amount must be a decimal string")
    try:
        parsed = Decimal(amount)
    except Exception as exc:
        raise PlannerResultError("invalid resource amount") from exc
    if not parsed.is_finite() or decimal_text(parsed) != amount:
        raise PlannerResultError("non-canonical objective resource amount")
    depth = data["committed_steps"]
    if type(depth) is not int or depth < 0:
        raise PlannerResultError("committed step count must be non-negative")


class PlannerPlan:
    __slots__ = ("_document", "_steps")
    _FIELDS = {
        "schema", "plan_id", "scope", "objective_identity", "search_policy_identity",
        "scenario_identity", "resource_contract_identity", "initial_state", "action_ids",
        "action_ordinals", "steps", "objective_value", "termination_reason",
        "validation_label", "evidence_summary", "related_exclusion_ids",
    }

    def __init__(self, data: Mapping[str, Any]) -> None:
        _exact(data, self._FIELDS, "plan")
        owned = copy.deepcopy(dict(data))
        if owned["schema"] != PLAN_SCHEMA or owned["scope"] != SCOPE:
            raise PlannerResultError("unknown plan schema or scope")
        if owned["evidence_summary"] != EVIDENCE or owned["validation_label"] != EVIDENCE["validation"]:
            raise PlannerResultError("plan evidence or validation overclaims")
        if owned["termination_reason"] not in ("OBJECTIVE_SATISFIED", "HORIZON_REACHED"):
            raise PlannerResultError("unknown plan termination")
        initial = _facts(owned["initial_state"])
        steps = [TrajectoryStep.from_dict(item) for item in owned["steps"]]
        actions = owned["action_ids"]
        ordinals = owned["action_ordinals"]
        if not isinstance(actions, list) or not isinstance(ordinals, list) or len(actions) != len(steps) or len(ordinals) != len(steps):
            raise PlannerResultError("plan actions/ordinals/steps differ")
        if any(not isinstance(a, str) or not a for a in actions) or any(type(n) is not int or n < 0 for n in ordinals):
            raise PlannerResultError("invalid action or ordinal")
        if not isinstance(owned["related_exclusion_ids"], list) or any(
            not isinstance(x, str) or not x for x in owned["related_exclusion_ids"]
        ):
            raise PlannerResultError("invalid related exclusion identities")
        previous = initial
        for index, step in enumerate(steps):
            document = step.to_dict()
            if document["step_index"] != index or document["path"] != actions[:index + 1]:
                raise PlannerResultError("plan step order/path mismatch")
            if document["state_before"] != previous:
                raise PlannerResultError("plan state continuity mismatch")
            if document["decision"]["selected_action_id"] != actions[index]:
                raise PlannerResultError("plan action differs from step")
            if document["scenario"]["scenario_identity"] != owned["scenario_identity"]:
                raise PlannerResultError("plan scenario differs from step")
            if document["scenario"]["resource_contract_identity"] != owned["resource_contract_identity"]:
                raise PlannerResultError("plan contract differs from step")
            previous = document["state_after"]
        _value(owned["objective_value"])
        if owned["objective_value"]["committed_steps"] != len(steps):
            raise PlannerResultError("objective value depth differs from plan")
        payload = copy.deepcopy(owned)
        if payload.pop("plan_id") != identity(payload):
            raise PlannerResultError("plan identity mismatch")
        self._document = owned
        self._steps = tuple(steps)

    @classmethod
    def create(cls, **fields: Any) -> "PlannerPlan":
        doc = {"schema": PLAN_SCHEMA, **fields}
        doc["plan_id"] = identity(doc)
        return cls(doc)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlannerPlan":
        return cls(data)

    @property
    def plan_id(self) -> str:
        return self._document["plan_id"]

    @property
    def steps(self) -> tuple[TrajectoryStep, ...]:
        return self._steps

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)


class PlannerResult:
    __slots__ = ("_document", "_plans", "_exclusions")
    _FIELDS = {
        "schema", "result_id", "content_target", "scope", "scenario_identity",
        "resource_contract_identity", "search_policy", "search_policy_identity",
        "objective", "objective_identity", "initial_state", "status", "search_complete",
        "plans", "candidate_plan_count", "explored_node_count", "committed_edge_count",
        "rejected_edge_count", "blocked_node_count", "repeated_state_count",
        "exclusions", "termination_reasons", "evidence_summary",
    }

    def __init__(self, data: Mapping[str, Any]) -> None:
        _exact(data, self._FIELDS, "result")
        owned = copy.deepcopy(dict(data))
        if owned["schema"] != RESULT_SCHEMA or owned["content_target"] != CONTENT_TARGET or owned["scope"] != SCOPE:
            raise PlannerResultError("unknown result schema/content/scope")
        if owned["evidence_summary"] != EVIDENCE:
            raise PlannerResultError("result evidence overclaims")
        policy = PlannerSearchPolicy.from_dict(owned["search_policy"])
        objective = PlannerObjective.from_dict(owned["objective"])
        if owned["search_policy_identity"] != policy.identity or owned["objective_identity"] != objective.identity:
            raise PlannerResultError("policy/objective identity mismatch")
        initial = _facts(owned["initial_state"])
        if owned["status"] not in STATUSES or type(owned["search_complete"]) is not bool:
            raise PlannerResultError("invalid search status/completeness")
        plans = [PlannerPlan.from_dict(item) for item in owned["plans"]]
        exclusions = [ExclusionRecord.from_dict(item) for item in owned["exclusions"]]
        if len({p.plan_id for p in plans}) != len(plans):
            raise PlannerResultError("duplicate selected plan")
        exclusion_ids = {e.exclusion_id for e in exclusions}
        for plan in plans:
            doc = plan.to_dict()
            if doc["initial_state"] != initial or doc["objective_identity"] != objective.identity or doc["search_policy_identity"] != policy.identity:
                raise PlannerResultError("selected plan is not bound to result")
            if doc["scenario_identity"] != owned["scenario_identity"] or doc["resource_contract_identity"] != owned["resource_contract_identity"]:
                raise PlannerResultError("selected plan scenario/contract mismatch")
            if not set(doc["related_exclusion_ids"]) <= exclusion_ids:
                raise PlannerResultError("plan refers to unknown exclusion")
        for name in ("candidate_plan_count", "explored_node_count", "committed_edge_count", "rejected_edge_count", "blocked_node_count", "repeated_state_count"):
            if type(owned[name]) is not int or owned[name] < 0:
                raise PlannerResultError(f"invalid {name}")
        if len(plans) > policy.max_plans or len(plans) > owned["candidate_plan_count"]:
            raise PlannerResultError("selected plan count exceeds declared bounds")
        if len(plans) != min(owned["candidate_plan_count"], policy.max_plans):
            raise PlannerResultError("selected plans do not match candidate/output count")
        explored = owned["explored_node_count"]
        if explored > policy.node_limit or (owned["status"] != "UNSUPPORTED" and explored == 0):
            raise PlannerResultError("explored node count violates root/limit rule")
        if owned["committed_edge_count"] not in (max(0, explored - 1), explored):
            raise PlannerResultError("committed edge count violates visited-node relation")
        if owned["rejected_edge_count"] != sum(e.to_dict()["classification"] == "REJECTED" for e in exclusions):
            raise PlannerResultError("rejected edge count differs from ledger")
        if owned["blocked_node_count"] != sum(e.to_dict()["classification"] == "BLOCKED" for e in exclusions):
            raise PlannerResultError("blocked node count differs from ledger")
        if not isinstance(owned["termination_reasons"], list) or len(owned["termination_reasons"]) != len(set(owned["termination_reasons"])) or not set(owned["termination_reasons"]) <= REASONS:
            raise PlannerResultError("invalid termination reasons")
        status = owned["status"]
        limited = "NODE_LIMIT" in owned["termination_reasons"]
        blocked = owned["blocked_node_count"] > 0
        if owned["search_complete"] != (status != "UNSUPPORTED" and not limited and not blocked):
            raise PlannerResultError("search completeness disagrees with blockers or limit")
        if status == "FOUND" and not plans:
            raise PlannerResultError("FOUND requires a selected plan")
        if status != "FOUND" and plans:
            raise PlannerResultError("non-FOUND result cannot select plans")
        if status == "NO_PLAN_WITHIN_HORIZON" and (not owned["search_complete"] or owned["candidate_plan_count"]):
            raise PlannerResultError("no-plan claim requires complete unsuccessful search")
        if status in ("BLOCKED", "LIMIT_REACHED", "UNSUPPORTED") and owned["search_complete"]:
            raise PlannerResultError("incomplete status cannot claim complete search")
        if status == "BLOCKED" and owned["blocked_node_count"] == 0:
            raise PlannerResultError("BLOCKED requires a blocked node")
        if status == "LIMIT_REACHED" and "NODE_LIMIT" not in owned["termination_reasons"]:
            raise PlannerResultError("LIMIT_REACHED requires node-limit reason")
        if status == "BLOCKED" and limited:
            raise PlannerResultError("node limit takes precedence over blocked status")
        if status == "UNSUPPORTED" and owned["explored_node_count"] != 0:
            raise PlannerResultError("unsupported request cannot explore nodes")
        payload = copy.deepcopy(owned)
        if payload.pop("result_id") != identity(payload):
            raise PlannerResultError("result identity mismatch")
        self._document = owned
        self._plans = tuple(plans)
        self._exclusions = tuple(exclusions)

    @classmethod
    def create(cls, **fields: Any) -> "PlannerResult":
        doc = {"schema": RESULT_SCHEMA, **fields}
        doc["result_id"] = identity(doc)
        return cls(doc)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlannerResult":
        return cls(data)

    @property
    def result_id(self) -> str:
        return self._document["result_id"]

    @property
    def plans(self) -> tuple[PlannerPlan, ...]:
        return self._plans

    @property
    def exclusions(self) -> tuple[ExclusionRecord, ...]:
        return self._exclusions

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)

    def to_bytes(self) -> bytes:
        return (json.dumps(self._document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
