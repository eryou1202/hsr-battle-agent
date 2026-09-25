from __future__ import annotations

import unittest

from hsr_battle_agent.planner_search.api import PlannerRequest, plan
from tests.planner_search._fixtures import (
    blocked_fixture, fixture, horizon, policy, reach, tied_fixture,
)


def run(scenario, contract, objective, search_policy=None):
    return plan(PlannerRequest(scenario, contract, objective, search_policy or policy()))


class SearchTests(unittest.TestCase):
    def test_horizon_extrema_and_exact_counts(self):
        scenario, contract = fixture()
        maximum = run(scenario, contract, horizon(contract))
        minimum = run(scenario, contract, horizon(contract, "MINIMIZE"))
        self.assertEqual(maximum.plans[0].to_dict()["action_ids"], ["A", "A"])
        self.assertEqual(minimum.plans[0].to_dict()["action_ids"], ["D", "D"])
        self.assertEqual(maximum.to_dict()["explored_node_count"], 21)
        self.assertEqual(maximum.to_dict()["committed_edge_count"], 20)
        self.assertEqual(maximum.to_dict()["rejected_edge_count"], 0)
        self.assertTrue(maximum.to_dict()["search_complete"])

    def test_reach_min_steps_and_root_zero_step(self):
        scenario, contract = fixture()
        for objective in (reach(contract), reach(contract, minimum_steps=True)):
            found = run(scenario, contract, objective)
            self.assertEqual(found.plans[0].to_dict()["action_ids"], ["B"])
            self.assertEqual(found.plans[0].to_dict()["termination_reason"], "OBJECTIVE_SATISFIED")
        root = run(scenario, contract, reach(contract, threshold="10"))
        self.assertEqual(root.to_dict()["explored_node_count"], 1)
        self.assertEqual(root.plans[0].to_dict()["steps"], [])
        self.assertEqual(root.plans[0].to_dict()["action_ids"], [])

    def test_source_order_tie_ignores_action_id_lexical_order(self):
        scenario, contract = tied_fixture()
        result = run(scenario, contract, horizon(contract), policy(depth=1))
        self.assertEqual(result.plans[0].to_dict()["action_ids"], ["Z"])

    def test_rejections_blockers_and_absence_claim(self):
        scenario, contract = fixture("5")
        found = run(scenario, contract, horizon(contract))
        self.assertEqual(found.to_dict()["status"], "FOUND")
        self.assertEqual(found.to_dict()["explored_node_count"], 15)
        self.assertEqual(found.to_dict()["committed_edge_count"], 14)
        self.assertEqual(found.to_dict()["rejected_edge_count"], 6)
        self.assertTrue(all(e.to_dict()["classification"] == "REJECTED" for e in found.exclusions))
        no_plan = run(scenario, contract, reach(contract, "LT", "0"))
        self.assertEqual(no_plan.to_dict()["status"], "NO_PLAN_WITHIN_HORIZON")
        self.assertTrue(no_plan.to_dict()["search_complete"])
        blocked_scenario, blocked_contract = blocked_fixture()
        blocked = run(blocked_scenario, blocked_contract, horizon(blocked_contract))
        self.assertEqual(blocked.to_dict()["status"], "BLOCKED")
        self.assertEqual(blocked.to_dict()["explored_node_count"], 1)
        self.assertEqual(blocked.to_dict()["blocked_node_count"], 1)
        self.assertFalse(blocked.to_dict()["search_complete"])
        self.assertEqual(blocked.exclusions[0].to_dict()["attempted_action_id"], "decision-context")

    def test_node_limit_and_found_incomplete(self):
        scenario, contract = fixture()
        limit = run(scenario, contract, reach(contract, "LT", "0"), policy(nodes=1))
        self.assertEqual(limit.to_dict()["status"], "LIMIT_REACHED")
        self.assertEqual(limit.to_dict()["explored_node_count"], 1)
        self.assertEqual(limit.to_dict()["committed_edge_count"], 1)
        self.assertFalse(limit.to_dict()["search_complete"])
        partial = run(scenario, contract, reach(contract, threshold="9"), policy(nodes=2))
        self.assertEqual(partial.to_dict()["status"], "FOUND")
        self.assertFalse(partial.to_dict()["search_complete"])
        self.assertIn("NODE_LIMIT", partial.to_dict()["termination_reasons"])

    def test_max_plans_does_not_change_rank_one_or_search_counts(self):
        scenario, contract = fixture()
        one = run(scenario, contract, horizon(contract), policy(plans=1))
        five = run(scenario, contract, horizon(contract), policy(plans=5))
        self.assertEqual(one.plans[0].to_dict()["action_ids"], five.plans[0].to_dict()["action_ids"])
        self.assertEqual(len(one.plans), 1)
        self.assertEqual(len(five.plans), 5)
        for count in ("explored_node_count", "committed_edge_count", "candidate_plan_count"):
            self.assertEqual(one.to_dict()[count], five.to_dict()[count])

    def test_request_level_unsupported_and_full_state_accounting(self):
        scenario, contract = fixture()
        unsupported = run(scenario, contract, type(horizon(contract))(
            "tests.m9", "1", "RESOURCE_AT_HORIZON", "other:resource", comparison="MAXIMIZE"
        ))
        self.assertEqual(unsupported.to_dict()["status"], "UNSUPPORTED")
        self.assertEqual(unsupported.to_dict()["explored_node_count"], 0)
        result = run(scenario, contract, horizon(contract))
        self.assertEqual(result.to_dict()["repeated_state_count"], 0)
