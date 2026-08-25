"""Invariant tests for the source-backed HOT reference trace."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


class SourceBackedHotReferenceTest(unittest.TestCase):
    def test_real_source_payload_heals_fixture_state_deterministically(self) -> None:
        path = Path("data/semantics/4.4.54/full_reconstruction/source_backed_hot_reference_001.json")
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(fixture["status"], "SOURCE_BACKED_REFERENCE_NOT_GOLDEN")
        self.assertEqual(fixture["trace"][0]["disposition"], "BRANCH_SUCCESS")
        self.assertEqual(fixture["trace"][2]["disposition"], "HEAL_COMMITTED")
        self.assertEqual(fixture["selected_state"]["entities"]["p1"]["survival"]["hp"], "850.00")
        self.assertTrue(fixture["source"]["behavior_id"].endswith("MAvatar_Natasha_00_HOT_HPByMaxHP"))
        self.assertEqual(fixture["source"]["source_refs"][0]["commit"], "b11066beacc4de454b625fafc7ea3dd540c5bbf3")


if __name__ == "__main__":
    unittest.main()
