"""Tests for toughness/break reference semantics."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.toughness_break_reference import (
    ToughnessState,
    apply_toughness_damage,
    recover_toughness,
)


class ToughnessBreakTest(unittest.TestCase):
    def test_reduction_and_zero_transition(self) -> None:
        state = ToughnessState(Decimal("100"), Decimal("100"))
        reduced = apply_toughness_damage(state, Decimal("30"))
        self.assertEqual(reduced.action, "TOUGHNESS_REDUCED")
        self.assertEqual(reduced.state.current_toughness, Decimal("70"))
        broken = apply_toughness_damage(reduced.state, Decimal("80"), enemy_max_toughness=100)
        self.assertEqual(broken.action, "BREAK_TRIGGERED")
        self.assertTrue(broken.state.broken)
        self.assertGreater(broken.break_damage, Decimal("0"))

    def test_broken_absorbs_no_more_and_recovers(self) -> None:
        state = ToughnessState(Decimal("100"), Decimal("0"), broken=True)
        self.assertEqual(apply_toughness_damage(state, Decimal("10")).action, "TOUGHNESS_REDUCED")
        recovered = recover_toughness(state)
        self.assertEqual(recovered.action, "RECOVERY_RESTORED")
        self.assertFalse(recovered.state.broken)
        self.assertEqual(recovered.state.current_toughness, Decimal("100"))


if __name__ == "__main__":
    unittest.main()
