# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.sandbox import StrictSandbox
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.strict_executor import (
    STRICT_NO_OP_ACTION, StrictExecutor, StrictStepError, StrictStepOutcome,
)
from hsr_battle_agent.battle_sandbox.transaction import plan_transaction
from tests.battle_sandbox.test_transaction_plan import make_certificate, make_state


def no_op_inputs():
    state = make_state()
    operations = ()
    certificate = make_certificate(state, operations)
    return state, plan_transaction(state, certificate, operations)


class TestStrictNoOp(unittest.TestCase):
    def test_no_op_commits_one_deterministic_revision(self):
        state, plan = no_op_inputs()
        before = state.to_dict()
        result = StrictExecutor().step(state, plan, STRICT_NO_OP_ACTION)
        self.assertIs(result.outcome, StrictStepOutcome.COMMITTED)
        published = result.committed_state
        self.assertIsNotNone(published)
        assert published is not None
        self.assertEqual(published.revision.counter, state.revision.counter + 1)
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(published.rng_state.to_dict(), state.rng_state.to_dict())
        self.assertEqual(published.allocator.to_dict(), state.allocator.to_dict())

    def test_identical_clones_produce_identical_result_state_and_hash(self):
        state, plan = no_op_inputs()
        left = StrictExecutor().step(state.clone(), plan, STRICT_NO_OP_ACTION)
        right = StrictExecutor().step(state.clone(), plan, STRICT_NO_OP_ACTION)
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(left.transaction_identity, right.transaction_identity)
        assert left.committed_state is not None and right.committed_state is not None
        policy = plan.certificate.policy_identity
        self.assertEqual(
            semantic_hash_v2(TerraSnapshotV2(state=left.committed_state, policy_identity=policy)),
            semantic_hash_v2(TerraSnapshotV2(state=right.committed_state, policy_identity=policy)),
        )

    def test_committed_result_read_is_detached(self):
        state, plan = no_op_inputs()
        result = StrictExecutor().step(state, plan, STRICT_NO_OP_ACTION)
        before = result.committed_state.to_dict()
        exported = result.committed_state
        exported.rng_state.next_u64()
        self.assertEqual(result.committed_state.to_dict(), before)


class TestStrictRejection(unittest.TestCase):
    def assertUnchanged(self, state, before):
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(state.rng_state.to_dict(), before["rng_state"])
        self.assertEqual(state.allocator.to_dict(), before["allocator"])

    def test_unsupported_action_is_explicit_and_atomic(self):
        state, plan = no_op_inputs()
        before = state.to_dict()
        result = StrictExecutor().step(state, plan, "battle.action.attack")
        self.assertIs(result.outcome, StrictStepOutcome.UNSUPPORTED)
        self.assertEqual(result.rejections[0].reason_code, "STRICT_ACTION_UNSUPPORTED")
        self.assertIsNone(result.committed_state)
        self.assertUnchanged(state, before)

    def test_nonempty_plan_cannot_masquerade_as_no_op(self):
        from hsr_battle_agent.battle_sandbox.transaction import TransactionOperation
        state = make_state()
        operations = (TransactionOperation("attack", {}),)
        plan = plan_transaction(state, make_certificate(state, operations), operations)
        before = state.to_dict()
        result = StrictExecutor().step(state, plan, STRICT_NO_OP_ACTION)
        self.assertIs(result.outcome, StrictStepOutcome.UNSUPPORTED)
        self.assertUnchanged(state, before)

    def test_stale_revision_rejects_without_retry(self):
        state, plan = no_op_inputs()
        changed = state.to_dict()
        changed["revision_and_transaction_sequence"]["published_revision"]["counter"] += 1
        stale = type(state).from_dict(changed)
        before = stale.to_dict()
        result = StrictExecutor().step(stale, plan, STRICT_NO_OP_ACTION)
        self.assertIs(result.outcome, StrictStepOutcome.REJECTED)
        self.assertEqual(result.rejections[0].reason_code, "STRICT_TRANSACTION_REJECTED")
        self.assertUnchanged(stale, before)

    def test_invalid_certificate_binding_rejects(self):
        state, plan = no_op_inputs()
        plan._certificate_identity = "forged"  # corruption reproducer
        before = state.to_dict()
        result = StrictExecutor().step(state, plan, STRICT_NO_OP_ACTION)
        self.assertIs(result.outcome, StrictStepOutcome.REJECTED)
        self.assertEqual(result.rejections[0].reason_code, "STRICT_CERTIFICATE_MISMATCH")
        self.assertUnchanged(state, before)

    def test_non_plan_cannot_substitute_for_gate_authorization(self):
        state = make_state()
        before = state.to_dict()
        result = StrictExecutor().step(state, True, STRICT_NO_OP_ACTION)
        self.assertIs(result.outcome, StrictStepOutcome.REJECTED)
        self.assertUnchanged(state, before)

    def test_result_and_outcome_have_no_truthiness(self):
        state, plan = no_op_inputs()
        result = StrictExecutor().step(state, plan, "unsupported")
        with self.assertRaises(StrictStepError):
            bool(result)
        with self.assertRaises(StrictStepError):
            bool(result.outcome)


class TestLegacyIsolation(unittest.TestCase):
    def test_strict_executor_imports_no_legacy_executor_registry_or_runtime(self):
        path = REPO / "src/hsr_battle_agent/battle_sandbox/strict_executor.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        forbidden = {
            "hsr_battle_agent.battle_sandbox.executor",
            "hsr_battle_agent.battle_sandbox.registry",
            "hsr_battle_agent.battle_sandbox.context",
            "hsr_battle_agent.battle_runtime",
        }
        self.assertTrue(modules.isdisjoint(forbidden))

    def test_strict_facade_never_calls_legacy_executor(self):
        state, plan = no_op_inputs()
        with patch(
            "hsr_battle_agent.battle_sandbox.executor.PrimitiveExecutor.execute",
            side_effect=AssertionError("legacy executor reached"),
        ):
            result = StrictSandbox().step(state, plan, STRICT_NO_OP_ACTION)
        self.assertTrue(result.is_committed())

    def test_strict_facade_has_no_reference_fallback(self):
        source = inspect.getsource(StrictSandbox)
        self.assertNotIn("PrimitiveExecutor", source)
        self.assertNotIn("Reference", source)
        self.assertNotIn("execute(", source)


if __name__ == "__main__":
    unittest.main()
