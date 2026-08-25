"""Tests for TargetAlias resolution (TARGET-001 reference)."""
from __future__ import annotations

import unittest

from hsr_battle_agent.game_data.target_semantics_reference import (
    BattleTargetContext,
    EntitySnapshot,
    UnsupportedTargetAlias,
    resolve_target_alias,
    resolve_target_payload,
)


def context() -> BattleTargetContext:
    entities = {
        "p1": EntitySnapshot("p1", "light", position=(0, 0)),
        "p2": EntitySnapshot("p2", "light", position=(0, 1)),
        "p3": EntitySnapshot("p3", "light", position=(0, 2), selectable=False),
        "e1": EntitySnapshot("e1", "dark", position=(0, 0)),
        "e2": EntitySnapshot("e2", "dark", position=(0, 1)),
        "e3": EntitySnapshot("e3", "dark", position=(1, 0), alive=False),
        "e4": EntitySnapshot("e4", "dark", position=(0, 2), selectable=False),
    }
    return BattleTargetContext(
        entities=entities,
        caster_id="p1",
        ability_target_id="e1",
        modifier_owner_id="p1",
        current_turn_action_entity_id="e1",
        current_turn_owner_id="p1",
        damage_attacker_id="p1",
        damage_defender_id="e1",
        param_entity_ids=("e1",),
    )


class TargetSemanticsTest(unittest.TestCase):
    def test_direct_and_collection_aliases(self) -> None:
        ctx = context()
        self.assertEqual(resolve_target_alias("Caster", ctx), ("p1",))
        self.assertEqual(resolve_target_alias("AbilityTargetEntity", ctx), ("e1",))
        self.assertEqual(resolve_target_alias("ModifierOwnerEntity", ctx), ("p1",))
        self.assertEqual(resolve_target_alias("AllEnemy", ctx), ("e1", "e2"))
        self.assertEqual(resolve_target_alias("AllEnemyWithUnSelectable", ctx), ("e1", "e2", "e4"))
        self.assertEqual(resolve_target_alias("AllLightTeam", ctx), ("p1", "p2"))

    def test_adjoin_and_center(self) -> None:
        ctx = context()
        self.assertEqual(resolve_target_alias("ModifierOwnerAdjoinEntity", ctx), ("p2",))
        self.assertEqual(resolve_target_alias("DarkTeamCenter", ctx), ("e1",))

    def test_unsupported_alias_rejects(self) -> None:
        with self.assertRaises(UnsupportedTargetAlias):
            resolve_target_alias("HimekoNova_00_AssistTarget", context())
        with self.assertRaises(UnsupportedTargetAlias):
            resolve_target_alias("UnknownAlias", context())

    def test_payload_extraction(self) -> None:
        ctx = context()
        self.assertEqual(resolve_target_payload({"$type": "RPG.GameCore.TargetAlias", "Alias": "Caster"}, ctx), ("p1",))


if __name__ == "__main__":
    unittest.main()
