from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler
from hsr_battle_agent.game_data.reference_execution import SemanticExecutor


CORPUS_PATH = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")


def walk(values):
    for value in values:
        yield value
        for group in value.get("children", []):
            yield from walk(group.get("operations", []))


class ExecutableHandlerEligibilityTest(unittest.TestCase):
    def test_every_compiler_executable_kind_has_a_handler_context_contract(self) -> None:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        report = BehaviorCompiler().compile_corpus(corpus)
        kinds = set()
        for record in report["records"]:
            for entrypoint in record.get("entrypoints", []):
                kinds.update(operation["kind"] for operation in walk(entrypoint.get("operations", [])) if operation.get("disposition") == "EXECUTABLE_REFERENCE")
            for template in record.get("template_definitions", []):
                kinds.update(operation["kind"] for operation in walk(template.get("operations", [])) if operation.get("disposition") == "EXECUTABLE_REFERENCE")
        self.assertTrue(kinds)
        self.assertFalse(kinds - set(SemanticExecutor.executable_operation_contract()))


if __name__ == "__main__":
    unittest.main()
