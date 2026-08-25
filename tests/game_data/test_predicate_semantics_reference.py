"""Tests for the Predicate AST evaluator reference."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.predicate_semantics_reference import (
    PredicateContext,
    UnsupportedPredicate,
    evaluate_predicate,
)


def context() -> PredicateContext:
    return PredicateContext(
        resolve_target=lambda alias: {
            "Caster": ("p1",),
            "ModifierOwnerEntity": ("p1",),
            "AllEnemy": ("e1", "e2"),
            "AllEnemyWithUnSelectable": ("e1", "e2", "e4"),
            "AllTeamMember": ("p1", "p2", "p3"),
            "ParamEntity": ("e1",),
        }.get(alias, ()),
        dynamic_get=lambda _scope, key: {"Layer": Decimal("2"), "Chance": Decimal("0.5")}.get(key, Decimal("0")),
        has_modifier=lambda entity, name, added_or_alive, caster_matches: entity == "p1" and name == "M_X",
        has_behavior_flag=lambda entity, flag: entity == "p1" and flag == "Break",
        entity_team=lambda entity: {"p1": "light", "e1": "dark", "e2": "dark", "e4": "dark"}.get(entity, "neutral"),
        entity_alive=lambda entity: entity != "e4",
        entity_character_id=lambda entity: {"p1": 1412, "e1": 99}.get(entity),
        random_01=lambda: Decimal("0.25"),
        wave_count=1,
        challenge_left=2,
        current_hp=Decimal("50"),
        current_max_hp=Decimal("100"),
    )


class PredicateReferenceTest(unittest.TestCase):
    def test_boolean_composition(self) -> None:
        ctx = context()
        and_payload = {"$type": "RPG.GameCore.ByAnd", "PredicateList": [
            {"$type": "RPG.GameCore.ByTargetTeam", "Team": "TeamDark", "TargetType": {"$type": "RPG.GameCore.TargetAlias", "Alias": "ParamEntity"}},
            {"$type": "RPG.GameCore.ByRandomChance", "Chance": {"IsDynamic": False, "FixedValue": {"Value": 0.75}}},
        ]}
        self.assertTrue(evaluate_predicate(and_payload, ctx))
        not_payload = {"$type": "RPG.GameCore.ByNot", "Predicate": {"$type": "RPG.GameCore.ByTargetTeam", "Team": "TeamLight", "TargetType": {"$type": "RPG.GameCore.TargetAlias", "Alias": "Caster"}}}
        self.assertFalse(evaluate_predicate(not_payload, ctx))

    def test_dynamic_and_modifier_predicates(self) -> None:
        ctx = context()
        dynamic = {"$type": "RPG.GameCore.ByCompareDynamicValue", "CompareType": "GreaterEqual", "CompareValue": {"IsDynamic": False, "FixedValue": {"Value": 2}}, "DynamicKey": {"Value": "Layer"}}
        self.assertTrue(evaluate_predicate(dynamic, ctx))
        modifier = {"$type": "RPG.GameCore.ByIsContainModifier", "AddedOrAlive": True, "ModifierName": {"Value": "M_X"}, "TargetType": {"$type": "RPG.GameCore.TargetAlias", "Alias": "ModifierOwnerEntity"}}
        self.assertTrue(evaluate_predicate(modifier, ctx))
        flag = {"$type": "RPG.GameCore.ByContainBehaviorFlag", "Flag": "Break"}
        self.assertTrue(evaluate_predicate(flag, ctx))

    def test_target_and_hp_predicates(self) -> None:
        ctx = context()
        self.assertTrue(evaluate_predicate({"$type": "RPG.GameCore.ByHaveEnemyAlive"}, ctx))
        self.assertFalse(evaluate_predicate({"$type": "RPG.GameCore.ByHaveEnemyAlive", "Inverse": True}, ctx))
        self.assertTrue(evaluate_predicate({"$type": "RPG.GameCore.ByCompareHP", "CompareType": "Greater", "CompareValue": {"IsDynamic": False, "FixedValue": {"Value": 0}}}, ctx))
        self.assertTrue(evaluate_predicate({"$type": "RPG.GameCore.ByCompareHPRatio", "CompareType": "LessEqual", "CompareValue": {"IsDynamic": False, "FixedValue": {"Value": 0.75}}}, ctx))

    def test_unsupported_predicate_rejects(self) -> None:
        with self.assertRaises(UnsupportedPredicate):
            evaluate_predicate({"$type": "RPG.GameCore.ByHasStanceWeak", "WeakType": {"DamageType": "Fire"}}, context())


if __name__ == "__main__":
    unittest.main()
