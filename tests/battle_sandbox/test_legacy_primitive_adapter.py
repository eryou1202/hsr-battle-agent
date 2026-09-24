# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import (
    PrimitiveCall,
    PrimitiveResult,
    TARGET_SELECT_NONE_PRIMITIVE_ID,
    TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID,
)
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_ir.targets import TargetSet
from hsr_battle_agent.battle_sandbox.legacy_primitive_adapter import (
    LEGACY_PRIMITIVE_ALLOWLIST,
    LegacyAdapterError,
    LegacyAdapterOutcome,
    LegacyPrimitiveAdapter,
)
from hsr_battle_agent.battle_sandbox.transaction import TransactionOperation, plan_transaction
from hsr_battle_agent.battle_sandbox.preflight import ObligationAccess
from tests.battle_sandbox.test_transaction_plan import make_certificate, make_state


def inputs():
    state = make_state()
    operations = (TransactionOperation(TARGET_SELECT_NONE_PRIMITIVE_ID, {}),)
    plan = plan_transaction(state, make_certificate(state, operations), operations)
    return state, plan, PrimitiveCall(TARGET_SELECT_NONE_PRIMITIVE_ID)


class TestCertifiedPureLeaf(unittest.TestCase):
    def test_allowlist_contains_exactly_one_pure_leaf(self):
        self.assertEqual(LEGACY_PRIMITIVE_ALLOWLIST, (TARGET_SELECT_NONE_PRIMITIVE_ID,))

    def test_pure_leaf_stages_empty_certified_diff(self):
        state, plan, call = inputs()
        before = state.to_dict()
        result = LegacyPrimitiveAdapter().stage(state, plan, call)
        self.assertIs(result.outcome, LegacyAdapterOutcome.STAGED)
        self.assertEqual(result.primitive_id, TARGET_SELECT_NONE_PRIMITIVE_ID)
        self.assertEqual(result.staged_delta.writes, ())
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(result.result_summary["private_trace_event_count"], 2)

    def test_staged_delta_and_result_views_are_detached(self):
        state, plan, call = inputs()
        result = LegacyPrimitiveAdapter().stage(state, plan, call)
        before = result.to_dict()
        summary = result.result_summary
        summary["future"] = []
        delta = result.staged_delta
        exported = delta.allocator
        exported.begin_generation("mutated")
        self.assertEqual(result.to_dict(), before)

    def test_no_commit_or_publication_surface(self):
        result = LegacyPrimitiveAdapter().stage(*inputs())
        self.assertFalse(hasattr(result, "commit"))
        self.assertFalse(hasattr(result, "publish"))
        with self.assertRaises(LegacyAdapterError):
            bool(result)


