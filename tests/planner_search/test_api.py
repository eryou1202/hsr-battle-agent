from __future__ import annotations

import unittest

from hsr_battle_agent.battle_sandbox.custom_scenario import CustomScenario
from hsr_battle_agent.planner_search.api import PlannerRequest, plan
from tests.planner_search._fixtures import fixture, horizon, policy


class ApiTests(unittest.TestCase):
    def test_same_input_and_cloned_state_produce_identical_bytes(self):
        scenario, contract = fixture()
        objective, search_policy = horizon(contract), policy()
        request = PlannerRequest(scenario, contract, objective, search_policy)
        original = plan(request)
        self.assertEqual(original.to_bytes(), plan(request).to_bytes())
        clone = CustomScenario(
            stage_id=scenario.stage_id, participants=scenario.participants,
            initial_state=scenario.initial_state.clone(), terminal_rule=scenario.terminal_rule,
        )
        replayed = plan(PlannerRequest(clone, contract, objective, search_policy))
        self.assertEqual(original.result_id, replayed.result_id)
        self.assertEqual(original.to_bytes(), replayed.to_bytes())
