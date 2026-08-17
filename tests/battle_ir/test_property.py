# -*- coding: utf-8 -*-
"""Canonical Generic Property IR tests (Handoffs 09/10/11)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.modifiers import ModifierRef, ModifierState  # noqa: E402
from hsr_battle_agent.battle_ir.property import (  # noqa: E402
    CURRENT_HP_PROPERTY_ID,
    SPECIAL_PROPERTY_IDS,
    MaterializationKind,
    ModifierPropertyContribution,
    PropertyChangeBoundary,
    PropertyEntry,
    StackPropertyTaskConfig,
    StackPropertyTaskContext,
    modifier_contribution_key,
    parse_property_entry_key,
    property_entry_key,
)
from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: E402


class TestPropertyEntryModel(unittest.TestCase):
    def test_create_empty_reserves_inactive_source_zero(self):
        entry = PropertyEntry.create_empty(
            materialization_kind=int(
                MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
            )
        )
        self.assertEqual(entry.source_generation, [0])
        self.assertEqual(entry.source_active, [False])
        self.assertEqual(entry.source_value, [0])
        self.assertEqual(entry.active_source_extent, 0)

    def test_dict_roundtrip_preserves_every_slot(self):
        entry = PropertyEntry(
            source_generation=[0, 5],
            source_active=[False, True],
            source_value=[123, 456],
            post_hook_context={"opaque": ["a", 1]},
            post_transform_a="opaque_a",
            post_transform_b=None,
            materialization_kind=3,
            generation_counter=5,
            active_source_extent=1,
            last_changed_source=1,
            base_or_fallback=10,
            materialized=466,
        )
        restored = PropertyEntry.from_dict(entry.to_dict())
        self.assertEqual(restored.to_dict(), entry.to_dict())
        self.assertIsNot(restored.source_value, entry.source_value)

    def test_from_dict_has_no_alias_to_input(self):
        data = {
            "schema": "battle_ir_property/1",
            "kind": "PropertyEntry",
            "source_generation": [0],
            "source_active": [False],
            "source_value": [0],
            "post_hook_context": {"nested": [1]},
        }
        entry = PropertyEntry.from_dict(data)
        data["source_value"][0] = 99
        data["post_hook_context"]["nested"].append(2)
        self.assertEqual(entry.source_value, [0])
        self.assertEqual(entry.post_hook_context, {"nested": [1]})

    def test_clone_isolation_both_directions(self):
        entry = PropertyEntry.create_empty()
        clone = entry.clone()
        clone.source_value[0] = 7
        clone.source_active[0] = True
        self.assertEqual(entry.source_value, [0])
        self.assertFalse(entry.source_active[0])
        entry.post_hook_context = {"x": [1]}
        self.assertIsNone(clone.post_hook_context)

    def test_equal_state_dicts_are_equal(self):
        self.assertEqual(
            PropertyEntry.create_empty().to_dict(),
            PropertyEntry.create_empty().to_dict(),
        )

    def test_invalid_parallel_array_length_rejected(self):
        with self.assertRaises(ValueError):
            PropertyEntry(
                source_generation=[0, 1],
                source_active=[False],
                source_value=[0],
            )

    def test_non_json_opaque_value_rejected(self):
        with self.assertRaises(TypeError):
            PropertyEntry(
                source_generation=[0],
                source_active=[False],
                source_value=[0],
                post_hook_context=object(),
            )


class TestPropertyKeys(unittest.TestCase):
    def test_property_entry_key_roundtrip(self):
        key = property_entry_key(EntityRef(42), 10)
        self.assertEqual(key, "property_entry:42:10")
        self.assertEqual(parse_property_entry_key(key), (42, 10))

    def test_modifier_contribution_key_is_logical_ref_only(self):
        ref = ModifierRef("A", EntityRef(7), 3)
        self.assertEqual(
            modifier_contribution_key(ref),
            "modifier_property:7:3:A",
        )

    def test_special_ids_include_current_hp(self):
        self.assertIn(CURRENT_HP_PROPERTY_ID, SPECIAL_PROPERTY_IDS)
        self.assertEqual(
            SPECIAL_PROPERTY_IDS,
            frozenset({10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32}),
        )


class TestContributionAndBoundaryRecords(unittest.TestCase):
    def test_contribution_roundtrip_preserves_identity(self):
        record = ModifierPropertyContribution(
            modifier=ModifierRef("A", EntityRef(1), 0),
            target=EntityRef(2),
            property_id=5,
            source_index=3,
        )
        self.assertEqual(
            ModifierPropertyContribution.from_dict(record.to_dict()),
            record,
        )

    def test_boundary_summary_is_deterministic(self):
        boundary = PropertyChangeBoundary(
            operation="source_allocated",
            entity=EntityRef(2),
            property_id=5,
            source_index=1,
            old_materialized=10,
            new_materialized=110,
        )
        self.assertEqual(boundary.trace_summary(), boundary.trace_summary())
        self.assertIn("source_allocated", boundary.trace_summary())
        self.assertIn("old:0xA", boundary.trace_summary())
        self.assertIn("new:0x6E", boundary.trace_summary())


class TestStackPropertyTaskIr(unittest.TestCase):
    def test_task_context_requires_modifier(self):
        with self.assertRaises(TypeError):
            StackPropertyTaskContext(modifier=None)

    def test_task_config_copies_opaque_payload(self):
        payload = {"nested": [1]}
        config = StackPropertyTaskConfig(property_id=5, target_payload=payload)
        payload["nested"].append(2)
        self.assertEqual(config.target_payload, {"nested": [1]})


if __name__ == "__main__":
    unittest.main()
