from __future__ import annotations

import copy
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario, CustomTerminalRule, EmptySidePolicy, ResultPolicy,
    ScenarioParticipant, SimultaneousExhaustionPolicy,
)
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.legal_actions import (
    LegalActionProposal, LegalActionsStatus, query_player_legal_actions,
    settle_legal_action,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.strict_executor import (
    STRICT_NO_OP_ACTION, StrictExecutor, StrictStepOutcome,
)
from hsr_battle_agent.battle_sandbox.transaction import plan_transaction
from hsr_battle_agent.game_data.reference_schedule_v2 import (
    SchedulerCandidate, SchedulerFamily, select_ordinary_candidate,
)
from tests.battle_sandbox.test_transaction_plan import make_certificate, make_state
import tests.battle_sandbox.test_transaction_plan as transaction_fixtures


def custom(state, rule_id="empty-side"):
    return CustomScenario(
        stage_id=None,
        participants=(ScenarioParticipant("p1", "left", 0),
                      ScenarioParticipant("p2", "right", 0)),
        initial_state=state,
        terminal_rule=CustomTerminalRule(
            "tests.replay", "1", rule_id, EmptySidePolicy.TERMINAL,
            SimultaneousExhaustionPolicy.DRAW,
            ResultPolicy.REPORT_CUSTOM_OUTCOME,
        ),
    )


def atomic_noop(state):
    operations = ()
    plan = plan_transaction(state, make_certificate(state, operations), operations)
    result = StrictExecutor().step(state, plan, STRICT_NO_OP_ACTION)
    if result.outcome is not StrictStepOutcome.COMMITTED:
        raise AssertionError(result.to_dict())
    return result.committed_state


def run_turns(state, count):
    current = state
    observed = []
    resource = Decimal("10")
    for index in range(count):
        candidates = (
            SchedulerCandidate(f"turn-{index}-a", "actor-a", SchedulerFamily.ORDINARY,
                               Decimal(index + 1), (0,), EvidenceMode.REFERENCE_MODEL),
            SchedulerCandidate(f"turn-{index}-b", "actor-b", SchedulerFamily.ORDINARY,
                               Decimal(index + 2), (0,), EvidenceMode.REFERENCE_MODEL),
        )
        selection = select_ordinary_candidate(candidates, evidence_mode=EvidenceMode.REFERENCE_MODEL)
        action_id = f"skill-{index}"
        proposal = LegalActionProposal(
            action_id, selection.selected.occurrence_id,
            selection.selected.actor_id, ("target",), Decimal("1"), True, True,
        )
        view = query_player_legal_actions(
            tuple(item.occurrence_id for item in selection.ordered_candidates),
            (proposal,),
        )
        if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
            raise AssertionError(view)
        resource = settle_legal_action(view, action_id, resource)
        observed.append((selection.selected.occurrence_id, action_id, str(resource)))
        current = atomic_noop(current)
    return current, tuple(observed)


class MultiTurnReplayV2Tests(unittest.TestCase):
    def test_initial_clone_has_equal_snapshot_hash_and_rng_position(self):
        state = make_state()
        clone = state.clone()
        policy = custom(state).policy_identity()
        self.assertEqual(state.to_dict(), clone.to_dict())
        self.assertEqual(semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=policy)),
                         semantic_hash_v2(TerraSnapshotV2(state=clone, policy_identity=policy)))
        self.assertEqual(state.rng_state.to_dict(), clone.rng_state.to_dict())

    def test_multi_turn_clone_midway_replays_identically(self):
        first, prefix = run_turns(make_state(), 2)
        midway = first.clone()
        left, left_actions = run_turns(first, 3)
        right, right_actions = run_turns(midway, 3)
        policy = custom(left).policy_identity()
        self.assertEqual(prefix, (("turn-0-a", "skill-0", "9"),
                                  ("turn-1-a", "skill-1", "8")))
        self.assertEqual(left_actions, right_actions)
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(left.revision.counter, make_state().revision.counter + 5)
        self.assertEqual(left.revision_sequence.replay_sequence,
                         right.revision_sequence.replay_sequence)
        self.assertEqual(left.revision_sequence.committed_effect_sequence,
                         right.revision_sequence.committed_effect_sequence)
        self.assertEqual(left.rng_state.to_dict(), right.rng_state.to_dict())
        self.assertEqual(semantic_hash_v2(TerraSnapshotV2(state=left, policy_identity=policy)),
                         semantic_hash_v2(TerraSnapshotV2(state=right, policy_identity=policy)))

    def test_each_supported_step_is_atomic_and_source_is_unchanged(self):
        state = make_state()
        before = copy.deepcopy(state.to_dict())
        published = atomic_noop(state)
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(published.revision.counter, state.revision.counter + 1)
        self.assertEqual(published.rng_state.to_dict(), state.rng_state.to_dict())

    def test_supported_scope_legal_actions_are_stable_and_settle_explicitly(self):
        candidates = (
            SchedulerCandidate("c1", "actor-a", SchedulerFamily.ORDINARY,
                               Decimal("2"), (0,), EvidenceMode.REFERENCE_MODEL),
            SchedulerCandidate("c2", "actor-b", SchedulerFamily.ORDINARY,
                               Decimal("4"), (0,), EvidenceMode.REFERENCE_MODEL),
        )
        first = select_ordinary_candidate(candidates, evidence_mode=EvidenceMode.REFERENCE_MODEL)
        second = select_ordinary_candidate(tuple(candidates), evidence_mode=EvidenceMode.REFERENCE_MODEL)
        proposal = LegalActionProposal("skill", "c1", "actor-a", ("target",),
                                       Decimal("1"), True, True)
        left = query_player_legal_actions(
            tuple(item.occurrence_id for item in first.ordered_candidates), (proposal,)
        )
        right = query_player_legal_actions(
            tuple(item.occurrence_id for item in second.ordered_candidates), (proposal,)
        )
        self.assertEqual(left, right)
        self.assertIs(left.status, LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE)
        self.assertEqual(settle_legal_action(left, "skill", Decimal("5")), Decimal("4"))

    def test_rejected_action_leaves_complete_state_identity_unchanged(self):
        state = make_state()
        policy = custom(state).policy_identity()
        before = state.to_dict()
        before_hash = semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=policy))
        plan = plan_transaction(state, make_certificate(state, ()), ())
        result = StrictExecutor().step(state, plan, "unsupported.action")
        self.assertIs(result.outcome, StrictStepOutcome.UNSUPPORTED)
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=policy)), before_hash)

    def test_custom_rule_change_invalidates_snapshot_identity(self):
        state = make_state()
        first, second = custom(state, "rule-a"), custom(state, "rule-b")
        self.assertNotEqual(first.policy_identity(), second.policy_identity())
        self.assertNotEqual(first.semantic_hash(), second.semantic_hash())

    def test_profile_binding_is_part_of_certificate_and_cached_plan_identity(self):
        state = make_state()
        original = plan_transaction(state, make_certificate(state, ()), ())
        changed_document = original.certificate.policy_identity.to_dict()
        changed_document["profile_id"] = "changed-profile"
        changed_policy = type(original.certificate.policy_identity).from_dict(changed_document)
        with patch.object(transaction_fixtures, "make_policy", return_value=changed_policy):
            changed = plan_transaction(state, transaction_fixtures.make_certificate(state, ()), ())
        self.assertNotEqual(original.certificate_identity, changed.certificate_identity)
        self.assertNotEqual(original.source_state_hash, changed.source_state_hash)
        self.assertNotEqual(original.to_dict(), changed.to_dict())

    def test_supported_reference_and_custom_paths_never_claim_native_proof(self):
        state = make_state()
        scenario = custom(state)
        candidate = SchedulerCandidate("c", "a", SchedulerFamily.ORDINARY,
                                       Decimal("1"), (0,), EvidenceMode.REFERENCE_MODEL)
        selected = select_ordinary_candidate((candidate,), evidence_mode=EvidenceMode.REFERENCE_MODEL)
        self.assertIs(scenario.policy_identity().evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertIs(selected.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertFalse(hasattr(selected, "gate_certificate"))


if __name__ == "__main__":
    unittest.main()
