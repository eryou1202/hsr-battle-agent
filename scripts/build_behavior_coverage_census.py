"""Publish the first strict compiler coverage census for the reviewed corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import write_json


parser = argparse.ArgumentParser()
parser.add_argument("--report", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_002.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_coverage_census_002.json"))
parser.add_argument("--corpus", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json"))
arguments = parser.parse_args()
report = json.loads(arguments.report.read_text(encoding="utf-8"))
corpus = json.loads(arguments.corpus.read_text(encoding="utf-8"))
coverage = report["coverage"]
SOURCE_BACKED_EXECUTABLE_BEHAVIORS = {
    "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json:GlobalModifiers:MAvatar_Natasha_00_HOT_HPByMaxHP",
    "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Property.json:MCommon_AttackRatioUp",
    "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_WeakType_Fire",
    "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_HOT_SP",
}
SOURCE_BACKED_EXECUTED_COMPONENTS = (
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_Skill02_Phase02",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_Skill02_Phase02:ONSTART:2",
        "owner_kind": "Avatar",
        "fixture": "source_backed_normal_damage_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3001213",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Level/Level_MazeBuff_Ability.json:StageAbility_3001213:MODIFIER_CALLBACK:StageAbility_3001213_Modifier._CallbackList[0]:OnListenCharacterCreate:0/SuccessTaskList:0",
        "owner_kind": "StageBuff",
        "fixture": "source_backed_modifier_dynamic_entrypoint_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT:MODIFIER_CALLBACK:MAvatar_BlackSwan_00_DOT._CallbackList[1]:OnPhase1:1/SuccessTaskList:6/SuccessTaskList:0/SuccessTaskList:0",
        "owner_kind": "Modifier",
        "fixture": "source_backed_dot_damage_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT:MODIFIER_CALLBACK:MAvatar_BlackSwan_00_DOT._CallbackList[3]:OnCustomEvent:0",
        "owner_kind": "Modifier",
        "fixture": "source_backed_modifier_layer_dynamic_value_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Element_Bleed",
        "operation_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Element_Bleed:MODIFIER_CALLBACK:MCommon_Element_Bleed._CallbackList[0]:OnCreate:1",
        "owner_kind": "Modifier",
        "fixture": "source_backed_max_hp_dynamic_value_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Windfury_SkillNoNeed",
        "operation_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Windfury_SkillNoNeed:MODIFIER_CALLBACK:MCommon_Windfury_SkillNoNeed._CallbackList[1]:OnBeforeSkillCost:2/SuccessTaskList:0/SuccessTaskList:1",
        "owner_kind": "Modifier",
        "fixture": "source_backed_modifier_dynamic_value_mutation_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:M_BlackSwan_DOTFlag",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:M_BlackSwan_DOTFlag:MODIFIER_CALLBACK:M_BlackSwan_DOTFlag._CallbackList[0]:OnStack:0/SuccessTaskList:0",
        "owner_kind": "Modifier",
        "fixture": "source_backed_remove_self_modifier_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:GlobalModifiers:MAvatar_BlackSwan_00_DOT:MODIFIER_CALLBACK:MAvatar_BlackSwan_00_DOT._CallbackList[1]:OnPhase1:1/SuccessTaskList:2",
        "owner_kind": "Modifier",
        "fixture": "source_backed_add_modifier_alive_only_false_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_MindControl_Damage",
        "operation_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_MindControl_Damage:MODIFIER_CALLBACK:MCommon_MindControl_Damage._CallbackList[0]:OnListenCharmMakeDamage:3/TaskList:0",
        "owner_kind": "Modifier",
        "fixture": "source_backed_param_entity_attack_dynamic_value_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_DOT_Tear",
        "operation_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_DOT_Tear:MODIFIER_CALLBACK:MCommon_DOT_Tear._CallbackList[0]:OnCreate:2",
        "owner_kind": "Modifier",
        "fixture": "source_backed_snapshot_property_attack_dynamic_value_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Element_Bleed",
        "operation_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Element_Bleed:MODIFIER_CALLBACK:MCommon_Element_Bleed._CallbackList[0]:OnCreate:3",
        "owner_kind": "Modifier",
        "fixture": "source_backed_snapshot_break_damage_dynamic_value_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_SkillTree03",
        "operation_id": "external:TurnBasedGameData:Config/ConfigAbility/Avatar/Avatar_BlackSwan_00_Ability.json:Avatar_BlackSwan_00_SkillTree03:MODIFIER_CALLBACK:M_BlackSwan_00_SkillTree03._CallbackList[0]:OnEnterBattle:0",
        "owner_kind": "Avatar",
        "fixture": "source_backed_status_probability_dynamic_value_component_reference_001.json",
    },
    {
        "behavior_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Windfury",
        "operation_id": "external:TurnBasedGameData:Config/ConfigGlobalModifier/GlobalModifier_Common_Specific.json:MCommon_Windfury:MODIFIER_CALLBACK:MCommon_Windfury._CallbackList[2]:OnStack:2",
        "owner_kind": "Modifier",
        "fixture": "source_backed_own_modifier_layer_dynamic_value_component_reference_001.json",
    },
)


def walk(operations):
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        yield operation
        for group in operation.get("children", []):
            if isinstance(group, dict):
                yield from walk(group.get("operations", []))


def compiled_operations(record):
    for entrypoint in record.get("entrypoints", []):
        yield from walk(entrypoint.get("operations", []))
    for template in record.get("template_definitions", []):
        yield from walk(template.get("operations", []))


canonical_statuses = {}
for record in corpus.get("records", []):
    for entrypoint in record.get("entrypoints", []):
        for operation in walk(entrypoint.get("operations", [])):
            status = str(operation.get("semantic_status", "OPAQUE"))
            canonical_statuses[status] = canonical_statuses.get(status, 0) + 1
    for template in record.get("template_definitions", []):
        for operation in walk(template.get("operations", [])):
            status = str(operation.get("semantic_status", "OPAQUE"))
            canonical_statuses[status] = canonical_statuses.get(status, 0) + 1

owner_source_backed = {}
for record in report["records"]:
    if record.get("behavior_id") in SOURCE_BACKED_EXECUTABLE_BEHAVIORS and record.get("compile_status") == "EXECUTABLE_REFERENCE":
        owner = str(record.get("owner_kind"))
        owner_source_backed[owner] = owner_source_backed.get(owner, 0) + 1
source_backed_components_by_owner = {}
for component in SOURCE_BACKED_EXECUTED_COMPONENTS:
    record = next((item for item in report["records"] if item.get("behavior_id") == component["behavior_id"]), None)
    if record and any(
        operation.get("operation_id") == component["operation_id"]
        and operation.get("disposition") == "EXECUTABLE_REFERENCE"
        for operation in compiled_operations(record)
    ):
        owner = str(component["owner_kind"])
        source_backed_components_by_owner[owner] = source_backed_components_by_owner.get(owner, 0) + 1
families = {owner: {
    "captured_records": values["captured"],
    "behavior_bearing_denominator": values["behavior_bearing"],
    "static_definition_only": values["static_definition_only"],
    "canonicalized": values["captured"],
    "structural_compiled": values["structural_compiled"],
    "executable_reference": values.get("executable_reference", 0),
    "source_backed_executable": owner_source_backed.get(owner, 0),
    "source_backed_executed_components": source_backed_components_by_owner.get(owner, 0),
    "executable": values.get("executable_reference", 0),
    "golden_tested": 0,
    "unsupported_or_uncompiled": values["behavior_bearing"] - values["structural_compiled"] - values.get("executable_reference", 0),
    "full_game_behavior_denominator": "UNKNOWN",
} for owner, values in coverage["by_owner_kind"].items()}
for absent in ("Trace", "Eidolon", "LightCone", "RelicSet"):
    families[absent] = {"captured_records": 0, "behavior_bearing_denominator": 0, "static_definition_only": 0, "canonicalized": 0, "structural_compiled": 0, "executable_reference": 0, "source_backed_executable": 0, "source_backed_executed_components": 0, "executable": 0, "golden_tested": 0, "unsupported_or_uncompiled": 0, "full_game_behavior_denominator": "UNKNOWN"}
payload = {
    "report_id": "BEHAVIOR-COVERAGE-CENSUS-002",
    "game_version": "4.4.54",
    "status": "EXECUTABLE_REFERENCE_REVIEWED_CORPUS_BASELINE",
    "input_compiler_report_sha256": report["report_sha256"],
    "counting_rule": "The behavior denominator is the reviewed captured records that contain at least one operational entrypoint or TaskListTemplate. Records with no operational behavior are counted separately as static definitions and never deflate the behavior denominator. source_backed_executable counts complete BehaviorRecords executed through the bridge; source_backed_executed_components counts explicit provenance fixtures for independently executable canonical operations from records whose full entrypoint remains incomplete. The full 4.4.54 behavior corpus denominator remains UNKNOWN.",
    "families": dict(sorted(families.items())),
    "overall": {
        "captured_records": coverage["captured"],
        "canonicalized": coverage["canonicalized"],
        "behavior_bearing_denominator": coverage["behavior_bearing"],
        "static_definition_only": coverage["static_definition_only"],
        "structural_compiled": coverage["structural_compiled"],
        "executable_reference": coverage.get("executable", 0),
        "source_backed_executable": sum(owner_source_backed.values()),
        "source_backed_executed_components": sum(source_backed_components_by_owner.values()),
        "executable": coverage.get("executable", 0),
        "golden_tested": 0,
        "uncompiled": coverage["behavior_bearing"] - coverage["structural_compiled"] - coverage.get("executable", 0),
    },
    "operation_level": {
        "canonical_semantic_status": dict(sorted(canonical_statuses.items())),
        "compiled_disposition": coverage.get("operation_level", {}).get("compiled_disposition", {}),
        "executable_bound": coverage.get("operation_level", {}).get("executable_bound", 0),
        "executable_entrypoints": coverage.get("operation_level", {}).get("executable_entrypoints", 0),
    },
    "failure_clusters": coverage["failure_reasons"],
    "next_high_leverage": {"ticket_id": "EXECUTABLE-BRIDGE-EXPANSION-001", "reason": "The first generic bridge executes only fully closed conditional/heal and StackProperty records. Select the next operation family by executable-reference gain after this report's strict disposition counts, never by static entity count."},
}
write_json(arguments.output, payload)
print(json.dumps({"output_path": str(arguments.output), "overall": payload["overall"]}, sort_keys=True))
