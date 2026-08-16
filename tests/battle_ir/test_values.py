# -*- coding: utf-8 -*-
"""Unit tests for canonical Battle IR value representation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.values import (  # noqa: E402
    DynamicValue,
    DynamicValueType,
    ObjectRef,
)


class TestDynamicValueType(unittest.TestCase):
    def test_ordinals_match_vertical_slice_01(self):
        expected = {
            "INT": 0,
            "FLOAT": 1,
            "BOOL": 2,
            "ARRAY": 3,
            "MAP": 4,
            "STRING": 5,
            "NULL": 6,
        }
        self.assertEqual(
            {item.name: item.value for item in DynamicValueType},
            expected,
        )

    def test_enum_cannot_be_extended_by_construction(self):
        with self.assertRaises(ValueError):
            DynamicValueType(7)


class TestObjectRef(unittest.TestCase):
    def test_same_ref_id_equal_even_with_different_metadata(self):
        left = ObjectRef(ref_id=7, contents=[1, 2, 3])
        right = ObjectRef(ref_id=7, contents=[9, 9, 9])
        self.assertEqual(left, right)

    def test_different_ref_id_unequal_even_with_identical_contents(self):
        contents = [1, 2, {"x": 3}]
        left = ObjectRef(ref_id=1, contents=contents)
        right = ObjectRef(ref_id=2, contents=list(contents))
        self.assertNotEqual(left, right)
        self.assertNotEqual(hash(left), hash(right))

    def test_ref_id_validation(self):
        with self.assertRaises(TypeError):
            ObjectRef("1")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ObjectRef(-1)


class TestDynamicValueConstruction(unittest.TestCase):
    def test_scalar_and_null_factories(self):
        self.assertEqual(DynamicValue.int_value(5).tag_name, "INT")
        self.assertEqual(DynamicValue.float_value(1.5).tag_name, "FLOAT")
        self.assertEqual(DynamicValue.bool_value(1).tag_name, "BOOL")
        self.assertEqual(DynamicValue.string_value("x").tag_name, "STRING")
        self.assertIsNone(DynamicValue.null_value().payload)
        self.assertEqual(DynamicValue.null_value().tag, 6)

    def test_bool_factory_preserves_raw_union_payload(self):
        self.assertEqual(DynamicValue.bool_value(2).payload, 2)
        self.assertEqual(DynamicValue.bool_value(0).payload, 0)

    def test_array_and_map_require_object_ref(self):
        ref = ObjectRef(ref_id=10, contents=[1, 2])
        self.assertEqual(DynamicValue.array_ref(ref).payload, ref)
        self.assertEqual(DynamicValue.map_ref(ref).payload, ref)
        with self.assertRaises(TypeError):
            DynamicValue(DynamicValueType.ARRAY, [1, 2])
        with self.assertRaises(TypeError):
            DynamicValue(DynamicValueType.MAP, {"a": 1})

    def test_int_payload_rejects_out_of_range_and_bool(self):
        with self.assertRaises(ValueError):
            DynamicValue.int_value(2**63)
        with self.assertRaises(TypeError):
            DynamicValue(DynamicValueType.INT, True)

    def test_invalid_tag_rejected_at_representation_boundary(self):
        with self.assertRaises(ValueError):
            DynamicValue(7, None)  # type: ignore[arg-type]

    def test_null_payload_must_be_none(self):
        with self.assertRaises(TypeError):
            DynamicValue(DynamicValueType.NULL, 0)

    def test_dynamic_value_is_intentionally_unhashable(self):
        with self.assertRaises(TypeError):
            hash(DynamicValue.int_value(1))


class TestDynamicValueClone(unittest.TestCase):
    def test_clone_preserves_scalar_payload(self):
        value = DynamicValue.float_value(float("nan"))
        cloned = value.clone()
        self.assertIsNot(value, cloned)
        self.assertEqual(value.value_type, cloned.value_type)
        self.assertNotEqual(cloned.payload, cloned.payload)  # NaN payload survives

    def test_clone_preserves_reference_identity(self):
        ref = ObjectRef(ref_id=42, contents={"a": [1, 2]})
        value = DynamicValue.map_ref(ref)
        cloned = value.clone()
        self.assertIs(cloned.payload, ref)
        self.assertEqual(cloned.payload, ObjectRef(ref_id=42, contents={}))

    def test_clone_does_not_change_original(self):
        ref = ObjectRef(ref_id=1, contents=[1])
        original = DynamicValue.array_ref(ref)
        cloned = original.clone()
        self.assertEqual(original.payload, cloned.payload)
        self.assertIsNot(original, cloned)


if __name__ == "__main__":
    unittest.main()
