# -*- coding: utf-8 -*-
"""Semantic Batch 02 + catalog loader validation tests."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.catalog import (  # noqa: E402
    CATALOG_SCHEMA,
    load_catalog_primitives,
    load_semantic_catalog,
    validate_semantic_catalog,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (  # noqa: E402
    SemanticArtifactError,
    load_vertical_slice_01,
)
from hsr_battle_agent.battle_ir.semantic_batch import (  # noqa: E402
    BATCH_SCHEMA,
    default_batch_02_path,
    load_battle_semantics_batch,
    load_dynamic_value_batch_02,
    validate_dynamic_value_batch_02,
)


class TestBatch02Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = default_batch_02_path()
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_dynamic_value_batch_02()

    def test_artifact_exists_and_has_expected_shape(self):
        self.assertTrue(self.path.is_file())
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(len(self.raw["primitives"]), 11)

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 11)
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertEqual(primitive.spec.inputs[0].name, "value")
                self.assertEqual(primitive.spec.inputs[0].type, "DynamicValue")
                self.assertEqual(primitive.spec.context_reads, ("value",))
                self.assertEqual(primitive.spec.context_writes, ())
                self.assertEqual(primitive.spec.determinism, "DETERMINISTIC")
                self.assertEqual(
                    primitive.provenance.runtime_type,
                    "RPG.GameCore.DynamicValue",
                )
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_primitive_ids_are_unique_and_canonical(self):
        ids = [primitive.spec.primitive_id for primitive in self.primitives]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(pid.startswith("battle.ir.value.") for pid in ids))

    def test_enum_block_matches_vertical_slice(self):
        values = [
            (item["name"], item["ordinal"])
            for item in self.raw["dynamic_value_type_enum"]["values"]
        ]
        self.assertEqual(
            values,
            [
                ("INT", 0),
                ("FLOAT", 1),
                ("BOOL", 2),
                ("ARRAY", 3),
                ("MAP", 4),
                ("STRING", 5),
                ("NULL", 6),
            ],
        )


class TestBatch02ArtifactRejection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid = json.loads(default_batch_02_path().read_text(encoding="utf-8"))

    def test_wrong_schema_rejected(self):
        data = copy.deepcopy(self.valid)
        data["schema"] = "other/1"
        with self.assertRaises(SemanticArtifactError):
            validate_dynamic_value_batch_02(data)

    def test_wrong_evidence_level_rejected(self):
        data = copy.deepcopy(self.valid)
        data["evidence_level"] = "E3_METADATA"
        data["primitives"][0]["evidence_level"] = "E3_METADATA"
        with self.assertRaises(SemanticArtifactError):
            validate_dynamic_value_batch_02(data)

    def test_duplicate_primitive_id_rejected(self):
        data = copy.deepcopy(self.valid)
        data["primitives"][1]["primitive_id"] = data["primitives"][0]["primitive_id"]
        with self.assertRaises(SemanticArtifactError):
            validate_dynamic_value_batch_02(data)

    def test_context_writes_must_be_empty(self):
        data = copy.deepcopy(self.valid)
        data["primitives"][0]["context_writes"] = ["battle_state"]
        with self.assertRaises(SemanticArtifactError):
            validate_dynamic_value_batch_02(data)


class TestFixPointComparisonBatch03Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(REPO)
            / "data"
            / "semantics"
            / "4.4.54"
            / "fixpoint_comparison_batch_03.json"
        )
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_battle_semantics_batch(cls.path)

    def test_artifact_has_expected_shape(self):
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(
            self.raw["final_status"],
            "BATTLE_SEMANTIC = FIXPOINT_COMPARISON_BATCH_03_PROOF",
        )
        self.assertEqual(len(self.raw["primitives"]), 10)

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 10)
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertEqual(primitive.spec.context_writes, ())
                self.assertEqual(primitive.spec.determinism, "DETERMINISTIC")
                self.assertEqual(
                    primitive.provenance.runtime_type,
                    "RPG.GameCore.FixPoint",
                )
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_primitive_ids_are_unique_and_grouped(self):
        ids = [primitive.spec.primitive_id for primitive in self.primitives]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(1 for i in ids if i.startswith("battle.ir.compare.")), 6)
        self.assertEqual(
            sum(1 for i in ids if i.startswith("battle.ir.predicate.")), 3
        )
        self.assertEqual(
            sum(1 for i in ids if i.startswith("battle.ir.value.")), 1
        )

    def test_comparison_semantics_block_is_explicit(self):
        semantics = self.raw["comparison_semantics"]
        self.assertTrue(
            semantics["special_mode_or_sentinel"].startswith("NONE_OBSERVED")
        )
        self.assertIn("signed 64-bit", semantics["signedness"])
        self.assertNotEqual(semantics["proven_comparison_coverage"], "")
        self.assertNotEqual(semantics["sandbox_constructible_domain"], "")


class TestPredicateEvaluationBridgeBatch04Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(REPO)
            / "data"
            / "semantics"
            / "4.4.54"
            / "predicate_evaluation_bridge_04.json"
        )
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_battle_semantics_batch(cls.path)

    def test_artifact_has_expected_shape(self):
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["batch_id"], "PREDICATE_EVALUATION_BRIDGE_04")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(len(self.raw["primitives"]), 5)
        self.assertTrue(self.raw["composition_chains"])
        self.assertTrue(self.raw["candidate_table"])

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 5)
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertEqual(primitive.spec.context_writes, ())
                self.assertEqual(primitive.spec.determinism, "DETERMINISTIC")
                self.assertEqual(
                    primitive.provenance.runtime_type,
                    "RPG.GameCore.ValueEvaluatorConfig",
                )
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_primitive_ids_grouped_and_unique(self):
        ids = [primitive.spec.primitive_id for primitive in self.primitives]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(pid.startswith("battle.ir.predicate.") for pid in ids))
        self.assertEqual(
            sum(1 for pid in ids if pid.endswith("_from_int32")), 1
        )
        self.assertEqual(
            sum(1 for pid in ids if pid.endswith("_from_fixpoint_raw")), 1
        )
        self.assertEqual(
            sum(1 for pid in ids if pid.endswith("_equal_int32")), 1
        )
        self.assertEqual(
            sum(
                1
                for pid in ids
                if pid == "battle.ir.predicate.evaluator_spec_fixpoint_equal_raw"
            ),
            1,
        )
        self.assertEqual(
            sum(1 for pid in ids if pid.endswith("_not_equal_raw")), 1
        )

    def test_composition_chains_are_machine_readable(self):
        for chain in self.raw["composition_chains"]:
            with self.subTest(chain_id=chain["chain_id"]):
                self.assertIn("steps", chain)
                self.assertTrue(chain["steps"])
                for step in chain["steps"]:
                    self.assertIn("primitive_id", step)
                    self.assertIn("role", step)


class TestTargetSelectorBatch05Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(REPO)
            / "data"
            / "semantics"
            / "4.4.54"
            / "target_selector_batch_05.json"
        )
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_battle_semantics_batch(cls.path)

    def test_artifact_has_expected_shape(self):
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["batch_id"], "TARGET_SELECTOR_BATCH_05")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(
            self.raw["final_status"],
            "BATTLE_SEMANTIC = TARGET_SELECTOR_BATCH_05_PROOF",
        )
        self.assertEqual(len(self.raw["primitives"]), 8)
        self.assertEqual(len(self.raw["selector_chains"]), 3)
        self.assertTrue(self.raw["context_requirements"])
        self.assertTrue(self.raw["candidate_table"])

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 8)
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertEqual(primitive.spec.context_writes, ())
                self.assertEqual(primitive.spec.determinism, "DETERMINISTIC")
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_primitive_ids_grouped_and_unique(self):
        ids = [primitive.spec.primitive_id for primitive in self.primitives]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(1 for pid in ids if pid.startswith("battle.ir.target.")), 7)
        self.assertEqual(sum(1 for pid in ids if pid.startswith("battle.ir.entity.")), 1)

    def test_selector_chains_are_machine_readable(self):
        for chain in self.raw["selector_chains"]:
            with self.subTest(chain_id=chain["chain_id"]):
                self.assertIn("selector_config", chain)
                self.assertIn("runtime_bridge", chain)
                self.assertIn("evaluator_method_index", chain["runtime_bridge"])
                self.assertTrue(chain["steps"])


class TestActionExecutionBridgeBatch06Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(REPO)
            / "data"
            / "semantics"
            / "4.4.54"
            / "action_execution_bridge_06.json"
        )
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_battle_semantics_batch(cls.path)

    def test_artifact_has_expected_shape(self):
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["batch_id"], "ACTION_EXECUTION_BRIDGE_06")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(
            self.raw["final_status"],
            "BATTLE_SEMANTIC = ACTION_EXECUTION_BRIDGE_06_PROOF",
        )
        self.assertEqual(
            self.raw["runtime_layer_name"],
            "GENERATED_TASK_EXECUTOR_RUNTIME",
        )
        self.assertEqual(len(self.raw["primitives"]), 7)
        self.assertEqual(len(self.raw["execution_chains"]), 4)
        self.assertTrue(self.raw["first_round_report"])
        self.assertTrue(self.raw["deferred_effects"])
        self.assertTrue(self.raw["semantic_dependencies"])

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 7)
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertEqual(primitive.spec.context_writes, ())
                self.assertEqual(primitive.spec.determinism, "DETERMINISTIC")
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_primitive_ids_grouped_and_unique(self):
        ids = [primitive.spec.primitive_id for primitive in self.primitives]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(pid.startswith("battle.ir.action.") for pid in ids))
        self.assertEqual(
            sum(1 for pid in ids if pid == "battle.ir.action.task_executor_init"),
            1,
        )
        self.assertEqual(
            sum(
                1
                for pid in ids
                if pid == "battle.ir.action.task_begin_select_single_target"
            ),
            1,
        )

    def test_execution_chains_are_machine_readable(self):
        for chain in self.raw["execution_chains"]:
            with self.subTest(chain_id=chain["chain_id"]):
                self.assertIn("chain_id", chain)
                self.assertIn("status", chain)
                self.assertIn("runtime_bridge", chain)
                self.assertTrue(chain["steps"])
                for step in chain["steps"]:
                    self.assertIn("role", step)
                    self.assertTrue(
                        any(key in step for key in ("effect", "primitive_id", "dependency"))
                    )

    def test_task_state_model_matches_native_constants(self):
        model = self.raw["task_state_model"]
        self.assertEqual(model["runtime_type"], "RPG.GameCore.TaskState")
        self.assertEqual(model["native_field_offset"], "+0x10 (int32) on generated task executors")
        self.assertEqual(
            model["raw_values"],
            {
                "Ready": "0x7777",
                "Executing": "0x8888",
                "Success": "0x9999",
                "Fail": "0xAAAA",
            },
        )

    def test_context_and_state_requirements_are_explicit(self):
        self.assertEqual(self.raw["context_reads"], ["targets"])
        self.assertEqual(self.raw["context_writes"], [])
        self.assertEqual(self.raw["state_reads"], [])
        self.assertEqual(self.raw["state_writes"], [])


class TestModifierApplicationBridgeBatch07Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(REPO)
            / "data"
            / "semantics"
            / "4.4.54"
            / "modifier_application_bridge_07.json"
        )
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_battle_semantics_batch(cls.path)

    def test_artifact_has_expected_shape(self):
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(
            self.raw["final_status"],
            "BATTLE_SEMANTIC = MODIFIER_APPLICATION_BRIDGE_07_PROOF",
        )
        self.assertEqual(len(self.raw["primitives"]), 16)
        self.assertEqual(
            self.raw["runtime_layer_name"],
            "TURNBASED_MODIFIER_APPLICATION_RUNTIME",
        )

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 16)
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertEqual(primitive.spec.context_writes, ())
                self.assertEqual(primitive.spec.determinism, "DETERMINISTIC")
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_application_chains_are_machine_readable(self):
        self.assertTrue(self.raw["application_chains"])
        self.assertEqual(
            self.raw["application_chains"][0]["chain_id"],
            "add_modifier_action_application_chain",
        )
        for chain in self.raw["application_chains"]:
            with self.subTest(chain_id=chain["chain_id"]):
                self.assertIn("chain_id", chain)
                self.assertIn("status", chain)
                self.assertTrue(chain["steps"])
                for step in chain["steps"]:
                    self.assertIn("role", step)
                    self.assertIn("evidence", step)

    def test_persistent_read_write_sets_are_explicit(self):
        self.assertTrue(self.raw["persistent_reads"])
        self.assertTrue(self.raw["persistent_writes"])
        self.assertTrue(self.raw["modifier_identity"])
        self.assertTrue(self.raw["stack_policy"])
        self.assertTrue(self.raw["lifetime_semantics"])
        self.assertTrue(self.raw["unknowns"])


class TestModifierLifecycleBridgeBatch08Artifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = (
            Path(REPO)
            / "data"
            / "semantics"
            / "4.4.54"
            / "modifier_lifecycle_bridge_08.json"
        )
        cls.raw = json.loads(cls.path.read_text(encoding="utf-8"))
        cls.primitives = load_battle_semantics_batch(cls.path)

    def test_artifact_has_expected_shape(self):
        self.assertEqual(self.raw["schema"], BATCH_SCHEMA)
        self.assertEqual(self.raw["game_version"], "4.4.54")
        self.assertEqual(self.raw["evidence_level"], "E4_STATIC_MACHINE_CODE")
        self.assertEqual(
            self.raw["final_status"],
            "BATTLE_SEMANTIC = MODIFIER_LIFECYCLE_BRIDGE_08_PROOF",
        )
        self.assertEqual(len(self.raw["primitives"]), 8)
        self.assertEqual(
            self.raw["runtime_layer_name"],
            "TURNBASED_MODIFIER_LIFECYCLE_RUNTIME",
        )
        self.assertTrue(self.raw["duplicate_application_cases"])
        self.assertTrue(self.raw["removal_chains"])
        self.assertTrue(self.raw["lifecycle_chains"])
        self.assertTrue(self.raw["instance_identity"])
        self.assertTrue(self.raw["duplicate_match_identity"])

    def test_loader_returns_separated_spec_and_provenance(self):
        self.assertEqual(len(self.primitives), 8)
        expected_ids = {
            "battle.ir.modifier.try_add_modifier_instance",
            "battle.ir.modifier.container_find_modifier_instance",
            "battle.ir.modifier.match_modifier_search",
            "battle.ir.modifier.lifecycle_destroy",
            "battle.ir.modifier.container_remove_dirty",
            "battle.ir.modifier.lifecycle_process_redd",
            "battle.ir.modifier.lifecycle_on_added",
            "battle.ir.modifier.lifecycle_on_activate",
        }
        self.assertEqual(
            {primitive.spec.primitive_id for primitive in self.primitives},
            expected_ids,
        )
        for primitive in self.primitives:
            with self.subTest(primitive_id=primitive.spec.primitive_id):
                self.assertIn("4.4.54:", primitive.provenance.source_reference())
                self.assertEqual(
                    primitive.provenance.evidence_level,
                    "E4_STATIC_MACHINE_CODE",
                )
                self.assertFalse(hasattr(primitive.spec, "method_index"))

    def test_duplicate_cases_cover_every_stacking_ordinal(self):
        cases = self.raw["duplicate_application_cases"]
        self.assertEqual(len(cases), 28)  # 14 ordinals x existing/no-existing
        self.assertEqual(
            {case["stacking_ordinal"] for case in cases},
            set(range(14)),
        )
        self.assertIn(
            "DESTROY_EXISTING_THEN_APPEND",
            {case["policy"] for case in cases},
        )


class TestSemanticCatalog(unittest.TestCase):
    def test_default_catalog_loads_vertical_slice_plus_batches(self):
        primitives = load_catalog_primitives()
        ids = [primitive.spec.primitive_id for primitive in primitives]
        self.assertEqual(ids[0], "battle.ir.value.dynamic_value_equals")
        self.assertEqual(len(ids), 66)
        self.assertEqual(len(set(ids)), 66)
        # Vertical-slice loader stays byte-for-byte compatible.
        self.assertEqual(
            primitives[0].spec,
            load_vertical_slice_01().spec,
        )

    def test_catalog_schema_and_entries(self):
        catalog = load_semantic_catalog()
        self.assertEqual(catalog.schema, CATALOG_SCHEMA)
        self.assertEqual(catalog.game_version, "4.4.54")
        self.assertEqual(len(catalog.artifacts), 8)
        self.assertTrue(all(entry.enabled for entry in catalog.artifacts))

    def test_sha256_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            catalog_data = json.loads(
                (Path(REPO) / "data/semantics/4.4.54/catalog.json").read_text(
                    encoding="utf-8"
                )
            )
            for entry in catalog_data["artifacts"]:
                source = (
                    Path(REPO)
                    / "data"
                    / "semantics"
                    / "4.4.54"
                    / entry["path"]
                )
                target = tmp_path / entry["path"]
                target.write_bytes(source.read_bytes())
            catalog_data["artifacts"][0]["sha256"] = "0" * 64
            catalog_path = tmp_path / "catalog.json"
            catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")
            with self.assertRaises(SemanticArtifactError):
                load_catalog_primitives(catalog_path)

    def test_disabled_entry_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            catalog_data = json.loads(
                (Path(REPO) / "data/semantics/4.4.54/catalog.json").read_text(
                    encoding="utf-8"
                )
            )
            for entry in catalog_data["artifacts"]:
                source = (
                    Path(REPO)
                    / "data"
                    / "semantics"
                    / "4.4.54"
                    / entry["path"]
                )
                target = tmp_path / entry["path"]
                target.write_bytes(source.read_bytes())
            catalog_data["artifacts"][1]["enabled"] = False
            catalog_path = tmp_path / "catalog.json"
            catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")
            primitives = load_catalog_primitives(catalog_path)
            ids = [primitive.spec.primitive_id for primitive in primitives]
            self.assertEqual(ids[0], "battle.ir.value.dynamic_value_equals")
            # vertical slice + FixPoint Batch 03 + Predicate Bridge Batch 04
            # + Target Selector Batch 05 + Action Execution Bridge 06
            # + Modifier Application Bridge 07 + Modifier Lifecycle Bridge 08
            # (DynamicValue Batch 02 disabled)
            self.assertEqual(len(ids), 55)
            self.assertEqual(
                sum(1 for pid in ids if pid.startswith("battle.ir.compare.")), 6
            )
            self.assertEqual(
                sum(1 for pid in ids if pid.startswith("battle.ir.predicate.")),
                3 + 5,
            )
            self.assertEqual(
                sum(1 for pid in ids if pid.startswith("battle.ir.target.")), 7
            )
            self.assertEqual(
                sum(1 for pid in ids if pid.startswith("battle.ir.action.")), 8
            )
            self.assertEqual(
                sum(1 for pid in ids if pid.startswith("battle.ir.modifier.")), 23
            )

    def test_unsupported_artifact_schema_rejected(self):
        data = {
            "schema": CATALOG_SCHEMA,
            "game_version": "4.4.54",
            "artifacts": [
                {
                    "path": "x.json",
                    "schema": "unknown_battle_semantics/1",
                    "sha256": "0" * 64,
                    "enabled": True,
                }
            ],
        }
        with self.assertRaises(SemanticArtifactError):
            validate_semantic_catalog(data)


if __name__ == "__main__":
    unittest.main()