class TestFailClosedIsolation(unittest.TestCase):
    def assertRejectsUnchanged(self, side_effect, expected_reason):
        state, plan, call = inputs()
        before = state.to_dict()
        with patch(
            "hsr_battle_agent.battle_sandbox.legacy_primitive_adapter.PrimitiveExecutor.execute",
            side_effect=side_effect,
        ):
            result = LegacyPrimitiveAdapter().stage(state, plan, call)
        self.assertIs(result.outcome, LegacyAdapterOutcome.REJECTED)
        self.assertEqual(result.reason, expected_reason)
        self.assertEqual(state.to_dict(), before)
        self.assertIsNone(result.staged_delta)

    def test_exception_rejects_without_live_change(self):
        self.assertRejectsUnchanged(RuntimeError("boom"), "LEGACY_EXECUTION_REJECTED")

    def test_unexpected_private_state_write_rejects(self):
        def mutate(primitive, context):
            context.state.set_extension("unexpected", {"items": [1]})
            return type("R", (), {"primitive_id": primitive.primitive_id,
                                   "semantic_result_type": "TargetSet",
                                   "runtime_result_type": "TargetSet"})()
        self.assertRejectsUnchanged(mutate, "UNEXPECTED_LEGACY_STATE_DIFF")

    def test_unexpected_private_rng_draw_rejects(self):
        def draw(primitive, context):
            context.rng.next_u64()
            return type("R", (), {"primitive_id": primitive.primitive_id,
                                   "semantic_result_type": "TargetSet",
                                   "runtime_result_type": "TargetSet"})()
        self.assertRejectsUnchanged(draw, "UNEXPECTED_LEGACY_RNG_DIFF")

    def test_unexpected_private_trace_or_event_rejects(self):
        def emit_extra(primitive, context):
            started = context.trace.started(primitive.primitive_id, (), "test")
            context.trace.finished(started, TargetSet())
            extra = context.trace.started("unexpected.event", (), "test")
            context.trace.finished(extra, None)
            return PrimitiveResult(
                primitive.primitive_id, TargetSet(), "TargetSet", "TargetSet"
            )
        self.assertRejectsUnchanged(emit_extra, "UNEXPECTED_LEGACY_TRACE_DIFF")

    def test_unexpected_result_rejects(self):
        def wrong_result(primitive, context):
            started = context.trace.started(primitive.primitive_id, (), "test")
            context.trace.finished(started, TargetSet())
            return PrimitiveResult(primitive.primitive_id, True, "TargetSet", "bool")
        self.assertRejectsUnchanged(wrong_result, "UNEXPECTED_LEGACY_RESULT")

    def test_allocator_queue_and_event_permissions_cannot_enter_pure_leaf_plan(self):
        for target in ("allocator:ghost", "queue:ordinary", "event:future"):
            state = make_state()
            operations = (TransactionOperation(TARGET_SELECT_NONE_PRIMITIVE_ID, {}),)
            write = ObligationAccess(target, PresenceValue.present({"attempt": True}))
            plan = plan_transaction(
                state, make_certificate(state, operations, writes=(write,)), operations
            )
            before = state.to_dict()
            result = LegacyPrimitiveAdapter().stage(
                state, plan, PrimitiveCall(TARGET_SELECT_NONE_PRIMITIVE_ID)
            )
            self.assertIs(result.outcome, LegacyAdapterOutcome.REJECTED)
            self.assertEqual(result.reason, "PLAN_BINDING_MISMATCH")
            self.assertEqual(state.to_dict(), before)

    def test_non_allowlisted_and_turn_advance_are_unsupported(self):
        state, plan, _ = inputs()
        before = state.to_dict()
        for primitive_id in (
            "battle.ir.modifier.lifecycle_process_redd",
            TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID,
            "future.unknown",
        ):
            result = LegacyPrimitiveAdapter().stage(state, plan, PrimitiveCall(primitive_id))
            self.assertIs(result.outcome, LegacyAdapterOutcome.UNSUPPORTED)
            self.assertEqual(state.to_dict(), before)

    def test_plan_primitive_and_footprint_must_match_exactly(self):
        state, plan, _ = inputs()
        mismatched = PrimitiveCall(TARGET_SELECT_NONE_PRIMITIVE_ID)
        plan._operations = (TransactionOperation("another", {}),)
        result = LegacyPrimitiveAdapter().stage(state, plan, mismatched)
        self.assertIs(result.outcome, LegacyAdapterOutcome.REJECTED)
        self.assertEqual(result.reason, "PLAN_BINDING_MISMATCH")

    def test_invalid_certificate_binding_rejects_before_legacy_execution(self):
        state, plan, call = inputs()
        plan._certificate_identity = "forged"
        before = state.to_dict()
        with patch(
            "hsr_battle_agent.battle_sandbox.legacy_primitive_adapter.PrimitiveExecutor.execute",
            side_effect=AssertionError("legacy execution must not begin"),
        ) as execute:
            result = LegacyPrimitiveAdapter().stage(state, plan, call)
        self.assertIs(result.outcome, LegacyAdapterOutcome.REJECTED)
        self.assertEqual(result.reason, "PLAN_BINDING_MISMATCH")
        execute.assert_not_called()
        self.assertEqual(state.to_dict(), before)

    def test_non_strict_inputs_and_reference_substitutes_reject(self):
        state, _, call = inputs()
        for substitute in (True, object(), "reference-profile"):
            result = LegacyPrimitiveAdapter().stage(state, substitute, call)
            self.assertIs(result.outcome, LegacyAdapterOutcome.REJECTED)


if __name__ == "__main__":
    unittest.main()
