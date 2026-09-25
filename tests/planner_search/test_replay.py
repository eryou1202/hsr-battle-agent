from __future__ import annotations

import copy
import unittest

from hsr_battle_agent.planner_search.api import PlannerRequest, plan
from hsr_battle_agent.planner_search.policy import identity
from hsr_battle_agent.planner_search.replay import (
    PlannerReplayError, validate_plan, validate_result,
)
from tests.planner_search._fixtures import fixture, horizon, policy, reach


class ReplayTests(unittest.TestCase):
    def test_prefix_and_zero_step_replay(self):
        scenario, contract = fixture()
        for objective in (reach(contract), reach(contract, threshold="10")):
            selected = plan(PlannerRequest(scenario, contract, objective, policy()))
            validation = validate_plan(selected.plans[0], scenario, contract, objective, policy())
            self.assertEqual(validation.steps_validated, len(selected.plans[0].steps))
            self.assertFalse(validation.native_validated)
            self.assertTrue(validation.deterministic_replay_only)

    def test_rehashed_action_ordinal_tamper_is_rejected(self):
        scenario, contract = fixture()
        objective = horizon(contract)
        selected = plan(PlannerRequest(scenario, contract, objective, policy()))
        changed = copy.deepcopy(selected.plans[0].to_dict())
        changed["action_ordinals"][0] = 1
        payload = copy.deepcopy(changed)
        payload.pop("plan_id")
        changed["plan_id"] = identity(payload)
        with self.assertRaisesRegex(PlannerReplayError, "ordinal mismatch"):
            validate_plan(changed, scenario, contract, objective, policy())

    def test_result_exclusions_replay_and_source_remains_unchanged(self):
        scenario, contract = fixture("5")
        before = scenario.initial_state.to_dict()
        objective = horizon(contract)
        search_policy = policy(plans=5)
        selected = plan(PlannerRequest(scenario, contract, objective, search_policy))
        validations = validate_result(selected, scenario, contract, objective, search_policy)
        self.assertEqual(len(validations), 5)
        self.assertEqual(len(validations), len(selected.plans))
        self.assertGreater(len(selected.exclusions), 0)
        self.assertEqual(scenario.initial_state.to_dict(), before)
