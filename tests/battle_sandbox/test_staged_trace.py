# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.staged_trace import StagedTrace
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.preflight import ObligationAccess
from hsr_battle_agent.battle_sandbox.transaction import TransactionError
from tests.battle_sandbox.test_transaction_plan import make_plan


def trace_plan(*records):
    writes = tuple(
        ObligationAccess(
            f"{channel.lower()}:{kind}",
            PresenceValue.null() if payload is None else PresenceValue.present(payload),
        )
        for channel, kind, payload in records
    )
    return make_plan(writes=writes)


class TestStagedTrace(unittest.TestCase):
    def test_all_channels_are_private_ordered_and_duplicate_preserving(self):
        live, _, plan = trace_plan(
            ("TRACE", "hit", {"x": [1]}),
            ("EVENT", "event", {"x": [1]}),
            ("QUEUE", "queue", {"x": [1]}),
        )
        before = live.to_dict()
        staged = StagedTrace(plan, live)
        staged = staged.stage_trace("hit", {"x": [1]})
        staged = staged.stage_event("event", {"x": [1]})
        staged = staged.stage_queue_write("queue", {"x": [1]})
        staged = staged.stage_event("event", {"x": [1]})
        self.assertEqual([x.channel for x in staged.records], ["TRACE", "EVENT", "QUEUE", "EVENT"])
        self.assertEqual([x.kind for x in staged.events], ["event", "event"])
        self.assertEqual(live.to_dict(), before)

    def test_tuple_list_and_nested_aliases_remain_lossless_and_detached(self):
        payload = {"tuple": (1, 2), "list": [1, 2], "nested": []}
        live, _, plan = trace_plan(("TRACE", "lossless", payload))
        staged = StagedTrace(plan, live).stage_trace("lossless", payload)
        before = staged.to_dict()
        payload["nested"].append("input")
        exported = staged.records[0].payload
        exported["nested"].append("output")
        self.assertIsInstance(exported["tuple"], tuple)
        self.assertIsInstance(exported["list"], list)
        self.assertEqual(staged.to_dict(), before)

    def test_abort_discards_every_channel_and_live_state_is_unchanged(self):
        live, _, plan = trace_plan(
            ("TRACE", "t", 1), ("EVENT", "e", 2), ("QUEUE", "q", 3)
        )
        before = live.to_dict()
        staged = StagedTrace(plan, live).stage_trace("t", 1).stage_event("e", 2).stage_queue_write("q", 3)
        discarded = staged.discard()
        self.assertEqual(discarded.records, ())
        self.assertTrue(discarded.discarded)
        self.assertEqual(live.to_dict(), before)
        with self.assertRaises(TransactionError):
            discarded.stage_trace("late", {})

    def test_no_callback_or_publication_surface(self):
        live, _, plan = make_plan()
        staged = StagedTrace(plan, live)
        forbidden = {"callback", "invoke", "publish", "commit", "execute"}
        self.assertTrue(forbidden.isdisjoint(dir(staged)))

    def test_uncertified_output_cannot_escape_write_footprint(self):
        live, _, plan = make_plan()
        staged = StagedTrace(plan, live)
        for method in (staged.stage_trace, staged.stage_event, staged.stage_queue_write):
            with self.assertRaises(TransactionError):
                method("undeclared", {"x": 1})

    def test_stale_plan_rejects_before_staging(self):
        live, _, plan = make_plan()
        doc = live.to_dict()
        doc["revision_and_transaction_sequence"]["published_revision"]["counter"] += 1
        with self.assertRaises(TransactionError):
            StagedTrace(plan, type(live).from_dict(doc))


if __name__ == "__main__":
    unittest.main()
