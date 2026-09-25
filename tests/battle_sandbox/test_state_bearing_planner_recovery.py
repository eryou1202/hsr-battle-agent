from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.gate_certificate import GateCertificate
from hsr_battle_agent.battle_sandbox.legal_actions import PlayerLegalAction
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceTransaction,
    SandboxTransitionOutcome,
    plan_sandbox_resource_transition,
    query_sandbox_legal_actions,
    read_sandbox_resource_state,
)
from hsr_battle_agent.game_data.reference_schedule_v2 import SchedulerCandidate
from tests.battle_sandbox.test_sandbox_transition_atomic import prepare, state_hash
from tests.battle_sandbox.test_sandbox_transition_contract import initialized


def step(state, contract, policy, action_id):
    _plan, transaction = prepare(state, contract, policy, action_id)
    result = transaction.commit(state)
    if result.outcome is not SandboxTransitionOutcome.COMMITTED:
        raise AssertionError(result.reason)
    return result.committed_state


class StateBearingPlannerRecoveryTests(unittest.TestCase):
    def test_two_way_branch_changes_resource_not_only_revision(self):
        source, contract, policy = initialized()
        left = step(source.clone(), contract, policy, "action-a")
        right = step(source.clone(), contract, policy, "action-b")
        self.assertEqual(left.revision_sequence, right.revision_sequence)
        self.assertEqual(read_sandbox_resource_state(left, contract).amount, 9)
        self.assertEqual(read_sandbox_resource_state(right, contract).amount, 8)
        self.assertNotEqual(left.stores["resources"].to_dict(),
                            right.stores["resources"].to_dict())
        self.assertNotEqual(state_hash(left, policy), state_hash(right, policy))

    def test_each_branch_replays_byte_and_semantically_identically(self):
        source, contract, policy = initialized()
        for action_id in ("action-a", "action-b"):
            first = step(source.clone(), contract, policy, action_id)
            second = step(source.clone(), contract, policy, action_id)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(state_hash(first, policy), state_hash(second, policy))
            self.assertEqual(first.rng_state.to_dict(), second.rng_state.to_dict())

    def test_multi_turn_branches_replay_from_midway_clones(self):
        source, contract, policy = initialized()
        left_mid = step(source.clone(), contract, policy, "action-a")
        right_mid = step(source.clone(), contract, policy, "action-b")
        left_final = step(left_mid.clone(), contract, policy, "action-c")
        right_final = step(right_mid.clone(), contract, policy, "action-d")
        left_replay = step(left_mid.clone(), contract, policy, "action-c")
        right_replay = step(right_mid.clone(), contract, policy, "action-d")
        self.assertEqual(left_final.to_dict(), left_replay.to_dict())
        self.assertEqual(right_final.to_dict(), right_replay.to_dict())
        self.assertEqual(read_sandbox_resource_state(left_final, contract).amount, 6)
        self.assertEqual(read_sandbox_resource_state(right_final, contract).amount, 4)
        self.assertNotEqual(state_hash(left_final, policy), state_hash(right_final, policy))

    def test_rejected_stale_action_preserves_complete_state_identity(self):
        source, contract, policy = initialized()
        plan, transaction = prepare(source, contract, policy, "action-a")
        changed = step(source, contract, policy, "action-b")
        before = copy.deepcopy(changed.to_dict())
        before_hash = state_hash(changed, policy)
        result = transaction.commit(changed)
        self.assertEqual(plan.source_revision, source.revision)
        self.assertIs(result.outcome, SandboxTransitionOutcome.REJECTED)
        self.assertEqual(changed.to_dict(), before)
        self.assertEqual(state_hash(changed, policy), before_hash)
        self.assertEqual(changed.rng_state.to_dict(), source.rng_state.to_dict())
        self.assertEqual(changed.allocator.to_dict(), source.allocator.to_dict())

    def test_supported_legal_actions_are_stable_for_declared_complete_scope(self):
        _source, contract, _policy = initialized()
        candidates = tuple(rule.candidate_occurrence_id for rule in contract.actions)
        first = query_sandbox_legal_actions(contract, candidates)
        second = query_sandbox_legal_actions(contract, tuple(candidates))
        self.assertEqual(first, second)
        self.assertEqual(tuple(action.action_id for action in first.actions),
                         tuple(rule.action_id for rule in contract.actions))

    def test_player_action_remains_distinct_from_scheduler_and_native_permission(self):
        source, contract, policy = initialized()
        view = query_sandbox_legal_actions(
            contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
        )
        plan = plan_sandbox_resource_transition(source, policy, contract, view, "action-a")
        self.assertIsInstance(view.actions[0], PlayerLegalAction)
        self.assertNotIsInstance(view.actions[0], SchedulerCandidate)
        self.assertNotIsInstance(view.actions[0], GateCertificate)
        self.assertNotIsInstance(plan, GateCertificate)

    def test_reference_action_and_extension_transition_labels_both_survive(self):
        source, contract, policy = initialized()
        view = query_sandbox_legal_actions(
            contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
        )
        plan = plan_sandbox_resource_transition(source, policy, contract, view, "action-a")
        published = SandboxResourceTransaction(contract, plan).commit(source).committed_state
        self.assertIs(view.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIs(view.actions[0].evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIs(plan.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertIs(read_sandbox_resource_state(published, contract).evidence_mode,
                      EvidenceMode.SANDBOX_EXTENSION)

    def test_rng_does_not_advance_on_success_or_rejection(self):
        source, contract, policy = initialized()
        before_rng = source.rng_state.to_dict()
        published = step(source, contract, policy, "action-a")
        self.assertEqual(published.rng_state.to_dict(), before_rng)
        plan, transaction = prepare(source, contract, policy, "action-b")
        rejected = transaction.commit(published)
        self.assertIs(rejected.outcome, SandboxTransitionOutcome.REJECTED)
        self.assertEqual(published.rng_state.to_dict(), before_rng)


if __name__ == "__main__":
    unittest.main()
