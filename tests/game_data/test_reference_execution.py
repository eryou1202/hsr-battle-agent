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
from hsr_battle_agent.game_data.scheduler_semantics_reference import ActionDelayState, OrdinaryTurnTimeline, TaskState, TaskStep
from hsr_battle_agent.game_data.toughness_break_reference import ToughnessState


CORPUS_PATH = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
HOT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json:GlobalModifiers:MAvatar_Natasha_00_HOT_HPByMaxHP"
PROPERTY_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json:MCommon_AttackRatioUp"
BLACK_SWAN_SKILL02_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_Skill02_Phase02"
BLACK_SWAN_SKILL01_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_Skill01_Phase02"
BLACK_SWAN_DOT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT"
WEAKNESS_FIRE_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_WeakType_Fire"
HOT_SP_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_HOT_SP"
BLEED_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Element_Bleed"
STAGE_ADD_DAMAGE_ID = "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3001213"
WINDFURY_SKILL_NO_NEED_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Windfury_SkillNoNeed"
BLACK_SWAN_DOT_FLAG_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:M_BlackSwan_DOTFlag"
BLACK_SWAN_DOT_FLAG_PARENT_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT"
MIND_CONTROL_DAMAGE_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_MindControl_Damage"
DOT_TEAR_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_DOT_Tear"
WINDFURY_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Windfury"
STAGE_DELAY_ID = "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:BattleEventAbility_900100"
AML_MINION_SKILL01_ID = "external:TurnBasedGameData:Config/ConfigAbility/Monster/Monster_AML_Minion01_00_Ability.json:Monster_AML_Minion01_00_Skill01_Phase02"
MODIFY_DELAY_TURN_END_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_ModifyActionDelayOnTurnEnd"
BLACK_SWAN_MAZE_ID = "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_SkillMazeInLevel"
SET_DELAY_TURN_END_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_SetActionDelayOnTurnEnd"
MIND_CONTROL_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_MindControl"
ONE_MORE_PER_TURN_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MoreOneMorePerTurn"
ONE_MORE_PER_TURN_4_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MoreOneMorePerTurn_4"
ONE_MORE_PER_TURN_5_ID = "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MoreOneMorePerTurn_5"


def _record(behavior_id: str) -> dict:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return next(record for record in corpus["records"] if record["behavior_id"] == behavior_id)


