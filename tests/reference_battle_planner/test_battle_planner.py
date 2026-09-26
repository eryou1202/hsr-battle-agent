from __future__ import annotations

import copy
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from hsr_battle_agent.game_data.reference_damage_adapters import ReferenceCombatState
from hsr_battle_agent.reference_sandbox import ReferenceActionEnvelope, ReferenceBattleSession, ReferenceSessionSpec
from hsr_battle_agent.reference_battle_planner import (
    HORIZON_ENTITY, HORIZON_RESOURCE, MIN_ENTITY, MIN_RESOURCE, REACH_ENTITY,
    REACH_RESOURCE,
    BattlePlanReplayError, ReferenceBattleObjective, ReferenceBattleSearchPolicy,
    ReferenceBattleAdapter, ResourceV1Boundary, search_battle_plans, validate_plan,
    validate_result,
)
from tests.reference_sandbox.test_local_session import fixture as m10_fixture
from tests.planner_search._fixtures import fixture as m9_fixture, horizon as m9_horizon, policy as m9_policy
from hsr_battle_agent.planner_search.api import PlannerRequest, plan as plan_m9


def fixture(*, resource: str = "5", tie: bool = False) -> ReferenceSessionSpec:
    """Synthetic envelopes using complete REF02 packet fields, not HSR skills."""
    base = m10_fixture()
    a = base.envelopes[0]
    light = copy.deepcopy(dict(a.packet))
    light["base_value"] = "5"
    light["resource_cost"] = "1"
    heavy = copy.deepcopy(dict(a.packet))
    heavy["base_value"] = "5" if tie else "10"
    heavy["resource_cost"] = "1" if tie else "2"
    envelopes = (
        ReferenceActionEnvelope("local.m11", "1", "z-light", "actor-a", ("actor-b",),
                                "ordinary:actor-a", "tests/game_data/test_reference_damage_v2.py:packet",
                                light, a.gate, Decimal("1")),
        ReferenceActionEnvelope("local.m11", "1", "a-heavy", "actor-a", ("actor-b",),
                                "ordinary:actor-a", "tests/game_data/test_reference_damage_v2.py:packet",
                                heavy, a.gate, Decimal(heavy["resource_cost"])),
        base.envelopes[1],
    )
    combat = ReferenceCombatState(base.combat_state.entities, base.combat_state.resource_owner,
                                  Decimal(resource), base.combat_state.timeline_token)
    return ReferenceSessionSpec(scenario=base.scenario, combat_state=combat, envelopes=envelopes,
                                timeline=base.timeline, speeds=base.speeds, max_actions=2)


def objective(kind: str, field: str = "HP", *, direction: str | None = None,
              operator: str | None = None, threshold: str | None = None) -> ReferenceBattleObjective:
    entity_id = "actor-b" if field != "REFERENCE_TEAM_RESOURCE" else None
    return ReferenceBattleObjective("tests.m11", "1", kind, field, entity_id,
                                    direction, operator, None if threshold is None else Decimal(threshold))


def policy(depth: int = 1, nodes: int = 100, plans: int = 3) -> ReferenceBattleSearchPolicy:
    return ReferenceBattleSearchPolicy("tests.m11", "1", depth, nodes, plans)


