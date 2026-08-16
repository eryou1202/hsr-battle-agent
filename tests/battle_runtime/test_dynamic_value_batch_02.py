# -*- coding: utf-8 -*-
"""DynamicValue Batch 02 runtime tests.

These tests check the E4-recovered native register semantics against an
independent reference implementation of the artifact pseudocode.  Float
conversions are additionally pinned with hand-computed binary32 cases.
"""
from __future__ import annotations

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
from hsr_battle_agent.battle_runtime import (  # noqa: E402
    dynamic_value_is_array,
    dynamic_value_is_map,
    dynamic_value_is_null,
    dynamic_value_string,
    dynamic_value_to_bool,
    dynamic_value_to_double,
    dynamic_value_to_float,
    dynamic_value_to_int,
    dynamic_value_to_long,
    dynamic_value_to_uint,
    dynamic_value_type,
)

_INT64_MIN = -(2**63)
_INT32_MIN = -(2**31)
_UINT32_MASK = 0xFFFFFFFF


def _ref_trunc64(x: float) -> int:
    if math.isnan(x) or x >= 2**63 or x < _INT64_MIN:
        return _INT64_MIN
    return int(x)


def _ref_trunc32(x: float) -> int:
    if math.isnan(x) or x >= 2**31 or x < _INT32_MIN:
        return _INT32_MIN
    return int(x)


def _ref_int(value: DynamicValue) -> int:
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1 if value.payload == 1 else 0
    if tag is DynamicValueType.FLOAT:
        return _ref_trunc32(value.payload)
    if tag is DynamicValueType.INT:
        bits = value.payload & _UINT32_MASK
        return bits if bits < 2**31 else bits - 2**32
    return 0


def _ref_uint(value: DynamicValue) -> int:
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1 if value.payload == 1 else 0
    if tag is DynamicValueType.FLOAT:
        return _ref_trunc64(value.payload) & _UINT32_MASK
    if tag is DynamicValueType.INT:
        return value.payload & _UINT32_MASK
    return 0


def _ref_long(value: DynamicValue) -> int:
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1 if value.payload == 1 else 0
    if tag is DynamicValueType.FLOAT:
        return _ref_trunc64(value.payload)
    if tag is DynamicValueType.INT:
        return value.payload
    return 0


def _ref_bool(value: DynamicValue) -> bool:
    tag = value.value_type
    if tag in (DynamicValueType.INT, DynamicValueType.BOOL):
        return value.payload == 1
    return False


def _ref_string(value: DynamicValue) -> str | None:
    if value.value_type is DynamicValueType.STRING:
        return value.payload
    return None


def _ref_is_array(value: DynamicValue) -> bool:
    return (
        value.value_type is DynamicValueType.ARRAY
        and value.payload is not None
    )


def _ref_is_map(value: DynamicValue) -> bool:
    return (
        value.value_type is DynamicValueType.MAP
        and value.payload is not None
    )


def _ref_is_null(value: DynamicValue) -> bool:
    return value.value_type is DynamicValueType.NULL


def _sample_corpus() -> list[DynamicValue]:
    ints = [
        _INT64_MIN,
        -(2**63) + 1,
        -(2**40) - 3,
        -(2**33),
        -(2**32) - 1,
        -(2**32),
        -(2**31) - 1,
        _INT32_MIN,
        -3,
        -1,
        0,
        1,
        2,
        3,
        2**31 - 1,
        2**31,
        2**32 - 1,
        2**32,
        2**33,
        2**53,
        2**63 - 1,
    ]
    floats = [
        float("nan"),
        float("-inf"),
        -2.0**63,
        -(2.0**31 + 1.0),
        -(2.0**31),
        -1.75,
        -1.0,
        -0.0,
        0.0,
        1.0,
        1.75,
        2.0**31,
        2.0**31 + 1.0,
        2.0**63,
        float("inf"),
    ]
    bools = [-2, -1, 0, 1, 2, 3]
    ref_a = ObjectRef(ref_id=11)
    ref_b = ObjectRef(ref_id=12)
    strings = [None, "", "a", "A", "True", "\U0001f600", "a\ud800b"]

    cells: list[DynamicValue] = []
    for payload in ints:
        cells.append(DynamicValue(DynamicValueType.INT, payload))
    for payload in floats:
        cells.append(DynamicValue(DynamicValueType.FLOAT, payload))
    for payload in bools:
        cells.append(DynamicValue(DynamicValueType.BOOL, payload))
    cells.append(DynamicValue(DynamicValueType.ARRAY, ref_a))
    cells.append(DynamicValue(DynamicValueType.MAP, ref_a))
    cells.append(DynamicValue(DynamicValueType.ARRAY, ref_b))
    cells.append(DynamicValue(DynamicValueType.MAP, ref_b))
    for payload in strings:
        cells.append(DynamicValue(DynamicValueType.STRING, payload))
    cells.append(DynamicValue.null_value())
    return cells


