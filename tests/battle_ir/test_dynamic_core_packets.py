"""Contract tests for Dynamic Core Closure v1 artifacts, without a network or DB."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "data" / "semantics" / "4.4.54" / "dynamic_core"
SCRIPT = REPO / "scripts" / "validate_dynamic_core_semantic_e2e.py"


def _load(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


class DynamicCorePacketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("dynamic_core_validator", SCRIPT)
        assert spec and spec.loader
        cls.validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.validator)

    def test_packet_bundle_is_complete_and_schema_valid(self) -> None:
        result = self.validator.validate()
        self.assertEqual(result["packet_count"], 11)
        self.assertEqual(result["overall_status"], "DYNAMIC_CORE_RECONSTRUCTION_PARTIAL")

    def test_every_packet_has_a_distinguishing_observation(self) -> None:
        packets = _load("packets_v1.json")["packets"]
        self.assertTrue(all(packet["distinguishing_observations"] for packet in packets))
        self.assertTrue(all(packet["DSH_implementation_boundary"] for packet in packets))

    def test_real_fixture_is_version_locked_and_unbuffed(self) -> None:
        fixture = _load("standard_dynamic_fixture_v1.json")
        self.assertEqual(fixture["game_version"], "4.4.54")
        self.assertEqual(fixture["static_scenario"]["stage_id"], "30113121")
        self.assertEqual(fixture["static_scenario"]["stage_buffs"], [])
        self.assertEqual(fixture["avatars"][0]["avatar_id"], "1105")

    def test_e2e_preserves_unresolved_heal_boundary(self) -> None:
        trace = _load("semantic_e2e_v1.json")["trace"]
        heal = next(row for row in trace if row["boundary"] == "real_natasha_heal_request")
        self.assertIn("CurrentHP remains FixPoint(400)", heal["state_diff"])
        blocked = next(row for row in trace if row["boundary"] == "positive_heal_consumer")
        self.assertTrue(blocked["state_diff"].startswith("STOP:"))


if __name__ == "__main__":
    unittest.main()
