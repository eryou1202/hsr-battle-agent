"""Tests for PRIM-DAMAGE / PRIM-SURVIVAL reference models."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.damage_survival_reference import (
    DamageMultiplierContext,
    SurvivalState,
    break_damage,
    crit_multiplier,
    defense_multiplier,
    dot_chance_multiplier,
    initial_damage,
    normal_damage,
    super_break_damage,
)


class DamageReferenceTest(unittest.TestCase):
    def test_initial_damage_and_defense(self) -> None:
        self.assertEqual(initial_damage(atk=1000, hp=0, defense=0, atk_scaling=2), Decimal("2000"))
        self.assertEqual(defense_multiplier(80, 0), Decimal("0.5"))
        self.assertLess(defense_multiplier(80, 0), defense_multiplier(80, 1))

    def test_crit_and_normal_damage(self) -> None:
        self.assertEqual(crit_multiplier(1, Decimal("0.5")), Decimal("1.5"))
        self.assertEqual(crit_multiplier(0, Decimal("0.5")), Decimal("1"))
        context = DamageMultiplierContext()
        self.assertEqual(normal_damage(Decimal("1000"), context, crit_rate=0, crit_damage=0), Decimal("500"))

    def test_break_and_super_break_reference(self) -> None:
        context = DamageMultiplierContext()
        base = break_damage(elemental_break_scaling=1, enemy_max_toughness=120, special_scaling=1, context=context)
        self.assertGreater(base, Decimal("1400"))
        super_break = super_break_damage(toughness_damage=30, fixed_toughness_damage=0, break_efficiency=1, super_break_modifier=1, context=context)
        self.assertGreater(super_break, Decimal("560"))

    def test_dot_chance(self) -> None:
        self.assertEqual(dot_chance_multiplier(dot_base_chance=1, enemy_effect_res=0), Decimal("1"))
        self.assertEqual(dot_chance_multiplier(dot_base_chance=0, dot_split=0), Decimal("0"))


class SurvivalReferenceTest(unittest.TestCase):
    def test_shield_absorbs_before_hp(self) -> None:
        state = SurvivalState(Decimal("1000"), Decimal("1000"), shield=Decimal("200"))
        after, absorbed, hp_lost = state.absorb(Decimal("300"))
        self.assertEqual((absorbed, hp_lost), (Decimal("200"), Decimal("100")))
        self.assertEqual((after.shield, after.hp, after.alive), (Decimal("0"), Decimal("900"), True))

    def test_heal_clamps_and_lock_hp_blocks_damage(self) -> None:
        state = SurvivalState(Decimal("900"), Decimal("1000"))
        self.assertEqual(state.heal(Decimal("300")).hp, Decimal("1000"))
        locked = state.set_lock_hp(True)
        after, absorbed, hp_lost = locked.absorb(Decimal("5000"))
        self.assertEqual((after.hp, absorbed, hp_lost), (Decimal("900"), Decimal("0"), Decimal("0")))
        self.assertEqual(locked.force_kill().hp, Decimal("900"))

    def test_force_kill_respects_alive(self) -> None:
        state = SurvivalState(Decimal("900"), Decimal("1000")).force_kill()
        self.assertEqual((state.hp, state.alive), (Decimal("0"), False))


if __name__ == "__main__":
    unittest.main()
