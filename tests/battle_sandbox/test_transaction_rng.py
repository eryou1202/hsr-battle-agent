# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.transaction import TransactionError
from hsr_battle_agent.battle_sandbox.transaction_rng import TransactionRng
from tests.battle_sandbox.test_transaction_plan import make_plan, make_state


class TestTransactionRng(unittest.TestCase):
    def test_private_draws_do_not_advance_live_rng(self):
        live, _, plan = make_plan()
        before = live.to_dict()
        staged = TransactionRng(plan, live)
        staged.next_u64()
        staged.randint(1, 7)
        staged.uniform(0.0, 1.0)
        self.assertEqual(staged.draw_count, 3)
        self.assertEqual(live.to_dict(), before)

    def test_draw_ledger_is_ordered_lossless_and_detached(self):
        live, _, plan = make_plan()
        staged = TransactionRng(plan, live)
        staged.randint(1, 3)
        staged.randint(1, 3)
        before = staged.to_dict()
        ledger = staged.ledger
        self.assertEqual([x.method for x in ledger], ["randint", "randint"])
        self.assertIsInstance(ledger[0].arguments, tuple)
        self.assertEqual(staged.to_dict(), before)

    def test_abort_leaves_live_bytes_and_next_draw_identical(self):
        live, _, plan = make_plan()
        baseline = live.rng_state
        staged = TransactionRng(plan, live)
        staged.next_u64()
        self.assertEqual(live.rng_state.to_dict(), baseline.to_dict())
        self.assertEqual(live.rng_state.next_u64(), baseline.next_u64())

    def test_commit_material_can_be_consumed_exactly_once(self):
        live, _, plan = make_plan()
        staged = TransactionRng(plan, live)
        result = staged.next_u64()
        material = staged.consume_commit_material()
        self.assertEqual(material.ledger[0].result, result)
        with self.assertRaises(TransactionError):
            staged.consume_commit_material()
        with self.assertRaises(TransactionError):
            staged.next_u64()

    def test_material_and_exported_state_do_not_alias(self):
        live, _, plan = make_plan()
        staged = TransactionRng(plan, live)
        staged.next_u64()
        material = staged.peek_material()
        before = material.to_dict()
        exported = material.rng.to_dict()
        exported["state"]["internal_state"][0] = -1
        self.assertEqual(material.to_dict(), before)

    def test_invalid_or_stale_plan_cannot_receive_rng(self):
        live, _, plan = make_plan()
        with self.assertRaises(TransactionError):
            TransactionRng(True, live)
        stale = make_state().to_dict()
        stale["revision_and_transaction_sequence"]["published_revision"]["counter"] += 1
        with self.assertRaises(TransactionError):
            TransactionRng(plan, type(live).from_dict(stale))

    def test_same_revision_but_different_rng_state_rejects(self):
        live, _, plan = make_plan()
        changed = live.to_dict()
        other_rng = live.rng_state
        other_rng.next_u64()
        changed["rng_state"] = other_rng.to_dict()
        with self.assertRaises(TransactionError):
            TransactionRng(plan, type(live).from_dict(changed))

    def test_transaction_rng_has_no_publish_or_commit_surface(self):
        live, _, plan = make_plan()
        staged = TransactionRng(plan, live)
        self.assertFalse(hasattr(staged, "publish"))
        self.assertFalse(hasattr(staged, "commit"))


if __name__ == "__main__":
    unittest.main()
