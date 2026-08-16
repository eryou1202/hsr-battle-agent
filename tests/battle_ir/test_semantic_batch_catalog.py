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


class TestSemanticCatalog(unittest.TestCase):
    def test_default_catalog_loads_vertical_slice_plus_batch(self):
        primitives = load_catalog_primitives()
        ids = [primitive.spec.primitive_id for primitive in primitives]
        self.assertEqual(ids[0], "battle.ir.value.dynamic_value_equals")
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)
        # Vertical-slice loader stays byte-for-byte compatible.
        self.assertEqual(
            primitives[0].spec,
            load_vertical_slice_01().spec,
        )

    def test_catalog_schema_and_entries(self):
        catalog = load_semantic_catalog()
        self.assertEqual(catalog.schema, CATALOG_SCHEMA)
        self.assertEqual(catalog.game_version, "4.4.54")
        self.assertEqual(len(catalog.artifacts), 2)
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
            self.assertEqual(
                [primitive.spec.primitive_id for primitive in primitives],
                ["battle.ir.value.dynamic_value_equals"],
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
