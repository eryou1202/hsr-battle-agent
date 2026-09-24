# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.atomic_commit import (
    AtomicCommit, AtomicCommitError, AtomicCommitInjectedFailure,
)
from hsr_battle_agent.battle_sandbox.identity import ENTITY
from hsr_battle_agent.battle_sandbox.preflight import ObligationAccess
from hsr_battle_agent.battle_sandbox.staged_trace import StagedTrace
from hsr_battle_agent.battle_sandbox.transaction import StagedDelta
from hsr_battle_agent.battle_sandbox.transaction_rng import TransactionRng
from tests.battle_sandbox.test_transaction_plan import make_plan


def transaction_components():
    writes = (
        ObligationAccess("store:resources:hp", PresenceValue.present({"delta": -3})),
        ObligationAccess("allocator:entity", PresenceValue.present({"family": "ENTITY"})),
        ObligationAccess("trace:effect", PresenceValue.present({"id": {"schema": "typed_identity/1", "family": "ENTITY", "namespace": "entity", "generation": 0, "value": 0, "authority": "LOCAL_DESIGN_IDENTITY"}})),
    )
    live, _, plan = make_plan(writes=writes)
    delta = StagedDelta(plan, live).stage_store_append("resources", "hp", {"delta": -3})
    delta, identity = delta.stage_allocation(ENTITY, "entity")
    rng = TransactionRng(plan, live)
    draw = rng.next_u64()
    # The draw is deterministic for this state; construct the remaining exact
    # permissions in a second plan so staged output cannot broaden them.
    writes = writes + (
        ObligationAccess("event:damage", PresenceValue.present({"draw": draw})),
        ObligationAccess("queue:followup", PresenceValue.present({"items": [None]})),
    )
    live, _, plan = make_plan(writes=writes)
    delta = StagedDelta(plan, live).stage_store_append("resources", "hp", {"delta": -3})
    delta, identity = delta.stage_allocation(ENTITY, "entity")
    rng = TransactionRng(plan, live)
    draw = rng.next_u64()
    trace = StagedTrace(plan, live).stage_trace("effect", {"id": identity.to_dict()})
    trace = trace.stage_event("damage", {"draw": draw})
    trace = trace.stage_queue_write("followup", {"items": [None]})
    return live, plan, delta, rng, trace


class TestAtomicCommit(unittest.TestCase):
    def test_success_returns_one_complete_new_revision(self):
        live, plan, delta, rng, trace = transaction_components()
        before = live.to_dict()
        result = AtomicCommit(plan, delta, rng, trace).commit(live)
        published = result.state
        self.assertEqual(live.to_dict(), before)
        self.assertEqual(published.revision.counter, live.revision.counter + 1)
        self.assertEqual(published.revision_sequence.replay_sequence, live.revision_sequence.replay_sequence + 1)
        self.assertEqual(published.revision_sequence.committed_effect_sequence, live.revision_sequence.committed_effect_sequence + 1)
        self.assertEqual(published.stores["resources"].keys(), ("hp",))
        self.assertNotEqual(published.rng_state.to_dict(), live.rng_state.to_dict())
        self.assertNotEqual(published.allocator.to_dict(), live.allocator.to_dict())
        self.assertEqual([x.channel for x in result.records], ["TRACE", "EVENT", "QUEUE"])

    def test_stale_revision_rejects_without_any_publication(self):
        live, plan, delta, rng, trace = transaction_components()
        stale_doc = live.to_dict()
        stale_doc["revision_and_transaction_sequence"]["published_revision"]["counter"] += 1
        stale = type(live).from_dict(stale_doc)
        before_live = live.to_dict()
        before_stale = stale.to_dict()
        with self.assertRaises(AtomicCommitError):
            AtomicCommit(plan, delta, rng, trace).commit(stale)
        self.assertEqual(live.to_dict(), before_live)
        self.assertEqual(stale.to_dict(), before_stale)

    def test_all_validation_and_publication_failures_leave_original_identical(self):
        for point in (
            "before_validation", "after_binding_validation", "after_delta_validation",
            "after_rng_validation", "after_trace_validation", "before_publication", "publication",
        ):
            live, plan, delta, rng, trace = transaction_components()
            before = live.to_dict()
            with self.assertRaises(AtomicCommitInjectedFailure, msg=point):
                AtomicCommit(plan, delta, rng, trace).commit(live, failure_point=point)
            self.assertEqual(live.to_dict(), before, point)

    def test_commit_cannot_be_replayed(self):
        live, plan, delta, rng, trace = transaction_components()
        commit = AtomicCommit(plan, delta, rng, trace)
        commit.commit(live)
        with self.assertRaises(AtomicCommitError):
            commit.commit(live)

    def test_discarded_trace_rejects(self):
        live, plan, delta, rng, trace = transaction_components()
        with self.assertRaises(AtomicCommitError):
            AtomicCommit(plan, delta, rng, trace.discard()).commit(live)

    def test_result_nested_reads_are_detached(self):
        live, plan, delta, rng, trace = transaction_components()
        result = AtomicCommit(plan, delta, rng, trace).commit(live)
        before = result.to_dict()
        result.events[0].payload["draw"] = -1
        result.state.stores["resources"].entries[0].value.require_present()["delta"] = 0
        self.assertEqual(result.to_dict(), before)

    def test_unknown_failure_point_rejects_before_publication(self):
        live, plan, delta, rng, trace = transaction_components()
        before = live.to_dict()
        with self.assertRaises(AtomicCommitError):
            AtomicCommit(plan, delta, rng, trace).commit(live, failure_point="other")
        self.assertEqual(live.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
