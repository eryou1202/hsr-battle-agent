from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario, CustomScenarioError, CustomTerminalRule, EmptySidePolicy,
    ResultPolicy, ScenarioParticipant, SimultaneousExhaustionPolicy,
)
from tests.battle_sandbox.test_terra_state import make_state


def rule(rule_id="empty-side", result_policy=ResultPolicy.REPORT_CUSTOM_OUTCOME):
    return CustomTerminalRule(
        namespace="tests.custom", version="1", rule_id=rule_id,
        empty_side_policy=EmptySidePolicy.TERMINAL,
        simultaneous_exhaustion_policy=SimultaneousExhaustionPolicy.DRAW,
        result_policy=result_policy,
    )


def scenario(rule_id="empty-side", stage_id=None,
             result_policy=ResultPolicy.REPORT_CUSTOM_OUTCOME):
    return CustomScenario(
        stage_id=stage_id,
        participants=(ScenarioParticipant("left-1", "left", 0),
                      ScenarioParticipant("right-1", "right", 0)),
        initial_state=make_state(), terminal_rule=rule(rule_id, result_policy),
    )


class CustomScenarioTests(unittest.TestCase):
    def test_absent_stage_id_is_not_fabricated(self):
        item = scenario()
        self.assertIsNone(item.stage_id)
        self.assertNotIn("stage_id", item.to_dict())

    def test_explicit_stage_id_is_only_an_optional_custom_label(self):
        item = scenario(stage_id="custom-stage")
        self.assertEqual(item.to_dict()["stage_id"], "custom-stage")
        self.assertIs(item.policy_identity().evidence_mode, EvidenceMode.SANDBOX_EXTENSION)

    def test_complete_state_and_participants_are_detached(self):
        state = make_state()
        participants = [ScenarioParticipant("left-1", "left", 0)]
        item = CustomScenario(stage_id=None, participants=participants,
                              initial_state=state, terminal_rule=rule())
        before = item.to_dict()
        participants.append(ScenarioParticipant("right-1", "right", 0))
        exported = item.initial_state
        exported.rng_state.next_u64()
        self.assertEqual(item.to_dict(), before)

    def test_rule_identity_changes_snapshot_and_hash(self):
        left, right = scenario("rule-a"), scenario("rule-b")
        self.assertNotEqual(left.policy_identity(), right.policy_identity())
        self.assertNotEqual(left.semantic_hash(), right.semantic_hash())

    def test_custom_exhaustion_never_claims_native_victory(self):
        result = scenario().evaluate_terminal(left_alive=0, right_alive=2)
        self.assertTrue(result.terminal)
        self.assertEqual(result.custom_outcome, "CUSTOM_LEFT_EXHAUSTED")
        self.assertIs(result.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertNotIn("VICTORY", result.custom_outcome)

    def test_simultaneous_policy_is_explicit_custom_output(self):
        result = scenario().evaluate_terminal(left_alive=0, right_alive=0)
        self.assertEqual(result.custom_outcome, "CUSTOM_SIMULTANEOUS_DRAW")
        self.assertEqual(result.exhausted_sides, ("left", "right"))

    def test_both_result_policies_are_observable_and_hash_distinct(self):
        custom = scenario(result_policy=ResultPolicy.REPORT_CUSTOM_OUTCOME)
        exhausted = scenario(result_policy=ResultPolicy.REPORT_EXHAUSTED_SIDES)
        custom_result = custom.evaluate_terminal(left_alive=0, right_alive=2)
        exhausted_result = exhausted.evaluate_terminal(left_alive=0, right_alive=2)
        self.assertIs(custom_result.result_policy, ResultPolicy.REPORT_CUSTOM_OUTCOME)
        self.assertIs(exhausted_result.result_policy, ResultPolicy.REPORT_EXHAUSTED_SIDES)
        self.assertNotEqual(custom.semantic_hash(), exhausted.semantic_hash())
        self.assertIs(custom_result.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertIs(exhausted_result.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertNotIn("VICTORY", custom_result.custom_outcome)
        self.assertNotIn("VICTORY", exhausted_result.custom_outcome)

    def test_no_implicit_wave_or_official_fallback_surface(self):
        item = scenario()
        for name in ("waves", "advance_wave", "official_stage", "native_victory", "activate_loadout"):
            self.assertFalse(hasattr(item, name))

    def test_required_initialization_components_reject(self):
        with self.assertRaises(CustomScenarioError):
            CustomScenario(stage_id=None, participants=(), initial_state=make_state(), terminal_rule=rule())


if __name__ == "__main__":
    unittest.main()