class TestBatch02IntegerTagPrimitiveDifferential(unittest.TestCase):
    """Exhaustive tag 0..6 + payload sweep for integer/tag/string primitives."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = _sample_corpus()

    def test_int_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_to_int(cell), _ref_int(cell))

    def test_uint_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_to_uint(cell), _ref_uint(cell))

    def test_long_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_to_long(cell), _ref_long(cell))

    def test_bool_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_to_bool(cell), _ref_bool(cell))

    def test_string_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_string(cell), _ref_string(cell))

    def test_is_array_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_is_array(cell), _ref_is_array(cell))

    def test_is_map_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_is_map(cell), _ref_is_map(cell))

    def test_is_null_matches_reference(self):
        for cell in self.corpus:
            with self.subTest(tag=cell.tag_name, payload=cell.payload):
                self.assertEqual(dynamic_value_is_null(cell), _ref_is_null(cell))

    def test_value_type_matches_reference_over_all_tags(self):
        for tag in DynamicValueType:
            if tag in (DynamicValueType.ARRAY, DynamicValueType.MAP):
                cell = DynamicValue(tag, ObjectRef(1))
            elif tag is DynamicValueType.NULL:
                cell = DynamicValue.null_value()
            elif tag is DynamicValueType.INT:
                cell = DynamicValue.int_value(1)
            elif tag is DynamicValueType.FLOAT:
                cell = DynamicValue.float_value(1.0)
            elif tag is DynamicValueType.BOOL:
                cell = DynamicValue.bool_value(1)
            else:
                cell = DynamicValue.string_value("x")
            with self.subTest(tag=tag.name):
                self.assertEqual(dynamic_value_type(cell), tag.value)


class TestBatch02IntValueEdgeCases(unittest.TestCase):
    def test_int_low_dword_truncation(self):
        self.assertEqual(dynamic_value_to_int(DynamicValue.int_value(2**31)), -2**31)
        self.assertEqual(
            dynamic_value_to_int(DynamicValue.int_value(2**32 + 5)), 5
        )
        self.assertEqual(
            dynamic_value_to_int(DynamicValue.int_value(-(2**32) - 1)),
            -1,
        )

    def test_int_float_out_of_range_indefinite(self):
        self.assertEqual(
            dynamic_value_to_int(DynamicValue.float_value(2.0**40)),
            _INT32_MIN,
        )
        self.assertEqual(
            dynamic_value_to_int(DynamicValue.float_value(float("nan"))),
            _INT32_MIN,
        )

    def test_int_bool_normalization(self):
        self.assertEqual(dynamic_value_to_int(DynamicValue.bool_value(1)), 1)
        self.assertEqual(dynamic_value_to_int(DynamicValue.bool_value(0)), 0)
        self.assertEqual(dynamic_value_to_int(DynamicValue.bool_value(2)), 0)

    def test_int_mismatch_default_zero(self):
        for tag in (
            DynamicValueType.ARRAY,
            DynamicValueType.MAP,
            DynamicValueType.STRING,
            DynamicValueType.NULL,
        ):
            with self.subTest(tag=tag):
                cell = {
                    DynamicValueType.ARRAY: DynamicValue.array_ref(ObjectRef(1)),
                    DynamicValueType.MAP: DynamicValue.map_ref(ObjectRef(1)),
                    DynamicValueType.STRING: DynamicValue.string_value("1"),
                    DynamicValueType.NULL: DynamicValue.null_value(),
                }[tag]
                self.assertEqual(dynamic_value_to_int(cell), 0)


class TestBatch02UIntValueEdgeCases(unittest.TestCase):
    def test_uint_bit_preserving_int(self):
        self.assertEqual(
            dynamic_value_to_uint(DynamicValue.int_value(-1)), 2**32 - 1
        )
        self.assertEqual(
            dynamic_value_to_uint(DynamicValue.int_value(-(2**31))), 2**31
        )

    def test_uint_float_uses_64_bit_trunc_then_low32(self):
        self.assertEqual(
            dynamic_value_to_uint(DynamicValue.float_value(2.0**32)), 0
        )
        self.assertEqual(
            dynamic_value_to_uint(DynamicValue.float_value(-1.0)), 2**32 - 1
        )
        self.assertEqual(
            dynamic_value_to_uint(DynamicValue.float_value(float("nan"))),
            0,
        )


class TestBatch02LongValueEdgeCases(unittest.TestCase):
    def test_long_float_out_of_range_indefinite(self):
        self.assertEqual(
            dynamic_value_to_long(DynamicValue.float_value(float("nan"))),
            _INT64_MIN,
        )
        self.assertEqual(
            dynamic_value_to_long(DynamicValue.float_value(2.0**63)),
            _INT64_MIN,
        )

    def test_long_int_full_width(self):
        self.assertEqual(
            dynamic_value_to_long(DynamicValue.int_value(-(2**63))),
            -(2**63),
        )
        self.assertEqual(
            dynamic_value_to_long(DynamicValue.int_value(2**63 - 1)),
            2**63 - 1,
        )


class TestBatch02FloatValueEdgeCases(unittest.TestCase):
    def test_float_is_quantized_to_binary32(self):
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.float_value(16777217.0)),
            16777216.0,
        )

    def test_float_double_to_single_rounding(self):
        self.assertEqual(dynamic_value_to_float(DynamicValue.float_value(1.5)), 1.5)
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.float_value(1.0000001)),
            1.0000001192092896,
        )

    def test_float_int64_rounding_is_nearest_even(self):
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.int_value(16777217)),
            16777216.0,
        )
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.int_value(16777219)),
            16777220.0,
        )
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.int_value(-(2**63))),
            -(2.0**63),
        )

    def test_float_bool_returns_one_or_zero(self):
        self.assertEqual(dynamic_value_to_float(DynamicValue.bool_value(1)), 1.0)
        self.assertEqual(dynamic_value_to_float(DynamicValue.bool_value(0)), 0.0)
        self.assertEqual(dynamic_value_to_float(DynamicValue.bool_value(2)), 0.0)

    def test_float_special_values(self):
        nan = dynamic_value_to_float(DynamicValue.float_value(float("nan")))
        self.assertTrue(math.isnan(nan))
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.float_value(float("inf"))),
            float("inf"),
        )
        self.assertEqual(
            dynamic_value_to_float(DynamicValue.float_value(float("-inf"))),
            float("-inf"),
        )
        # cvtsd2ss preserves the sign of zero.
        self.assertEqual(
            math.copysign(
                1.0, dynamic_value_to_float(DynamicValue.float_value(-0.0))
            ),
            -1.0,
        )

    def test_float_mismatch_default_positive_zero(self):
        result = dynamic_value_to_float(DynamicValue.null_value())
        self.assertEqual(result, 0.0)
        self.assertEqual(math.copysign(1.0, result), 1.0)


class TestBatch02DoubleValueEdgeCases(unittest.TestCase):
    def test_double_int_conversion_is_correctly_rounded(self):
        self.assertEqual(
            dynamic_value_to_double(DynamicValue.int_value(2**53 + 1)),
            float(2**53),
        )
        self.assertEqual(
            dynamic_value_to_double(DynamicValue.int_value(2**53 - 1)),
            float(2**53 - 1),
        )

    def test_double_special_values(self):
        nan = dynamic_value_to_double(DynamicValue.float_value(float("nan")))
        self.assertTrue(math.isnan(nan))
        self.assertEqual(
            dynamic_value_to_double(DynamicValue.float_value(float("inf"))),
            float("inf"),
        )
        self.assertEqual(
            math.copysign(
                1.0, dynamic_value_to_double(DynamicValue.float_value(-0.0))
            ),
            -1.0,
        )

    def test_double_bool_returns_one_or_zero(self):
        self.assertEqual(dynamic_value_to_double(DynamicValue.bool_value(1)), 1.0)
        self.assertEqual(dynamic_value_to_double(DynamicValue.bool_value(0)), 0.0)
        self.assertEqual(dynamic_value_to_double(DynamicValue.bool_value(9)), 0.0)

    def test_double_mismatch_default_zero(self):
        self.assertEqual(dynamic_value_to_double(DynamicValue.null_value()), 0.0)


class TestBatch02BoolValueEdgeCases(unittest.TestCase):
    def test_bool_invalid_int_raw_returns_false(self):
        for raw in (-2, -1, 2, 3, 2**31):
            with self.subTest(raw=raw):
                self.assertFalse(
                    dynamic_value_to_bool(DynamicValue.int_value(raw))
                )

    def test_bool_valid_int_raw(self):
        self.assertFalse(dynamic_value_to_bool(DynamicValue.int_value(0)))
        self.assertTrue(dynamic_value_to_bool(DynamicValue.int_value(1)))

    def test_bool_bool_tag_normalizes(self):
        self.assertTrue(dynamic_value_to_bool(DynamicValue.bool_value(1)))
        self.assertFalse(dynamic_value_to_bool(DynamicValue.bool_value(0)))
        self.assertFalse(dynamic_value_to_bool(DynamicValue.bool_value(2)))

    def test_bool_mismatch_false(self):
        self.assertFalse(dynamic_value_to_bool(DynamicValue.string_value("true")))


class TestBatch02TagAndPayloadQueries(unittest.TestCase):
    def test_string_payload_and_mismatch(self):
        self.assertEqual(
            dynamic_value_string(DynamicValue.string_value("abc")), "abc"
        )
        self.assertIsNone(dynamic_value_string(DynamicValue.string_value(None)))
        self.assertIsNone(dynamic_value_string(DynamicValue.int_value(1)))

    def test_is_array_and_is_map(self):
        ref_a = ObjectRef(1)
        self.assertTrue(dynamic_value_is_array(DynamicValue.array_ref(ref_a)))
        self.assertFalse(dynamic_value_is_array(DynamicValue.map_ref(ref_a)))
        self.assertFalse(dynamic_value_is_array(DynamicValue.null_value()))
        self.assertTrue(dynamic_value_is_map(DynamicValue.map_ref(ref_a)))
        self.assertFalse(dynamic_value_is_map(DynamicValue.array_ref(ref_a)))
        self.assertFalse(dynamic_value_is_map(DynamicValue.null_value()))

    def test_is_null(self):
        self.assertTrue(dynamic_value_is_null(DynamicValue.null_value()))
        self.assertFalse(dynamic_value_is_null(DynamicValue.int_value(0)))

    def test_all_primitives_reject_non_dynamic_value(self):
        functions = (
            dynamic_value_to_int,
            dynamic_value_to_uint,
            dynamic_value_to_long,
            dynamic_value_to_float,
            dynamic_value_to_double,
            dynamic_value_to_bool,
            dynamic_value_type,
            dynamic_value_string,
            dynamic_value_is_array,
            dynamic_value_is_map,
            dynamic_value_is_null,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                with self.assertRaises(TypeError):
                    function(1)


if __name__ == "__main__":
    unittest.main()
