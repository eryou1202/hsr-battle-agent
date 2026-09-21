# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.errors import StructuredRejectionError  # noqa: E402
from hsr_battle_agent.battle_sandbox.legacy_state_adapter import (  # noqa: E402
    LegacyProjectionError,
    LegacyStateProjection,
    project_certified_legacy_subset,
)
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState  # noqa: E402


class TestLegacyStateAdapter(unittest.TestCase):
    def test_supported_projection_is_deterministic_and_one_way(self):
        legacy = BattleState(extensions={"ordered": [2, 1]})
        left = project_certified_legacy_subset(legacy)
        right = project_certified_legacy_subset(legacy.to_dict())
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(left.certified_subset, {"schema_version": 4})
        self.assertFalse(left.can_construct_terra_state())
        self.assertNotIsInstance(left, TerraBattleState)
        with self.assertRaises(StructuredRejectionError) as raised:
            left.require_complete()
        self.assertEqual(
            raised.exception.reason_code,
            "LEGACY_STATE_PROJECTION_UNRESOLVED",
        )

    def test_payload_fields_are_unresolved_not_authoritative(self):
        projection = project_certified_legacy_subset(
            {"schema_version": 1, "extensions": {"x": [1]}}
        )
        handles = {item.provenance["legacy_field"]: item for item in projection.unresolved_fields}
        self.assertEqual(handles["extensions"].payload["presence"], "PRESENT")
        self.assertEqual(handles["extensions"].payload["value"], {"x": [1]})
        self.assertEqual(
            handles["turn_timeline"].payload,
            {"presence": "ABSENT"},
        )

    def test_unsupported_projection_rejects(self):
        with self.assertRaises(LegacyProjectionError):
            project_certified_legacy_subset(
                BattleState(), fields=("schema_version", "extensions")
            )
        with self.assertRaises(LegacyProjectionError):
            project_certified_legacy_subset({"extensions": {}})

    def test_no_shared_mutable_aliases(self):
        raw = {"schema_version": 4, "extensions": {"items": [1]}}
        projection = project_certified_legacy_subset(raw)
        raw["extensions"]["items"].append(2)
        exported = projection.to_dict()
        exported["unresolved_fields"][0]["payload"]["value"]["items"].append(3)
        restored = LegacyStateProjection.from_dict(projection.to_dict())
        exposed_handle = projection.unresolved_fields[0]
        exposed_handle.payload["value"]["items"].append(4)
        handle = next(
            item
            for item in restored.unresolved_fields
            if item.provenance["legacy_field"] == "extensions"
        )
        self.assertEqual(handle.payload["value"]["items"], [1])
        internal = next(
            item
            for item in projection.unresolved_fields
            if item.provenance["legacy_field"] == "extensions"
        )
        self.assertEqual(internal.payload["value"]["items"], [1])

    def test_unknown_legacy_fields_are_preserved_as_unresolved(self):
        projection = project_certified_legacy_subset(
            {"schema_version": 4, "future": {"tuple": (1, 2)}}
        )
        future = projection.unresolved_fields[-1]
        self.assertEqual(future.provenance["legacy_field"], "future")
        self.assertEqual(future.payload["value"]["tuple"], (1, 2))
        self.assertEqual(
            LegacyStateProjection.from_dict(projection.to_dict()).to_dict(),
            projection.to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
