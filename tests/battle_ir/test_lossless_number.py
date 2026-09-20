# -*- coding: utf-8 -*-
"""F01-006 tests: LosslessNumber, source lexeme and numeric category.

Acceptance criteria: an identifier above 2**53 round-trips exactly, ``1`` and
``1.0`` and differing source lexemes stay distinguishable where declared, and
non-finite values are rejected.  Also re-asserts the F01-005 PresenceValue
rules, since this task extends the same module.
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    LOSSLESS_NUMBER_SCHEMA,
    NUMERIC_CATEGORIES,
    LosslessNumber,
    LosslessValueError,
    NumericCategory,
    PresenceValue,
    require_exact_integer,
)

MODULE_PATH = (
    REPO / "src" / "hsr_battle_agent" / "battle_ir" / "lossless_value.py"
)

#: Integers that float cannot represent exactly.
BEYOND_FLOAT_PRECISION = (
    2**53,
    2**53 + 1,
    2**53 - 1,
    2**63,
    2**64 - 1,
    2**64,
    10**30 + 1,
)


class TestExactIntegerIdentity(unittest.TestCase):
    def test_identifiers_beyond_two_to_the_53_round_trip_exactly(self):
        for value in BEYOND_FLOAT_PRECISION:
            with self.subTest(value=value):
                original = LosslessNumber.from_int(value)
                restored = LosslessNumber.from_dict(original.to_dict())
                self.assertEqual(restored.require_int(), value)
                self.assertEqual(restored.lexeme, str(value))
                self.assertIs(restored.category, NumericCategory.INTEGER)
                self.assertIs(type(restored.require_int()), int)

    def test_float_would_have_lost_these_values(self):
        # Evidence that the float path really is lossy, justifying the guard.
        lossy = [v for v in BEYOND_FLOAT_PRECISION if int(float(v)) != v]
        self.assertTrue(lossy, "expected at least one value float cannot hold")
        for value in lossy:
            with self.subTest(value=value):
                self.assertNotEqual(int(float(value)), value)
                self.assertEqual(
                    LosslessNumber.from_int(value).require_int(), value
                )

    def test_large_signed_integers_round_trip(self):
        for value in (-(2**70) + 3, -(2**53) - 1):
            with self.subTest(value=value):
                restored = LosslessNumber.from_dict(
                    LosslessNumber.from_int(value).to_dict()
                )
                self.assertEqual(restored.require_int(), value)

    def test_require_exact_integer_accepts_exact_sources(self):
        self.assertEqual(require_exact_integer(2**53 + 1), 2**53 + 1)
        self.assertEqual(require_exact_integer("9007199254740993"), 2**53 + 1)
        self.assertEqual(
            require_exact_integer(LosslessNumber.from_int(2**53 + 1)), 2**53 + 1
        )

    def test_require_exact_integer_refuses_float_normalization(self):
        with self.assertRaises(LosslessValueError):
            require_exact_integer(float(2**53 + 1))
        with self.assertRaises(LosslessValueError):
            require_exact_integer(1.0)
        with self.assertRaises(LosslessValueError):
            require_exact_integer("1.0")
        with self.assertRaises(LosslessValueError):
            require_exact_integer(True)
        with self.assertRaises(LosslessValueError):
            require_exact_integer(None)

    def test_require_int_refuses_non_integer_categories(self):
        for number in (
            LosslessNumber.from_lexeme("1.0"),
            LosslessNumber.from_float(1.0),
        ):
            with self.subTest(category=number.category.value):
                with self.assertRaises(LosslessValueError):
                    number.require_int()


class TestCategoryAndLexemeDistinction(unittest.TestCase):
    def test_one_and_one_point_zero_are_distinguishable(self):
        # AUTHORITY_REQUIRED: category and source lexeme are representation
        # identity, so numerically equal spellings must not compare equal here.
        integer = LosslessNumber.from_lexeme("1")
        decimal = LosslessNumber.from_lexeme("1.0")
        self.assertIs(integer.category, NumericCategory.INTEGER)
        self.assertIs(decimal.category, NumericCategory.DECIMAL)
        self.assertNotEqual(integer, decimal)
        self.assertNotEqual(integer.to_dict(), decimal.to_dict())
        self.assertEqual(integer.require_int(), 1)
        self.assertEqual(decimal.as_decimal(), Decimal("1.0"))

    def test_differing_lexemes_for_the_same_value_stay_distinguishable(self):
        pairs = (("0.1", "0.10"), ("1.0", "1.00"), ("1e2", "100.0"), ("+1", "1"))
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                a = LosslessNumber.from_lexeme(left)
                b = LosslessNumber.from_lexeme(right)
                self.assertNotEqual(a.lexeme, b.lexeme)
                self.assertNotEqual(a, b)
                self.assertNotEqual(a.to_dict(), b.to_dict())

    def test_lexeme_is_preserved_byte_for_byte(self):
        for lexeme in ("0.10", "1e2", "-0.0", "+7", "1E-3", ".5", "5."):
            with self.subTest(lexeme=lexeme):
                number = LosslessNumber.from_lexeme(lexeme)
                self.assertEqual(number.lexeme, lexeme)
                self.assertEqual(
                    LosslessNumber.from_dict(number.to_dict()).lexeme, lexeme
                )

    def test_category_is_inferred_from_the_literal_shape(self):
        expectations = {
            "1": NumericCategory.INTEGER,
            "-1": NumericCategory.INTEGER,
            "+1": NumericCategory.INTEGER,
            "1.0": NumericCategory.DECIMAL,
            "0.1": NumericCategory.DECIMAL,
            "1e2": NumericCategory.DECIMAL,
            "1E-3": NumericCategory.DECIMAL,
        }
        for lexeme, expected in expectations.items():
            with self.subTest(lexeme=lexeme):
                self.assertIs(
                    LosslessNumber.from_lexeme(lexeme).category, expected
                )

    def test_from_source_keeps_the_python_category(self):
        self.assertIs(
            LosslessNumber.from_source(1).category, NumericCategory.INTEGER
        )
        self.assertIs(
            LosslessNumber.from_source(Decimal("1.5")).category,
            NumericCategory.DECIMAL,
        )
        self.assertIs(
            LosslessNumber.from_source(1.5).category, NumericCategory.FLOAT
        )
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_source(True)

    def test_float_category_is_distinct_from_decimal(self):
        as_float = LosslessNumber.from_float(0.1)
        as_decimal = LosslessNumber.from_lexeme("0.1")
        self.assertIs(as_float.category, NumericCategory.FLOAT)
        self.assertIs(as_decimal.category, NumericCategory.DECIMAL)
        self.assertNotEqual(as_float, as_decimal)
        self.assertEqual(as_decimal.as_decimal(), Decimal("0.1"))
        # Decimal(0.1) converts the binary double exactly, and that is NOT the
        # exact decimal 0.1 -- which is precisely why the categories are kept
        # apart instead of both being normalized to a float.
        self.assertNotEqual(Decimal(0.1), Decimal("0.1"))
        self.assertNotEqual(
            Decimal(as_float.as_float_lossy()), as_decimal.as_decimal()
        )

    def test_to_python_matches_the_category(self):
        self.assertIs(type(LosslessNumber.from_lexeme("1").to_python()), int)
        self.assertIs(
            type(LosslessNumber.from_lexeme("1.0").to_python()), Decimal
        )
        self.assertIs(type(LosslessNumber.from_float(1.0).to_python()), float)

    def test_as_decimal_refuses_the_float_category(self):
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_float(1.0).as_decimal()


class TestNonFiniteRejection(unittest.TestCase):
    def test_non_finite_lexemes_are_rejected(self):
        for lexeme in (
            "nan", "NaN", "-nan", "inf", "-inf", "+inf",
            "Infinity", "-Infinity", "infinity",
        ):
            with self.subTest(lexeme=lexeme):
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_lexeme(lexeme)
                with self.assertRaises(LosslessValueError):
                    LosslessNumber(lexeme=lexeme, category=NumericCategory.FLOAT)

    def test_non_finite_floats_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=repr(value)):
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_float(value)
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_source(value)

    def test_non_finite_detection_matches_the_stdlib(self):
        self.assertFalse(math.isfinite(float("nan")))
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_float(float("nan"))


class TestMalformedInputRejection(unittest.TestCase):
    def test_bad_lexemes_are_rejected(self):
        for lexeme in ("", " ", " 1", "1 ", "1_000", "0x10", "1..0", "abc",
                       "1,0", ".", "-", "+", "1e", "1e+", "--1", "1.2.3"):
            with self.subTest(lexeme=repr(lexeme)):
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_lexeme(lexeme)

    def test_category_lexeme_mismatch_is_rejected(self):
        with self.assertRaises(LosslessValueError):
            LosslessNumber(lexeme="1.0", category=NumericCategory.INTEGER)
        with self.assertRaises(LosslessValueError):
            LosslessNumber(lexeme="abc", category=NumericCategory.DECIMAL)
        with self.assertRaises(LosslessValueError):
            LosslessNumber(lexeme="nan", category=NumericCategory.DECIMAL)

    def test_unknown_category_is_rejected(self):
        for value in ("NUMBER", "", None, 1, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(LosslessValueError):
                    LosslessNumber(lexeme="1", category=value)

    def test_malformed_documents_are_rejected(self):
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_dict(None)
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_dict([])
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_dict({"category": "INTEGER"})
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_dict({"lexeme": "1"})
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_dict(
                {"schema": "lossless_number/2", "category": "INTEGER",
                 "lexeme": "1"}
            )
        with self.assertRaises(LosslessValueError):
            LosslessNumber.from_dict({"category": "BOGUS", "lexeme": "1"})

    def test_bool_is_not_a_number(self):
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_int(value)
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_float(value)
                with self.assertRaises(LosslessValueError):
                    LosslessNumber.from_source(value)


class TestSerialization(unittest.TestCase):
    def test_schema_constant(self):
        self.assertEqual(LOSSLESS_NUMBER_SCHEMA, "lossless_number/1")
        self.assertEqual(
            LosslessNumber.from_int(1).to_dict()["schema"],
            LOSSLESS_NUMBER_SCHEMA,
        )

    def test_categories_are_the_declared_set(self):
        self.assertEqual(NUMERIC_CATEGORIES, ("INTEGER", "DECIMAL", "FLOAT"))
        self.assertEqual(NumericCategory.spellings(), NUMERIC_CATEGORIES)

    def test_round_trip_is_exact_for_every_category(self):
        numbers = (
            LosslessNumber.from_lexeme("9007199254740993"),
            LosslessNumber.from_lexeme("0.10"),
            LosslessNumber.from_float(0.5),
        )
        for original in numbers:
            with self.subTest(category=original.category.value):
                restored = LosslessNumber.from_dict(original.to_dict())
                self.assertEqual(restored, original)
                self.assertEqual(restored.lexeme, original.lexeme)
                self.assertIs(restored.category, original.category)

    def test_json_round_trip(self):
        original = LosslessNumber.from_lexeme("9007199254740993")
        text = json.dumps(original.to_dict(), sort_keys=True)
        restored = LosslessNumber.from_dict(json.loads(text))
        self.assertEqual(restored, original)
        self.assertEqual(restored.require_int(), 2**53 + 1)

    def test_no_truthiness_on_numbers_or_categories(self):
        # API_DESIGN_LOCAL: refusing truthiness prevents a lossless numeric
        # envelope from silently standing in for its decoded numeric value.
        with self.assertRaises(LosslessValueError):
            bool(LosslessNumber.from_int(0))
        with self.assertRaises(LosslessValueError):
            bool(LosslessNumber.from_int(1))
        for category in NumericCategory:
            with self.subTest(category=category.name):
                with self.assertRaises(LosslessValueError):
                    bool(category)

    def test_module_has_no_default_based_decoding(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn(".get(", code)
        self.assertNotIn(".setdefault(", code)


class TestF01_005PresenceValuePreserved(unittest.TestCase):
    def test_presence_matrix_still_round_trips(self):
        for value in (
            PresenceValue.absent(),
            PresenceValue.null(),
            PresenceValue.present(False),
            PresenceValue.present(0),
            PresenceValue.present([]),
            PresenceValue.present([None]),
            PresenceValue.present({}),
            PresenceValue.present(""),
        ):
            with self.subTest(payload=repr(value.to_dict())):
                restored = PresenceValue.from_dict(value.to_dict())
                self.assertEqual(restored.to_dict(), value.to_dict())

    def test_invalid_forms_still_rejected(self):
        from hsr_battle_agent.battle_ir.lossless_value import (
            PresenceState,
            PresenceValueError,
        )

        with self.assertRaises(PresenceValueError):
            PresenceValue(state=PresenceState.ABSENT, value=1)
        with self.assertRaises(PresenceValueError):
            PresenceValue.present(None)
        with self.assertRaises(PresenceValueError):
            PresenceValue(state=PresenceState.NULL, value=1)


if __name__ == "__main__":
    unittest.main()
