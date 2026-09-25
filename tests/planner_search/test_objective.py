from __future__ import annotations

import unittest
from decimal import Decimal

from hsr_battle_agent.planner_search.objective import (
    AT_HORIZON, PlannerObjective, PlannerObjectiveError,
)
from tests.planner_search._fixtures import fixture, horizon, reach


class ObjectiveTests(unittest.TestCase):
    def test_explicit_resource_and_predicate_roundtrip(self):
        scenario, contract = fixture()
        objective = reach(contract, threshold="8.00")
        self.assertEqual(objective.to_dict()["threshold"], "8")
        restored = PlannerObjective.from_dict(objective.to_dict())
        self.assertEqual(restored.identity, objective.identity)
        self.assertFalse(objective.evaluate(scenario.initial_state, contract, 0, 2)[0])
        self.assertTrue(horizon(contract).supports(contract))

    def test_no_generic_metric_or_nonfinite_threshold(self):
        _, contract = fixture()
        with self.assertRaises(PlannerObjectiveError):
            PlannerObjective("tests.m9", "1", "DAMAGE_SCORE", contract.resource_key)
        with self.assertRaises(PlannerObjectiveError):
            PlannerObjective("tests.m9", "1", AT_HORIZON, contract.resource_key, comparison="NATIVE_BEST")
        with self.assertRaises(PlannerObjectiveError):
            PlannerObjective("tests.m9", "1", "REACH_RESOURCE_COMPARISON", contract.resource_key,
                             operator="LE", threshold=Decimal("NaN"))
