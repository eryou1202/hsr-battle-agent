"""Invariant tests for the source-backed StackProperty reference trace."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


class SourceBackedPropertyReferenceTest(unittest.TestCase):
    def test_real_stack_property_writes_stable_slot(self) -> None:
        path = Path("data/semantics/4.4.54/full_reconstruction/source_backed_property_reference_001.json")
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(fixture["status"], "SOURCE_BACKED_REFERENCE_NOT_GOLDEN")
        self.assertEqual(fixture["trace"][0]["disposition"], "PROPERTY_CONTRIBUTION_SET")
        self.assertEqual(fixture["trace"][0]["property"], "AttackAddedRatio")
        state = fixture["selected_state"]
        self.assertEqual(state["property_state"]["contributions"]["AttackAddedRatio@MCommon_AttackRatioUp"], "0.12")
        self.assertTrue(fixture["source"]["behavior_id"].endswith("MCommon_AttackRatioUp"))


if __name__ == "__main__":
    unittest.main()
