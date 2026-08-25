"""Publish the corpus coverage baseline from the canonical behavior corpus.

This baseline reports only captured/canonicalized recursive nodes.  Executable
and golden-tested coverage are always reported from the compiler report; this
file intentionally never infers either status from corpus normalization.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from hsr_battle_agent.game_data.nanoka_content import write_json


def walk(operations: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for operation in operations:
        if isinstance(operation, Mapping):
            yield operation
            for group in operation.get("children", []):
                if isinstance(group, Mapping):
                    yield from walk(item for item in group.get("operations", []) if isinstance(item, Mapping))


def main(corpus_path: Path, output: Path) -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    records = corpus["records"]
    entrypoints = 0
    modifier_callback_entrypoints = 0
    root_entrypoint_operations = 0
    template_definitions = 0
    root_template_operations = 0
    dynamic_value_definitions = 0
    operation_nodes = 0
    predicate_ast_nodes = 0
    statuses: Counter[str] = Counter()
    by_owner: dict[str, dict[str, Any]] = {}
    behavior_bearing_records = 0
    static_definition_records = 0
    for record in records:
        owner = str(record.get("owner_kind", "ExternalBehavior"))
        bucket = by_owner.setdefault(
            owner,
            {"captured": 0, "behavior_bearing": 0, "static_definition_only": 0, "canonicalized": 0, "compiled": 0, "golden_tested": 0, "total_game_denominator": "UNKNOWN"},
        )
        bucket["captured"] += 1
        bucket["canonicalized"] += 1
        has_behavior = any(
            isinstance(entrypoint, Mapping) and len(entrypoint.get("operations", [])) > 0
            for entrypoint in record.get("entrypoints", [])
        ) or any(
            isinstance(template, Mapping) and len(template.get("operations", [])) > 0
            for template in record.get("template_definitions", [])
        )
        if has_behavior:
            behavior_bearing_records += 1
            bucket["behavior_bearing"] += 1
        else:
            static_definition_records += 1
            bucket["static_definition_only"] += 1
        for entrypoint in record.get("entrypoints", []):
            if not isinstance(entrypoint, Mapping):
                continue
            entrypoints += 1
            if str(entrypoint.get("event", "")).startswith("MODIFIER_CALLBACK"):
                modifier_callback_entrypoints += 1
            operations = entrypoint.get("operations", [])
            root_entrypoint_operations += len(operations)
            for operation in walk(item for item in operations if isinstance(item, Mapping)):
                if operation.get("node_role") == "PREDICATE_AST":
                    predicate_ast_nodes += 1
                else:
                    operation_nodes += 1
                statuses[str(operation.get("semantic_status", "OPAQUE"))] += 1
        for template in record.get("template_definitions", []):
            if not isinstance(template, Mapping):
                continue
            template_definitions += 1
            operations = template.get("operations", [])
            root_template_operations += len(operations)
            for operation in walk(item for item in operations if isinstance(item, Mapping)):
                if operation.get("node_role") == "PREDICATE_AST":
                    predicate_ast_nodes += 1
                else:
                    operation_nodes += 1
                statuses[str(operation.get("semantic_status", "OPAQUE"))] += 1
        dynamic_value_definitions += len(record.get("dynamic_value_definitions", []))
    for absent in ("Trace", "Eidolon", "LightCone", "RelicSet"):
        by_owner.setdefault(absent, {
            "captured": 0, "behavior_bearing": 0, "static_definition_only": 0, "canonicalized": 0, "compiled": 0, "golden_tested": 0, "total_game_denominator": "UNKNOWN",
        })
    payload = {
        "report_id": "COVERAGE-BASELINE-001",
        "game_version": "4.4.54",
        "status": "RECURSIVE_EXTERNAL_BEHAVIOR_BASELINE",
        "input_corpus": {
            "path": str(corpus_path),
            "corpus_sha256": corpus.get("corpus_sha256"),
            "source": corpus.get("source"),
            "source_commit": corpus.get("source_commit"),
            "version_relation": "CLOSE_4.4.0_TO_4.4.54",
        },
        "counting_rule": "These are captured external behavior records, not the total 4.4.54 game denominator. behavior_bearing records contain at least one operational entrypoint or TaskListTemplate; static_definition_only records are canonicalized reference/configuration records without operational behavior and are not part of the behavior denominator. Recursive semantic nodes include entrypoint operations, predicate AST nodes and TaskListTemplate definitions; DynamicValues definitions are preserved as definition records, not operation nodes. Neither compiled nor golden coverage is implied until a generic compiler/kernel executes them without behavior-affecting opaque nodes.",
        "behavior_records": {
            "captured": len(records),
            "canonicalized": len(records),
            "behavior_bearing": behavior_bearing_records,
            "static_definition_only": static_definition_records,
            "semantic_modelled": 0,
            "compiled": 0,
            "golden_tested": 0,
            "explicitly_unsupported": 0,
            "total_game_denominator": "UNKNOWN",
        },
        "by_owner_kind": dict(sorted(by_owner.items())),
        "semantic_nodes": {
            "recursive_total": operation_nodes + predicate_ast_nodes,
            "operation_nodes": operation_nodes,
            "predicate_ast_nodes": predicate_ast_nodes,
            "root_entrypoint_operations": root_entrypoint_operations,
            "entrypoints": entrypoints,
            "modifier_callback_entrypoints": modifier_callback_entrypoints,
            "template_definitions": template_definitions,
            "root_template_operations": root_template_operations,
            "dynamic_value_definitions": dynamic_value_definitions,
            "semantic_status": dict(sorted(statuses.items())),
            "compiled": 0,
            "golden_tested": 0,
        },
        "triage_artifact": "data/semantics/4.4.54/full_reconstruction/operation_risk_triage_001.json",
        "next_coverage_gain_target": "COMPILER-VERTICAL-001: compile a strictly no-blocker subset through the static ScenarioCompiler and reference event/Modifier contracts. The 619/122/490 counts were superseded by this generator output and must not be used.",
    }
    write_json(output, payload)
    print(json.dumps({
        "output_path": str(output),
        "behavior_records": payload["behavior_records"],
        "semantic_nodes": payload["semantic_nodes"],
    }, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/coverage_baseline_001.json"))
    arguments = parser.parse_args()
    main(arguments.corpus, arguments.output)
