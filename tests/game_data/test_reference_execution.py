"""Executable-reference bridge tests using real canonical behavior records."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler
from hsr_battle_agent.game_data.damage_survival_reference import SurvivalState
from hsr_battle_agent.game_data.damage_survival_reference import DamageMultiplierContext
from hsr_battle_agent.game_data.dynamic_value_reference import DynamicValueStore
from hsr_battle_agent.game_data.modifier_catalog import ModifierDefinition, modifier_catalog_from_corpus
from hsr_battle_agent.game_data.modifier_lifecycle_reference import ModifierInstance, ModifierState
from hsr_battle_agent.game_data.reference_execution import (
    ExecutionContext,
    ReferenceBattleState,
    RuntimeEntity,
    SemanticExecutor,
    TeamSkillPointState,
    ToughnessCommitContext,
)
from hsr_battle_agent.game_data.toughness_break_reference import ToughnessState


CORPUS_PATH = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
HOT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json:GlobalModifiers:MAvatar_Natasha_00_HOT_HPByMaxHP"
PROPERTY_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json:MCommon_AttackRatioUp"
BLACK_SWAN_SKILL02_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_Skill02_Phase02"
BLACK_SWAN_DOT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT"
WEAKNESS_FIRE_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_WeakType_Fire"
HOT_SP_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_HOT_SP"
BLEED_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Element_Bleed"
STAGE_ADD_DAMAGE_ID = "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3001213"


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

    def test_modifier_layer_dynamic_projection_uses_explicit_layer_not_count(self) -> None:
        record = {
            "behavior_id": "modifier-layer-fixture", "owner_kind": "Modifier", "owner_ref": "modifier-layer-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "read-layer", "source_type": "RPG.GameCore.SetDynamicValueByModifierValue", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"ContextScope": "ContextModifier", "DynamicKey": "MDF_Layer", "ReadTargetType": {"Alias": "ModifierOwnerEntity"}, "ValueType": "Layer", "Multiplier": {"IsDynamic": False, "FixedValue": {"Value": 2}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        modifier = ModifierInstance("e1:layer:1", "MFixture", "Replace", 7, "e1", None, 99, ModifierState.ALIVE, layer=3)
        state = ReferenceBattleState(
            entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            modifier_instances={"e1": (modifier,)},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTACK", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="e1", modifier_id="MFixture", modifier_instance_id="e1:layer:1"),
        )
        self.assertEqual(result.state.dynamic_store.read("e1", "MDF_Layer"), Decimal("6"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_MODIFIER_LAYER")

    def test_modifier_owner_max_hp_dynamic_projection_reads_immutable_survival_state(self) -> None:
        record = {
            "behavior_id": "max-hp-fixture", "owner_kind": "Modifier", "owner_ref": "max-hp-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONCREATE", "operations": [{
                "operation_id": "read-max-hp", "source_type": "RPG.GameCore.SetDynamicValueByProperty", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": "MDF_TargetMaxHP", "ReadTargetType": {"Alias": "ModifierOwnerEntity"}, "Value": "MaxHP"}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("2"), Decimal("125")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONCREATE", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1"))
        self.assertEqual(result.state.dynamic_store.read("e1", "MDF_TargetMaxHP"), Decimal("125"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_MAX_HP")

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

    def test_add_modifier_evaluates_and_persists_modifier_local_dynamic_values(self) -> None:
        record = {
            "behavior_id": "modifier-dynamic-fixture", "owner_kind": "Avatar", "owner_ref": "modifier-dynamic-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"},
                "arguments": {"ModifierName": {"Value": "MFixture"}, "DynamicValues": {"MDF_Ratio": {"IsDynamic": True, "PostfixExpr": {"DynamicHashes": [123], "FixedValues": [], "OpCodes": "AQAR"}}}}, "children": [],
            }]}],
        }
        catalog = {"MFixture": ModifierDefinition("MFixture", "ReplaceByCaster", "fixture:modifier")}
        compiled = BehaviorCompiler(modifier_catalog=catalog).compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONSTART", state, ExecutionContext(caster_id="p1", caster_runtime_id=7, modifier_catalog=catalog, dynamic_hash_values={"123": "0.25"}))
        self.assertEqual(result.state.modifiers("p1")[0].dynamic_values, {"MDF_Ratio": Decimal("0.25")})
        self.assertEqual(result.trace[0]["dynamic_value_keys"], ["MDF_Ratio"])

    def test_source_backed_stage_callback_adds_modifier_with_local_dynamic_values(self) -> None:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        compiled = BehaviorCompiler(modifier_catalog=modifier_catalog_from_corpus(corpus)).compile_record(_record(STAGE_ADD_DAMAGE_ID))
        event = "MODIFIER_CALLBACK:StageAbility_3001213_Modifier._CallbackList[0]:OnListenCharacterCreate"
        entry = next(item for item in compiled["entrypoints"] if item["event"] == event)
        self.assertTrue(entry["executable_reference"])
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("100"), Decimal("100")))})
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            event,
            state,
            ExecutionContext(caster_id="stage", param_entity_ids=("p1",), modifier_catalog=modifier_catalog_from_corpus(corpus)),
        )
        instance = result.state.modifiers("p1")[0]
        self.assertEqual(instance.name, "MCommon_LevelAllDamageAddedRatio")
        self.assertEqual(instance.dynamic_values, {"MDF_PropertyValue": Decimal("0.35")})
        self.assertEqual([item["disposition"] for item in result.trace], ["BRANCH_SUCCESS", "MODIFIER_APPEND_OR_REFRESH_PENDING"])

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

    def test_dot_damage_request_commits_without_crit_through_shield_then_hp(self) -> None:
        record = {
            "behavior_id": "dot-fixture", "owner_kind": "Modifier", "owner_ref": "dot-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE1", "operations": [{
                "operation_id": "dot", "source_type": "RPG.GameCore.DamageByAttackProperty", "kind": "DAMAGE_REQUEST",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "ModifierOwnerEntity"},
                "arguments": {"AttackProperty": {"AttackType": "DOT", "DamagePercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "DamageType": {"DamageType": "Wind"}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")), attack=Decimal("120")),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("100"), Decimal("100"), shield=Decimal("50"))),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONPHASE1", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="e1", damage_multiplier_contexts={"e1": DamageMultiplierContext(enemy_level=80)}, crit_rate=Decimal("1"), crit_damage=Decimal("99")),
        )
        self.assertEqual(result.state.entity("e1").survival.shield, Decimal("0"))
        self.assertEqual(result.state.entity("e1").survival.hp, Decimal("90"))
        self.assertEqual(result.trace[0]["disposition"], "DOT_DAMAGE_COMMITTED")
        self.assertFalse(result.trace[0]["crit_applied"])

    def test_normal_damage_with_stance_commits_hp_then_toughness(self) -> None:
        record = {
            "behavior_id": "mixed-damage", "owner_kind": "Avatar", "owner_ref": "mixed-damage", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "mixed", "source_type": "RPG.GameCore.TargetDamage", "kind": "DAMAGE_REQUEST",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "AbilityTargetEntity"},
                "arguments": {"AttackProperty": {"AttackType": "Normal", "DamagePercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "DamageType": {"DamageType": "Physical"}, "StanceValue": {"IsDynamic": False, "FixedValue": {"Value": 30}}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")), attack=Decimal("120")),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("500"), Decimal("500")), toughness=ToughnessState(Decimal("50"), Decimal("50")), weaknesses=("Physical",)),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTART", state,
            ExecutionContext(
                caster_id="p1", ability_target_id="e1",
                damage_multiplier_contexts={"e1": DamageMultiplierContext(enemy_level=80)},
                toughness_contexts={"e1": ToughnessCommitContext()},
            ),
        )
        self.assertLess(result.state.entity("e1").survival.hp, Decimal("500"))
        self.assertEqual(result.state.entity("e1").toughness.current_toughness, Decimal("20"))
        self.assertEqual([item["disposition"] for item in result.trace], ["DAMAGE_COMMITTED", "TOUGHNESS_REDUCED"])

    def test_damage_request_with_unknown_state_field_is_not_marked_executable(self) -> None:
        record = {
            "behavior_id": "unsupported-damage", "owner_kind": "Avatar", "owner_ref": "unsupported-damage", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "mixed", "source_type": "RPG.GameCore.TargetDamage", "kind": "DAMAGE_REQUEST",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "AbilityTargetEntity"},
                "arguments": {"AttackProperty": {"AttackType": "Normal", "DamagePercentage": {"IsDynamic": False, "FixedValue": {"Value": 1}}, "SPHitRatio": {"IsDynamic": False, "FixedValue": {"Value": 1}}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        operation = compiled["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertEqual(operation["reference_execution_blocker"], "EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS")

    def test_attach_weakness_uses_shared_entity_state(self) -> None:
        record = {
            "behavior_id": "weakness-fixture", "owner_kind": "Modifier", "owner_ref": "weakness-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "weak", "source_type": "RPG.GameCore.StackWeakness", "kind": "MODIFY_WEAKNESS",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "ModifierOwnerEntity"},
                "arguments": {"OPType": "Attach", "WeakList": ["Fire", "Wind", "Fire"]}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("100"), Decimal("100")), weaknesses=("Physical",))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONSTACK", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1"))
        self.assertEqual(result.state.entity("e1").weaknesses, ("Physical", "Fire", "Wind"))
        self.assertEqual(result.trace[0]["disposition"], "WEAKNESS_ATTACHED")

    def test_source_backed_fire_weakness_callback_executes_through_generic_bridge(self) -> None:
        compiled = BehaviorCompiler().compile_record(_record(WEAKNESS_FIRE_ID))
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("100"), Decimal("100")))},
            dynamic_store=DynamicValueStore.empty().set_value("e1", "MDF_PropertyValue", Decimal("1")).store,
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            "MODIFIER_CALLBACK:MCommon_WeakType_Fire._CallbackList[0]:OnStack",
            state,
            ExecutionContext(caster_id="e1", modifier_owner_id="e1", modifier_id="MCommon_WeakType_Fire", dynamic_hash_values={"2128130574": "0.2"}),
        )
        self.assertEqual(result.state.entity("e1").weaknesses, ("Fire",))
        self.assertEqual(result.state.property_state("e1").read("FireResistanceDelta"), Decimal("-0.2"))
        self.assertEqual(
            [item["disposition"] for item in result.trace],
            ["BRANCH_SUCCESS", "BRANCH_SUCCESS", "PROPERTY_CONTRIBUTION_SET", "HEADLESS_PRESENTATION_OMITTED", "WEAKNESS_ATTACHED"],
        )

    def test_source_backed_hot_sp_callback_commits_shared_team_holder(self) -> None:
        compiled = BehaviorCompiler().compile_record(_record(HOT_SP_ID))
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("100"), Decimal("100")))},
            team_skill_points={"light": TeamSkillPointState(Decimal("4"), Decimal("5"))},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled,
            "MODIFIER_CALLBACK:MCommon_HOT_SP._CallbackList[0]:OnPhase1",
            state,
            ExecutionContext(caster_id="p1", modifier_owner_id="p1", modifier_id="MCommon_HOT_SP", dynamic_hash_values={"-295141034": "2"}),
        )
        self.assertEqual(result.state.team_skill_point_state("light").current, Decimal("5"))
        self.assertEqual(result.trace[0]["disposition"], "TEAM_SP_COMMITTED")
        self.assertEqual(result.trace[0]["committed_delta"], "1")

    def test_team_sp_negative_dynamic_value_does_not_become_a_signed_mutation(self) -> None:
        record = {
            "behavior_id": "team-sp-fixture", "owner_kind": "Modifier", "owner_ref": "team-sp-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE1", "operations": [{
                "operation_id": "sp", "source_type": "RPG.GameCore.ModifySPNew", "kind": "MODIFY_TEAM_SP",
                "semantic_status": "MODELLED", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"},
                "arguments": {"AddValue": {"IsDynamic": False, "FixedValue": {"Value": -2}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            team_skill_points={"light": TeamSkillPointState(Decimal("3"), Decimal("5"))},
        )
        result = SemanticExecutor().execute_entrypoint(compiled, "ONPHASE1", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.team_skill_point_state("light").current, Decimal("3"))
        self.assertEqual(result.trace[0]["committed_delta"], "0")

    def test_source_backed_black_swan_damage_component_executes_with_explicit_context(self) -> None:
        source = _record(BLACK_SWAN_SKILL02_ID)
        # The primary hit has SPHitRatio, whose runtime meaning is not closed.
        # The adjoining hit is otherwise the same selected normal+stance
        # family and has no unmodelled state field.
        damage = source["entrypoints"][0]["operations"][2]
        # The complete Skill02 entrypoint has retarget, chance and action
        # completion operations that remain outside this bridge.  This slice
        # preserves the real canonical operation and provenance while testing
        # only its independently closed DamageRequest component.
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-damage-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_DAMAGE_COMPONENT", "operations": [damage]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")), attack=Decimal("120")),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("500"), Decimal("500")), position=(0, 0)),
            "e2": RuntimeEntity("e2", "dark", SurvivalState(Decimal("500"), Decimal("500")), position=(0, 1), toughness=ToughnessState(Decimal("100"), Decimal("100")), weaknesses=("Wind",)),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_DAMAGE_COMPONENT", state,
            ExecutionContext(
                caster_id="p1", ability_target_id="e1",
                dynamic_hash_values={"-1847083384": "1", "-1315627076": "30"},
                damage_multiplier_contexts={"e2": DamageMultiplierContext(enemy_level=80)},
                toughness_contexts={"e2": ToughnessCommitContext()},
            ),
        )
        self.assertLess(result.state.entity("e2").survival.hp, Decimal("500"))
        self.assertEqual(result.state.entity("e2").toughness.current_toughness, Decimal("70"))
        self.assertEqual([item["disposition"] for item in result.trace], ["DAMAGE_COMMITTED", "TOUGHNESS_REDUCED"])

    def test_source_backed_black_swan_dot_component_executes_without_crit(self) -> None:
        source = _record(BLACK_SWAN_DOT_ID)

        def walk(values):
            for operation in values:
                if operation.get("kind") == "DAMAGE_REQUEST" and operation.get("arguments", {}).get("AttackProperty", {}).get("AttackType") == "DOT":
                    return operation
                for group in operation.get("children", []):
                    found = walk(group.get("operations", []))
                    if found is not None:
                        return found
            return None

        damage = next((walk(entrypoint.get("operations", [])) for entrypoint in source["entrypoints"] if walk(entrypoint.get("operations", [])) is not None), None)
        self.assertIsNotNone(damage)
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-dot-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_DOT_COMPONENT", "operations": [damage]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1000"), Decimal("1000")), attack=Decimal("120")),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("500"), Decimal("500"))),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_DOT_COMPONENT", state,
            ExecutionContext(
                caster_id="p1", modifier_owner_id="e1",
                dynamic_hash_values={"-949914540": "1", "-692968543": "1", "-1865831589": "1"},
                damage_multiplier_contexts={"e1": DamageMultiplierContext(enemy_level=80)},
                crit_rate=Decimal("1"), crit_damage=Decimal("99"),
            ),
        )
        self.assertEqual(result.state.entity("e1").survival.hp, Decimal("380.0"))
        self.assertEqual(result.trace[0]["disposition"], "DOT_DAMAGE_COMMITTED")
        self.assertFalse(result.trace[0]["crit_applied"])

    def test_source_backed_black_swan_modifier_layer_component_executes(self) -> None:
        source = _record(BLACK_SWAN_DOT_ID)
        layer = next(
            operation
            for entrypoint in source["entrypoints"]
            if entrypoint["event"] == "MODIFIER_CALLBACK:MAvatar_BlackSwan_00_DOT._CallbackList[3]:OnCustomEvent"
            for operation in entrypoint["operations"]
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByModifierValue"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-modifier-layer-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_MODIFIER_LAYER_COMPONENT", "operations": [layer]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        modifier = ModifierInstance("e1:dot:1", "MAvatar_BlackSwan_00_DOT", "Replace", 7, "e1", None, 99, ModifierState.ALIVE, layer=3)
        state = ReferenceBattleState(
            entities={
                "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
                "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("500"), Decimal("500"))),
            },
            modifier_instances={"e1": (modifier,)},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_MODIFIER_LAYER_COMPONENT", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="e1", modifier_id="MAvatar_BlackSwan_00_DOT", modifier_instance_id="e1:dot:1"),
        )
        self.assertEqual(result.state.dynamic_store.read("e1", "Dot_Layer_Count"), Decimal("3"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_MODIFIER_LAYER")

    def test_source_backed_bleed_max_hp_component_executes(self) -> None:
        source = _record(BLEED_ID)
        max_hp = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in entrypoint["operations"]
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByProperty"
            and operation["arguments"].get("Value") == "MaxHP"
            and operation["arguments"].get("ReadTargetType", {}).get("Alias") == "ModifierOwnerEntity"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-max-hp-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_MAX_HP_COMPONENT", "operations": [max_hp]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("500"), Decimal("750")))})
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_MAX_HP_COMPONENT", state,
            ExecutionContext(caster_id="e1", modifier_owner_id="e1"),
        )
        self.assertEqual(result.state.dynamic_store.read("e1", "MDF_TargetMaxHP"), Decimal("750"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_MAX_HP")

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
