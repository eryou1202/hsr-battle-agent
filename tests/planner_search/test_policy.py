from __future__ import annotations

import unittest

from hsr_battle_agent.planner_search.policy import PlannerPolicyError, PlannerSearchPolicy
from tests.planner_search._fixtures import policy


class PolicyTests(unittest.TestCase):
    def test_policy_roundtrip_and_identity(self):
        value = policy()
        restored = PlannerSearchPolicy.from_dict(value.to_dict())
        self.assertEqual(restored.identity, value.identity)
        self.assertEqual(restored.to_dict()["search_rng_draws"], 0)

    def test_rejects_invalid_limits_and_scope(self):
        for field in ("max_depth", "node_limit", "max_plans"):
            data = dict(namespace="tests.m9", version="1", max_depth=2, node_limit=10, max_plans=1)
            data[field] = 0
            with self.subTest(field=field), self.assertRaises(PlannerPolicyError):
                PlannerSearchPolicy(**data)
        with self.assertRaises(PlannerPolicyError):
            PlannerSearchPolicy("tests.m9", "1", 2, 10, 1, scope="GENERIC_BATTLE")
