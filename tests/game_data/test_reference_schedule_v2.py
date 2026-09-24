import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.legal_actions import (
    LegalActionError, LegalActionProposal, LegalActionsStatus, PlayerLegalAction,
    query_player_legal_actions, settle_legal_action,
)
from hsr_battle_agent.game_data.reference_schedule_v2 import (
    AIDecisionOpportunity, ReferenceScheduleError, SchedulerCandidate,
    SchedulerFamily, apply_behavior_delay_separately, select_ordinary_candidate,
)


def candidate(occurrence, actor, delay, tail=(0,), mode=EvidenceMode.REFERENCE_MODEL,
              family=SchedulerFamily.ORDINARY):
    return SchedulerCandidate(occurrence, actor, family, Decimal(str(delay)), tail, mode)


def proposal(action="skill", occurrence="c1", *, target=True, terminal=True, cost="1"):
    return LegalActionProposal(action, occurrence, "actor-a", ("target",), Decimal(cost),
                               target, terminal)


class ReferenceScheduleV2Tests(unittest.TestCase):
    def test_candidate_is_not_player_action(self):
        self.assertNotIsInstance(candidate("c1", "actor-a", 0), PlayerLegalAction)

    def test_ai_opportunity_is_not_player_action(self):
        self.assertNotIsInstance(AIDecisionOpportunity("ai1", "enemy"), PlayerLegalAction)

    def test_native_unresolved_all_key_tie_blocks(self):
        items = [candidate("c1", "a", 1, mode=EvidenceMode.NATIVE_EVIDENCED),
                 candidate("c2", "b", 1, mode=EvidenceMode.NATIVE_EVIDENCED)]
        with self.assertRaisesRegex(ReferenceScheduleError, "tie"):
            select_ordinary_candidate(items, evidence_mode=EvidenceMode.NATIVE_EVIDENCED)

    def test_reference_equal_tie_uses_prior_list_only_under_reference_label(self):
        first = candidate("first", "a", 1); second = candidate("second", "b", 1)
        result = select_ordinary_candidate([second, first], evidence_mode=EvidenceMode.REFERENCE_MODEL)
        self.assertEqual(result.selected.occurrence_id, "second")
        self.assertIs(result.evidence_mode, EvidenceMode.REFERENCE_MODEL)

    def test_av_zero_is_not_automatic_execution(self):
        item = candidate("c1", "a", 0)
        self.assertFalse(hasattr(item, "execute"))
        self.assertFalse(hasattr(item, "is_immediate"))

    def test_scheduler_families_are_not_merged(self):
        for family in tuple(SchedulerFamily)[1:]:
            with self.subTest(family=family), self.assertRaises(ReferenceScheduleError):
                select_ordinary_candidate([candidate("c", "a", 0, family=family)],
                                          evidence_mode=EvidenceMode.REFERENCE_MODEL)

    def test_behavior_delay_does_not_mutate_property38(self):
        item = candidate("c1", "a", 9)
        view = apply_behavior_delay_separately(item, 3)
        self.assertEqual(view.normalized_behavior_delay, Decimal("3"))
        self.assertEqual(view.property38_unchanged, Decimal("9"))
        self.assertEqual(item.remaining_delay, Decimal("9"))

    def test_unsupported_target_blocks_without_partial_actions_or_debit(self):
        before = Decimal("5")
        view = query_player_legal_actions(["c1"], [proposal(target=False)])
        self.assertIs(view.status, LegalActionsStatus.BLOCKED)
        self.assertEqual(view.actions, ())
        with self.assertRaises(LegalActionError):
            settle_legal_action(view, "skill", before)
        self.assertEqual(before, Decimal("5"))

    def test_unsupported_terminal_blocks_without_partial_actions_or_debit(self):
        before = Decimal("5")
        view = query_player_legal_actions(["c1"], [proposal(terminal=False)])
        self.assertIs(view.status, LegalActionsStatus.BLOCKED)
        self.assertEqual(view.actions, ())
        with self.assertRaises(LegalActionError):
            settle_legal_action(view, "skill", before)
        self.assertEqual(before, Decimal("5"))

    def test_complete_supported_scope_is_deterministic_and_settles(self):
        items = [candidate("c1", "actor-a", 2), candidate("c2", "actor-b", 5)]
        first = select_ordinary_candidate(items, evidence_mode=EvidenceMode.REFERENCE_MODEL)
        second = select_ordinary_candidate(items, evidence_mode=EvidenceMode.REFERENCE_MODEL)
        self.assertEqual(first, second)
        view1 = query_player_legal_actions([item.occurrence_id for item in first.ordered_candidates],
                                           [proposal()])
        view2 = query_player_legal_actions([item.occurrence_id for item in second.ordered_candidates],
                                           [proposal()])
        self.assertEqual(view1, view2)
        self.assertIs(view1.status, LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE)
        self.assertEqual(settle_legal_action(view1, "skill", 5), Decimal("4"))

    def test_missing_candidate_blocks_complete_view(self):
        view = query_player_legal_actions(["other"], [proposal()])
        self.assertIs(view.status, LegalActionsStatus.BLOCKED)
        self.assertEqual(view.actions, ())

    def test_no_native_permission_promotion(self):
        view = query_player_legal_actions(["c1"], [proposal()])
        self.assertIs(view.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        for value in (view, view.actions[0], candidate("c1", "actor-a", 1)):
            for name in ("gate_certificate", "native_contract", "execute", "commit"):
                self.assertFalse(hasattr(value, name))

    def test_constructor_sequences_are_detached(self):
        targets = ["target"]
        action = LegalActionProposal(
            "skill", "c1", "actor-a", targets, Decimal("1"), True, True
        )
        targets.append("mutated")
        self.assertEqual(action.target_ids, ("target",))
        tail = [1, 2]
        item = SchedulerCandidate(
            "c1", "actor-a", SchedulerFamily.ORDINARY,
            Decimal("1"), tail, EvidenceMode.REFERENCE_MODEL,
        )
        tail.append(3)
        self.assertEqual(item.comparator_tail, (1, 2))


if __name__ == "__main__":
    unittest.main()
