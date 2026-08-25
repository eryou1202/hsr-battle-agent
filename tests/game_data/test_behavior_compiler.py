"""Strict canonical BehaviorRecord compiler tests."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler


class BehaviorCompilerTest(unittest.TestCase):
    def test_uncompiled_behavior_is_a_rejection_not_a_noop(self) -> None:
        corpus = {"game_version": "4.4.54", "corpus_sha256": "fixture", "records": [{"behavior_id": "fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [{"operation_id": "bad", "source_type": "RPG.GameCore.TaskConfig", "kind": "OPAQUE", "semantic_status": "OPAQUE", "semantic_importance": "P1_UNCLASSIFIED_SEMANTIC", "gating_risk": "UNKNOWN", "children": []}]}]}]}
        report = BehaviorCompiler().compile_corpus(corpus)
        record = report["records"][0]
        self.assertEqual(record["compile_status"], "REJECTED")
        self.assertEqual(record["execution_blockers"][0]["policy"], "REJECT_NOT_NOOP")

    def test_modelled_leaf_compiles_to_packet_bound_ir(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [{"operation_id": "heal", "source_type": "RPG.GameCore.HealHP", "kind": "HEAL_REQUEST", "semantic_status": "MODELLED", "gating_risk": "KNOWN_STATE_COMMIT", "node_role": "OPERATION", "target": "SELF", "arguments": {}, "state_reads": ["UNKNOWN"], "state_writes": ["UNKNOWN"], "event_boundary": "UNKNOWN", "dependencies": [], "children": []}]}]}
        result = BehaviorCompiler().compile_record(record)
        self.assertEqual(result["compile_status"], "COMPILED_STRUCTURE_ONLY")
        self.assertIn("dynamic_mvp_v1:HEAL_STATE_TRANSITION", result["entrypoints"][0]["operations"][0]["dependencies"])
        self.assertFalse(result["executable"])

    def test_modifier_packet_binding_is_structural_not_executable(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Modifier", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONADD", "operations": [{"operation_id": "add", "source_type": "RPG.GameCore.AddModifier", "kind": "ADD_MODIFIER", "semantic_status": "REQUIRES_PACKET", "gating_risk": "KNOWN_STATE_COMMIT", "node_role": "OPERATION", "target": "UNKNOWN", "arguments": {}, "state_reads": ["UNKNOWN"], "state_writes": ["UNKNOWN"], "event_boundary": "UNKNOWN", "dependencies": [], "children": []}]}]}
        result = BehaviorCompiler().compile_record(record)
        self.assertEqual(result["compile_status"], "COMPILED_STRUCTURE_ONLY")
        operation = result["entrypoints"][0]["operations"][0]
        self.assertEqual(operation["disposition"], "BOUND_UNEXECUTABLE_PACKET")
        self.assertIn("PRIM-MODIFIER-001", operation["dependencies"])
        self.assertFalse(result["executable"])

    def test_predicate_ast_is_bound_without_choosing_a_branch(self) -> None:
        record = {"behavior_id": "fixture", "owner_kind": "Avatar", "owner_ref": "fixture", "source_refs": [], "entrypoints": [{"event": "ONSTART", "operations": [{"operation_id": "condition", "source_type": "RPG.GameCore.PredicateTaskList", "kind": "CONDITIONAL", "semantic_status": "REQUIRES_PACKET", "gating_risk": "UNKNOWN", "node_role": "OPERATION", "target": "UNKNOWN", "arguments": {}, "state_reads": ["UNKNOWN"], "state_writes": ["UNKNOWN"], "event_boundary": "UNKNOWN", "dependencies": [], "children": [{"field_path": "SuccessTaskList", "operations": []}, {"field_path": "FailedTaskList", "operations": []}]}]}]}
        result = BehaviorCompiler().compile_record(record)
        operation = result["entrypoints"][0]["operations"][0]
        self.assertEqual(result["compile_status"], "COMPILED_STRUCTURE_ONLY")
        self.assertIn("COMPILER-PREDICATE-001", operation["dependencies"])
        self.assertEqual([group["field_path"] for group in operation["children"]], ["SuccessTaskList", "FailedTaskList"])

    def test_actual_slice_compiles_only_the_strict_no_blocker_subset(self) -> None:
        corpus = json.loads(Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json").read_text(encoding="utf-8"))
        report = BehaviorCompiler().compile_corpus(corpus)
        coverage = report["coverage"]
        self.assertEqual(coverage["captured"], 553)
        self.assertEqual(coverage["behavior_bearing"], 249)
        self.assertEqual(coverage["static_definition_only"], 304)
        self.assertEqual(coverage["structural_compiled"], 201)
        self.assertEqual(coverage["executable"], 0)
        self.assertGreater(coverage["by_owner_kind"]["Avatar"]["structural_compiled"], 0)
        self.assertGreater(coverage["by_owner_kind"]["Monster"]["structural_compiled"], 0)
        self.assertGreater(coverage["by_owner_kind"]["Modifier"]["structural_compiled"], 0)
        self.assertGreater(coverage["by_owner_kind"]["StageBuff"]["structural_compiled"], 0)
        self.assertEqual(coverage["golden_tested"], 0)
