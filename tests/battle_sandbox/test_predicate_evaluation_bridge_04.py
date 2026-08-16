# -*- coding: utf-8 -*-
"""Sandbox integration tests for Predicate / Evaluator Bridge Batch 04.

Every new primitive is dispatched through PrimitiveCall -> Executor ->
Registry.  The required cross-batch composition runs the complete chain
through the same path and reuses the Batch 03 FixPoint primitives.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import (  # noqa: E402
    EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID,
    FIXPOINT_EQUAL_PRIMITIVE_ID,
    FIXPOINT_FROM_INT32_PRIMITIVE_ID,
    PrimitiveCall,
    PrimitiveResult,
)
from hsr_battle_agent.battle_ir.values import EvaluatorSpec  # noqa: E402
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
    EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID,
    EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
    EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
)


def make_context() -> ExecutionContext:
    return ExecutionContext()


class TestRegistryBindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()
        cls.executor = PrimitiveExecutor(cls.registry)

    def test_all_batch_04_ids_are_registered_from_catalog(self):
        for primitive_id in NEW_PRIMITIVE_IDS:
            with self.subTest(primitive_id=primitive_id):
                spec = self.registry.get_spec(primitive_id)
                self.assertEqual(spec.determinism, "DETERMINISTIC")
                self.assertEqual(spec.context_writes, ())
                self.assertIn(
                    "4.4.54:RPG.GameCore.ValueEvaluatorConfig.",
                    self.registry.resolve(primitive_id).provenance_ref,
                )

    def test_unknown_primitive_still_fails_explicitly(self):
        with self.assertRaises(UnsupportedPrimitiveError):
            self.executor.execute(
                PrimitiveCall.create("battle.ir.predicate.not_recovered"),
                make_context(),
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

    def test_factories_through_executor(self):
        context = make_context()
        from_int = self._run(
            EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID, context, value=7
        )
        self.assertIsInstance(from_int, PrimitiveResult)
        self.assertEqual(from_int.semantic_result_type, "evaluator_spec")
        self.assertEqual(from_int.runtime_result_type, "EvaluatorSpec")
        self.assertIsInstance(from_int.value, EvaluatorSpec)
        self.assertEqual(from_int.value.fixpoint_raw, 7 << 33)

        raw = (7 << 26) | 1
        from_raw = self._run(
            EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID, context, value=raw
        )
        self.assertEqual(from_raw.value, EvaluatorSpec(raw))

    def test_leaf_normal_and_branch_specific_paths(self):
        context = make_context()
        spec = self._run(
            EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID, context, value=7
        ).value

        equal_int = self._run(
            EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
            context,
            evaluator_spec=spec,
            rhs=7,
        )
        self.assertIs(equal_int.value, True)
        self.assertEqual(equal_int.semantic_result_type, "boolean")

        self.assertFalse(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
                context,
                evaluator_spec=spec,
                rhs=8,
            ).value
        )
        self.assertTrue(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=spec,
                rhs=7 << 33,
            ).value
        )
        self.assertTrue(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=spec,
                rhs=8 << 33,
            ).value
        )

    def test_default_null_and_wrong_type_paths(self):
        context = make_context()
        self.assertFalse(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=None,
                rhs=0,
            ).value
        )
        self.assertFalse(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=object(),
                rhs=0,
            ).value
        )
        self.assertTrue(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=None,
                rhs=0,
            ).value
        )
        self.assertTrue(
            self._run(
                EVALUATOR_SPEC_FIXPOINT_NOT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=object(),
                rhs=0,
            ).value
        )

    def test_invalid_rhs_rejected(self):
        context = make_context()
        spec = EvaluatorSpec(0)
        with self.assertRaises(ValueError):
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=spec,
                rhs=1 << 64,
            )
        with self.assertRaises(ValueError):
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_INT32_PRIMITIVE_ID,
                context,
                evaluator_spec=spec,
                rhs=2**31,
            )

    def test_missing_input_rejected(self):
        context = make_context()
        with self.assertRaises(InvalidPrimitiveInputError):
            self._run(
                EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
                context,
                evaluator_spec=EvaluatorSpec(0),
            )

    def test_trace_emits_started_finished_with_scalar_summary(self):
        context = make_context()
        self._run(EVALUATOR_SPEC_FROM_INT32_PRIMITIVE_ID, context, value=3)
        events = context.trace.events
        self.assertEqual(len(events), 2)
        self.assertIsInstance(events[0], PrimitiveStarted)
        self.assertIsInstance(events[1], PrimitiveFinished)
        self.assertEqual(events[1].result_type, "EvaluatorSpec")
        self.assertEqual(events[1].result, "EvaluatorSpec(fixpoint_raw=0x600000000)")
        self.assertIsInstance(context.trace.to_dict()["events"][1]["result"], str)


class TestCrossBatchComposition(unittest.TestCase):
    def test_config_value_to_fixpoint_to_comparison_to_boolean(self):
        registry = PrimitiveRegistry.create_default()
        executor = PrimitiveExecutor(registry)
        context = make_context()

        def run(primitive_id, **inputs):
            return executor.execute(
                PrimitiveCall.create(primitive_id, **inputs), context
            )

        # input/config value -> Batch 03 FixPoint conversion primitive
        raw = run(FIXPOINT_FROM_INT32_PRIMITIVE_ID, value=42)

        # config/runtime object -> Batch 04 evaluator-spec primitive
        spec = run(
            EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID, value=raw.value
        )

        # explicit Batch 03 comparison source-of-truth check
        comparison = run(
            FIXPOINT_EQUAL_PRIMITIVE_ID,
            lhs=spec.value.fixpoint_raw,
            rhs=raw.value,
        )
        self.assertIs(comparison.value, True)

        # Batch 04 predicate/evaluator leaf -> boolean
        predicate = run(
            EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
            evaluator_spec=spec.value,
            rhs=raw.value,
        )
        self.assertIs(predicate.value, True)
        self.assertEqual(predicate.semantic_result_type, "boolean")

        # Everything went through PrimitiveCall -> Executor -> Registry.
        self.assertEqual(
            [event.primitive_id for event in context.trace.events[::2]],
            [
                FIXPOINT_FROM_INT32_PRIMITIVE_ID,
                EVALUATOR_SPEC_FROM_FIXPOINT_RAW_PRIMITIVE_ID,
                FIXPOINT_EQUAL_PRIMITIVE_ID,
                EVALUATOR_SPEC_FIXPOINT_EQUAL_RAW_PRIMITIVE_ID,
            ],
        )
        for event in context.trace.events[1::2]:
            self.assertIsInstance(event, PrimitiveFinished)
            self.assertIn("4.4.54:", event.semantic_provenance_ref)


if __name__ == "__main__":
    unittest.main()
