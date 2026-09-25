from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.evidence_boundary import GateCertificate
from hsr_battle_agent.planner.trajectory import (
    Trajectory,
    TrajectoryError,
    TrajectoryStep,
    TrajectoryValidationLabel,
)
from tests.planner._fixtures import generated


class TrajectorySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.contract, cls.result = generated(2)
        cls.trajectory = cls.result.trajectories[0]
        cls.step = cls.trajectory.steps[0]

    def test_validation_label_is_not_evidence_mode_or_boolean(self):
        label = TrajectoryValidationLabel.DETERMINISTIC_REPLAY_ONLY
        self.assertNotIsInstance(label, EvidenceMode)
        with self.assertRaises(TrajectoryError):
            bool(label)

    def test_step_contains_complete_required_surfaces(self):
        data = self.step.to_dict()
        self.assertEqual(
            set(data),
            {
                "schema", "step_id", "step_index", "path", "state_before",
                "decision", "scenario", "transition", "state_after", "result",
                "validation_label", "validation_vocabulary_version",
            },
        )
        for side in ("state_before", "state_after"):
            self.assertEqual(
                set(data[side]),
                {"snapshot", "semantic_hash", "revision", "revision_sequence", "rng"},
            )

    def test_round_trip_preserves_canonical_identity(self):
        restored_step = TrajectoryStep.from_dict(self.step.to_dict())
        restored_trajectory = Trajectory.from_dict(self.trajectory.to_dict())
        self.assertEqual(restored_step.to_dict(), self.step.to_dict())
        self.assertEqual(restored_trajectory.to_dict(), self.trajectory.to_dict())

    def test_null_duplicates_and_source_order_survive(self):
        data = self.result.trajectories[0].steps[0].to_dict()
        actions = data["decision"]["legal_actions"]["actions"]
        self.assertEqual([item["action_id"] for item in actions], ["A", "B", "C", "D"])
        self.assertEqual(actions[0]["target_ids"], ["target", None, "target"])

    def test_termination_presence_is_explicit_absent(self):
        termination = self.trajectory.to_dict()["termination"]
        self.assertEqual(termination["reason"], "GENERATION_HORIZON_REACHED")
        self.assertEqual(termination["custom_terminal_result"]["presence"], "ABSENT")

    def test_public_documents_are_detached(self):
        before = self.trajectory.to_dict()
        leaked = self.trajectory.to_dict()
        leaked["steps"][0]["decision"]["legal_actions"]["actions"][0]["target_ids"].append("mutated")
        self.assertEqual(self.trajectory.to_dict(), before)

    def test_unknown_schema_and_validation_label_reject(self):
        for field, value in (("schema", "future/9"), ("validation_label", "GOLDEN")):
            changed = self.step.to_dict()
            changed[field] = value
            with self.assertRaises(TrajectoryError):
                TrajectoryStep.from_dict(changed)

        changed = self.trajectory.to_dict()
        changed["generation_policy"]["schema"] = "future_generation_policy/9"
        with self.assertRaisesRegex(TrajectoryError, "generation-policy schema"):
            Trajectory.from_dict(changed)

        changed = self.trajectory.to_dict()
        changed["evidence_summary"]["native_trace"] = True
        with self.assertRaisesRegex(TrajectoryError, "evidence summary"):
            Trajectory.from_dict(changed)

    def test_snapshot_fact_mutation_rejects_even_before_identity_check(self):
        changed = self.step.to_dict()
        changed["state_after"]["semantic_hash"] = "0" * 64
        with self.assertRaisesRegex(TrajectoryError, "facts"):
            TrajectoryStep.from_dict(changed)

    def test_trajectory_objects_have_no_native_permission_surface(self):
        self.assertNotIsInstance(self.step, GateCertificate)
        self.assertNotIsInstance(self.trajectory, GateCertificate)
        self.assertFalse(hasattr(self.trajectory, "execute"))
        self.assertFalse(hasattr(self.step, "is_native"))


if __name__ == "__main__":
    unittest.main()
