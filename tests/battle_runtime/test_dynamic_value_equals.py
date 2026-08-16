# -*- coding: utf-8 -*-
"""DynamicValueEquals E4 branch coverage tests."""
from __future__ import annotations

import itertools
import math
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
from hsr_battle_agent.battle_runtime.values import (  # noqa: E402
    dynamic_value_equals,
)


def reference_dynamic_value_equals(lhs: DynamicValue, rhs: DynamicValue) -> bool:
    """Straight transcription of the E4 pseudocode in the vertical slice."""
    if lhs.value_type != rhs.value_type:
        return False
    tag = lhs.value_type
    if tag.value > 5:
        return False
    if tag is DynamicValueType.INT:
        return lhs.payload == rhs.payload
    if tag is DynamicValueType.FLOAT:
        return lhs.payload == rhs.payload
    if tag is DynamicValueType.BOOL:
        return (lhs.payload == 1) == (rhs.payload == 1)
    if tag is DynamicValueType.ARRAY:
        return lhs.payload.ref_id == rhs.payload.ref_id
    if tag is DynamicValueType.MAP:
        return lhs.payload.ref_id == rhs.payload.ref_id
    if tag is DynamicValueType.STRING:
        left = lhs.payload
        right = rhs.payload
        if left is right:
            return True
        if left is None or right is None:
            return False
        left_units = left.encode("utf-16-le", "surrogatepass")
        right_units = right.encode("utf-16-le", "surrogatepass")
        if len(left_units) != len(right_units):
            return False
        return left_units == right_units
    return False


class TestDynamicValueEqualsInt(unittest.TestCase):
    def test_equal(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.int_value(7), DynamicValue.int_value(7)))

    def test_unequal(self):
        self.assertFalse(dynamic_value_equals(DynamicValue.int_value(7), DynamicValue.int_value(-7)))

    def test_negative_int_equal(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.int_value(-1), DynamicValue.int_value(-1)))


class TestDynamicValueEqualsFloat(unittest.TestCase):
    def test_equal(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.float_value(1.5), DynamicValue.float_value(1.5)))

    def test_unequal(self):
        self.assertFalse(dynamic_value_equals(DynamicValue.float_value(1.5), DynamicValue.float_value(2.5)))

    def test_nan_never_equals_nan(self):
        nan = float("nan")
        self.assertFalse(dynamic_value_equals(DynamicValue.float_value(nan), DynamicValue.float_value(nan)))

    def test_positive_and_negative_zero_are_ieee_equal(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.float_value(0.0), DynamicValue.float_value(-0.0)))


class TestDynamicValueEqualsBool(unittest.TestCase):
    def test_one_vs_one(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.bool_value(1), DynamicValue.bool_value(1)))

    def test_zero_vs_zero(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.bool_value(0), DynamicValue.bool_value(0)))

    def test_one_vs_zero(self):
        self.assertFalse(dynamic_value_equals(DynamicValue.bool_value(1), DynamicValue.bool_value(0)))

    def test_non_one_payloads_normalize_before_compare(self):
        self.assertTrue(dynamic_value_equals(DynamicValue.bool_value(2), DynamicValue.bool_value(3)))
        self.assertFalse(dynamic_value_equals(DynamicValue.bool_value(1), DynamicValue.bool_value(2)))


class TestDynamicValueEqualsArray(unittest.TestCase):
    def test_same_ref_true(self):
        ref = ObjectRef(ref_id=1, contents=[1, 2, 3])
        self.assertTrue(
            dynamic_value_equals(DynamicValue.array_ref(ref), DynamicValue.array_ref(ref))
        )

    def test_different_ref_same_contents_false(self):
        contents = [1, 2, 3]
        left = ObjectRef(ref_id=1, contents=contents)
        right = ObjectRef(ref_id=2, contents=list(contents))
        self.assertFalse(
            dynamic_value_equals(DynamicValue.array_ref(left), DynamicValue.array_ref(right))
        )


class TestDynamicValueEqualsMap(unittest.TestCase):
    def test_same_ref_true(self):
        ref = ObjectRef(ref_id=9, contents={"a": 1})
        self.assertTrue(
            dynamic_value_equals(DynamicValue.map_ref(ref), DynamicValue.map_ref(ref))
        )

    def test_different_ref_same_contents_false(self):
        contents = {"a": 1, "b": [2]}
        left = ObjectRef(ref_id=9, contents=contents)
        right = ObjectRef(ref_id=10, contents=dict(contents))
        self.assertFalse(
            dynamic_value_equals(DynamicValue.map_ref(left), DynamicValue.map_ref(right))
        )


