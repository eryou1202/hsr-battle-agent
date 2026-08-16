# -*- coding: utf-8 -*-
"""Semantic artifact -> Battle IR connection tests.

The artifact JSON is a real input; provenance is validated but stays out of
runtime execution structures.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import (  # noqa: E402
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (  # noqa: E402
    ARTIFACT_SCHEMA,
    SemanticArtifactError,
    default_artifact_path,
    load_vertical_slice_01,
    validate_vertical_slice_01,
)


class TestSemanticArtifactLoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recovered = load_vertical_slice_01()
        cls.raw = json.loads(
            default_artifact_path().read_text(encoding="utf-8")
        )

    def test_default_artifact_exists(self):
        self.assertTrue(default_artifact_path().is_file())

    def test_required_semantic_fields_validated(self):
        spec = self.recovered.spec
        self.assertEqual(spec.primitive_id, "battle.ir.value.dynamic_value_equals")
        self.assertEqual(spec.semantic_name, "DynamicValueEquals")
        self.assertEqual(spec.result, "boolean")
        self.assertEqual(spec.determinism, "DETERMINISTIC")
        self.assertEqual(spec.context_reads, ("lhs", "rhs"))
        self.assertEqual(spec.context_writes, ())

    def test_loaded_spec_matches_artifact_semantic_shape(self):
        spec = self.recovered.spec
        self.assertIsInstance(spec, PrimitiveSpec)
        self.assertEqual(
            [(item.name, item.type) for item in spec.inputs],
            [("lhs", "DynamicValue"), ("rhs", "DynamicValue")],
        )
        self.assertEqual(spec.result, "boolean")
        self.assertEqual(spec.determinism, "DETERMINISTIC")

    def test_provenance_is_separate_and_exact(self):
        provenance = self.recovered.provenance
        self.assertEqual(provenance.game_version, "4.4.54")
        self.assertEqual(provenance.runtime_type, "RPG.GameCore.DynamicValue")
        self.assertEqual(provenance.method, "Equals")
        self.assertEqual(provenance.method_index, 74632)
        self.assertEqual(provenance.native_rva, "0x1CFBE9E0")
        self.assertEqual(provenance.evidence_level, "E4_STATIC_MACHINE_CODE")
        self.assertEqual(
            provenance.source_reference(),
            "4.4.54:RPG.GameCore.DynamicValue.Equals:74632",
        )

    def test_runtime_spec_has_no_provenance_fields(self):
        self.assertFalse(hasattr(self.recovered.spec, "method_index"))
        self.assertFalse(hasattr(self.recovered.spec, "native_rva"))

    def test_dynamic_value_enum_ordinals_match_artifact(self):
        values = self.raw["dynamic_value_type_enum"]["values"]
        self.assertEqual(
            [(item["name"], item["ordinal"]) for item in values],
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


class TestSemanticArtifactRejection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid = json.loads(
            default_artifact_path().read_text(encoding="utf-8")
        )

    def test_missing_required_field_fails_closed(self):
        with self.assertRaises(SemanticArtifactError):
            validate_vertical_slice_01({"schema": ARTIFACT_SCHEMA})

    def test_wrong_schema_rejected(self):
        data = copy.deepcopy(self.valid)
        data["schema"] = "other/1"
        with self.assertRaises(SemanticArtifactError):
            validate_vertical_slice_01(data)

    def test_wrong_primitive_id_rejected(self):
        data = copy.deepcopy(self.valid)
        data["ir_primitive"]["primitive_id"] = "battle.ir.value.something_else"
        with self.assertRaises(SemanticArtifactError):
            validate_vertical_slice_01(data)

    def test_wrong_evidence_level_rejected(self):
        data = copy.deepcopy(self.valid)
        data["evidence_level"] = "E3_METADATA"
        data["ir_primitive"]["evidence_level"] = "E3_METADATA"
        with self.assertRaises(SemanticArtifactError):
            validate_vertical_slice_01(data)

    def test_wrong_enum_ordinal_rejected(self):
        data = copy.deepcopy(self.valid)
        data["dynamic_value_type_enum"]["values"][6]["ordinal"] = 7
        with self.assertRaises(SemanticArtifactError):
            validate_vertical_slice_01(data)

    def test_non_json_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(SemanticArtifactError):
                load_vertical_slice_01(path)


if __name__ == "__main__":
    unittest.main()
