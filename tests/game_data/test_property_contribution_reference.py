"""Tests for property-contribution reference semantics."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.property_contribution_reference import PropertyState


class PropertyContributionTest(unittest.TestCase):
    def test_slots_are_stable_and_removal_is_exact(self) -> None:
        state = PropertyState.empty({"AttackRatio": "1"})
        first = state.set_contribution("M_A", "AttackRatio", "0.2")
        second = first.state.set_contribution("M_B", "AttackRatio", "0.3")
        self.assertEqual(second.state.read("AttackRatio"), Decimal("1.5"))
        refreshed = second.state.set_contribution("M_A", "AttackRatio", "0.4")
        self.assertEqual(refreshed.state.read("AttackRatio"), Decimal("1.7"))
        removed = refreshed.state.remove_contribution("M_A", "AttackRatio")
        self.assertEqual(removed.action, "REMOVE_CONTRIBUTION")
        self.assertEqual(removed.state.read("AttackRatio"), Decimal("1.3"))

    def test_missing_removal_is_explicit(self) -> None:
        state = PropertyState.empty({"HP": "100"})
        self.assertEqual(state.remove_contribution("M_X", "HP").action, "REMOVE_CONTRIBUTION_MISSING")


if __name__ == "__main__":
    unittest.main()