class TestDynamicValueEqualsString(unittest.TestCase):
    def test_same_reference_true(self):
        text = "abc"
        self.assertTrue(
            dynamic_value_equals(DynamicValue.string_value(text), DynamicValue.string_value(text))
        )

    def test_equal_content_different_reference_true(self):
        left = "abc"
        right = "".join(["a", "b", "c"])
        self.assertIsNot(left, right)
        self.assertTrue(
            dynamic_value_equals(DynamicValue.string_value(left), DynamicValue.string_value(right))
        )

    def test_unequal_content_false(self):
        self.assertFalse(
            dynamic_value_equals(DynamicValue.string_value("abc"), DynamicValue.string_value("abd"))
        )

    def test_same_length_unequal_content_false(self):
        self.assertFalse(
            dynamic_value_equals(DynamicValue.string_value("abc"), DynamicValue.string_value("xyz"))
        )

    def test_one_null_false(self):
        self.assertFalse(
            dynamic_value_equals(DynamicValue.string_value(None), DynamicValue.string_value("a"))
        )
        self.assertFalse(
            dynamic_value_equals(DynamicValue.string_value("a"), DynamicValue.string_value(None))
        )

    def test_both_null_pointers_true_by_e4_pointer_precheck(self):
        # E4 checks `a == b` before the null guard, and NULL pointers compare
        # equal.  This differs from Python/idiomatic NULL-value semantics.
        self.assertTrue(
            dynamic_value_equals(DynamicValue.string_value(None), DynamicValue.string_value(None))
        )

    def test_ordinal_utf16_surrogate_units_compare(self):
        astral = "\U00010000"
        explicit_surrogates = "\ud800\udc00"
        self.assertTrue(
            dynamic_value_equals(
                DynamicValue.string_value(astral),
                DynamicValue.string_value(explicit_surrogates),
            )
        )


class TestDynamicValueEqualsNullAndMismatch(unittest.TestCase):
    def test_null_vs_null_false(self):
        self.assertFalse(
            dynamic_value_equals(DynamicValue.null_value(), DynamicValue.null_value())
        )

    def test_null_vs_other_tag_false(self):
        self.assertFalse(
            dynamic_value_equals(DynamicValue.null_value(), DynamicValue.int_value(0))
        )

    def test_every_type_mismatch_is_false(self):
        cells = [
            DynamicValue.int_value(1),
            DynamicValue.float_value(1.0),
            DynamicValue.bool_value(1),
            DynamicValue.array_ref(ObjectRef(1, contents=[])),
            DynamicValue.map_ref(ObjectRef(1, contents={})),
            DynamicValue.string_value("1"),
            DynamicValue.null_value(),
        ]
        for left, right in itertools.permutations(cells, 2):
            with self.subTest(left=left, right=right):
                self.assertFalse(dynamic_value_equals(left, right))

    def test_operand_type_validation(self):
        with self.assertRaises(TypeError):
            dynamic_value_equals(None, DynamicValue.int_value(1))  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            dynamic_value_equals(DynamicValue.int_value(1), "x")  # type: ignore[arg-type]


class TestReferenceDifferential(unittest.TestCase):
    def test_runtime_matches_reference_over_sample_corpus(self):
        sample = [
            DynamicValue.int_value(0),
            DynamicValue.int_value(1),
            DynamicValue.int_value(-1),
            DynamicValue.float_value(0.0),
            DynamicValue.float_value(-0.0),
            DynamicValue.float_value(1.5),
            DynamicValue.float_value(float("nan")),
            DynamicValue.bool_value(0),
            DynamicValue.bool_value(1),
            DynamicValue.bool_value(2),
            DynamicValue.array_ref(ObjectRef(1, contents=[1, 2])),
            DynamicValue.array_ref(ObjectRef(2, contents=[1, 2])),
            DynamicValue.map_ref(ObjectRef(3, contents={"a": 1})),
            DynamicValue.map_ref(ObjectRef(4, contents={"a": 1})),
            DynamicValue.string_value("abc"),
            DynamicValue.string_value("abd"),
            DynamicValue.string_value(None),
            DynamicValue.null_value(),
        ]
        for left, right in itertools.product(sample, repeat=2):
            with self.subTest(left=left, right=right):
                self.assertEqual(
                    dynamic_value_equals(left, right),
                    reference_dynamic_value_equals(left, right),
                )


if __name__ == "__main__":
    unittest.main()
