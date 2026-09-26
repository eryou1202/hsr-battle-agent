"""Source-order bounded DFS over immutable M10 battle sessions."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.legal_actions import LegalActionsStatus
from hsr_battle_agent.reference_sandbox import ReferenceBattleSession, ReferenceSandboxBlocked, SCOPE

from .adapter import ReferenceBattleAdapter
from .contract import (
    HORIZON_KINDS, BattlePlannerContractError, ReferenceBattleObjective,
    ReferenceBattleSearchPolicy, digest,
)

CONTENT_TARGET = "HSR-4.4.54"
VALIDATION = "DETERMINISTIC_REPLAY_ONLY"
PLAN_SCHEMA = "ReferenceBattlePlannerPlan/1"
RESULT_SCHEMA = "ReferenceBattlePlannerResult/1"
EVIDENCE = {"action_envelope": "SANDBOX_EXTENSION", "settlement": "REFERENCE_MODEL",
            "orchestration": "SANDBOX_EXTENSION", "validation": VALIDATION,
            "native_trace": False, "golden": False}
REASONS = ("OBJECTIVE_SATISFIED", "HORIZON_REACHED", "CUSTOM_TERMINAL",
           "BLOCKED_DECISION_CONTEXT", "REJECTED_ACTION", "NODE_LIMIT",
           "EXHAUSTED_SUPPORTED_BRANCHES", "UNSUPPORTED_OBJECTIVE_ENTITY")
STATUSES = frozenset(("FOUND", "NO_PLAN_WITHIN_HORIZON", "BLOCKED", "LIMIT_REACHED", "UNSUPPORTED"))


class BattlePlannerError(ValueError):
    pass


def _identified(document: dict[str, Any], name: str, domain: str) -> dict[str, Any]:
    document[name] = digest(document, domain)
    return document


class BattlePlan:
    _FIELDS = {
        "schema", "plan_id", "transition_scope", "session_spec_identity", "scenario_identity",
        "objective_identity", "search_policy_identity", "initial_spec", "initial_snapshot",
        "initial_hash", "action_ids", "action_ordinals", "steps", "per_step_hashes",
        "per_step_actors", "final_snapshot", "final_hash", "objective_value",
        "termination_reason", "evidence_summary", "validation_label",
    }

    def __init__(self, document: Mapping[str, Any]) -> None:
        self._document = copy.deepcopy(dict(document))
        d = self._document
        if set(d) != self._FIELDS or d.get("schema") != PLAN_SCHEMA or d.get("transition_scope") != SCOPE or d.get("evidence_summary") != EVIDENCE or d.get("validation_label") != VALIDATION:
            raise BattlePlannerError("invalid plan schema, scope or evidence")
        claimed = d.pop("plan_id", None)
        if claimed != digest(d, "reference-battle-plan/1"):
            raise BattlePlannerError("plan identity mismatch")
        d["plan_id"] = claimed
        if len(d["action_ids"]) != len(d["action_ordinals"]) or len(d["action_ids"]) != len(d["steps"]):
            raise BattlePlannerError("plan action/step lengths differ")
        if len(d["steps"]) != len(d["per_step_hashes"]) or len(d["steps"]) != len(d["per_step_actors"]):
            raise BattlePlannerError("plan step facts differ")
        if d["termination_reason"] not in ("OBJECTIVE_SATISFIED", "HORIZON_REACHED"):
            raise BattlePlannerError("invalid plan termination")
        previous = d["initial_snapshot"]
        for index, step in enumerate(d["steps"]):
            if step["before_snapshot"] != previous or step["selected_action_id"] != d["action_ids"][index]:
                raise BattlePlannerError("plan step continuity mismatch")
            if step["before_hash"] != d["per_step_hashes"][index]["before"] or step["after_hash"] != d["per_step_hashes"][index]["after"]:
                raise BattlePlannerError("plan hash continuity mismatch")
            if step["acting_entity"] != d["per_step_actors"][index]["acting_entity"] or step["next_actor"] != d["per_step_actors"][index]["next_actor"]:
                raise BattlePlannerError("plan actor continuity mismatch")
            previous = step["after_snapshot"]
        if previous != d["final_snapshot"] or d["objective_value"]["committed_steps"] != len(d["steps"]):
            raise BattlePlannerError("plan final state/depth mismatch")

    @property
    def plan_id(self) -> str:
        return self._document["plan_id"]

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)

    @classmethod
    def create(cls, **fields: Any) -> "BattlePlan":
        return cls(_identified({"schema": PLAN_SCHEMA, **fields}, "plan_id", "reference-battle-plan/1"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BattlePlan":
        return cls(data)


class BattlePlannerResult:
    _FIELDS = {
        "schema", "result_id", "content_target", "transition_scope", "session_spec_identity",
        "scenario_identity", "initial_spec", "initial_snapshot", "initial_hash", "objective",
        "objective_identity", "search_policy", "search_policy_identity", "status", "search_complete",
        "plans", "candidate_plan_count", "explored_node_count", "committed_edge_count",
        "rejected_edge_count", "blocked_state_count", "repeated_state_count", "exclusions",
        "termination_reasons", "evidence_summary",
    }

    def __init__(self, document: Mapping[str, Any]) -> None:
        self._document = copy.deepcopy(dict(document))
        d = self._document
        if set(d) != self._FIELDS or d.get("schema") != RESULT_SCHEMA or d.get("content_target") != CONTENT_TARGET or d.get("transition_scope") != SCOPE:
            raise BattlePlannerError("invalid result schema/content/scope")
        if d.get("status") not in STATUSES or type(d.get("search_complete")) is not bool or d.get("evidence_summary") != EVIDENCE:
            raise BattlePlannerError("invalid result status or evidence")
        policy = ReferenceBattleSearchPolicy.from_dict(d["search_policy"])
        objective = ReferenceBattleObjective.from_dict(d["objective"])
        if policy.identity != d["search_policy_identity"] or objective.identity != d["objective_identity"]:
            raise BattlePlannerError("policy/objective identity mismatch")
        plans = tuple(BattlePlan.from_dict(item) for item in d["plans"])
        if len(plans) > policy.max_plans or len(plans) > d["candidate_plan_count"]:
            raise BattlePlannerError("invalid plan count")
        for plan in plans:
            p = plan.to_dict()
            if p["objective_identity"] != objective.identity or p["search_policy_identity"] != policy.identity:
                raise BattlePlannerError("unbound selected plan")
            if p["session_spec_identity"] != d["session_spec_identity"] or p["initial_snapshot"] != d["initial_snapshot"]:
                raise BattlePlannerError("plan initial state mismatch")
        for name in ("explored_node_count", "committed_edge_count", "rejected_edge_count",
                     "blocked_state_count", "repeated_state_count", "candidate_plan_count"):
            if type(d[name]) is not int or d[name] < 0:
                raise BattlePlannerError(f"invalid {name}")
        claimed = d.pop("result_id", None)
        if claimed != digest(d, "reference-battle-planner-result/1"):
            raise BattlePlannerError("result identity mismatch")
        d["result_id"] = claimed
        self._plans = plans

    @property
    def plans(self) -> tuple[BattlePlan, ...]:
        return self._plans

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._document)

    @classmethod
    def create(cls, **fields: Any) -> "BattlePlannerResult":
        return cls(_identified({"schema": RESULT_SCHEMA, **fields}, "result_id", "reference-battle-planner-result/1"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BattlePlannerResult":
        return cls(data)


@dataclass
class _Frame:
    session: ReferenceBattleSession
    path: tuple[str, ...]
    ordinals: tuple[int, ...]
    steps: tuple[dict[str, Any], ...]
    entered: bool = False
    view: Any = None
    next_index: int = 0


def search_battle_plans(initial: ReferenceBattleSession, objective: ReferenceBattleObjective,
                        policy: ReferenceBattleSearchPolicy) -> BattlePlannerResult:
    if not isinstance(initial, ReferenceBattleSession) or not isinstance(objective, ReferenceBattleObjective) or not isinstance(policy, ReferenceBattleSearchPolicy):
        raise BattlePlannerError("M10 session, versioned objective and policy required")
    before = initial.snapshot().to_dict()
    spec = initial.spec
    spec_id = spec.identity
    initial_hash = initial.semantic_hash()
    counts = {"explored_node_count": 0, "committed_edge_count": 0,
              "rejected_edge_count": 0, "blocked_state_count": 0,
              "repeated_state_count": 0}
    exclusions: list[dict[str, Any]] = []
    candidates: list[tuple[_Frame, dict[str, Any], str]] = []
    reasons: set[str] = set()
    seen: dict[tuple[str, str, str, str, int, str], list[dict[str, Any]]] = {}
    limit_reached = False

    def make_result(status: str, complete: bool) -> BattlePlannerResult:
        ranked = sorted(candidates, key=lambda item: objective.rank_key(item[1], item[0].ordinals))
        selected = []
        for frame, value, reason in ranked[:policy.max_plans]:
            steps = list(frame.steps)
            selected.append(BattlePlan.create(
                transition_scope=SCOPE, session_spec_identity=spec_id,
                scenario_identity=spec.scenario.terminal_rule.content_sha256,
                objective_identity=objective.identity, search_policy_identity=policy.identity,
                initial_spec=spec.to_dict(), initial_snapshot=before, initial_hash=initial_hash,
                action_ids=list(frame.path), action_ordinals=list(frame.ordinals), steps=steps,
                per_step_hashes=[{"before": step["before_hash"], "after": step["after_hash"]} for step in steps],
                per_step_actors=[{"acting_entity": step["acting_entity"], "next_actor": step["next_actor"]} for step in steps],
                final_snapshot=frame.session.snapshot().to_dict(), final_hash=frame.session.semantic_hash(),
                objective_value=value, termination_reason=reason, evidence_summary=EVIDENCE,
                validation_label=VALIDATION,
            ).to_dict())
        return BattlePlannerResult.create(
            content_target=CONTENT_TARGET, transition_scope=SCOPE,
            session_spec_identity=spec_id, scenario_identity=spec.scenario.terminal_rule.content_sha256,
            initial_spec=spec.to_dict(), initial_snapshot=before, initial_hash=initial_hash,
            objective=objective.to_dict(), objective_identity=objective.identity,
            search_policy=policy.to_dict(), search_policy_identity=policy.identity,
            status=status, search_complete=complete, plans=selected,
            candidate_plan_count=len(candidates), **counts, exclusions=exclusions,
            termination_reasons=[x for x in REASONS if x in reasons], evidence_summary=EVIDENCE,
        )

    if not objective.supports(initial):
        reasons.add("UNSUPPORTED_OBJECTIVE_ENTITY")
        return make_result("UNSUPPORTED", False)

    stack = [_Frame(initial.clone(), (), (), ())]
    while stack:
        frame = stack[-1]
        if not frame.entered:
            counts["explored_node_count"] += 1
            frame.entered = True
            snapshot = frame.session.snapshot().to_dict()
            key = (SCOPE, spec_id, objective.identity, policy.identity,
                   policy.max_depth - len(frame.path), frame.session.semantic_hash())
            bucket = seen.setdefault(key, [])
            if snapshot in bucket:
                counts["repeated_state_count"] += 1
            else:
                bucket.append(snapshot)
            satisfied, value = objective.evaluate(frame.session, len(frame.path), policy.max_depth)
            if satisfied:
                reason = "HORIZON_REACHED" if objective.kind in HORIZON_KINDS else "OBJECTIVE_SATISFIED"
                candidates.append((frame, value, reason))
                reasons.add(reason)
                stack.pop()
                continue
            if len(frame.path) == policy.max_depth:
                reasons.add("HORIZON_REACHED")
                stack.pop()
                continue
            if frame.session.is_terminal():
                reasons.add("CUSTOM_TERMINAL")
                stack.pop()
                continue
            frame.view = ReferenceBattleAdapter(frame.session).legal_actions()
            if frame.view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
                counts["blocked_state_count"] += 1
                reasons.add("BLOCKED_DECISION_CONTEXT")
                exclusions.append({"classification": "BLOCKED", "source_path": list(frame.path),
                                   "source_hash": frame.session.semantic_hash(),
                                   "attempted_action_id": "decision-context",
                                   "reason": list(frame.view.blockers), "evidence_mode": "SANDBOX_EXTENSION"})
                stack.pop()
                continue
        if frame.next_index >= len(frame.view.actions):
            stack.pop()
            continue
        ordinal = frame.next_index
        action = frame.view.actions[ordinal]
        frame.next_index += 1
        source = frame.session.snapshot().to_dict()
        try:
            transition = ReferenceBattleAdapter(frame.session).commit(action.action_id)
        except ReferenceSandboxBlocked as exc:
            if frame.session.snapshot().to_dict() != source:
                raise BattlePlannerError("rejected action mutated source session") from exc
            counts["rejected_edge_count"] += 1
            reasons.add("REJECTED_ACTION")
            exclusions.append({"classification": "REJECTED", "source_path": list(frame.path),
                               "source_hash": frame.session.semantic_hash(),
                               "attempted_action_id": action.action_id,
                               "reason": exc.reason_code, "evidence_mode": "SANDBOX_EXTENSION"})
            continue
        if frame.session.snapshot().to_dict() != source:
            raise BattlePlannerError("committed action mutated source session")
        counts["committed_edge_count"] += 1
        if counts["explored_node_count"] >= policy.node_limit:
            limit_reached = True
            reasons.add("NODE_LIMIT")
            break
        stack.append(_Frame(transition.session, frame.path + (action.action_id,),
                            frame.ordinals + (ordinal,), frame.steps + (transition.to_dict(),)))

    if initial.snapshot().to_dict() != before:
        raise BattlePlannerError("search mutated caller session")
    if not limit_reached:
        reasons.add("EXHAUSTED_SUPPORTED_BRANCHES")
    status = ("FOUND" if candidates else "LIMIT_REACHED" if limit_reached else
              "BLOCKED" if counts["blocked_state_count"] else "NO_PLAN_WITHIN_HORIZON")
    return make_result(status, not limit_reached and counts["blocked_state_count"] == 0)
