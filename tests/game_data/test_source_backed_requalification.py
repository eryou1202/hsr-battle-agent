from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "data/semantics/4.4.54/full_reconstruction"


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def find_key(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for nested in value.values():
            found = find_key(nested, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = find_key(nested, key)
            if found is not None:
                return found
    return None


class SourceBackedRequalificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.freeze = load("astra_semantic_freeze_v1.json")
        cls.ledger = load("terra_source_requalification_v1.json")

    def test_every_frozen_historical_fixture_is_ledgered_exactly_once(self):
        inventory = find_key(self.freeze, "source_backed_fixture_inventory")
        expected = {Path(item["artifact"]).name for item in inventory}
        actual = [item["artifact"] for item in self.ledger["entries"]]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))

    def test_frontier_is_explicit_and_never_promotes_reference(self):
        allowed = {"ACCEPTED", "REFERENCE", "QUARANTINED", "BLOCKED"}
        self.assertTrue(all(item["frontier"] in allowed for item in self.ledger["entries"]))
        self.assertFalse(any(item["frontier"] == "ACCEPTED" for item in self.ledger["entries"]))
        for item in self.ledger["entries"]:
            if item["frontier"] != "ACCEPTED":
                self.assertTrue(item["blockers"])
            self.assertNotEqual(item["evidence_mode"], "NATIVE_EVIDENCED")

    def test_historical_metrics_remain_separate_and_exact(self):
        self.assertEqual(self.ledger["historical_metrics"], {
            "canonical_records": 14042, "behavior_bearing_records": 10685,
            "report_entrypoints": 19715, "historically_executable_entrypoints": 4738,
            "historically_executable_bound_operations": 59595,
            "historically_executable_reference_records": 1528,
            "source_backed_executed_records": 4,
            "source_backed_executed_components": 27, "golden": 0,
        })
        current = self.ledger["current_frontier_metrics"]
        self.assertEqual(current["source_backed_executed_components"], 0)
        self.assertEqual(current["source_backed_executed_records"], 0)
        self.assertEqual(current["golden"], 0)

    def test_component_and_entrypoint_do_not_promote(self):
        by_name = {item["artifact"]: item for item in self.ledger["entries"]}
        component = by_name["source_backed_normal_damage_component_reference_001.json"]
        entrypoint = by_name["source_backed_modifier_dynamic_entrypoint_reference_001.json"]
        self.assertEqual(component["claim_unit"], "COMPONENT")
        self.assertEqual(entrypoint["claim_unit"], "ENTRYPOINT")
        self.assertNotEqual(component["claim_unit"], "RECORD")
        self.assertNotEqual(entrypoint["claim_unit"], "RECORD")

    def test_c02_mapping_coverage_is_not_execution_coverage(self):
        facts = self.ledger["c02_mapping_facts"]
        self.assertEqual((facts["d5_requested_ids"], facts["d5_occurrences"]), (11, 15))
        self.assertEqual((facts["d8_exact_trace_joins"], facts["d8_missing"], facts["d8_candidates"]),
                         (4696, 322, 136))
        self.assertTrue(facts["d9_documented_absence_preserved"])
        self.assertFalse(facts["execution_promotion"])

    def test_repeat_and_clone_are_stable_without_executor_output(self):
        cloned = copy.deepcopy(self.ledger)
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
        self.assertEqual(canonical(self.ledger), canonical(cloned))
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertFalse(any("strict_executor" in name for name in imported))

    def test_golden_remains_zero(self):
        self.assertEqual(self.ledger["historical_metrics"]["golden"], 0)
        self.assertEqual(self.ledger["current_frontier_metrics"]["golden"], 0)


if __name__ == "__main__":
    unittest.main()
