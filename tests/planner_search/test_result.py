from __future__ import annotations

import copy
import unittest

from hsr_battle_agent.planner_search.api import PlannerRequest, plan
from hsr_battle_agent.planner_search.result import PlannerResult, PlannerResultError
from tests.planner_search._fixtures import fixture, horizon, policy


class ResultTests(unittest.TestCase):
    def test_canonical_roundtrip_and_no_native_labels(self):
        scenario, contract = fixture()
        result = plan(PlannerRequest(scenario, contract, horizon(contract), policy()))
        restored = PlannerResult.from_dict(result.to_dict())
        self.assertEqual(restored.result_id, result.result_id)
        self.assertEqual(restored.to_bytes(), result.to_bytes())
        self.assertEqual(restored.to_dict()["evidence_summary"]["validation"], "DETERMINISTIC_REPLAY_ONLY")
        self.assertFalse(restored.to_dict()["evidence_summary"]["golden"])

    def test_rejects_overclaimed_native_validation(self):
        scenario, contract = fixture()
        result = plan(PlannerRequest(scenario, contract, horizon(contract), policy()))
        changed = copy.deepcopy(result.to_dict())
        changed["evidence_summary"]["native_trace"] = True
        with self.assertRaises(PlannerResultError):
            PlannerResult.from_dict(changed)
