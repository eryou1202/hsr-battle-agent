"""Tests for KERNEL-RNG-001 weighted selection."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.rng_semantics_reference import (
    RngSemanticError,
    rng_01_from_seed,
    select_weighted_index,
)


class RngSemanticsTest(unittest.TestCase):
    def test_weighted_selection_boundaries(self) -> None:
        self.assertEqual(select_weighted_index([0.3333, 0.3333, 0.3334], Decimal("0")).selected_index, 0)
        self.assertEqual(select_weighted_index([0.3333, 0.3333, 0.3334], Decimal("0.34")).selected_index, 1)
        self.assertEqual(select_weighted_index([0.3333, 0.3333, 0.3334], Decimal("0.99")).selected_index, 2)

    def test_odds_are_normalized(self) -> None:
        result = select_weighted_index([1, 1], Decimal("0.5"))
        self.assertEqual(result.selected_index, 1)
        self.assertEqual(sum(result.normalized_odds), Decimal("1"))

    def test_invalid_odds_reject(self) -> None:
        with self.assertRaises(RngSemanticError):
            select_weighted_index([], Decimal("0"))
        with self.assertRaises(RngSemanticError):
            select_weighted_index([0, 0], Decimal("0"))
        with self.assertRaises(RngSemanticError):
            select_weighted_index([1], Decimal("2"))

    def test_seeded_draw_is_reproducible(self) -> None:
        self.assertEqual(rng_01_from_seed(42), rng_01_from_seed(42))


if __name__ == "__main__":
    unittest.main()
