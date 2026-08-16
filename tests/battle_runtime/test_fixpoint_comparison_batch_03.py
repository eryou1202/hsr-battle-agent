# -*- coding: utf-8 -*-
"""Runtime tests for FixPoint Comparison Batch 03 primitives.

The comparison functions are verified two ways:

1. canonical int32 -> raw encodings are ordered exactly like the signed int32
   source values, for every operator pair;
2. an instruction-level reference model of the native branch structure is
   differential-tested against the consolidated implementation over random
   qword raw values, including non-canonical low-7-bit fractions.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
    fixpoint_greater,
    fixpoint_greater_equal,
    fixpoint_is_negative,
    fixpoint_is_positive,
    fixpoint_is_zero,
    fixpoint_less,
    fixpoint_less_equal,
    fixpoint_not_equal,
)

MASK64 = 0xFFFFFFFFFFFFFFFF
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def signed64(value: int) -> int:
    value &= MASK64
    return value - (1 << 64) if value & (1 << 63) else value


def sar64(value: int, shift: int) -> int:
    return (signed64(value) >> shift) & MASK64


def sign(value: int) -> int:
    return (value > 0) - (value < 0)


def reference_fixpoint_compare(lhs: int, rhs: int) -> int:
    """Direct translation of each native compare body branch structure."""
    lhs &= MASK64
    rhs &= MASK64
    lhs_ext = lhs & 1
    rhs_ext = rhs & 1

    if lhs_ext == 1 and rhs_ext == 0:
        cmp = sign(signed64(lhs & ~1) - signed64(sar64(rhs, 7)))
        if cmp == 0 and (rhs & 0x7F):
            return -1
        return cmp

    if lhs_ext == 0 and rhs_ext == 1:
        cmp = sign(signed64(sar64(lhs, 7)) - signed64(rhs & ~1))
        if cmp == 0 and (lhs & 0x7F):
            return 1
        return cmp

    if lhs_ext == 0 and rhs_ext == 0:
        return sign(signed64(lhs) - signed64(rhs))

    return sign(signed64(lhs & ~1) - signed64(rhs & ~1))


class TestFixPointFromInt32(unittest.TestCase):
    def test_zero_and_unit_encodings(self):
        self.assertEqual(fixpoint_from_int32(0), 0)
        self.assertEqual(fixpoint_from_int32(1), 1 << 33)
        self.assertEqual(fixpoint_from_int32(-1), (-1 << 33) & MASK64)

    def test_threshold_mode_switch(self):
        # STANDARD: abs(n) < 0x40000000.
        self.assertEqual(fixpoint_from_int32(0x3FFFFFFF), 0x3FFFFFFF << 33)
        self.assertEqual(
            fixpoint_from_int32(-0x3FFFFFFF), (-0x3FFFFFFF << 33) & MASK64
        )
        # EXTENDED: abs(n) >= 0x40000000.
        self.assertEqual(fixpoint_from_int32(0x40000000), (0x40000000 << 26) | 1)
        self.assertEqual(
            fixpoint_from_int32(-0x40000000),
            ((-0x40000000 << 26) & MASK64) | 1,
        )

    def test_int32_extremes(self):
        self.assertEqual(fixpoint_from_int32(0x7FFFFFFF), (0x7FFFFFFF << 26) | 1)
        self.assertEqual(
            fixpoint_from_int32(-(2**31)),
            ((-(2**31) << 26) & MASK64) | 1,
        )

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            fixpoint_from_int32(2**31)
        with self.assertRaises(ValueError):
            fixpoint_from_int32(-(2**31) - 1)
        with self.assertRaises(TypeError):
            fixpoint_from_int32(1.5)
        with self.assertRaises(TypeError):
            fixpoint_from_int32(True)


class TestFixPointPredicates(unittest.TestCase):
    def test_is_zero_accepts_both_zero_encodings(self):
        self.assertTrue(fixpoint_is_zero(0))
        self.assertTrue(fixpoint_is_zero(1))
        self.assertFalse(fixpoint_is_zero(2))
        self.assertFalse(fixpoint_is_zero(-1))
        self.assertFalse(fixpoint_is_zero(1 << 33))

    def test_is_negative_reads_sign_bit(self):
        self.assertFalse(fixpoint_is_negative(0))
        self.assertFalse(fixpoint_is_negative(1))
        self.assertFalse(fixpoint_is_negative(1 << 33))
        self.assertTrue(fixpoint_is_negative(-1))
        self.assertTrue(fixpoint_is_negative((-1 << 33) & MASK64))
        self.assertTrue(fixpoint_is_negative(INT64_MIN))

    def test_is_positive_masks_mode_flag(self):
        self.assertTrue(fixpoint_is_positive(1 << 33))
        self.assertTrue(fixpoint_is_positive((1 << 26) | 1))
        self.assertFalse(fixpoint_is_positive(0))
        self.assertFalse(fixpoint_is_positive(1))  # EXTENDED zero
        self.assertFalse(fixpoint_is_positive(-1))
        self.assertFalse(fixpoint_is_positive((-1 << 33) & MASK64))


class TestCanonicalComparisonMatrix(unittest.TestCase):
    SAMPLES = [
        -(2**31),
        -0x40000001,
        -0x40000000,
        -0x3FFFFFFF,
        -1000,
        -1,
        0,
        1,
        1000,
        0x3FFFFFFF,
        0x40000000,
        0x40000001,
        0x7FFFFFFF,
    ]

    def test_canonical_int32_encodings_preserve_signed_order(self):
        encoded = [fixpoint_from_int32(value) for value in self.SAMPLES]
        for i, lhs_value in enumerate(self.SAMPLES):
            for j, rhs_value in enumerate(self.SAMPLES):
                lhs_raw = encoded[i]
                rhs_raw = encoded[j]
                expected = sign(lhs_value - rhs_value)
                with self.subTest(lhs=lhs_value, rhs=rhs_value):
                    self.assertEqual(fixpoint_equal(lhs_raw, rhs_raw), expected == 0)
                    self.assertEqual(
                        fixpoint_not_equal(lhs_raw, rhs_raw), expected != 0
                    )
                    self.assertEqual(fixpoint_less(lhs_raw, rhs_raw), expected < 0)
                    self.assertEqual(
                        fixpoint_less_equal(lhs_raw, rhs_raw), expected <= 0
                    )
                    self.assertEqual(
                        fixpoint_greater(lhs_raw, rhs_raw), expected > 0
                    )
                    self.assertEqual(
                        fixpoint_greater_equal(lhs_raw, rhs_raw), expected >= 0
                    )

    def test_both_zero_encodings_are_equal(self):
        self.assertTrue(fixpoint_equal(0, 1))
        self.assertFalse(fixpoint_not_equal(0, 1))
        self.assertFalse(fixpoint_less(0, 1))
        self.assertTrue(fixpoint_less_equal(0, 1))
        self.assertFalse(fixpoint_greater(0, 1))
        self.assertTrue(fixpoint_greater_equal(0, 1))


class TestNonCanonicalDifferentialMatrix(unittest.TestCase):
    def test_random_raw_qwords_match_instruction_level_reference(self):
        rng = random.Random(0xB037)
        edge_values = [
            0,
            1,
            2,
            0x7F,
            0x80,
            (1 << 33),
            (1 << 33) | 0x7F,
            (1 << 26) | 1,
            (1 << 26) | 0x7F,
            (-1 << 33) & MASK64,
            ((-1 << 33) & MASK64) | 0x7F,
            ((-1 << 26) & MASK64) | 1,
            INT64_MIN,
            INT64_MAX,
            MASK64 - 1,
        ]
        values = list(edge_values) + [
            rng.getrandbits(64) for _ in range(300)
        ]
        for lhs in values:
            for rhs in values[:60]:
                expected = reference_fixpoint_compare(lhs, rhs)
                with self.subTest(lhs=hex(lhs), rhs=hex(rhs)):
                    self.assertEqual(fixpoint_equal(lhs, rhs), expected == 0)
                    self.assertEqual(fixpoint_not_equal(lhs, rhs), expected != 0)
                    self.assertEqual(fixpoint_less(lhs, rhs), expected < 0)
                    self.assertEqual(fixpoint_less_equal(lhs, rhs), expected <= 0)
                    self.assertEqual(fixpoint_greater(lhs, rhs), expected > 0)
                    self.assertEqual(
                        fixpoint_greater_equal(lhs, rhs), expected >= 0
                    )

    def test_raw_input_validation(self):
        for function in (
            fixpoint_equal,
            fixpoint_not_equal,
            fixpoint_less,
            fixpoint_less_equal,
            fixpoint_greater,
            fixpoint_greater_equal,
        ):
            with self.assertRaises(ValueError):
                function(2**64, 0)
            with self.assertRaises(ValueError):
                function(-(2**63) - 1, 0)
            with self.assertRaises(TypeError):
                function(1.0, 0)
        for function in (fixpoint_is_zero, fixpoint_is_negative, fixpoint_is_positive):
            with self.assertRaises(ValueError):
                function(2**64)
            with self.assertRaises(TypeError):
                function(None)


if __name__ == "__main__":
    unittest.main()
