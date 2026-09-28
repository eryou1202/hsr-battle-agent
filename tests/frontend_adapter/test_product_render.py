"""P5A consumers of public P2/P3/P4 authorities; frozen modules stay untouched."""
from __future__ import annotations

import ast
from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hsr_battle_agent.content_support import load_registry
from hsr_battle_agent.frontend_adapter import product_render as render
from hsr_battle_agent.frontend_adapter.product_generate import pack_details
from hsr_battle_agent.game_data.content_product import ContentProductService
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, stable_bytes
from hsr_battle_agent.game_data.scenario_compiler import ScenarioCompiler
from hsr_battle_agent.product_support import ScenarioSupportReporter
from tests.product_support.test_scenario_support_report import _request

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/db/hsr_content_4.4.54.sqlite"
STATIC = ROOT / "frontend/public/data/product/4.4.54"
VERSION = "4.4.54"


class ProductBoundaryTests(unittest.TestCase):
    def test_renderer_imports_only_public_product_authorities(self):
        source = Path(render.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(set(imports), {"__future__", "copy", "typing",
                         "hsr_battle_agent.game_data.content_product",
                         "hsr_battle_agent.game_data.nanoka_content", "hsr_battle_agent.product_support"})
        calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertFalse(calls & {"open", "Path", "read_json", "load_registry", "ScenarioCompiler"})
        self.assertFalse(any(name.endswith((".read_text", ".read_bytes", ".execute")) for name in calls))
        self.assertNotIn("content_planner", source)
        self.assertNotIn("real_content_execution_eligibility", source)

    def test_explicit_registry_is_required_for_reports(self):
        parameter = inspect.signature(render.emit_scenario_support_report).parameters["registry"]
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIs(parameter.default, inspect.Parameter.empty)


@unittest.skipUnless(DATABASE.is_file(), "real explicit 4.4.54 database required")
class ProductRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = ContentDatabase(DATABASE, VERSION)
        cls.registry = load_registry(VERSION)
        cls.service = ContentProductService(cls.database, registry=cls.registry)
        cls.provenance = {"starting_head": "p5a-test-head", "authorities": ["P2", "P3", "P4"]}

    def test_all_summary_counts_schemas_and_verbatim_rows(self):
        families = (
            ("characters", render.emit_character_catalog, self.service.list_characters, 97),
            ("monsters", render.emit_monster_catalog, self.service.list_monsters, 628),
            ("stages", render.emit_stage_catalog, self.service.list_stages, 1459),
            ("encounters", render.emit_encounter_catalog, self.service.list_encounters, 1543),
        )
        for name, emitter, public, expected_count in families:
            with self.subTest(collection=name):
                result = emitter(VERSION, self.service)
                self.assertEqual(result["schema"], render.COLLECTION_SCHEMA)
                self.assertEqual(result["count"], expected_count)
                self.assertEqual(result["row_schema"], render.SUMMARY_SCHEMAS[name])
                self.assertEqual(result["rows"], list(public()))
                self.assertTrue(all("skills" not in row and "waves" not in row for row in result["rows"]))

    def test_root_is_deterministic_and_never_calls_detail_or_stage_package(self):
        with patch.object(self.service, "get_character", side_effect=AssertionError("detail")), \
             patch.object(self.service, "get_monster", side_effect=AssertionError("detail")), \
             patch.object(self.service, "get_stage", side_effect=AssertionError("detail")), \
             patch.object(self.service, "get_encounter", side_effect=AssertionError("detail")), \
             patch.object(self.database, "get_stage_package", side_effect=AssertionError("topology")):
            first = render.emit_product_catalog(VERSION, self.service, provenance=self.provenance)
            second = render.emit_product_catalog(VERSION, self.service, provenance=self.provenance)
        self.assertEqual(first["schema"], render.PRODUCT_CATALOG_SCHEMA)
        self.assertEqual(stable_bytes(first), stable_bytes(second))
        self.assertLess(len(stable_bytes(first)), 5000)
        self.assertEqual(first["counts"], dict(zip(render.COLLECTIONS, (97, 628, 1459, 1543))))
        self.assertEqual(first["scenario_compilation"], "NOT_CONNECTED")
        self.assertFalse(first["dynamic_backend_connected"])

    def test_explicit_version_and_coherence_fail_before_any_enumeration(self):
        for version in (None, "", "latest", "4.5.54"):
            with self.subTest(version=version), patch.object(self.service, "list_stages") as listing:
                with self.assertRaisesRegex(ValueError, "EXPLICIT_4_4_54_REQUIRED"):
                    render.emit_stage_catalog(version, self.service)
                listing.assert_not_called()
        other = ContentProductService(ContentDatabase(DATABASE, "4.5.54"))
        with self.assertRaisesRegex(ValueError, "CONTENT_VERSION_MISMATCH"):
            render.emit_product_catalog(VERSION, other, provenance=self.provenance)

    def test_details_are_exact_backend_documents_and_copy_isolated(self):
        for name, key, emitter, public in (
            ("characters", "1105", render.emit_character_detail, self.service.get_character),
            ("monsters", "1002020", render.emit_monster_detail, self.service.get_monster),
            ("stages", "420101", render.emit_stage_detail, self.service.get_stage),
            ("encounters", "boss:3001:30011:event_id_list1:0", render.emit_encounter_detail, self.service.get_encounter),
        ):
            with self.subTest(collection=name):
                authority = public(key)
                document = emitter(VERSION, self.service, key)
                self.assertEqual(document, authority)
                self.assertEqual(document["schema"], render.PRODUCT_SCHEMAS[name])
                self.assertEqual(stable_bytes(document), stable_bytes(emitter(VERSION, self.service, key)))
                document["identity"].clear()
                self.assertTrue(authority["identity"])
                with self.assertRaises(LookupError):
                    emitter(VERSION, self.service, "missing-p5a-id")

    def test_adapter_never_rederives_semantic_fields(self):
        authority = self.service.get_character("1105")
        authority["skills"][0]["m14_capability"]["execution_readiness"] = "opaque-authority-value"
        authority["skills"][0]["m14_execution_eligibility"]["reason_detail"] = "verbatim authority"
        with patch.object(self.service, "get_character", return_value=authority):
            document = render.emit_character_detail(VERSION, self.service, "1105")
        self.assertEqual(document, authority)
        self.assertIsNot(document, authority)

    def test_no_registry_nulls_and_monster_context_are_not_defaulted(self):
        static_only = ContentProductService(self.database)
        character = render.emit_character_detail(VERSION, static_only, "1105")
        self.assertIsNone(character["capability"]["skills_with_m14_row"])
        self.assertTrue(all(s["m14_execution_eligibility"] is None for s in character["skills"]))
        self.assertEqual(character["memosprite"], {"present": False})
        monster = render.emit_monster_detail(VERSION, self.service, "100202001")
        self.assertEqual(monster["runtime_support"]["evidence_scope"], "FAMILY_LEVEL_ONLY")
        self.assertIsNone(monster["context"]["level"])
        self.assertIsNone(monster["context"]["formation"])
        self.assertEqual(monster["identity"]["resolved_kind"], "MONSTER_VARIANT")

    def test_p4_reports_return_verbatim_and_validate_existing_packages(self):
        package = ScenarioCompiler(self.database).compile(_request("p5a-free"))
        authority = ScenarioSupportReporter(self.database, registry=self.registry).build(package)
        with patch.object(ScenarioSupportReporter, "build", return_value=authority):
            self.assertIs(render.emit_scenario_support_report(VERSION, self.database, package, registry=self.registry), authority)
        self.assertEqual(render.emit_scenario_support_report(VERSION, self.database, package, registry=self.registry), authority)
        with self.assertRaises(ValueError):
            render.emit_scenario_support_report(VERSION, self.database, {"schema": "scenario_package/1"}, registry=self.registry)
        with self.assertRaises(ValueError):
            render.emit_scenario_support_report(VERSION, self.database, package, registry=None)
        invalid = deepcopy(package)
        invalid["rules"]["rng_seed"] = 99
        with self.assertRaises(ValueError):
            render.emit_scenario_support_report(VERSION, self.database, invalid, registry=self.registry)

    def test_product_rendering_reads_no_m13_registry_file(self):
        observed = []
        original = Path.open
        def record_open(path, *args, **kwargs):
            observed.append(path.as_posix())
            return original(path, *args, **kwargs)
        package = ScenarioCompiler(self.database).compile(_request("p5a-no-raw"))
        with patch.object(Path, "open", record_open):
            render.emit_character_detail(VERSION, self.service, "1105")
            render.emit_monster_detail(VERSION, self.service, "1002020")
            render.emit_stage_detail(VERSION, self.service, "420101")
            render.emit_encounter_detail(VERSION, self.service, "boss:3001:30011:event_id_list1:0")
            render.emit_scenario_support_report(VERSION, self.database, package, registry=self.registry)
        self.assertFalse(any("registry" in path.lower() for path in observed), observed)

    def test_chunking_is_deterministic_complete_and_does_not_split_documents(self):
        documents = [self.service.get_character(key) for key in ("1105", "1409", "1508")]
        first = pack_details(VERSION, "characters", documents, chunk_bytes=50000)
        self.assertEqual(first, pack_details(VERSION, "characters", documents, chunk_bytes=50000))
        index, files = first
        decoded = [d for payload in files.values() for d in json.loads(payload)["documents"]]
        self.assertEqual(decoded, documents)
        self.assertEqual(set(index["locations"]), {"1105", "1409", "1508"})
        for chunk in index["chunks"]:
            self.assertEqual(chunk["sha256"], sha256(files[chunk["location"]]).hexdigest())
            if chunk["size_bytes"] > 50000:
                self.assertTrue(chunk["oversize_single_document"])
                self.assertEqual(chunk["document_count"], 1)
        with self.assertRaises(ValueError):
            pack_details(VERSION, "characters", [documents[0], documents[0]])

    def test_generated_transport_has_all_keys_and_p4_examples_are_byte_identical(self):
        root = json.loads((STATIC / "catalog.json").read_text(encoding="utf-8"))
        for name in render.COLLECTIONS:
            catalog = json.loads((STATIC / root["collections"][name]["catalog_location"]).read_text(encoding="utf-8"))
            index = json.loads((STATIC / root["collections"][name]["detail_index_location"]).read_text(encoding="utf-8"))
            keys = [row[render.KEY_FIELDS[name]] for row in catalog["rows"]]
            self.assertEqual(set(keys), set(index["locations"]))
            self.assertEqual(len(keys), root["counts"][name])
            for chunk in index["chunks"]:
                payload = (STATIC / chunk["location"]).read_bytes()
                self.assertEqual(sha256(payload).hexdigest(), chunk["sha256"])
                self.assertLessEqual(len(payload), index["chunk_target_bytes"])
                self.assertEqual(len(json.loads(payload)["documents"]), chunk["document_count"])
        for example in root["example_support_reports"]:
            payload = (STATIC / example["location"]).read_bytes()
            self.assertTrue(example["examples_only"])
            self.assertFalse(example["production_default"])
            self.assertEqual(sha256(payload).hexdigest(), example["sha256"])
            self.assertEqual(payload, (ROOT / f'tmp/audit/p4_example_{example["key"]}.json').read_bytes())


if __name__ == "__main__":
    unittest.main()
