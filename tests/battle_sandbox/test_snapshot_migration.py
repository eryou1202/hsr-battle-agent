# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.lossless_value import PresenceState  # noqa: E402
from hsr_battle_agent.battle_sandbox.errors import StructuredRejectionError  # noqa: E402
from hsr_battle_agent.battle_sandbox.snapshot_migration import (  # noqa: E402
    MigrationError,
    MigrationResult,
    migrate_legacy_snapshot,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2  # noqa: E402


def fixture() -> dict:
    return {
        "schema_version": 1,
        "battle_state": {
            "schema_version": 4,
            "extensions": {"ordered": [2, 1]},
            "modifier_state_by_entity": {},
            "entity_property_entries": {},
            "modifier_property_contributions": {},
            "component_lock_hp_records": {},
            "turn_timeline": {},
        },
        "rng_state": {
            "schema_version": 1,
            "algorithm": "PYTHON_RANDOM_MT19937",
            "state": {"version": 3, "internal_state": [0], "gauss_next": None},
        },
        "trace": [{"type": "legacy-observation"}],
    }


class TestSnapshotMigration(unittest.TestCase):
    def test_known_fixture_is_read_deterministically_but_remains_blocked(self):
        left = migrate_legacy_snapshot(fixture())
        right = migrate_legacy_snapshot(copy.deepcopy(fixture()))
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(left.status, "BLOCKED_UNRESOLVED")
        self.assertFalse(left.can_construct_terra_snapshot())
        self.assertFalse(left.claims_semantic_equality())
        self.assertIsNotNone(left.certified_state_projection)
        with self.assertRaises(StructuredRejectionError):
            left.require_terra_snapshot()

    def test_raw_payload_and_unrepresentable_fields_round_trip_losslessly(self):
        raw = fixture()
        raw["future"] = {"tuple": (1, 2), "list": [1, 2], "null": None}
        result = migrate_legacy_snapshot(raw)
        raw["future"]["list"].append(3)
        exposed_raw = result.raw_legacy_payload
        exposed_raw["future"]["list"].append(4)
        exposed_handle = result.unresolved_fields[-1]
        exposed_handle.payload["value"]["list"].append(5)
        restored = MigrationResult.from_dict(result.to_dict())
        self.assertEqual(restored.raw_legacy_payload["future"]["tuple"], (1, 2))
        self.assertEqual(restored.raw_legacy_payload["future"]["list"], [1, 2])
        blocker_ids = tuple(item.blocker_id for item in restored.unresolved_fields)
        self.assertIn("LEGACY_SNAPSHOT_UNKNOWN_FIELD_FUTURE", blocker_ids)
        self.assertEqual(restored.to_dict(), result.to_dict())

    def test_ambiguous_absence_and_null_are_distinct_blockers(self):
        absent = migrate_legacy_snapshot({})
        null = migrate_legacy_snapshot(
            {"schema_version": None, "battle_state": None}
        )
        self.assertIs(absent.legacy_snapshot_schema.state, PresenceState.ABSENT)
        self.assertIs(null.legacy_snapshot_schema.state, PresenceState.NULL)
        absent_ids = {item.blocker_id for item in absent.unresolved_fields}
        null_ids = {item.blocker_id for item in null.unresolved_fields}
        self.assertIn("LEGACY_SNAPSHOT_SCHEMA_ABSENT", absent_ids)
        self.assertIn("LEGACY_SNAPSHOT_SCHEMA_NULL", null_ids)
        self.assertIn("LEGACY_SNAPSHOT_BATTLE_STATE_AMBIGUOUS", absent_ids)

    def test_no_terra_stores_or_identities_are_invented(self):
        document = migrate_legacy_snapshot(fixture()).to_dict()
        self.assertIsNone(document["terra_snapshot"])
        self.assertFalse(document["semantic_equality_claimed"])
        self.assertNotIn("allocator", document)
        self.assertNotIn("rng_streams", document)
        with self.assertRaises(MigrationError):
            broken = copy.deepcopy(document)
            broken["terra_snapshot"] = {"schema": "terra_snapshot/2"}
            MigrationResult.from_dict(broken)

    def test_v2_input_is_not_downgraded(self):
        with self.assertRaises(MigrationError):
            migrate_legacy_snapshot(
                {"schema": "terra_snapshot/2", "state": {}, "policy_identity": {}}
            )
        self.assertFalse(hasattr(MigrationResult, "to_legacy_snapshot"))
        self.assertFalse(hasattr(TerraSnapshotV2, "to_legacy_snapshot"))

    def test_unsupported_legacy_version_is_preserved_and_blocked(self):
        raw = fixture()
        raw["schema_version"] = 99
        result = migrate_legacy_snapshot(raw)
        self.assertEqual(result.raw_legacy_payload["schema_version"], 99)
        self.assertIn(
            "LEGACY_SNAPSHOT_SCHEMA_UNSUPPORTED",
            {item.blocker_id for item in result.unresolved_fields},
        )


if __name__ == "__main__":
    unittest.main()
