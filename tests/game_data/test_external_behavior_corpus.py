"""Recursive-lift integrity tests for the canonical external behavior corpus."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.external_behavior import _modifier_definitions


class ExternalBehaviorCorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
        cls.corpus = json.loads(path.read_text(encoding="utf-8"))

    def test_no_modifier_callback_or_template_remains_raw_only(self) -> None:
        for record in self.corpus["records"]:
            raw_unknown = record.get("raw_unknown", {})
            self.assertNotIn("_CallbackList", raw_unknown, record["behavior_id"])
            self.assertNotIn("TaskListTemplate", raw_unknown, record["behavior_id"])
            self.assertNotIn("DynamicValues", raw_unknown, record["behavior_id"])

    def test_template_invocations_resolve_to_template_definitions(self) -> None:
        template_ids = {
            template["template_id"]
            for record in self.corpus["records"]
            for template in record.get("template_definitions", [])
        }

        def walk(operations):
            for operation in operations:
                if isinstance(operation, dict):
                    yield operation
                    for group in operation.get("children", []):
                        if isinstance(group, dict):
                            yield from walk(group.get("operations", []))

        invocations = []
        for record in self.corpus["records"]:
            for entrypoint in record.get("entrypoints", []):
                for operation in walk(entrypoint.get("operations", [])):
                    if operation.get("template_ref") is not None:
                        invocations.append(operation)
            for template in record.get("template_definitions", []):
                for operation in walk(template.get("operations", [])):
                    if operation.get("template_ref") is not None:
                        invocations.append(operation)
        self.assertGreaterEqual(len(invocations), 1)
        for operation in invocations:
            self.assertIn(operation["template_ref"], template_ids, operation["operation_id"])

    def test_singular_predicates_are_lifted_as_ast_nodes(self) -> None:
        def walk(operations):
            for operation in operations:
                if isinstance(operation, dict):
                    yield operation
                    for group in operation.get("children", []):
                        if isinstance(group, dict):
                            yield from walk(group.get("operations", []))

        predicate_count = 0
        for record in self.corpus["records"]:
            for entrypoint in record.get("entrypoints", []):
                predicate_count += sum(
                    operation.get("node_role") == "PREDICATE_AST"
                    for operation in walk(entrypoint.get("operations", []))
                )
            for template in record.get("template_definitions", []):
                predicate_count += sum(
                    operation.get("node_role") == "PREDICATE_AST"
                    for operation in walk(template.get("operations", []))
                )
        self.assertEqual(predicate_count, 515)

    def test_embedded_modifier_map_is_preserved_as_definition_data(self) -> None:
        definitions = _modifier_definitions({
            "Modifiers": {
                "MEmbedded": {
                    "Stacking": "ReplaceByCaster",
                    "DynamicValues": {"Floats": {"1": {"ReadInfo": {"Type": "None"}}}},
                }
            }
        })
        self.assertEqual(definitions[0]["name"], "MEmbedded")
        self.assertEqual(definitions[0]["source_field_path"], "Modifiers.MEmbedded")
        self.assertEqual(definitions[0]["payload"]["Stacking"], "ReplaceByCaster")
        self.assertIn("DynamicValues", definitions[0]["payload"])


if __name__ == "__main__":
    unittest.main()