class ReferenceBattlePlannerTests(unittest.TestCase):
    def test_two_scope_boundary_keeps_m9_api(self) -> None:
        scenario, contract = m9_fixture()
        boundary = ResourceV1Boundary(scenario, contract)
        expected = boundary.search(m9_horizon(contract), m9_policy()).to_dict()
        direct = plan_m9(PlannerRequest(scenario, contract, m9_horizon(contract), m9_policy())).to_dict()
        self.assertEqual(json.dumps(expected, sort_keys=True), json.dumps(direct, sort_keys=True))
        self.assertEqual(boundary.scope, "SANDBOX_RESOURCE_V1")
        self.assertEqual(expected["scope"], boundary.scope)
        battle = ReferenceBattleAdapter(ReferenceBattleSession.create(fixture()))
        self.assertEqual(battle.scope, "REFERENCE_BATTLE_SANDBOX_V1_LOCAL_ACTION_ENVELOPE")
        self.assertEqual(battle.initial_identity(), battle.session.spec.identity)
        self.assertEqual(battle.step("z-light").session.combat_state.entity("actor-b").hp, Decimal("95"))

    def test_branching_hp_resource_and_source_order_tie(self) -> None:
        session = ReferenceBattleSession.create(fixture())
        original = session.snapshot().to_dict()
        self.assertEqual([x.action_id for x in session.legal_actions().actions], ["z-light", "a-heavy"])
        hp = search_battle_plans(session, objective(HORIZON_ENTITY, direction="MINIMIZE"), policy())
        resource = search_battle_plans(session, objective(HORIZON_RESOURCE, "REFERENCE_TEAM_RESOURCE", direction="MAXIMIZE"), policy())
        self.assertEqual(hp.plans[0].to_dict()["action_ids"], ["a-heavy"])
        self.assertEqual(resource.plans[0].to_dict()["action_ids"], ["z-light"])
        self.assertEqual(hp.to_dict()["explored_node_count"], 3)
        self.assertEqual(hp.to_dict()["committed_edge_count"], 2)
        self.assertEqual(hp.plans[0].to_dict()["steps"][0]["settlement_evidence"], "REFERENCE_MODEL")
        self.assertEqual(session.snapshot().to_dict(), original)
        tied = search_battle_plans(ReferenceBattleSession.create(fixture(tie=True)),
                                   objective(HORIZON_ENTITY, direction="MINIMIZE"), policy())
        self.assertEqual(tied.plans[0].to_dict()["action_ids"], ["z-light"])

    def test_reach_min_steps_zero_step_and_depth_two(self) -> None:
        session = ReferenceBattleSession.create(fixture())
        for kind in (REACH_ENTITY, MIN_ENTITY):
            found = search_battle_plans(session, objective(kind, operator="LE", threshold="90"), policy(depth=2))
            self.assertEqual(found.plans[0].to_dict()["action_ids"], ["a-heavy"])
            self.assertEqual(found.plans[0].to_dict()["termination_reason"], "OBJECTIVE_SATISFIED")
        root = search_battle_plans(session, objective(REACH_ENTITY, operator="LE", threshold="100"), policy(depth=2))
        self.assertEqual(root.plans[0].to_dict()["steps"], [])
        self.assertEqual(root.to_dict()["explored_node_count"], 1)
        depth2 = search_battle_plans(session, objective(HORIZON_ENTITY, direction="MINIMIZE"), policy(depth=2))
        self.assertEqual(depth2.to_dict()["explored_node_count"], 5)
        for plan in depth2.plans:
            steps = plan.to_dict()["steps"]
            self.assertEqual([x["acting_entity"] for x in steps], ["actor-a", "actor-b"])
            self.assertEqual(steps[0]["next_actor"], "actor-b")
            self.assertEqual(steps[1]["terminal_status"], "CUSTOM_TERMINAL")
            self.assertEqual(validate_plan(plan, objective(HORIZON_ENTITY, direction="MINIMIZE"), policy(depth=2)).steps_validated, 2)

    def test_toughness_and_resource_reach_objectives(self) -> None:
        session = ReferenceBattleSession.create(fixture())
        toughness = objective(HORIZON_ENTITY, "TOUGHNESS", direction="MINIMIZE")
        self.assertEqual(search_battle_plans(session, toughness, policy()).plans[0].to_dict()["action_ids"], ["z-light"])
        for kind in (REACH_RESOURCE, MIN_RESOURCE):
            declared = objective(kind, "REFERENCE_TEAM_RESOURCE", operator="LE", threshold="3")
            self.assertEqual(ReferenceBattleObjective.from_dict(declared.to_dict()).identity, declared.identity)
            result = search_battle_plans(session, declared, policy(depth=2))
            self.assertEqual(result.plans[0].to_dict()["action_ids"], ["a-heavy"])
        absent = ReferenceBattleObjective("tests.m11", "1", HORIZON_ENTITY, "HP", "missing", "MINIMIZE")
        self.assertEqual(search_battle_plans(session, absent, policy()).to_dict()["status"], "UNSUPPORTED")

    def test_limits_blockers_and_plan_truncation(self) -> None:
        session = ReferenceBattleSession.create(fixture())
        reach = objective(REACH_ENTITY, operator="LE", threshold="95")
        partial = search_battle_plans(session, reach, policy(nodes=2))
        self.assertEqual(partial.to_dict()["status"], "FOUND")
        self.assertFalse(partial.to_dict()["search_complete"])
        self.assertIn("NODE_LIMIT", partial.to_dict()["termination_reasons"])
        no_candidate = search_battle_plans(session, objective(REACH_ENTITY, operator="LT", threshold="0"), policy(nodes=1))
        self.assertEqual(no_candidate.to_dict()["status"], "LIMIT_REACHED")
        self.assertEqual(no_candidate.to_dict()["explored_node_count"], 1)
        self.assertEqual(no_candidate.to_dict()["committed_edge_count"], 1)
        blocked = search_battle_plans(ReferenceBattleSession.create(fixture(resource="3")),
                                      objective(HORIZON_ENTITY, direction="MINIMIZE"), policy(depth=2))
        self.assertEqual(blocked.to_dict()["status"], "FOUND")
        self.assertEqual(blocked.to_dict()["blocked_state_count"], 1)
        self.assertFalse(blocked.to_dict()["search_complete"])
        self.assertEqual(blocked.to_dict()["exclusions"][0]["classification"], "BLOCKED")
        one = search_battle_plans(session, objective(HORIZON_ENTITY, direction="MINIMIZE"), policy(plans=1))
        many = search_battle_plans(session, objective(HORIZON_ENTITY, direction="MINIMIZE"), policy(plans=2))
        self.assertEqual(one.plans[0].to_dict()["action_ids"], many.plans[0].to_dict()["action_ids"])
        self.assertEqual(one.to_dict()["explored_node_count"], many.to_dict()["explored_node_count"])

    def test_deterministic_replay_and_tamper_rejection(self) -> None:
        session = ReferenceBattleSession.create(fixture())
        obj = objective(HORIZON_ENTITY, direction="MINIMIZE")
        pol = policy()
        first = search_battle_plans(session, obj, pol)
        second = search_battle_plans(ReferenceBattleSession.create(fixture()), obj, pol)
        self.assertEqual(json.dumps(first.to_dict(), sort_keys=True), json.dumps(second.to_dict(), sort_keys=True))
        self.assertEqual(len(validate_result(first)), len(first.plans))
        plan = first.plans[0].to_dict()
        for field, value in (("selected_action_id", "z-light"), ("target_ids", ["actor-a"]),
                             ("hp_delta", "-1"), ("next_actor", "actor-a"),
                             ("settlement_evidence", "NATIVE_EVIDENCED"),
                             ("completion_policy", "OTHER"), ("schedule_policy", "OTHER")):
            with self.subTest(field=field):
                corrupted = copy.deepcopy(plan)
                corrupted["steps"][0][field] = value
                with self.assertRaises(BattlePlanReplayError):
                    validate_plan(corrupted, obj, pol)
        corrupted = copy.deepcopy(first.to_dict())
        corrupted["explored_node_count"] = 999
        with self.assertRaises((BattlePlanReplayError, ValueError)):
            validate_result(corrupted)


if __name__ == "__main__":
    unittest.main()
