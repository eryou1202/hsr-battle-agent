"""Independent re-execution of selected M10 action paths and M11 search output."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.battle_sandbox.legal_actions import LegalActionsStatus
from hsr_battle_agent.reference_sandbox import ReferenceBattleSession, ReferenceSessionSpec
from hsr_battle_agent.reference_sandbox.replay import replay_session

from .contract import HORIZON_KINDS, ReferenceBattleObjective, ReferenceBattleSearchPolicy
from .search import BattlePlan, BattlePlannerResult, search_battle_plans


class BattlePlanReplayError(ValueError):
    pass


@dataclass(frozen=True)
class BattlePlanValidation:
    plan_id: str
    steps_validated: int
    deterministic_replay_only: bool = True
    native_validated: bool = False


def validate_plan(plan: BattlePlan | Mapping[str, Any], objective: ReferenceBattleObjective,
                  policy: ReferenceBattleSearchPolicy) -> BattlePlanValidation:
    try:
        checked = plan if isinstance(plan, BattlePlan) else BattlePlan.from_dict(plan)
        d = checked.to_dict()
        if d["objective_identity"] != objective.identity or d["search_policy_identity"] != policy.identity:
            raise BattlePlanReplayError("objective/policy mismatch")
        spec = ReferenceSessionSpec.from_dict(d["initial_spec"])
        if spec.identity != d["session_spec_identity"] or spec.scenario.terminal_rule.content_sha256 != d["scenario_identity"]:
            raise BattlePlanReplayError("spec/scenario mismatch")
        session = ReferenceBattleSession.create(spec)
        if session.snapshot().to_dict() != d["initial_snapshot"] or session.semantic_hash() != d["initial_hash"]:
            raise BattlePlanReplayError("initial state mismatch")
        for index, recorded in enumerate(d["steps"]):
            satisfied_before, _ = objective.evaluate(session, index, policy.max_depth)
            if satisfied_before or session.is_terminal():
                raise BattlePlanReplayError("recorded plan continued after stop")
            view = session.legal_actions()
            ordinal = d["action_ordinals"][index]
            if (view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE or
                    type(ordinal) is not int or ordinal < 0 or ordinal >= len(view.actions) or
                    view.actions[ordinal].action_id != d["action_ids"][index]):
                raise BattlePlanReplayError("action or source ordinal mismatch")
            actual = session.step(d["action_ids"][index])
            if canonical_v2_bytes(actual.to_dict()) != canonical_v2_bytes(recorded):
                raise BattlePlanReplayError("M10 step mismatch")
            session = actual.session
        replayed = replay_session({"schema": "ReferenceBattleReplay/1", "spec": d["initial_spec"],
                                   "initial_snapshot": d["initial_snapshot"], "initial_hash": d["initial_hash"],
                                   "steps": d["steps"], "validation": "DETERMINISTIC_REPLAY_ONLY"})
        if replayed.semantic_hash() != session.semantic_hash():
            raise BattlePlanReplayError("M10 replay state mismatch")
        if session.snapshot().to_dict() != d["final_snapshot"] or session.semantic_hash() != d["final_hash"]:
            raise BattlePlanReplayError("final state mismatch")
        satisfied, value = objective.evaluate(session, len(d["steps"]), policy.max_depth)
        expected = "HORIZON_REACHED" if objective.kind in HORIZON_KINDS else "OBJECTIVE_SATISFIED"
        if not satisfied or value != d["objective_value"] or d["termination_reason"] != expected:
            raise BattlePlanReplayError("objective or termination mismatch")
        return BattlePlanValidation(checked.plan_id, len(d["steps"]))
    except BattlePlanReplayError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise BattlePlanReplayError(f"plan replay rejected: {exc}") from exc


def validate_result(result: BattlePlannerResult | Mapping[str, Any]) -> tuple[BattlePlanValidation, ...]:
    try:
        checked = result if isinstance(result, BattlePlannerResult) else BattlePlannerResult.from_dict(result)
        d = checked.to_dict()
        objective = ReferenceBattleObjective.from_dict(d["objective"])
        policy = ReferenceBattleSearchPolicy.from_dict(d["search_policy"])
        spec = ReferenceSessionSpec.from_dict(d["initial_spec"])
        if spec.identity != d["session_spec_identity"]:
            raise BattlePlanReplayError("result spec mismatch")
        initial = ReferenceBattleSession.create(spec)
        rerun = search_battle_plans(initial, objective, policy)
        if canonical_v2_bytes(rerun.to_dict()) != canonical_v2_bytes(d):
            raise BattlePlanReplayError("search result mismatch")
        return tuple(validate_plan(plan, objective, policy) for plan in checked.plans)
    except BattlePlanReplayError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise BattlePlanReplayError(f"result replay rejected: {exc}") from exc
