from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceTransaction,
    SandboxTransitionOutcome,
    plan_sandbox_resource_transition,
    query_sandbox_legal_actions,
    read_sandbox_resource_state,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from tests.battle_sandbox.test_sandbox_transition_contract import initialized


def prepare(state, contract, policy, action_id):
    view = query_sandbox_legal_actions(
        contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
    )
    plan = plan_sandbox_resource_transition(state, policy, contract, view, action_id)
    return plan, SandboxResourceTransaction(contract, plan)


def state_hash(state, policy):
    return semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=policy))


class SandboxTransitionAtomicTests(unittest.TestCase):
    def test_success_publishes_resource_and_revision_exactly_once(self):
        state, contract, policy = initialized()
        plan, transaction = prepare(state, contract, policy, "action-b")
        result = transaction.commit(state)
        self.assertIs(result.outcome, SandboxTransitionOutcome.COMMITTED)
        published = result.committed_state
        self.assertEqual(read_sandbox_resource_state(published, contract).amount, 8)
        self.assertEqual(published.revision.counter, state.revision.counter + 1)
        self.assertEqual(published.revision_sequence.replay_sequence,
                         state.revision_sequence.replay_sequence + 1)
        self.assertEqual(published.revision_sequence.committed_effect_sequence,
                         state.revision_sequence.committed_effect_sequence + 1)
        self.assertEqual(result.plan_identity, plan.identity)

    def test_success_does_not_mutate_source_rng_allocator_or_other_stores(self):
        state, contract, policy = initialized()
        before = copy.deepcopy(state.to_dict())
        _plan, transaction = prepare(state, contract, policy, "action-a")
        published = transaction.commit(state).committed_state
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(published.rng_state.to_dict(), state.rng_state.to_dict())
        self.assertEqual(published.allocator.to_dict(), state.allocator.to_dict())
        for name, store in state.stores.items():
            if name != "resources":
                self.assertEqual(published.stores[name].to_dict(), store.to_dict())
        self.assertEqual(
            {name: store.to_dict() for name, store in published.opaque_stores.items()},
            {name: store.to_dict() for name, store in state.opaque_stores.items()},
        )

    def test_same_transaction_cannot_publish_twice(self):
        state, contract, policy = initialized()
        _plan, transaction = prepare(state, contract, policy, "action-a")
        first = transaction.commit(state)
        second = transaction.commit(state)
        self.assertIs(first.outcome, SandboxTransitionOutcome.COMMITTED)
        self.assertIs(second.outcome, SandboxTransitionOutcome.REJECTED)
        self.assertEqual(second.reason, "ALREADY_COMMITTED")
        self.assertIsNone(second.committed_state)

    def test_stale_revision_rejects_and_live_state_is_bit_equivalent(self):
        state, contract, policy = initialized()
        _plan, transaction = prepare(state, contract, policy, "action-a")
        _other_plan, other = prepare(state, contract, policy, "action-b")
        stale_live = other.commit(state).committed_state
        before = copy.deepcopy(stale_live.to_dict())
        before_hash = state_hash(stale_live, policy)
        result = transaction.commit(stale_live)
        self.assertIs(result.outcome, SandboxTransitionOutcome.REJECTED)
        self.assertEqual(result.reason, "STALE_REVISION")
        self.assertEqual(stale_live.to_dict(), before)
        self.assertEqual(state_hash(stale_live, policy), before_hash)

    def test_source_content_change_rejects_even_with_same_revision(self):
        state, contract, policy = initialized()
        _plan, transaction = prepare(state, contract, policy, "action-a")
        altered, _same_contract, _same_policy = initialized("9")
        before = copy.deepcopy(altered.to_dict())
        result = transaction.commit(altered)
        self.assertIs(result.outcome, SandboxTransitionOutcome.REJECTED)
        self.assertEqual(result.reason, "STALE_STATE")
        self.assertEqual(altered.to_dict(), before)

    def test_result_state_property_is_detached(self):
        state, contract, policy = initialized()
        _plan, transaction = prepare(state, contract, policy, "action-a")
        result = transaction.commit(state)
        first = result.committed_state
        doc = first.to_dict()
        doc["allocator"]["namespaces"] = []
        self.assertEqual(result.committed_state.to_dict(), first.to_dict())

    def test_no_rng_draw_or_allocator_publication_on_rejection(self):
        state, contract, policy = initialized()
        _plan, transaction = prepare(state, contract, policy, "action-a")
        _plan2, transaction2 = prepare(state, contract, policy, "action-b")
        changed = transaction2.commit(state).committed_state
        rng = changed.rng_state.to_dict()
        allocator = changed.allocator.to_dict()
        result = transaction.commit(changed)
        self.assertIs(result.outcome, SandboxTransitionOutcome.REJECTED)
        self.assertEqual(changed.rng_state.to_dict(), rng)
        self.assertEqual(changed.allocator.to_dict(), allocator)

    def test_commit_changes_battle_state_beyond_revision_bookkeeping(self):
        state, contract, policy = initialized()
        _plan, transaction = prepare(state, contract, policy, "action-c")
        published = transaction.commit(state).committed_state
        self.assertNotEqual(state.stores["resources"].to_dict(),
                            published.stores["resources"].to_dict())
        self.assertEqual(read_sandbox_resource_state(published, contract).amount, 7)

    def test_action_a_and_b_from_same_source_produce_different_states(self):
        state, contract, policy = initialized()
        _pa, ta = prepare(state.clone(), contract, policy, "action-a")
        _pb, tb = prepare(state.clone(), contract, policy, "action-b")
        left = ta.commit(state.clone()).committed_state
        right = tb.commit(state.clone()).committed_state
        self.assertEqual(read_sandbox_resource_state(left, contract).amount, 9)
        self.assertEqual(read_sandbox_resource_state(right, contract).amount, 8)
        self.assertNotEqual(state_hash(left, policy), state_hash(right, policy))


if __name__ == "__main__":
    unittest.main()