def _walk_operations(operations):
    for operation in operations:
        yield operation
        for group in operation.get("children", []):
            yield from _walk_operations(group.get("operations", []))


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

    def test_param_entity_attack_dynamic_projection_reads_selected_runtime_attack(self) -> None:
        record = {
            "behavior_id": "attack-read-fixture", "owner_kind": "Modifier", "owner_ref": "attack-read-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONCREATE", "operations": [{
                "operation_id": "read-attack", "source_type": "RPG.GameCore.SetDynamicValueByProperty", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": "ATK_Avatar", "ReadTargetType": {"Alias": "ParamEntity2"}, "Value": "Attack"}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
            "e2": RuntimeEntity("e2", "dark", SurvivalState(Decimal("1"), Decimal("1")), attack=Decimal("321")),
        })
        result = SemanticExecutor().execute_entrypoint(compiled, "ONCREATE", state, ExecutionContext(caster_id="p1", param_entity2_ids=("e2",)))
        self.assertEqual(result.state.dynamic_store.read("p1", "ATK_Avatar"), Decimal("321"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_ENTITY_ATTACK")

    def test_snapshot_property_entity_attack_projection_requires_explicit_snapshot_context(self) -> None:
        record = {
            "behavior_id": "snapshot-attack-read-fixture", "owner_kind": "Modifier", "owner_ref": "snapshot-attack-read-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONCREATE", "operations": [{
                "operation_id": "read-snapshot-attack", "source_type": "RPG.GameCore.SetDynamicValueByProperty", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": "MDF_CasterAttack", "ReadTargetType": {"Alias": "SnapshotPropertyEntity"}, "Value": "Attack"}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
            "snapshot": RuntimeEntity("snapshot", "dark", SurvivalState(Decimal("1"), Decimal("1")), attack=Decimal("789")),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONCREATE", state,
            ExecutionContext(caster_id="p1", snapshot_property_entity_id="snapshot"),
        )
        self.assertEqual(result.state.dynamic_store.read("p1", "MDF_CasterAttack"), Decimal("789"))
        self.assertEqual(result.trace[0]["read_target_alias"], "SnapshotPropertyEntity")

    def test_break_damage_added_ratio_projection_reads_only_explicit_caster_or_snapshot(self) -> None:
        record = {
            "behavior_id": "break-damage-read-fixture", "owner_kind": "Modifier", "owner_ref": "break-damage-read-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONCREATE", "operations": [{
                "operation_id": "read-break", "source_type": "RPG.GameCore.SetDynamicValueByProperty", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": "MDF_Break", "ReadTargetType": {"Alias": "SnapshotPropertyEntity"}, "Value": "BreakDamageAddedRatio"}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")), break_damage_added_ratio=Decimal("0.1")),
            "snapshot": RuntimeEntity("snapshot", "dark", SurvivalState(Decimal("1"), Decimal("1")), break_damage_added_ratio=Decimal("0.44")),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONCREATE", state,
            ExecutionContext(caster_id="p1", snapshot_property_entity_id="snapshot"),
        )
        self.assertEqual(result.state.dynamic_store.read("p1", "MDF_Break"), Decimal("0.44"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_BREAK_DAMAGE_ADDED_RATIO")

    def test_status_probability_base_projection_reads_only_materialized_caster_leaf(self) -> None:
        record = {
            "behavior_id": "status-probability-read-fixture", "owner_kind": "Modifier", "owner_ref": "status-probability-read-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONCREATE", "operations": [{
                "operation_id": "read-status", "source_type": "RPG.GameCore.SetDynamicValueByProperty", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": "CasterStatusProbability", "ReadTargetType": {"Alias": "Caster"}, "Value": "StatusProbabilityBase"}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")), status_probability_base=Decimal("0.36"))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONCREATE", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.dynamic_store.read("p1", "CasterStatusProbability"), Decimal("0.36"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_STATUS_PROBABILITY_BASE")

    def test_targetless_own_modifier_layer_projection_requires_live_callback_instance(self) -> None:
        record = {
            "behavior_id": "own-layer-read-fixture", "owner_kind": "Modifier", "owner_ref": "own-layer-read-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "read-layer", "source_type": "RPG.GameCore.SetDynamicValueByModifierValue", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": "MDF_Layer", "ValueType": "Layer", "Multiplier": {"IsDynamic": False, "FixedValue": {"Value": 2}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        own = ModifierInstance("p1:windfury:1", "MCommon_Windfury", "Replace", 7, "p1", None, None, ModifierState.ALIVE, layer=3)
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"p1": (own,)})
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTACK", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="p1", modifier_id="MCommon_Windfury", modifier_instance_id="p1:windfury:1"),
        )
        self.assertEqual(result.state.dynamic_store.read("p1", "MDF_Layer"), Decimal("6"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_OWN_MODIFIER_LAYER")

    def test_fixed_action_delay_commits_per_resolved_target_and_clamps(self) -> None:
        record = {
            "behavior_id": "delay-fixture", "owner_kind": "StageBuff", "owner_ref": "delay-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE", "operations": [{
                "operation_id": "delay", "source_type": "RPG.GameCore.ModifyActionDelay", "kind": "DELAY_ACTION",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "AllDarkTeam"},
                "arguments": {"AddNormalizedValue": {"IsDynamic": False, "FixedValue": {"Value": -1}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={
                "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
                "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1"))),
                "e2": RuntimeEntity("e2", "dark", SurvivalState(Decimal("1"), Decimal("1"))),
            },
            action_delays={"e1": ActionDelayState(Decimal("0.25")), "e2": ActionDelayState(Decimal("2"))},
        )
        result = SemanticExecutor().execute_entrypoint(compiled, "ONPHASE", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.action_delay_state("e1").normalized_value, Decimal("0"))
        self.assertEqual(result.state.action_delay_state("e2").normalized_value, Decimal("1"))
        self.assertEqual([item["disposition"] for item in result.trace], ["ACTION_DELAY_MODIFIED", "ACTION_DELAY_MODIFIED"])

    def test_dynamic_action_delay_uses_unified_dynamic_hash_context(self) -> None:
        record = {
            "behavior_id": "dynamic-delay-fixture", "owner_kind": "Modifier", "owner_ref": "dynamic-delay-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "delay", "source_type": "RPG.GameCore.ModifyActionDelay", "kind": "DELAY_ACTION",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT",
                "target": {"Alias": "ModifierOwnerEntity"},
                "arguments": {"AddNormalizedValue": {"IsDynamic": True, "PostfixExpr": {"DynamicHashes": [7], "FixedValues": [], "OpCodes": "AQAR"}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_delays={"e1": ActionDelayState(Decimal("0.3"))},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTACK", state,
            ExecutionContext(caster_id="e1", modifier_owner_id="e1", dynamic_hash_values={"7": "-0.2"}),
        )
        self.assertEqual(result.state.action_delay_state("e1").normalized_value, Decimal("0.1"))
        self.assertEqual(result.trace[0]["disposition"], "ACTION_DELAY_MODIFIED")

    def test_dynamic_action_delay_rejects_missing_dynamic_hash(self) -> None:
        record = {
            "behavior_id": "dynamic-delay-fixture", "owner_kind": "Modifier", "owner_ref": "dynamic-delay-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTACK", "operations": [{
                "operation_id": "delay", "source_type": "RPG.GameCore.ModifyActionDelay", "kind": "DELAY_ACTION",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT",
                "target": {"Alias": "ModifierOwnerEntity"},
                "arguments": {"AddNormalizedValue": {"IsDynamic": True, "PostfixExpr": {"DynamicHashes": [7], "FixedValues": [], "OpCodes": "AQAR"}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))})
        with self.assertRaisesRegex(Exception, "DynamicHash 7"):
            SemanticExecutor().execute_entrypoint(compiled, "ONSTACK", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1"))

    def test_skill_perform_finish_marks_explicit_executing_action_task_success(self) -> None:
        record = {
            "behavior_id": "skill-finish-fixture", "owner_kind": "Avatar", "owner_ref": "skill-finish-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "finish", "source_type": "RPG.GameCore.SkillPerformFinish", "kind": "ACTION_COMPLETION_MARKER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:p1:1": TaskStep("skill:p1:1", TaskState.EXECUTING, "p1")},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTART", state, ExecutionContext(caster_id="p1", action_task_id="skill:p1:1"),
        )
        self.assertEqual(result.state.action_task("skill:p1:1").state, TaskState.SUCCESS)
        self.assertEqual(result.state.action_task("skill:p1:1").owner_id, "p1")
        self.assertEqual(result.trace[0]["disposition"], "ACTION_COMPLETION_MARKED_SUCCESS")

    def test_ordinary_completion_composes_success_marker_with_av_recharge_without_special_arbitration(self) -> None:
        state = ReferenceBattleState(
            entities={
                "p1105": RuntimeEntity("p1105", "light", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100")),
                "p1307": RuntimeEntity("p1307", "light", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100")),
                "m4014030": RuntimeEntity("m4014030", "dark", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100")),
            },
            action_tasks={"skill:p1105:1": TaskStep("skill:p1105:1", TaskState.SUCCESS, "p1105")},
            ordinary_turn_timeline=OrdinaryTurnTimeline(
                action_order=("p1105", "p1307", "m4014030"),
                remaining_delays={"p1105": Decimal("0"), "p1307": Decimal("20"), "m4014030": Decimal("30")},
                current_actor_id="p1105",
                turn_index=1,
            ),
        )
        result = SemanticExecutor().advance_ordinary_after_completed_action(
            state,
            ExecutionContext(caster_id="p1105", action_task_id="skill:p1105:1"),
        )
        timeline = result.state.ordinary_turn_timeline
        self.assertIsNotNone(timeline)
        assert timeline is not None
        self.assertEqual(timeline.current_actor_id, "p1307")
        self.assertEqual(timeline.remaining_delays, {"p1307": Decimal("0"), "m4014030": Decimal("10"), "p1105": Decimal("80")})
        self.assertEqual(result.trace[0]["disposition"], "ORDINARY_ACTION_RECHARGED_AND_NEXT_SELECTED")
        self.assertEqual(result.trace[0]["eligible_entity_ids"], ["p1105", "p1307", "m4014030"])
        self.assertEqual(result.trace[0]["pending_inserted_actions_ignored"], 0)

    def test_ordinary_completion_rejects_unfinished_action_task_and_derives_alive_ordinary_domain(self) -> None:
        alive = RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100"))
        dead = RuntimeEntity("e1", "dark", SurvivalState(Decimal("0"), Decimal("1"), alive=False), speed=Decimal("100"))
        special = RuntimeEntity("special", "dark", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100"), ordinary_action_eligible=False)
        state = ReferenceBattleState(
            entities={"p1": alive, "e1": dead, "special": special},
            action_tasks={"skill:p1:1": TaskStep("skill:p1:1", TaskState.EXECUTING, "p1")},
            ordinary_turn_timeline=OrdinaryTurnTimeline(
                action_order=("p1", "e1", "special"),
                remaining_delays={"p1": Decimal("0"), "e1": Decimal("10"), "special": Decimal("5")},
                current_actor_id="p1",
            ),
        )
        executor = SemanticExecutor()
        context = ExecutionContext(caster_id="p1", action_task_id="skill:p1:1")
        with self.assertRaisesRegex(Exception, "SUCCESS action task"):
            executor.advance_ordinary_after_completed_action(state, context)
        completed = ReferenceBattleState(
            entities=state.entities,
            action_tasks={"skill:p1:1": TaskStep("skill:p1:1", TaskState.SUCCESS, "p1")},
            ordinary_turn_timeline=state.ordinary_turn_timeline,
        )
        result = executor.advance_ordinary_after_completed_action(completed, context)
        self.assertEqual(result.trace[0]["eligible_entity_ids"], ["p1"])
        self.assertEqual(result.state.ordinary_turn_timeline.current_actor_id, "p1")

    def test_scheduler_candidate_state_exposes_source_backed_pending_insert_without_arbitration(self) -> None:
        source = _record(BLACK_SWAN_MAZE_ID)
        insert = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.TurnInsertAbility"
            and operation["arguments"].get("AbilityName", {}).get("Value") == "Avatar_BlackSwan_00_SkillMazeInLevel_Insert"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:scheduler-candidate-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_INSERT_CANDIDATE_COMPONENT", "operations": [insert]}],
        }
        state = ReferenceBattleState(
            entities={
                "black-swan": RuntimeEntity("black-swan", "light", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100")),
                "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")), speed=Decimal("100")),
            },
            ordinary_turn_timeline=OrdinaryTurnTimeline(
                action_order=("black-swan", "e1"),
                remaining_delays={"black-swan": Decimal("0"), "e1": Decimal("15")},
            ),
        )
        queued = SemanticExecutor().execute_entrypoint(
            BehaviorCompiler().compile_record(record), "SOURCE_INSERT_CANDIDATE_COMPONENT", state, ExecutionContext(caster_id="black-swan"),
        )
        candidates = SemanticExecutor().scheduler_candidate_state(queued.state)
        self.assertEqual(candidates.ordinary_candidate_ids, ("black-swan", "e1"))
        self.assertEqual(len(candidates.pending_inserted_actions), 1)
        self.assertEqual(candidates.pending_inserted_actions[0].spec.insert_priority, "AvatarBuffSelf")
        self.assertEqual(candidates.arbitration_status, "UNRESOLVED_PENDING_INSERT_ACTION_ARBITRATION")

    def test_skill_perform_finish_rejects_missing_or_nonexecuting_task(self) -> None:
        record = {
            "behavior_id": "skill-finish-fixture", "owner_kind": "Avatar", "owner_ref": "skill-finish-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "finish", "source_type": "RPG.GameCore.SkillPerformFinish", "kind": "ACTION_COMPLETION_MARKER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        state = ReferenceBattleState(
            entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:p1:1": TaskStep("skill:p1:1", TaskState.READY, "p1")},
        )
        with self.assertRaisesRegex(Exception, "action_task_id"):
            SemanticExecutor().execute_entrypoint(compiled, "ONSTART", state, ExecutionContext(caster_id="p1"))
        with self.assertRaisesRegex(Exception, "EXECUTING"):
            SemanticExecutor().execute_entrypoint(
                compiled, "ONSTART", state, ExecutionContext(caster_id="p1", action_task_id="skill:p1:1"),
            )

    def test_source_backed_black_swan_skill_finish_component_executes(self) -> None:
        source = _record(BLACK_SWAN_SKILL01_ID)
        finish = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SkillPerformFinish"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-skill-finish-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_SKILL_FINISH_COMPONENT", "operations": [finish]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"black-swan": RuntimeEntity("black-swan", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:black-swan:1": TaskStep("skill:black-swan:1", TaskState.EXECUTING, "black-swan")},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_SKILL_FINISH_COMPONENT", state,
            ExecutionContext(caster_id="black-swan", action_task_id="skill:black-swan:1"),
        )
        self.assertEqual(result.state.action_task("skill:black-swan:1").state, TaskState.SUCCESS)
        self.assertEqual(result.trace[0]["disposition"], "ACTION_COMPLETION_MARKED_SUCCESS")

    def test_damage_perform_finish_marks_separate_executing_damage_task_success(self) -> None:
        record = {
            "behavior_id": "damage-finish-fixture", "owner_kind": "Avatar", "owner_ref": "damage-finish-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "finish", "source_type": "RPG.GameCore.DamagePerformFinish", "kind": "DAMAGE_COMPLETION_MARKER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:p1:1": TaskStep("skill:p1:1", TaskState.EXECUTING, "p1")},
            damage_tasks={"damage:p1:1": TaskStep("damage:p1:1", TaskState.EXECUTING, "p1")},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTART", state, ExecutionContext(caster_id="p1", damage_task_id="damage:p1:1"),
        )
        self.assertEqual(result.state.damage_task("damage:p1:1").state, TaskState.SUCCESS)
        self.assertEqual(result.state.action_task("skill:p1:1").state, TaskState.EXECUTING)
        self.assertEqual(result.trace[0]["disposition"], "DAMAGE_COMPLETION_MARKED_SUCCESS")

    def test_skill_execution_start_marks_explicit_ready_action_task_executing(self) -> None:
        record = {
            "behavior_id": "skill-start-fixture", "owner_kind": "Monster", "owner_ref": "skill-start-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "start", "source_type": "RPG.GameCore.SkillExecutionStart", "kind": "ACTION_START_MARKER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"m1": RuntimeEntity("m1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:m1:1": TaskStep("skill:m1:1", TaskState.READY, "m1")},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "ONSTART", state, ExecutionContext(caster_id="m1", action_task_id="skill:m1:1"),
        )
        self.assertEqual(result.state.action_task("skill:m1:1").state, TaskState.EXECUTING)
        self.assertEqual(result.trace[0]["disposition"], "ACTION_MARKED_EXECUTING")

    def test_skill_execution_start_rejects_missing_or_nonready_action_task(self) -> None:
        record = {
            "behavior_id": "skill-start-fixture", "owner_kind": "Monster", "owner_ref": "skill-start-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "start", "source_type": "RPG.GameCore.SkillExecutionStart", "kind": "ACTION_START_MARKER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        state = ReferenceBattleState(
            entities={"m1": RuntimeEntity("m1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:m1:1": TaskStep("skill:m1:1", TaskState.EXECUTING, "m1")},
        )
        with self.assertRaisesRegex(Exception, "action_task_id"):
            SemanticExecutor().execute_entrypoint(compiled, "ONSTART", state, ExecutionContext(caster_id="m1"))
        with self.assertRaisesRegex(Exception, "READY"):
            SemanticExecutor().execute_entrypoint(
                compiled, "ONSTART", state, ExecutionContext(caster_id="m1", action_task_id="skill:m1:1"),
            )

    def test_damage_perform_finish_rejects_missing_or_nonexecuting_damage_task(self) -> None:
        record = {
            "behavior_id": "damage-finish-fixture", "owner_kind": "Avatar", "owner_ref": "damage-finish-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONSTART", "operations": [{
                "operation_id": "finish", "source_type": "RPG.GameCore.DamagePerformFinish", "kind": "DAMAGE_COMPLETION_MARKER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        state = ReferenceBattleState(
            entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            damage_tasks={"damage:p1:1": TaskStep("damage:p1:1", TaskState.READY, "p1")},
        )
        with self.assertRaisesRegex(Exception, "damage_task_id"):
            SemanticExecutor().execute_entrypoint(compiled, "ONSTART", state, ExecutionContext(caster_id="p1"))
        with self.assertRaisesRegex(Exception, "EXECUTING"):
            SemanticExecutor().execute_entrypoint(
                compiled, "ONSTART", state, ExecutionContext(caster_id="p1", damage_task_id="damage:p1:1"),
            )

    def test_source_backed_black_swan_damage_finish_component_executes(self) -> None:
        source = _record(BLACK_SWAN_SKILL01_ID)
        finish = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.DamagePerformFinish"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-damage-finish-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_DAMAGE_FINISH_COMPONENT", "operations": [finish]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"black-swan": RuntimeEntity("black-swan", "light", SurvivalState(Decimal("1"), Decimal("1")))},
            damage_tasks={"damage:black-swan:1": TaskStep("damage:black-swan:1", TaskState.EXECUTING, "black-swan")},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_DAMAGE_FINISH_COMPONENT", state,
            ExecutionContext(caster_id="black-swan", damage_task_id="damage:black-swan:1"),
        )
        self.assertEqual(result.state.damage_task("damage:black-swan:1").state, TaskState.SUCCESS)
        self.assertEqual(result.trace[0]["disposition"], "DAMAGE_COMPLETION_MARKED_SUCCESS")

    def test_source_backed_monster_skill_execution_start_component_executes(self) -> None:
        source = _record(AML_MINION_SKILL01_ID)
        start = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SkillExecutionStart"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-skill-start-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_SKILL_START_COMPONENT", "operations": [start]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"minion": RuntimeEntity("minion", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_tasks={"skill:minion:1": TaskStep("skill:minion:1", TaskState.READY, "minion")},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_SKILL_START_COMPONENT", state,
            ExecutionContext(caster_id="minion", action_task_id="skill:minion:1"),
        )
        self.assertEqual(result.state.action_task("skill:minion:1").state, TaskState.EXECUTING)
        self.assertEqual(result.trace[0]["disposition"], "ACTION_MARKED_EXECUTING")

    def test_set_modifier_dynamic_value_overwrites_unique_alive_modifier_local_value(self) -> None:
        record = {
            "behavior_id": "modifier-local-write-fixture", "owner_kind": "Modifier", "owner_ref": "modifier-local-write-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE", "operations": [{
                "operation_id": "write", "source_type": "RPG.GameCore.SetModifierDynamicValue", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": {"Value": "MDF_Count"}, "ModifierName": {"Value": "MFixture"}, "NewValue": {"IsDynamic": False, "FixedValue": {"Value": 4}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        existing = ModifierInstance("e1:fixture:1", "MFixture", "Replace", 7, "e1", None, None, ModifierState.ALIVE, dynamic_values={"MDF_Count": Decimal("1"), "MDF_Keep": Decimal("2")})
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"e1": (existing,)})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONPHASE", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1"))
        self.assertEqual(result.state.modifiers("e1")[0].dynamic_values, {"MDF_Count": Decimal("4"), "MDF_Keep": Decimal("2")})
        self.assertEqual(result.trace[0]["disposition"], "MODIFIER_LOCAL_DYNAMIC_VALUE_SET")

    def test_set_modifier_dynamic_value_rejects_missing_or_non_alive_named_instance(self) -> None:
        record = {
            "behavior_id": "modifier-local-write-fixture", "owner_kind": "Modifier", "owner_ref": "modifier-local-write-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE", "operations": [{
                "operation_id": "write", "source_type": "RPG.GameCore.SetModifierDynamicValue", "kind": "SET_DYNAMIC_VALUE",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None,
                "arguments": {"DynamicKey": {"Value": "MDF_Count"}, "ModifierName": {"Value": "MFixture"}, "NewValue": {"IsDynamic": False, "FixedValue": {"Value": 4}}}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        pending = ModifierInstance("e1:fixture:1", "MFixture", "Replace", 7, "e1", None, None, ModifierState.TO_BE_ADDED)
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"e1": (pending,)})
        with self.assertRaisesRegex(Exception, "exactly one ALIVE"):
            SemanticExecutor().execute_entrypoint(compiled, "ONPHASE", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1"))

    def test_remove_self_modifier_marks_callback_instance_for_later_cleanup(self) -> None:
        record = {
            "behavior_id": "remove-self-fixture", "owner_kind": "Modifier", "owner_ref": "remove-self-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE", "operations": [{
                "operation_id": "remove-self", "source_type": "RPG.GameCore.RemoveSelfModifier", "kind": "REMOVE_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": [],
            }]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        own = ModifierInstance("e1:own:1", "MFixture", "Replace", 7, "e1", None, None, ModifierState.ALIVE, callback_registration_keys=("callback",), property_contribution_keys=("property",))
        other = ModifierInstance("e1:other:1", "MFixture", "Replace", 7, "e1", None, None, ModifierState.ALIVE)
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"e1": (own, other)})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONPHASE", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1", modifier_id="MFixture", modifier_instance_id="e1:own:1"))
        self.assertEqual(result.state.modifiers("e1")[0].state, ModifierState.TO_BE_REMOVED)
        self.assertEqual(result.state.modifiers("e1")[0].callback_registration_keys, ("callback",))
        self.assertEqual(result.state.modifiers("e1")[1].state, ModifierState.ALIVE)
        self.assertEqual(result.trace[0]["disposition"], "MODIFIER_SELF_MARKED_FOR_DIRTY_REMOVAL")

    def test_source_backed_black_swan_dot_flag_remove_self_component_executes(self) -> None:
        source = _record(BLACK_SWAN_DOT_FLAG_ID)
        remove = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.RemoveSelfModifier"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-remove-self-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_REMOVE_SELF_COMPONENT", "operations": [remove]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        dot_flag = ModifierInstance("e1:dot-flag:1", "M_BlackSwan_DOTFlag", "Replace", 7, "e1", None, None, ModifierState.ALIVE)
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"e1": (dot_flag,)})
        result = SemanticExecutor().execute_entrypoint(compiled, "SOURCE_REMOVE_SELF_COMPONENT", state, ExecutionContext(caster_id="p1", modifier_owner_id="e1", modifier_id="M_BlackSwan_DOTFlag", modifier_instance_id="e1:dot-flag:1"))
        self.assertEqual(result.state.modifiers("e1")[0].state, ModifierState.TO_BE_REMOVED)
        self.assertEqual(result.trace[0]["disposition"], "MODIFIER_SELF_MARKED_FOR_DIRTY_REMOVAL")

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

    def test_add_modifier_accepts_explicit_false_alive_only_without_extra_filter(self) -> None:
        record = {
            "behavior_id": "modifier-alive-only-false-fixture", "owner_kind": "Modifier", "owner_ref": "modifier-alive-only-false-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE", "operations": [{
                "operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "ModifierOwnerEntity"},
                "arguments": {"ModifierName": {"Value": "MFixture"}, "AliveOnly": False}, "children": [],
            }]}],
        }
        catalog = {"MFixture": ModifierDefinition("MFixture", "Replace", "fixture:modifier")}
        compiled = BehaviorCompiler(modifier_catalog=catalog).compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "ONPHASE", state, ExecutionContext(caster_id="p1", modifier_owner_id="e1", caster_runtime_id=7, modifier_catalog=catalog))
        self.assertEqual(result.state.modifiers("e1")[0].state, ModifierState.TO_BE_ADDED)
        self.assertFalse(result.trace[0]["alive_only"])

    def test_add_modifier_static_lifetime_persists_through_pending_lifecycle(self) -> None:
        record = {
            "behavior_id": "modifier-lifetime-fixture", "owner_kind": "Modifier", "owner_ref": "modifier-lifetime-fixture", "source_refs": [],
            "entrypoints": [{"event": "ONPHASE", "operations": [{
                "operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER",
                "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "ModifierOwnerEntity"},
                "arguments": {"ModifierName": {"Value": "MFixture"}, "LifeTime": {"IsDynamic": False, "FixedValue": {"Value": 2}}}, "children": [],
            }]}],
        }
        catalog = {"MFixture": ModifierDefinition("MFixture", "Merge", "fixture:modifier")}
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(
            BehaviorCompiler(modifier_catalog=catalog).compile_record(record), "ONPHASE", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="e1", caster_runtime_id=7, modifier_catalog=catalog),
        )
        instance = result.state.modifiers("e1")[0]
        self.assertEqual((instance.current_life, instance.state), (2, ModifierState.TO_BE_ADDED))
        self.assertEqual(result.trace[0]["current_life"], 2)

    def test_source_backed_fixed_lifetime_add_modifier_component_executes(self) -> None:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        catalog = modifier_catalog_from_corpus(corpus)
        for behavior_id, expected_lifetime in (
            (ONE_MORE_PER_TURN_ID, 2),
            (ONE_MORE_PER_TURN_4_ID, 3),
            (ONE_MORE_PER_TURN_5_ID, 4),
        ):
            source = _record(behavior_id)
            entrypoint = next(item for item in source["entrypoints"] if item["event"].endswith(":OnPhase1"))
            component = {
                "behavior_id": f"{behavior_id}:fixed-lifetime-add-modifier-component",
                "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
                "entrypoints": [{"event": "SOURCE_FIXED_LIFETIME_ADD_MODIFIER_COMPONENT", "operations": entrypoint["operations"]}],
            }
            state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))})
            compiled = BehaviorCompiler(modifier_catalog=catalog).compile_record(component)
            self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
            result = SemanticExecutor().execute_entrypoint(
                compiled, "SOURCE_FIXED_LIFETIME_ADD_MODIFIER_COMPONENT", state,
                ExecutionContext(caster_id="p1", modifier_owner_id="p1", caster_runtime_id=7, modifier_catalog=catalog),
            )
            instance = result.state.modifiers("p1")[0]
            self.assertEqual((instance.name, instance.current_life, instance.stacking), ("OneMore", expected_lifetime, "Merge"))
            self.assertEqual(result.trace[0]["disposition"], "MODIFIER_APPEND_OR_REFRESH_PENDING")

    def test_source_backed_certain_self_caster_param_lifetime_components_execute(self) -> None:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        catalog = modifier_catalog_from_corpus(corpus)
        cases = (
            (
                "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3999010",
                "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3999010:MODIFIER_CALLBACK:MLevel_WB_StageAbility_3999010_Modifier._CallbackList[0]:OnAfterHit:0",
                "MCommon_DOT_Electric", 3, {"Modifier_Electric_DamagePercentage": Decimal("0.5")}, {},
            ),
            (
                "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3999027",
                "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3999027:MODIFIER_CALLBACK:MLevel_WB_StageAbility_3999027_Modifier_Sub._CallbackList[0]:OnAfterAttack:0/TaskList:0",
                "MCommon_Element_Electric", 1, {"MDF_DamagePercentage": Decimal("0.7")}, {"462955996": "0.7"},
            ),
        )
        for behavior_id, operation_id, name, lifetime, expected_values, dynamic_hash_values in cases:
            source = _record(behavior_id)
            operation = next(
                item for entrypoint in source["entrypoints"] for item in _walk_operations(entrypoint["operations"])
                if item["operation_id"] == operation_id
            )
            component = {
                "behavior_id": f"{behavior_id}:certain-self-caster-param-lifetime-component",
                "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
                "entrypoints": [{"event": "SOURCE_CERTAIN_SELF_CASTER_PARAM_LIFETIME_COMPONENT", "operations": [operation]}],
            }
            state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))})
            result = SemanticExecutor().execute_entrypoint(
                BehaviorCompiler(modifier_catalog=catalog).compile_record(component),
                "SOURCE_CERTAIN_SELF_CASTER_PARAM_LIFETIME_COMPONENT", state,
                ExecutionContext(caster_id="stage", caster_runtime_id=7, param_entity_ids=("e1",), modifier_catalog=catalog, dynamic_hash_values=dynamic_hash_values),
            )
            instance = result.state.modifiers("e1")[0]
            self.assertEqual((instance.name, instance.current_life, instance.stacking), (name, lifetime, "ReplaceByCaster"))
            self.assertEqual((instance.source_provider_id, instance.caster_runtime_id, instance.dynamic_values), ("stage", 7, expected_values))
            self.assertEqual((result.trace[0]["disposition"], result.trace[0]["inherit_caster"]), ("MODIFIER_APPEND_OR_REFRESH_PENDING", "CasterSelf"))

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

    def test_source_backed_black_swan_add_modifier_alive_only_false_component_executes(self) -> None:
        source = _record(BLACK_SWAN_DOT_FLAG_PARENT_ID)
        add = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.AddModifier"
            and operation["arguments"] == {"AliveOnly": False, "ModifierName": {"Value": "M_BlackSwan_00_ForbidEffectFlag"}}
        )
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        catalog = modifier_catalog_from_corpus(corpus)
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-add-alive-only-false-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_ADD_ALIVE_ONLY_FALSE_COMPONENT", "operations": [add]}],
        }
        compiled = BehaviorCompiler(modifier_catalog=catalog).compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))})
        result = SemanticExecutor().execute_entrypoint(compiled, "SOURCE_ADD_ALIVE_ONLY_FALSE_COMPONENT", state, ExecutionContext(caster_id="p1", modifier_owner_id="e1", caster_runtime_id=7, modifier_catalog=catalog))
        self.assertEqual(result.state.modifiers("e1")[0].name, "M_BlackSwan_00_ForbidEffectFlag")
        self.assertFalse(result.trace[0]["alive_only"])

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

    def test_source_backed_mind_control_param_entity_attack_component_executes(self) -> None:
        source = _record(MIND_CONTROL_DAMAGE_ID)
        attack = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByProperty"
            and operation["arguments"].get("Value") == "Attack"
            and operation["arguments"].get("ReadTargetType", {}).get("Alias") == "ParamEntity"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-param-attack-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_PARAM_ATTACK_COMPONENT", "operations": [attack]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")), attack=Decimal("456")),
        })
        result = SemanticExecutor().execute_entrypoint(compiled, "SOURCE_PARAM_ATTACK_COMPONENT", state, ExecutionContext(caster_id="p1", modifier_owner_id="p1", param_entity_ids=("e1",)))
        self.assertEqual(result.state.dynamic_store.read("p1", "ATK_Avatar"), Decimal("456"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_ENTITY_ATTACK")

    def test_source_backed_dot_tear_snapshot_attack_component_executes(self) -> None:
        source = _record(DOT_TEAR_ID)
        attack = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByProperty"
            and operation["arguments"].get("Value") == "Attack"
            and operation["arguments"].get("ReadTargetType", {}).get("Alias") == "SnapshotPropertyEntity"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-snapshot-attack-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_SNAPSHOT_ATTACK_COMPONENT", "operations": [attack]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
            "snapshot": RuntimeEntity("snapshot", "dark", SurvivalState(Decimal("1"), Decimal("1")), attack=Decimal("654")),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_SNAPSHOT_ATTACK_COMPONENT", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="p1", snapshot_property_entity_id="snapshot"),
        )
        self.assertEqual(result.state.dynamic_store.read("p1", "MDF_CasterAttack"), Decimal("654"))
        self.assertEqual(result.trace[0]["read_target_alias"], "SnapshotPropertyEntity")

    def test_source_backed_element_bleed_snapshot_break_damage_component_executes(self) -> None:
        source = _record(BLEED_ID)
        break_ratio = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByProperty"
            and operation["arguments"].get("Value") == "BreakDamageAddedRatio"
            and operation["arguments"].get("ReadTargetType", {}).get("Alias") == "SnapshotPropertyEntity"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-snapshot-break-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_SNAPSHOT_BREAK_COMPONENT", "operations": [break_ratio]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
            "snapshot": RuntimeEntity("snapshot", "dark", SurvivalState(Decimal("1"), Decimal("1")), break_damage_added_ratio=Decimal("0.5")),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_SNAPSHOT_BREAK_COMPONENT", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="p1", snapshot_property_entity_id="snapshot"),
        )
        self.assertEqual(result.state.dynamic_store.read("p1", "_CasterBreakDamageAddedRatio"), Decimal("0.5"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_BREAK_DAMAGE_ADDED_RATIO")

    def test_source_backed_black_swan_status_probability_component_executes(self) -> None:
        source = _record("external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_SkillTree03")
        status_probability = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByProperty"
            and operation["arguments"].get("Value") == "StatusProbabilityBase"
            and operation["arguments"].get("ReadTargetType", {}).get("Alias") == "Caster"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-status-probability-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_STATUS_PROBABILITY_COMPONENT", "operations": [status_probability]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")), status_probability_base=Decimal("0.41"))})
        result = SemanticExecutor().execute_entrypoint(compiled, "SOURCE_STATUS_PROBABILITY_COMPONENT", state, ExecutionContext(caster_id="p1", modifier_owner_id="p1"))
        self.assertEqual(result.state.dynamic_store.read("p1", "CasterStatusProbability"), Decimal("0.41"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_STATUS_PROBABILITY_BASE")

    def test_source_backed_windfury_own_modifier_layer_component_executes(self) -> None:
        source = _record(WINDFURY_ID)
        layer = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetDynamicValueByModifierValue"
            and operation["arguments"].get("ValueType") == "Layer"
            and "ReadTargetType" not in operation["arguments"]
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-own-layer-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_OWN_LAYER_COMPONENT", "operations": [layer]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        own = ModifierInstance("p1:windfury:1", "MCommon_Windfury", "Replace", 7, "p1", None, None, ModifierState.ALIVE, layer=4)
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"p1": (own,)})
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_OWN_LAYER_COMPONENT", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="p1", modifier_id="MCommon_Windfury", modifier_instance_id="p1:windfury:1"),
        )
        self.assertEqual(result.state.dynamic_store.read("p1", "MDF_WindfuryCount"), Decimal("4"))
        self.assertEqual(result.trace[0]["disposition"], "DYNAMIC_VALUE_SET_FROM_OWN_MODIFIER_LAYER")

    def test_source_backed_stage_fixed_action_delay_component_executes(self) -> None:
        source = _record(STAGE_DELAY_ID)
        delay = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.ModifyActionDelay"
            and operation["arguments"].get("AddNormalizedValue", {}).get("IsDynamic") is False
            and operation.get("target", {}).get("Alias") == "AllDarkTeam"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-delay-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_DELAY_COMPONENT", "operations": [delay]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={
                "p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1"))),
                "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1"))),
            },
            action_delays={"e1": ActionDelayState(Decimal("0.4"))},
        )
        result = SemanticExecutor().execute_entrypoint(compiled, "SOURCE_DELAY_COMPONENT", state, ExecutionContext(caster_id="p1"))
        self.assertEqual(result.state.action_delay_state("e1").normalized_value, Decimal("0"))
        self.assertEqual(result.trace[0]["action"], "ADD")

    def test_source_backed_dynamic_action_delay_component_executes(self) -> None:
        source = _record(MODIFY_DELAY_TURN_END_ID)
        delay = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.ModifyActionDelay"
            and operation["arguments"].get("AddNormalizedValue", {}).get("IsDynamic") is True
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-dynamic-delay-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_DYNAMIC_DELAY_COMPONENT", "operations": [delay]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_delays={"e1": ActionDelayState(Decimal("0.5"))},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_DYNAMIC_DELAY_COMPONENT", state,
            ExecutionContext(caster_id="e1", modifier_owner_id="e1", dynamic_hash_values={"1784011670": "0.2"}),
        )
        self.assertEqual(result.state.action_delay_state("e1").normalized_value, Decimal("0.3"))
        self.assertEqual(result.trace[0]["action"], "ADD")

    def test_source_backed_set_action_delay_component_executes(self) -> None:
        source = _record(SET_DELAY_TURN_END_ID)
        delay = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetActionDelay"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-set-delay-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_SET_DELAY_COMPONENT", "operations": [delay]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_delays={"e1": ActionDelayState(Decimal("0.25"))},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_SET_DELAY_COMPONENT", state,
            ExecutionContext(caster_id="e1", modifier_owner_id="e1", dynamic_hash_values={"-1227794911": "0.6"}),
        )
        self.assertEqual(result.state.action_delay_state("e1").normalized_value, Decimal("0.6"))
        self.assertEqual(result.trace[0]["action"], "SET")

    def test_source_backed_reset_action_delay_component_executes(self) -> None:
        source = _record(MIND_CONTROL_ID)
        reset = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.ResetActionDelay"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-reset-delay-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_RESET_DELAY_COMPONENT", "operations": [reset]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(
            entities={"e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1")))},
            action_delays={"e1": ActionDelayState(Decimal("0.6"))},
        )
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_RESET_DELAY_COMPONENT", state, ExecutionContext(caster_id="e1", modifier_owner_id="e1"),
        )
        self.assertEqual(result.state.action_delay_state("e1").normalized_value, Decimal("0"))
        self.assertTrue(result.state.action_delay_state("e1").skip_target_turn)
        self.assertEqual(result.trace[0]["action"], "RESET")

    def test_source_backed_black_swan_insert_ability_component_queues_without_arbitration(self) -> None:
        source = _record(BLACK_SWAN_MAZE_ID)
        insert = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.TurnInsertAbility"
            and operation["arguments"].get("AbilityName", {}).get("Value") == "Avatar_BlackSwan_00_SkillMazeInLevel_Insert"
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-insert-ability-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_INSERT_ABILITY_COMPONENT", "operations": [insert]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        state = ReferenceBattleState(entities={
            "black-swan": RuntimeEntity("black-swan", "light", SurvivalState(Decimal("1"), Decimal("1"))),
            "e1": RuntimeEntity("e1", "dark", SurvivalState(Decimal("1"), Decimal("1"))),
            "e2": RuntimeEntity("e2", "dark", SurvivalState(Decimal("1"), Decimal("1"))),
        })
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_INSERT_ABILITY_COMPONENT", state, ExecutionContext(caster_id="black-swan"),
        )
        self.assertEqual(len(result.state.pending_inserted_actions), 1)
        pending = result.state.pending_inserted_actions[0]
        self.assertEqual(pending.enqueue_index, 0)
        self.assertEqual(pending.owner_id, "black-swan")
        self.assertEqual(pending.spec.ability_name, "Avatar_BlackSwan_00_SkillMazeInLevel_Insert")
        self.assertEqual(pending.spec.insert_priority, "AvatarBuffSelf")
        self.assertEqual(pending.spec.ability_target, {"$type": "RPG.GameCore.TargetAlias", "Alias": "AllEnemy"})
        self.assertEqual(result.trace[0]["disposition"], "ACTION_INSERTED_PENDING")
        self.assertEqual(result.state.action_tasks, {})
        self.assertEqual(result.state.action_delays, {})

    def test_insert_ability_rejects_abort_or_liveness_qualified_shape(self) -> None:
        operation = {
            "operation_id": "insert", "source_type": "RPG.GameCore.TurnInsertAbility", "kind": "INSERT_ACTION",
            "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT",
            "target": {"$type": "RPG.GameCore.TargetAlias", "Alias": "Caster"},
            "arguments": {
                "AbilityName": {"Value": "Skill_Insert"},
                "AbilityTarget": {"$type": "RPG.GameCore.TargetAlias", "Alias": "AllEnemy"},
                "CanRunOnUnselectableTarget": True,
                "InsertAbilityPriority": "AvatarBuffSelf",
                "ShowInActionBar": True,
                "AbortBehaviorFlags": ["STAT_CTRL"],
            },
            "children": [],
        }
        record = {"behavior_id": "insert-reject-fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [operation]}]}
        compiled = BehaviorCompiler().compile_record(record)
        operation_ir = compiled["entrypoints"][0]["operations"][0]
        self.assertEqual(compiled["compile_status"], "COMPILED_STRUCTURE_ONLY")
        self.assertEqual(operation_ir["reference_execution_blocker"], "EXECUTABLE_REFERENCE_INSERT_ACTION_ARGUMENTS_UNSUPPORTED")

    def test_source_backed_windfury_modifier_local_dynamic_value_component_executes(self) -> None:
        source = _record(WINDFURY_SKILL_NO_NEED_ID)
        write = next(
            operation
            for entrypoint in source["entrypoints"]
            for operation in _walk_operations(entrypoint["operations"])
            if operation["source_type"] == "RPG.GameCore.SetModifierDynamicValue"
            and operation["arguments"]["DynamicKey"]["Value"] == "_AssistEnergyNeedOnce"
            and operation["arguments"]["NewValue"]["FixedValue"]["Value"] == 0
        )
        record = {
            "behavior_id": f"{source['behavior_id']}:source-backed-modifier-local-dynamic-component",
            "owner_kind": source["owner_kind"], "owner_ref": source["owner_ref"], "source_refs": source["source_refs"],
            "entrypoints": [{"event": "SOURCE_MODIFIER_LOCAL_DYNAMIC_COMPONENT", "operations": [write]}],
        }
        compiled = BehaviorCompiler().compile_record(record)
        self.assertEqual(compiled["compile_status"], "EXECUTABLE_REFERENCE")
        windfury = ModifierInstance("p1:windfury:1", "MCommon_Windfury", "Replace", 7, "p1", None, None, ModifierState.ALIVE, dynamic_values={"_AssistEnergyNeedOnce": Decimal("1")})
        state = ReferenceBattleState(entities={"p1": RuntimeEntity("p1", "light", SurvivalState(Decimal("1"), Decimal("1")))}, modifier_instances={"p1": (windfury,)})
        result = SemanticExecutor().execute_entrypoint(
            compiled, "SOURCE_MODIFIER_LOCAL_DYNAMIC_COMPONENT", state,
            ExecutionContext(caster_id="p1", modifier_owner_id="p1", modifier_id="MCommon_Windfury"),
        )
        self.assertEqual(result.state.modifiers("p1")[0].dynamic_values["_AssistEnergyNeedOnce"], Decimal("0"))
        self.assertEqual(result.trace[0]["disposition"], "MODIFIER_LOCAL_DYNAMIC_VALUE_SET")

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
