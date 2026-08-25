"""Invariant tests for the cross-family interaction reference fixture."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


class CrossFamilyFixtureTest(unittest.TestCase):
    def test_fixture_is_explicitly_not_source_golden_and_commits_deterministically(self) -> None:
        path = Path("data/semantics/4.4.54/full_reconstruction/cross_family_interaction_fixture_001.json")
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(fixture["status"], "REFERENCE_INTERACTION_NOT_SOURCE_GOLDEN")
        self.assertEqual(len(fixture["trace"]), 5)
        self.assertEqual(fixture["trace"][3]["disposition"], "DAMAGE_COMMITTED")
        self.assertEqual(fixture["selected_state"]["entities"]["e1"]["survival"]["hp"], "800")
        self.assertEqual(fixture["selected_state"]["entities"]["e1"]["survival"]["shield"], "0")
        self.assertTrue(fixture["sources"]["predicate_operation_id"].startswith("external:"))
        self.assertTrue(fixture["sources"]["formula_operation_id"].startswith("external:"))


if __name__ == "__main__":
    unittest.main()
