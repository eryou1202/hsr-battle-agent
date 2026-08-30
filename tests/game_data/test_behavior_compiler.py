"""Strict canonical BehaviorRecord compiler tests."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler
from hsr_battle_agent.game_data.modifier_catalog import ModifierDefinition


class BehaviorCompilerTest(unittest.TestCase):
    def test_uncompiled_behavior_is_a_rejection_not_a_noop(self) -> None:
        corpus = {"game_version": "4.4.54", "corpus_sha256": "fixture", "records": [{"behavior_id": "fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [{"operation_id": "bad", "source_type": "RPG.GameCore.TaskConfig", "kind": "OPAQUE", "semantic_status": "OPAQUE", "semantic_importance": "P1_UNCLASSIFIED_SEMANTIC", "gating_risk": "UNKNOWN", "children": []}]}]}]}
        report = BehaviorCompiler().compile_corpus(corpus)
        record = report["records"][0]
        self.assertEqual(record["compile_status"], "REJECTED")
        self.assertEqual(record["execution_blockers"][0]["policy"], "REJECT_NOT_NOOP")

    def test_modelled_leaf_compiles_to_executable_reference_ir_when_complete(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [{"operation_id": "heal", "source_type": "RPG.GameCore.HealHP", "kind": "HEAL_REQUEST", "semantic_status": "MODELLED", "gating_risk": "KNOWN_STATE_COMMIT", "node_role": "OPERATION", "target": {"Alias": "Caster"}, "arguments": {"FormulaType": "HealByHealerMaxHP", "HealPercentage": {"IsDynamic": False, "FixedValue": {"Value": 0.1}}, "ModifyValue": {"IsDynamic": False, "FixedValue": {"Value": 0}}}, "state_reads": ["UNKNOWN"], "state_writes": ["UNKNOWN"], "event_boundary": "UNKNOWN", "dependencies": [], "children": []}]}]}
        result = BehaviorCompiler().compile_record(record)
        self.assertEqual(result["compile_status"], "EXECUTABLE_REFERENCE")
        self.assertIn("dynamic_mvp_v1:HEAL_STATE_TRANSITION", result["entrypoints"][0]["operations"][0]["dependencies"])
        self.assertTrue(result["executable"])

    def test_modifier_packet_binding_is_structural_not_executable(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONADD", "operations": [{"operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "node_role": "OPERATION", "target": "UNKNOWN", "arguments": {}, "state_reads": ["UNKNOWN"], "state_writes": ["UNKNOWN"], "event_boundary": "UNKNOWN", "dependencies": [], "children": []}]}]}
        result = BehaviorCompiler().compile_record(record)
        self.assertEqual(result["compile_status"], "COMPILED_STRUCTURE_ONLY")
        operation = result["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertIn("PRIM-MODIFIER-001", operation["dependencies"])
        self.assertFalse(result["executable"])

    def test_predicate_ast_compiles_to_executable_reference_without_choosing_a_branch(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [{"operation_id": "condition", "source_type": "RPG.GameCore.PredicateTaskList", "kind": "CONDITIONAL", "semantic_status": "REQUIRES_PACKET", "gating_risk": "UNKNOWN", "node_role": "OPERATION", "target": {"Alias": "Caster"}, "arguments": {"Predicate": {"$type": "RPG.GameCore.ByCompareHP", "CompareType": "Greater", "CompareValue": {"IsDynamic": False, "FixedValue": {"Value": 0}}, "TargetType": {"Alias": "Caster"}}}, "state_reads": ["UNKNOWN"], "state_writes": ["UNKNOWN"], "event_boundary": "UNKNOWN", "dependencies": [], "children": [{"field_path": "SuccessTaskList", "operations": []}, {"field_path": "FailedTaskList", "operations": []}]}]}]}
        result = BehaviorCompiler().compile_record(record)
        operation = result["entrypoints"][0]["operations"][0]
        self.assertEqual(result["compile_status"], "EXECUTABLE_REFERENCE")
        self.assertIn("COMPILER-PREDICATE-001-SEMANTICS", operation["dependencies"])
        self.assertEqual([group["field_path"] for group in operation["children"]], ["SuccessTaskList", "FailedTaskList"])

    def test_actual_slice_compiles_only_the_strict_no_blocker_subset(self) -> None:
        corpus = json.loads(Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json").read_text(encoding="utf-8"))
        report = BehaviorCompiler().compile_corpus(corpus)
        coverage = report["coverage"]
        self.assertEqual(coverage["captured"], 553)
        self.assertEqual(coverage["behavior_bearing"], 249)
        self.assertEqual(coverage["static_definition_only"], 304)
        self.assertGreater(coverage["executable"], 0)
        self.assertEqual(coverage["structural_compiled"] + coverage["executable"], 201)
        self.assertGreater(coverage["by_owner_kind"]["Avatar"]["structural_compiled"], 0)
        self.assertGreater(coverage["by_owner_kind"]["Monster"]["structural_compiled"], 0)
        self.assertGreater(coverage["by_owner_kind"]["Modifier"]["structural_compiled"], 0)
        self.assertGreater(coverage["by_owner_kind"]["StageBuff"]["structural_compiled"], 0)
        self.assertEqual(coverage["golden_tested"], 0)

    def test_modifier_layer_reader_rejects_max_layer_and_unknown_read_shapes(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTACK", "operations": [{"operation_id": "read", "source_type": "RPG.GameCore.SetDynamicValueByModifierValue", "kind": "SET_DYNAMIC_VALUE", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {"DynamicKey": "MDF_Max", "ReadTargetType": {"Alias": "ModifierOwnerEntity"}, "ValueType": "MaxLayer", "Multiplier": {"IsDynamic": False, "FixedValue": {"Value": 1}}}, "children": []}]}]}
        result = BehaviorCompiler().compile_record(record)
        operation = result["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertEqual(operation["reference_execution_blocker"], "EXECUTABLE_REFERENCE_MODIFIER_VALUE_TYPE_UNSUPPORTED")

    def test_property_dynamic_reader_rejects_unsupported_property_target_pairs(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTACK", "operations": [{"operation_id": "read", "source_type": "RPG.GameCore.SetDynamicValueByProperty", "kind": "SET_DYNAMIC_VALUE", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {"DynamicKey": "MDF_Attack", "ReadTargetType": {"Alias": "ModifierOwnerEntity"}, "Value": "Attack"}, "children": []}]}]}
        result = BehaviorCompiler().compile_record(record)
        operation = result["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertEqual(operation["reference_execution_blocker"], "EXECUTABLE_REFERENCE_PROPERTY_VALUE_TARGET_UNSUPPORTED")

    def test_set_modifier_dynamic_value_accepts_only_targetless_overwrite_shape(self) -> None:
        base = {"operation_id": "write", "source_type": "RPG.GameCore.SetModifierDynamicValue", "kind": "SET_DYNAMIC_VALUE", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {"DynamicKey": {"Value": "MDF_Count"}, "ModifierName": {"Value": "MFixture"}, "NewValue": {"IsDynamic": False, "FixedValue": {"Value": 1}}}, "children": []}
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONPHASE", "operations": [base]}]}
        self.assertEqual(BehaviorCompiler().compile_record(record)["compile_status"], "EXECUTABLE_REFERENCE")
        add_form = dict(base)
        add_form["arguments"] = dict(base["arguments"], ModifyFunction="Add")
        rejected = BehaviorCompiler().compile_record(dict(record, entrypoints=[{"event": "ONPHASE", "operations": [add_form]}]))
        operation = rejected["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertEqual(operation["reference_execution_blocker"], "EXECUTABLE_REFERENCE_SET_MODIFIER_DYNAMIC_ARGUMENTS_UNSUPPORTED")

    def test_remove_self_modifier_accepts_only_empty_targetless_shape(self) -> None:
        operation = {"operation_id": "remove", "source_type": "RPG.GameCore.RemoveSelfModifier", "kind": "REMOVE_MODIFIER", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": None, "arguments": {}, "children": []}
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONPHASE", "operations": [operation]}]}
        self.assertEqual(BehaviorCompiler().compile_record(record)["compile_status"], "EXECUTABLE_REFERENCE")
        invalid = dict(operation, target={"Alias": "Caster"})
        rejected = BehaviorCompiler().compile_record(dict(record, entrypoints=[{"event": "ONPHASE", "operations": [invalid]}]))
        self.assertEqual(rejected["entrypoints"][0]["operations"][0]["reference_execution_blocker"], "EXECUTABLE_REFERENCE_REMOVE_SELF_TARGET_UNSUPPORTED")

    def test_add_modifier_accepts_only_explicit_false_alive_only(self) -> None:
        operation = {"operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "Caster"}, "arguments": {"ModifierName": {"Value": "MFixture"}, "AliveOnly": False}, "children": []}
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONPHASE", "operations": [operation]}]}
        catalog = {"MFixture": ModifierDefinition("MFixture", "Replace", "fixture:modifier")}
        self.assertEqual(BehaviorCompiler(modifier_catalog=catalog).compile_record(record)["compile_status"], "EXECUTABLE_REFERENCE")
        invalid = dict(operation, arguments={"ModifierName": {"Value": "MFixture"}, "AliveOnly": True})
        rejected = BehaviorCompiler(modifier_catalog=catalog).compile_record(dict(record, entrypoints=[{"event": "ONPHASE", "operations": [invalid]}]))
        self.assertEqual(rejected["entrypoints"][0]["operations"][0]["reference_execution_blocker"], "EXECUTABLE_REFERENCE_ADD_MODIFIER_ALIVE_ONLY_UNSUPPORTED")

    def test_add_modifier_accepts_only_catalog_defined_static_lifetime_on_modifier_owner(self) -> None:
        operation = {"operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "target": {"Alias": "ModifierOwnerEntity"}, "arguments": {"ModifierName": {"Value": "MFixture"}, "LifeTime": {"IsDynamic": False, "FixedValue": {"Value": 2}}}, "children": []}
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONPHASE", "operations": [operation]}]}
        catalog = {"MFixture": ModifierDefinition("MFixture", "Merge", "fixture:modifier")}
        self.assertEqual(BehaviorCompiler(modifier_catalog=catalog).compile_record(record)["compile_status"], "EXECUTABLE_REFERENCE")
        dynamic = dict(operation, arguments={"ModifierName": {"Value": "MFixture"}, "LifeTime": {"IsDynamic": True, "PostfixExpr": {}}})
        rejected = BehaviorCompiler(modifier_catalog=catalog).compile_record(dict(record, entrypoints=[{"event": "ONPHASE", "operations": [dynamic]}]))
        self.assertEqual(rejected["entrypoints"][0]["operations"][0]["reference_execution_blocker"], "EXECUTABLE_REFERENCE_ADD_MODIFIER_FIXED_LIFETIME_UNSUPPORTED")
