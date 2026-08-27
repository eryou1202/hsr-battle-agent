"""Executable-reference bridge tests using real canonical behavior records."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler
from hsr_battle_agent.game_data.damage_survival_reference import SurvivalState
from hsr_battle_agent.game_data.damage_survival_reference import DamageMultiplierContext
from hsr_battle_agent.game_data.modifier_catalog import ModifierDefinition
from hsr_battle_agent.game_data.modifier_lifecycle_reference import ModifierInstance, ModifierState
from hsr_battle_agent.game_data.reference_execution import (
    ExecutionContext,
    ReferenceBattleState,
    RuntimeEntity,
    SemanticExecutor,
)


CORPUS_PATH = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
HOT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json:GlobalModifiers:MAvatar_Natasha_00_HOT_HPByMaxHP"
PROPERTY_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json:MCommon_AttackRatioUp"


def _record(behavior_id: str) -> dict:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return next(record for record in corpus["records"] if record["behavior_id"] == behavior_id)


class ReferenceExecutionTest(unittest.TestCase):
    def test_natasha_hot_compiles_and_executes_through_generic_bridge(self) -> None:
        compiled = BehaviorCompiler().compile_record(_record(HOT_ID))
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("900"), Decimal("900"))),
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("800"), Decimal("1000"))),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            "MODIFIER_CALLBACK:MAvatar_Natasha_00_HOT_HPByMaxHP._CallbackList[0]:OnPhase1",
            state,
            ExecutionContext(
                caster_id="p1",
                modifier_owner_id="p1",
                modifier_id="MAvatar_Natasha_00_HOT_HPByMaxHP",
                dynamic_hash_values={"1733325153": "0.05", "2136609680": "0"},
            ),
        )
        self.assertEqual(result.state.entity("p1").survival.hp, Decimal("850.00"))
        self.assertEqual([item["disposition"] for item in result.trace], ["BRANCH_SUCCESS", "HEADLESS_PRESENTATION_OMITTED", "HEAL_COMMITTED"])

    def test_real_stack_property_compiles_and_executes_through_generic_bridge(self) -> None:
        compiled = BehaviorCompiler().compile_record(_record(PROPERTY_ID))
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")))})
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            "MODIFIER_CALLBACK:MCommon_AttackRatioUp._CallbackList[0]:OnStack",
            state,
            ExecutionContext(
                caster_id="p1",
                modifier_owner_id="p1",
                modifier_id="MCommon_AttackRatioUp",
                dynamic_hash_values={"2128130574": "0.12"},
            ),
        )
        self.assertEqual(result.state.property_state("p1").read("AttackAddedRatio"), Decimal("0.12"))
        self.assertEqual(result.trace[0]["disposition"], "PROPERTY_CONTRIBUTION_SET")

    def test_dynamic_value_write_uses_shared_store_and_scope_resolution(self) -> None:
        record = {
            "behavior_id": "dynamic-fixture", "owner_kind": "Modifier", "owner_ref": "dynamic-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "set", "source_type": "RPG.GameCore.SetDynamicValue", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"ContextScope": "ContextCaster", "DynamicKey": {"Value": "stacks"},
                              "Value": {"IsDynamic": False, "FixedValue": {"Value": 3}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONSTACK", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.dynamic_store.read("p1", "stacks"), Decimal("3"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET")

    def test_add_modifier_requires_catalog_and_preserves_pending_lifecycle_boundary(self) -> None:
        record = {
            "behavior_id": "modifier-fixture", "owner_kind": "Avatar", "owner_ref": "modifier-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"},
                "arguments": {"ModifierName": {"Value": "MFixture"}}, "children": [],
            }]}],
        }
        catalog = {"MFixture": ModifierDefinition("MFixture", "ReplaceByCaster", "fixture:modifier")}
        compiled = BehaviorCompiler(modifier_catalog=catalog).compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONSTART", state, ExecutionContext(caster_id="p1", caster_runtime_id=7, modifier_catalog=catalog))
        instance = result.state.modifiers("p1")[0]
        self.assertEqual(instance.name, "MFixture")
        self.assertEqual(instance.state, ModifierState.TO_BE_ADDED)
        self.assertEqual(result.trace[0]["disposition"], "MODIFIER_APPEND_OR_REFRESH_PENDING")

    def test_remove_modifier_marks_instances_but_does_not_clean_them_early(self) -> None:
        record = {
            "behavior_id": "remove-fixture", "owner_kind": "Avatar", "owner_ref": "remove-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONEND", "operations": [{
                "operation_id": "remove", "source_type": "RPG.GameCore.RemoveModifier", "kind": "REMOVE_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"},
                "arguments": {"ModifierName": {"Value": "MFixture"}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        pending = ModifierDefinition("MFixture", "Replace", "fixture:modifier")
        original = ModifierInstance("p1:MFixture:1", "MFixture", "Replace", 7, "p1", None, None, ModifierState.ALIVE)
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"p1": (original,)})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONEND", state, ExecutionContext(caster_id="p1", modifier_catalog={"MFixture": pending}))
        self.assertEqual(result.state.modifiers("p1")[0].state, ModifierState.TO_BE_REMOVED)
        self.assertEqual(result.trace[0]["disposition"], "MODIFIER_MARKED_FOR_DIRTY_REMOVAL")

    def test_damage_request_uses_explicit_context_and_commits_shield_before_hp(self) -> None:
        record = {
            "behavior_id": "damage-fixture", "owner_kind": "Avatar", "owner_ref": "damage-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "damage", "source_type": "RPG.GameCore.TargetDamage", "kind": "DAMAGE_REQUEST",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "AbilityTargetEntity"},
                "arguments": {"AttackProperty": {"AttackType": "Normal", "DamagePercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "DamageType": {"DamageType": "Physical"}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")), attack=Decimal("120")),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("100"), Decimal("100"), shield=Decimal("50"))),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTART", state,
            ExecutionContext(caster_id="p1", ability_target_id="e1", damage_multiplier_contexts={"e1": DamageMultiplierContext(enemy_level=80)}),
        )
        self.assertEqual(result.state.entity("e1").survival.shield, Decimal("0"))
        self.assertLess(result.state.entity("e1").survival.hp, Decimal("100"))
        self.assertEqual(result.trace[0]["disposition"], "DAMAGE_COMMITTED")

    def test_mixed_damage_request_is_not_marked_executable(self) -> None:
        record = {
            "behavior_id": "mixed-damage", "owner_kind": "Avatar", "owner_ref": "mixed-damage", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "mixed", "source_type": "RPG.GameCore.TargetDamage", "kind": "DAMAGE_REQUEST",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "AbilityTargetEntity"},
                "arguments": {"AttackProperty": {"AttackType": "Normal", "DamagePercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "StanceValue": {"IsDynamic": False, "FixedValue": {"Value": 30}}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        operation = compiled["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertEqual(operation["reference_execution_blocker"], "EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS")

    def test_unbound_operation_remains_a_hard_execution_error(self) -> None:
        compiled = BehaviorCompiler().compile_record({
            "behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "bad", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "children": [],
            }]}],
        })
        self.assertEqual(compiled["compile_status"], "COMPILED_STRUCTURE_ONLY")
        with self.assertRaisesRegex(Exception, "not compiled"):
            SemanticExecutor().execute_entrypoint(
                compiled, "ONSTART",
                ReferenceBattleState(entities={"p": RuntimeEntity("p", "light", SurvivalState(Decimal("1"), Decimal("1")))}),
                ExecutionContext(caster_id="p"),
            )

    def test_closed_entrypoint_executes_even_when_another_entrypoint_is_structural_only(self) -> None:
        record = {
            "behavior_id": "mixed", "owner_kind": "Modifier", "owner_ref": "mixed", "source_refs": [],
            "entrypoints": [
                {"event": "HEAL", "operations": [{
                    "operation_id": "heal", "source_type": "RPG.GameCore.HealHP", "kind": "HEAL_REQUEST",
                    "semantic_status": "MODELLED", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"},
                    "arguments": {"FormulaType": "HealByHealerMaxHP", "HealPercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "ModifyValue": {"IsDynamic": False, "FixedValue": {"Value": 0}}}, "children": [],
                }]},
                {"event": "UNBOUND", "operations": [{
                    "operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                    "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "arguments": {}, "children": [],
                }]},
            ],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "COMPILED_STRUCTURE_ONLY")
        self.assertTrue(compiled["entrypoints"][0]["executable_reference"])
        self.assertFalse(compiled["entrypoints"][1]["executable_reference"])
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("10")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "HEAL", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.entity("p1").survival.hp, Decimal("10"))


if __name__ == "__main__":
    unittest.main()
