# -*- coding: utf-8 -*-
"""Sandbox integration tests for FixPoint Comparison Batch 03.

Every new primitive is dispatched through PrimitiveCall -> Executor ->
Registry, never by direct runtime-function calls.  The required cross-batch
composition runs the complete chain through the same path.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import (  # noqa: E402
    FIXPOINT_EQUAL_PRIMITIVE_ID,
    FIXPOINT_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID,
    FIXPOINT_GREATER_PRIMITIVE_ID,
    FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID,
    FIXPOINT_IS_POSITIVE_PRIMITIVE_ID,
    FIXPOINT_IS_ZERO_PRIMITIVE_ID,
    FIXPOINT_LESS_EQUAL_PRIMITIVE_ID,
    FIXPOINT_LESS_PRIMITIVE_ID,
    FIXPOINT_NOT_EQUAL_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
    PrimitiveCall,
    PrimitiveResult,
)
from hsr_battle_agent.battle_ir.values import DynamicValue  # noqa: E402
from hsr_battle_agent.battle_sandbox.context import ExecutionContext  # noqa: E402
from hsr_battle_agent.battle_sandbox.errors import (  # noqa: E402
    InvalidPrimitiveInputError,
    UnsupportedPrimitiveError,
)
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor  # noqa: E402
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.trace import (  # noqa: E402
    PrimitiveFinished,
    PrimitiveStarted,
)

NEW_PRIMITIVE_IDS = (
    FIXPOINT_EQUAL_PRIMITIVE_ID,
    FIXPOINT_NOT_EQUAL_PRIMITIVE_ID,
    FIXPOINT_LESS_PRIMITIVE_ID,
    FIXPOINT_LESS_EQUAL_PRIMITIVE_ID,
    FIXPOINT_GREATER_PRIMITIVE_ID,
    FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID,
    FIXPOINT_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_IS_ZERO_PRIMITIVE_ID,
    FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID,
    FIXPOINT_IS_POSITIVE_PRIMITIVE_ID,
)


def make_context() -> ExecutionContext:
    return ExecutionContext()


class TestRegistryBindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()
        cls.executor = PrimitiveExecutor(cls.registry)

    def test_all_batch_03_ids_are_registered(self):
        for primitive_id in NEW_PRIMITIVE_IDS:
            with self.subTest(primitive_id=primitive_id):
                spec = self.registry.get_spec(primitive_id)
                self.assertEqual(spec.determinism, "DETERMINISTIC")
                self.assertEqual(spec.context_writes, ())
                self.assertIn(
                    "4.4.54:RPG.GameCore.FixPoint.",
                    self.registry.resolve(primitive_id).provenance_ref,
                )

    def test_unknown_primitive_still_fails_explicitly(self):
        context = make_context()
        with self.assertRaises(UnsupportedPrimitiveError):
            self.executor.execute(
                PrimitiveCall.create("battle.ir.predicate.not_recovered"),
                context,
            )


class TestPrimitiveDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()
        cls.executor = PrimitiveExecutor(cls.registry)

    def _run(self, primitive_id, context, **inputs):
        return self.executor.execute(
            PrimitiveCall.create(primitive_id, **inputs), context
        )

    def test_conversion_primitive_through_executor(self):
        context = make_context()
        result = self._run(FIXPOINT_FROM_INT32_PRIMITIVE_ID, context, value=1)
        self.assertIsInstance(result, PrimitiveResult)
        self.assertEqual(result.semantic_result_type, "fixpoint_raw")
        self.assertEqual(result.value, 1 << 33)
        self.assertEqual(result.runtime_result_type, "int")

    def test_comparison_normal_boundary_and_mixed_mode(self):
        context = make_context()
        standard_one = 1 << 33
        extended_one = (1 << 26) | 1
        self.assertTrue(
            self._run(
                FIXPOINT_EQUAL_PRIMITIVE_ID, context,
                lhs=standard_one, rhs=extended_one,
            ).value
        )
        self.assertFalse(
            self._run(
                FIXPOINT_LESS_PRIMITIVE_ID, context,
                lhs=standard_one, rhs=extended_one,
            ).value
        )
        self.assertTrue(
            self._run(
                FIXPOINT_GREATER_EQUAL_PRIMITIVE_ID, context,
                lhs=standard_one, rhs=extended_one,
            ).value
        )

    def test_predicate_default_and_mismatch_paths(self):
        context = make_context()
        self.assertTrue(
            self._run(FIXPOINT_IS_ZERO_PRIMITIVE_ID, context, value=0).value
        )
        self.assertTrue(
            self._run(FIXPOINT_IS_ZERO_PRIMITIVE_ID, context, value=1).value
        )
        self.assertFalse(
            self._run(FIXPOINT_IS_ZERO_PRIMITIVE_ID, context, value=2).value
        )
        self.assertFalse(
            self._run(FIXPOINT_IS_POSITIVE_PRIMITIVE_ID, context, value=1).value
        )
        self.assertTrue(
            self._run(FIXPOINT_IS_NEGATIVE_PRIMITIVE_ID, context, value=-1).value
        )

    def test_invalid_primitive_inputs_are_rejected(self):
        context = make_context()
        with self.assertRaises(InvalidPrimitiveInputError):
            self._run(FIXPOINT_EQUAL_PRIMITIVE_ID, context, lhs=0)
        with self.assertRaises(ValueError):
            self._run(FIXPOINT_FROM_INT32_PRIMITIVE_ID, context, value=2**31)

    def test_trace_emits_started_and_finished_events(self):
        context = make_context()
        self._run(FIXPOINT_FROM_INT32_PRIMITIVE_ID, context, value=2)
        events = context.trace.events
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], PrimitiveStarted)
        self.assertIsInstance(events[1], PrimitiveFinished)
        self.assertEqual(events[1].primitive_id, FIXPOINT_FROM_INT32_PRIMITIVE_ID)


class TestCrossBatchComposition(unittest.TestCase):
    def test_dynamic_value_int_to_fixpoint_comparison_to_boolean(self):
        registry = PrimitiveRegistry.create_default()
        executor = PrimitiveExecutor(registry)
        context = make_context()

        def run(primitive_id, **inputs):
            return executor.execute(
                PrimitiveCall.create(primitive_id, **inputs), context
            )

        lhs_value = DynamicValue.int_value(42)
        rhs_value = DynamicValue.int_value(100)

        lhs_int = run(
            DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID, value=lhs_value
        )
        rhs_int = run(
            DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID, value=rhs_value
        )
        lhs_fix = run(
            FIXPOINT_FROM_INT32_PRIMITIVE_ID, value=lhs_int.value
        )
        rhs_fix = run(
            FIXPOINT_FROM_INT32_PRIMITIVE_ID, value=rhs_int.value
        )
        less = run(
            FIXPOINT_LESS_PRIMITIVE_ID,
            lhs=lhs_fix.value,
            rhs=rhs_fix.value,
        )
        positive = run(
            FIXPOINT_IS_POSITIVE_PRIMITIVE_ID, value=lhs_fix.value
        )

        self.assertEqual(lhs_int.value, 42)
        self.assertEqual(rhs_int.value, 100)
        self.assertEqual(lhs_fix.value, 42 << 33)
        self.assertEqual(rhs_fix.value, 100 << 33)
        self.assertIs(less.value, True)
        self.assertEqual(less.semantic_result_type, "boolean")
        self.assertIs(positive.value, True)
        self.assertEqual(positive.semantic_result_type, "boolean")

        # Whole chain went through PrimitiveCall -> Executor -> Registry: six
        # primitive calls produce exactly six started/finished pairs.
        events = context.trace.events
        self.assertEqual(len(events), 12)
        self.assertEqual(
            [event.primitive_id for event in events[::2]],
            [
                DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
                DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
                FIXPOINT_FROM_INT32_PRIMITIVE_ID,
                FIXPOINT_FROM_INT32_PRIMITIVE_ID,
                FIXPOINT_LESS_PRIMITIVE_ID,
                FIXPOINT_IS_POSITIVE_PRIMITIVE_ID,
            ],
        )
        for event in events[1::2]:
            self.assertIsInstance(event, PrimitiveFinished)
            self.assertIn("4.4.54:", event.semantic_provenance_ref)


if __name__ == "__main__":
    unittest.main()
