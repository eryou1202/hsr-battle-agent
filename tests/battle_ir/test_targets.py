# -*- coding: utf-8 -*-
"""Canonical EntityRef / TargetSet representation tests (Batch 05)."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet


class TestEntityRef(unittest.TestCase):
    def test_immutable_and_stable_equality(self):
        a = EntityRef(runtime_id=7)
        b = EntityRef(runtime_id=7)
        c = EntityRef(runtime_id=8)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, c)
        self.assertEqual(a.runtime_id, 7)
        self.assertNotIn("id", a.__dict__)

    def test_clone_friendly(self):
        a = EntityRef(runtime_id=7)
        self.assertEqual(a.clone(), a)

    def test_serializable_roundtrip(self):
        a = EntityRef(runtime_id=-42)
        d = a.to_dict()
        b = EntityRef.from_dict(d)
        self.assertEqual(a, b)
        self.assertEqual(d["runtime_id"], -42)

    def test_rejects_non_int_runtime_id(self):
        with self.assertRaises(TypeError):
            EntityRef(runtime_id="7")
        with self.assertRaises(TypeError):
            EntityRef(runtime_id=True)


class TestTargetSet(unittest.TestCase):
    def test_ordered_tuple_backed_representation(self):
        a = EntityRef(runtime_id=1)
        b = EntityRef(runtime_id=2)
        target_set = TargetSet.of(a, b, a)
        self.assertEqual(target_set.items, (a, b, a))
        self.assertEqual(target_set.count, 3)

    def test_duplicates_preserved_and_null_allowed(self):
        a = EntityRef(runtime_id=1)
        target_set = TargetSet.of(a, None, a)
        self.assertEqual(target_set.items, (a, None, a))
        self.assertEqual(TargetSet().count, 0)
        self.assertIsNone(target_set.items[1])

    def test_order_is_semantic(self):
        a = EntityRef(runtime_id=1)
        b = EntityRef(runtime_id=2)
        self.assertNotEqual(TargetSet.of(a, b), TargetSet.of(b, a))

    def test_clone_friendly_and_deep_copy_independent(self):
        target_set = TargetSet.of(EntityRef(runtime_id=1))
        copied = copy.deepcopy(target_set)
        self.assertEqual(copied, target_set)
        self.assertEqual(target_set.clone(), target_set)

    def test_serializable_roundtrip_with_nulls(self):
        target_set = TargetSet.of(EntityRef(runtime_id=1), None)
        d = target_set.to_dict()
        restored = TargetSet.from_dict(d)
        self.assertEqual(restored, target_set)
        self.assertIsNone(restored.items[1])

    def test_rejects_non_tuple_or_bad_items(self):
        with self.assertRaises(TypeError):
            TargetSet(items=[EntityRef(runtime_id=1)])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            TargetSet.of(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
