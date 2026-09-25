from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.planner.dataset import (
    DatasetError,
    PlannerDataset,
    export_dataset,
    load_dataset,
)
from tests.planner._fixtures import dataset


class DatasetExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.contract, cls.dataset = dataset(2)

    def test_manifest_is_honestly_local_not_golden_or_native(self):
        data = self.dataset.to_dict()
        self.assertEqual(data["classification"]["scope"], "LOCAL_SANDBOX_EXTENSION")
        self.assertEqual(data["classification"]["validation"], "DETERMINISTIC_REPLAY_ONLY")
        self.assertEqual(data["classification"]["golden"], "NOT_GOLDEN")
        self.assertEqual(data["classification"]["native_trace"], "NOT_NATIVE_TRACE")
        self.assertEqual(data["golden_count"], 0)
        self.assertEqual(data["native_trace_count"], 0)

    def test_manifest_counts_and_ordered_identities_match_records(self):
        data = self.dataset.to_dict()
        self.assertEqual(data["trajectory_count"], len(data["trajectories"]))
        self.assertEqual(data["exclusion_count"], len(data["exclusions"]))
        self.assertEqual(data["trajectory_identities"], [x["trajectory_id"] for x in data["trajectories"]])
        self.assertEqual(data["exclusion_identities"], [x["exclusion_id"] for x in data["exclusions"]])

    def test_round_trip_and_dataset_identity_are_stable(self):
        restored = PlannerDataset.from_dict(self.dataset.to_dict())
        self.assertEqual(restored.dataset_id, self.dataset.dataset_id)
        self.assertEqual(restored.to_dict(), self.dataset.to_dict())

    def test_same_dataset_exports_byte_identically(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            left = export_dataset(self.dataset, first).read_bytes()
            right = export_dataset(self.dataset, second).read_bytes()
        self.assertEqual(left, right)

    def test_export_load_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = export_dataset(self.dataset, directory)
            restored = load_dataset(path)
        self.assertEqual(restored.to_dict(), self.dataset.to_dict())

    def test_export_contains_no_machine_path_username_or_timestamp(self):
        text = self.dataset.to_bytes().decode("utf-8")
        self.assertNotIn(str(REPO), text)
        self.assertNotIn("Users", text)
        self.assertNotIn("generated_at", text)
        self.assertNotIn("timestamp", text)

    def test_bad_output_location_and_filename_reject(self):
        with self.assertRaises(DatasetError):
            export_dataset(self.dataset, REPO / "does-not-exist")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DatasetError):
                export_dataset(self.dataset, directory, filename="../escape.json")

    def test_unknown_schema_and_count_tampering_reject(self):
        for key, value in (("schema", "future/9"), ("trajectory_count", 0)):
            changed = self.dataset.to_dict()
            changed[key] = value
            with self.assertRaises(DatasetError):
                PlannerDataset.from_dict(changed)


if __name__ == "__main__":
    unittest.main()
