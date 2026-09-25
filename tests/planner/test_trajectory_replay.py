from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.planner.dataset import PlannerDataset
from hsr_battle_agent.planner.replay import (
    ReplayValidationError,
    replay_trajectory,
    validate_exclusion_replay,
    validate_dataset_replay,
)
from tests.planner._fixtures import blocked_generated, dataset


def identity(document):
    return hashlib.sha256(canonical_v2_bytes(document)).hexdigest()


def rehash_step_trajectory_dataset(document, trajectory_index=0, step_index=0):
    step = document["trajectories"][trajectory_index]["steps"][step_index]
    payload = copy.deepcopy(step)
    payload.pop("step_id", None)
    step["step_id"] = identity(payload)
    trajectory = document["trajectories"][trajectory_index]
    payload = copy.deepcopy(trajectory)
    payload.pop("trajectory_id", None)
    trajectory["trajectory_id"] = identity(payload)
    document["trajectory_identities"][trajectory_index] = trajectory["trajectory_id"]
    payload = copy.deepcopy(document)
    payload.pop("dataset_id", None)
    document["dataset_id"] = identity(payload)


def rehash_exclusion_dataset(document, exclusion_index=0):
    exclusion = document["exclusions"][exclusion_index]
    payload = copy.deepcopy(exclusion)
    payload.pop("exclusion_id", None)
    exclusion["exclusion_id"] = identity(payload)
    document["exclusion_identities"][exclusion_index] = exclusion["exclusion_id"]
    payload = copy.deepcopy(document)
    payload.pop("dataset_id", None)
    document["dataset_id"] = identity(payload)


class TrajectoryReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.contract, cls.dataset = dataset(2)

    def test_independent_dataset_replay_validates_all_records(self):
        result = validate_dataset_replay(self.dataset, self.scenario, self.contract)
        self.assertEqual(result.trajectories_validated, len(self.dataset.trajectories))
        self.assertEqual(result.exclusions_validated, len(self.dataset.exclusions))
        self.assertTrue(result.deterministic_replay_only)
        self.assertFalse(result.native_validated)

    def test_exclusion_ledger_is_independently_replayed(self):
        scenario, contract, constrained = dataset(2, "5")
        self.assertGreater(len(constrained.exclusions), 0)
        result = validate_dataset_replay(constrained, scenario, contract)
        self.assertEqual(result.exclusions_validated, len(constrained.exclusions))

    def test_single_trajectory_replay_reaches_exported_final_state(self):
        trajectory = self.dataset.trajectories[0]
        state = replay_trajectory(trajectory, self.scenario, self.contract)
        self.assertEqual(
            state.to_dict(),
            trajectory.steps[-1].to_dict()["state_after"]["snapshot"]["state"],
        )

    def test_rehashed_selected_action_corruption_is_detected_by_replay(self):
        changed = self.dataset.to_dict()
        changed["trajectories"][0]["steps"][1]["decision"]["selected_action_id"] = "D"
        changed["trajectories"][0]["steps"][1]["path"][-1] = "D"
        rehash_step_trajectory_dataset(changed, step_index=1)
        corrupted = PlannerDataset.from_dict(changed)
        with self.assertRaises(ReplayValidationError):
            validate_dataset_replay(corrupted, self.scenario, self.contract)

    def test_after_hash_corruption_is_detected(self):
        changed = self.dataset.to_dict()
        changed["trajectories"][0]["steps"][0]["state_after"]["semantic_hash"] = "0" * 64
        with self.assertRaises(Exception):
            PlannerDataset.from_dict(changed)

    def test_revision_corruption_is_detected(self):
        changed = self.dataset.to_dict()
        changed["trajectories"][0]["steps"][0]["state_after"]["revision"]["counter"] += 1
        with self.assertRaises(Exception):
            PlannerDataset.from_dict(changed)

    def test_rng_corruption_is_detected(self):
        changed = self.dataset.to_dict()
        changed["trajectories"][0]["steps"][0]["state_before"]["rng"]["algorithm"] = "fake"
        with self.assertRaises(Exception):
            PlannerDataset.from_dict(changed)

    def test_scenario_rule_identity_corruption_is_detected(self):
        changed = self.dataset.to_dict()
        changed["trajectories"][0]["steps"][0]["scenario"]["terminal_rule_identity"] = "0" * 64
        rehash_step_trajectory_dataset(changed)
        corrupted = PlannerDataset.from_dict(changed)
        with self.assertRaises(ReplayValidationError):
            validate_dataset_replay(corrupted, self.scenario, self.contract)

    def test_validation_label_corruption_is_detected(self):
        changed = self.dataset.to_dict()
        changed["trajectories"][0]["steps"][0]["validation_label"] = "NATIVE_TRACE"
        with self.assertRaises(Exception):
            PlannerDataset.from_dict(changed)

    def test_exclusion_source_mutation_or_reason_tamper_is_detected(self):
        _scenario, _contract, constrained = dataset(2, "5")
        changed = constrained.to_dict()
        changed["exclusions"][0]["source_state_hash"] = "0" * 64
        with self.assertRaises(Exception):
            PlannerDataset.from_dict(changed)
        changed = constrained.to_dict()
        changed["exclusions"][0]["reason"] = "fabricated reason"
        rehash_exclusion_dataset(changed)
        reparsed = PlannerDataset.from_dict(changed)
        with self.assertRaisesRegex(ReplayValidationError, "reason mismatch"):
            validate_dataset_replay(reparsed, _scenario, _contract)

    def test_authentic_blocked_exclusion_replays_and_tampered_reason_rejects(self):
        scenario, contract, generated = blocked_generated()
        self.assertEqual(generated.trajectories, ())
        self.assertEqual(len(generated.exclusions), 1)
        exclusion = generated.exclusions[0]
        self.assertEqual(exclusion.to_dict()["classification"], "BLOCKED")
        before = copy.deepcopy(scenario.initial_state.to_dict())
        validate_exclusion_replay(exclusion, scenario, contract)
        self.assertEqual(scenario.initial_state.to_dict(), before)

        changed = exclusion.to_dict()
        changed["reason"] = "fabricated blocked reason"
        payload = copy.deepcopy(changed)
        payload.pop("exclusion_id")
        changed["exclusion_id"] = identity(payload)
        with self.assertRaisesRegex(ReplayValidationError, "reason mismatch"):
            validate_exclusion_replay(changed, scenario, contract)


if __name__ == "__main__":
    unittest.main()
