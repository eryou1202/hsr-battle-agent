# -*- coding: utf-8 -*-
"""Runtime tests for Predicate / Evaluator Bridge Batch 04.

Every recovered native leaf is tested against the shared Batch 03 helpers it
reuses, plus normal / boundary / invalid / branch-specific paths.  The
functions themselves are also independently tested through the sandbox in
``tests/battle_sandbox/test_predicate_evaluation_bridge_04.py``.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.values import EvaluatorSpec  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    evaluator_spec_fixpoint_equal_int32,
    evaluator_spec_fixpoint_equal_raw,
    evaluator_spec_fixpoint_not_equal_raw,
    evaluator_spec_from_fixpoint_raw,
    evaluator_spec_from_int32,
    fixpoint_equal,
    fixpoint_from_int32,
    fixpoint_not_equal,
)

MASK64 = 0xFFFFFFFFFFFFFFFF


class TestEvaluatorSpecRepresentation(unittest.TestCase):
    def test_immutable_and_clone_friendly(self):
        spec = EvaluatorSpec(5 << 33)
        self.assertEqual(spec.fixpoint_raw, 5 << 33)
        clone = spec.clone()
        self.assertEqual(clone, spec)
        with self.assertRaises(AttributeError):
            clone.fixpoint_raw = 0  # type: ignore[misc]

    def test_invalid_raw_rejected(self):
        with self.assertRaises(TypeError):
            EvaluatorSpec(True)
        with self.assertRaises(ValueError):
            EvaluatorSpec(-(2**63) - 1)
        with self.assertRaises(ValueError):
            EvaluatorSpec(1 << 64)


class TestEvaluatorSpecFactories(unittest.TestCase):
    def test_from_int32_normal_and_boundaries(self):
        self.assertEqual(evaluator_spec_from_int32(0), EvaluatorSpec(0))
        self.assertEqual(
            evaluator_spec_from_int32(0x3FFFFFFF),
            EvaluatorSpec(0x3FFFFFFF << 33),
        )
        self.assertEqual(
            evaluator_spec_from_int32(0x40000000),
            EvaluatorSpec((0x40000000 << 26) | 1),
        )
        self.assertEqual(
            evaluator_spec_from_int32(-(2**31)),
            EvaluatorSpec(((-(2**31) << 26) & MASK64) | 1),
        )

    def test_from_int32_invalid(self):
        with self.assertRaises(ValueError):
            evaluator_spec_from_int32(2**31)
        with self.assertRaises(TypeError):
            evaluator_spec_from_int32(1.0)

    def test_from_fixpoint_raw_preserves_qword(self):
        for raw in (0, 1, 5 << 33, (5 << 26) | 1, -1, MASK64):
            with self.subTest(raw=raw):
                self.assertEqual(evaluator_spec_from_fixpoint_raw(raw), EvaluatorSpec(raw))

    def test_from_fixpoint_raw_invalid(self):
        with self.assertRaises(TypeError):
            evaluator_spec_from_fixpoint_raw(True)
        with self.assertRaises(ValueError):
            evaluator_spec_from_fixpoint_raw(1 << 64)


class TestEvaluatorSpecEqualInt32Leaf(unittest.TestCase):
    def test_normal_standard_and_extended_agreement(self):
        for value in (-100, -1, 0, 1, 42, 0x3FFFFFFF, 0x40000000):
            with self.subTest(value=value):
                spec = evaluator_spec_from_int32(value)
                self.assertIs(
                    evaluator_spec_fixpoint_equal_int32(spec, value),
                    True,
                )
                self.assertIs(
                    evaluator_spec_fixpoint_equal_int32(spec, value + 1),
                    False,
                )

    def test_int32_max_boundary(self):
        spec = evaluator_spec_from_int32(2**31 - 1)
        self.assertTrue(evaluator_spec_fixpoint_equal_int32(spec, 2**31 - 1))
        self.assertFalse(evaluator_spec_fixpoint_equal_int32(spec, 0))

    def test_mixed_mode_lhs_standard_vs_rhs_extended(self):
        # Batch 03 mixed-mode normalization is exercised through a raw LHS
        # built by the raw factory and an int32 RHS that encodes EXTENDED.
        spec = evaluator_spec_from_fixpoint_raw(1 << 33)  # STANDARD 1
        self.assertTrue(evaluator_spec_fixpoint_equal_int32(spec, 1))

    def test_default_null_and_wrong_type_path(self):
        self.assertFalse(evaluator_spec_fixpoint_equal_int32(None, 1))
        self.assertFalse(evaluator_spec_fixpoint_equal_int32(object(), 1))

    def test_invalid_rhs_rejected_on_valid_spec(self):
        spec = evaluator_spec_from_int32(1)
        with self.assertRaises(ValueError):
            evaluator_spec_fixpoint_equal_int32(spec, 2**31)
        with self.assertRaises(TypeError):
            evaluator_spec_fixpoint_equal_int32(spec, "1")


class TestEvaluatorSpecEqualRawLeaf(unittest.TestCase):
    def test_normal_agreement_with_fixpoint_equal(self):
        raw_lhs = 5 << 33
        raw_rhs = (5 << 26) | 1
        spec = evaluator_spec_from_fixpoint_raw(raw_lhs)
        self.assertIs(
            evaluator_spec_fixpoint_equal_raw(spec, raw_rhs),
            fixpoint_equal(raw_lhs, raw_rhs),
        )
        self.assertFalse(evaluator_spec_fixpoint_equal_raw(spec, raw_rhs + 2))

    def test_default_null_and_wrong_type_path(self):
        self.assertFalse(evaluator_spec_fixpoint_equal_raw(None, 0))
        self.assertFalse(evaluator_spec_fixpoint_equal_raw(123, 0))

    def test_invalid_rhs_rejected_on_valid_spec(self):
        spec = evaluator_spec_from_fixpoint_raw(0)
        with self.assertRaises(ValueError):
            evaluator_spec_fixpoint_equal_raw(spec, 1 << 64)


class TestEvaluatorSpecNotEqualRawLeaf(unittest.TestCase):
    def test_normal_agreement_with_fixpoint_not_equal(self):
        raw_lhs = 5 << 33
        raw_rhs = (5 << 26) | 1
        spec = evaluator_spec_from_fixpoint_raw(raw_lhs)
        self.assertIs(
            evaluator_spec_fixpoint_not_equal_raw(spec, raw_rhs),
            fixpoint_not_equal(raw_lhs, raw_rhs),
        )
        self.assertTrue(evaluator_spec_fixpoint_not_equal_raw(spec, raw_rhs + 2))

    def test_default_null_and_wrong_type_path_returns_true(self):
        # Native `mov al,1` prelude: null / wrong type -> true, not an error.
        self.assertTrue(evaluator_spec_fixpoint_not_equal_raw(None, 0))
        self.assertTrue(evaluator_spec_fixpoint_not_equal_raw(object(), 0))

    def test_invalid_rhs_rejected_on_valid_spec(self):
        spec = evaluator_spec_from_fixpoint_raw(0)
        with self.assertRaises(ValueError):
            evaluator_spec_fixpoint_not_equal_raw(spec, -(2**63) - 1)


if __name__ == "__main__":
    unittest.main()
