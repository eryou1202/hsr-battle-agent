from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.planner.generator import generate_trajectories
from tests.planner._fixtures import (
    blocked_generated,
    generated,
    generation_policy,
    scenario_and_contract,
)


def by_path(result):
    return {
        tuple(step.to_dict()["decision"]["selected_action_id"] for step in trajectory.steps): trajectory
        for trajectory in result.trajectories
    }


class TrajectoryGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.contract, cls.result = generated(2)
        cls.paths = by_path(cls.result)

    def test_multiple_full_horizon_trajectories_exist(self):
        self.assertGreater(len(self.result.trajectories), 2)
        self.assertTrue(all(len(item.steps) == 2 for item in self.result.trajectories))

    def test_a_and_b_first_step_hashes_differ(self):
        a_hash = self.paths[("A", "A")].steps[0].to_dict()["state_after"]["semantic_hash"]
        b_hash = self.paths[("B", "A")].steps[0].to_dict()["state_after"]["semantic_hash"]
        self.assertNotEqual(a_hash, b_hash)

    def test_a_c_and_b_d_depth_two_states_differ(self):
        left = self.paths[("A", "C")].steps[1].to_dict()["state_after"]
        right = self.paths[("B", "D")].steps[1].to_dict()["state_after"]
        self.assertNotEqual(left["semantic_hash"], right["semantic_hash"])
        self.assertNotEqual(left["snapshot"]["state"]["stores"], right["snapshot"]["state"]["stores"])

    def test_repeat_generation_is_byte_structurally_identical(self):
        scenario, contract = scenario_and_contract()
        repeated = generate_trajectories(scenario, contract, generation_policy(2))
        self.assertEqual(
            [item.to_dict() for item in repeated.trajectories],
            [item.to_dict() for item in self.result.trajectories],
        )
        self.assertEqual(
            [item.to_dict() for item in repeated.exclusions],
            [item.to_dict() for item in self.result.exclusions],
        )

    def test_horizon_is_explicit_dataset_boundary_not_terminal_claim(self):
        for trajectory in self.result.trajectories:
            termination = trajectory.to_dict()["termination"]
            self.assertEqual(termination["reason"], "GENERATION_HORIZON_REACHED")
            self.assertEqual(termination["depth"], 2)
            self.assertNotIn("victory", str(termination).lower())

    def test_generation_uses_zero_rng_and_preserves_initial_state(self):
        scenario, contract = scenario_and_contract()
        before = copy.deepcopy(scenario.initial_state.to_dict())
        before_rng = scenario.initial_state.rng_state.to_dict()
        result = generate_trajectories(scenario, contract, generation_policy(2))
        self.assertTrue(result.trajectories)
        self.assertEqual(scenario.initial_state.to_dict(), before)
        for trajectory in result.trajectories:
            self.assertEqual(
                trajectory.steps[-1].to_dict()["state_after"]["rng"], before_rng
            )

    def test_branches_share_no_live_state_alias(self):
        first = self.result.trajectories[0].to_dict()
        second_before = self.result.trajectories[1].to_dict()
        first["steps"][0]["state_after"]["snapshot"]["state"]["allocator"]["namespaces"].append({})
        self.assertEqual(self.result.trajectories[1].to_dict(), second_before)

    def test_evidence_labels_remain_reference_and_sandbox(self):
        step = self.result.trajectories[0].steps[0].to_dict()
        self.assertEqual(step["decision"]["selected_action_evidence_mode"], EvidenceMode.REFERENCE_MODEL.value)
        self.assertEqual(step["transition"]["evidence_mode"], EvidenceMode.SANDBOX_EXTENSION.value)

    def test_invalid_late_branch_is_only_in_exclusion_ledger(self):
        _scenario, _contract, constrained = generated(2, "5")
        excluded_paths = {
            tuple(item.to_dict()["source_path"] + [item.to_dict()["attempted_action_id"]])
            for item in constrained.exclusions
        }
        successful_paths = set(by_path(constrained))
        self.assertIn(("D", "D"), excluded_paths)
        self.assertNotIn(("D", "D"), successful_paths)
        self.assertNotIn(("D",), successful_paths)

    def test_blocked_decision_context_emits_only_unchanged_exclusion(self):
        scenario, _contract, result = blocked_generated()
        before = copy.deepcopy(scenario.initial_state.to_dict())
        self.assertEqual(result.trajectories, ())
        self.assertEqual(len(result.exclusions), 1)
        exclusion = result.exclusions[0].to_dict()
        self.assertEqual(exclusion["classification"], "BLOCKED")
        self.assertEqual(exclusion["attempted_action_id"], "decision-context")
        self.assertEqual(exclusion["reason"], "UNSUPPORTED_TARGET:BLOCKED-A")
        self.assertTrue(exclusion["source_unchanged"])
        self.assertEqual(scenario.initial_state.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
