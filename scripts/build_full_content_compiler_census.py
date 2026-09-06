"""Publish a full-content compiler census with actionable failure clusters.

The census is deliberately source/corpus scoped: it measures only the pinned
family payloads captured so far, never substitutes static entity totals for an
effect-bearing behavior denominator.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from hsr_battle_agent.game_data.nanoka_content import write_json


def walk(operations: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for operation in operations:
        if not isinstance(operation, Mapping):
            continue
        yield operation
        for group in operation.get("children", []):
            if isinstance(group, Mapping):
                yield from walk(group.get("operations", []))


def record_operations(record: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for entrypoint in record.get("entrypoints", []):
        if isinstance(entrypoint, Mapping):
            yield from walk(entrypoint.get("operations", []))
    for template in record.get("template_definitions", []):
        if isinstance(template, Mapping):
            yield from walk(template.get("operations", []))


parser = argparse.ArgumentParser()
parser.add_argument("--corpus", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_corpus_001.json"))
parser.add_argument("--compiler-report", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_compiler_report_001.json"))
parser.add_argument("--mapping", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_mapping_001.json"))
parser.add_argument("--modifier-catalog", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_modifier_definition_catalog_001.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_compiler_census_001.json"))
arguments = parser.parse_args()

corpus = json.loads(arguments.corpus.read_text(encoding="utf-8"))
report = json.loads(arguments.compiler_report.read_text(encoding="utf-8"))
mapping = json.loads(arguments.mapping.read_text(encoding="utf-8"))
modifier_catalog = json.loads(arguments.modifier_catalog.read_text(encoding="utf-8"))
links_by_behavior = {
    str(row.get("behavior_id")): row
    for row in mapping.get("record_links", [])
    if isinstance(row, Mapping)
}

clusters: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
operation_status: dict[str, int] = defaultdict(int)
for record in report.get("records", []):
    if not isinstance(record, Mapping):
        continue
    behavior_id = str(record.get("behavior_id"))
    link = links_by_behavior.get(behavior_id, {})
    static_link = link.get("static_link", {}) if isinstance(link, Mapping) else {}
    static_family = str(static_link.get("static_family") or "GLOBAL_OR_UNMAPPED")
    owner_kind = str(record.get("owner_kind", "UNKNOWN"))
    for operation in record_operations(record):
        disposition = str(operation.get("disposition", "UNKNOWN"))
        operation_status[disposition] += 1
        if disposition in {"EXECUTABLE_REFERENCE", "HEADLESS_PRESENTATION_OMITTED"}:
            continue
        blocker = str(operation.get("reference_execution_blocker") or "NO_EXECUTABLE_LOWERING")
        key = (
            str(operation.get("kind", "UNKNOWN")),
            str(operation.get("source_type", "UNKNOWN")),
            owner_kind,
            static_family,
            blocker,
        )
        cluster = clusters.setdefault(key, {
            "operation_kind": key[0],
            "source_type": key[1],
            "owner_kind": key[2],
            "static_family": key[3],
            "blocking_dependency": key[4],
            "operation_count": 0,
            "behavior_ids": set(),
            "operation_ids": [],
        })
        cluster["operation_count"] += 1
        cluster["behavior_ids"].add(behavior_id)
        if len(cluster["operation_ids"]) < 12:
            cluster["operation_ids"].append(operation.get("operation_id"))

failure_clusters = []
for cluster in clusters.values():
    behavior_ids = sorted(cluster.pop("behavior_ids"))
    cluster["unlockable_record_count"] = len(behavior_ids)
    cluster["sample_behavior_ids"] = behavior_ids[:12]
    cluster["operation_ids"] = sorted(str(value) for value in cluster["operation_ids"])
    failure_clusters.append(cluster)
failure_clusters.sort(key=lambda row: (
    -int(row["unlockable_record_count"]),
    -int(row["operation_count"]),
    str(row["operation_kind"]),
    str(row["source_type"]),
))

coverage = report.get("coverage", {})
payload = {
    "report_id": "FULL-CONTENT-COMPILER-CENSUS-001",
    "game_version": corpus.get("game_version"),
    "status": "PINNED_FAMILY_CORPUS_FULL_CONTENT_BASELINE_NOT_FULL_GAME_COMPLETION",
    "inputs": {
        "corpus_path": str(arguments.corpus).replace("\\", "/"),
        "corpus_sha256": corpus.get("corpus_sha256"),
        "compiler_report_path": str(arguments.compiler_report).replace("\\", "/"),
        "compiler_report_sha256": report.get("report_sha256"),
        "mapping_path": str(arguments.mapping).replace("\\", "/"),
        "mapping_sha256": mapping.get("report_sha256"),
        "modifier_catalog_path": str(arguments.modifier_catalog).replace("\\", "/"),
        "modifier_catalog_sha256": modifier_catalog.get("catalog_sha256"),
    },
    "counting_rule": (
        "The denominator is behavior-bearing Canonical BehaviorRecords from the currently captured pinned source families. "
        "It is not the complete 4.4.54 game behavior denominator, and static entity counts are reported separately only as mapping coverage."
    ),
    "coverage": coverage,
    "operation_dispositions": dict(sorted(operation_status.items())),
    "modifier_definition_catalog": {
        key: modifier_catalog.get(key)
        for key in (
            "definition_candidate_count",
            "unique_definition_name_count",
            "equivalent_duplicate_count",
            "true_conflict_count",
            "supported_catalog_definition_count",
            "unsupported_definition_count",
            "definitions_by_stacking",
        )
    },
    "static_family_coverage": mapping.get("family_coverage_table", []),
    "failure_clusters": failure_clusters,
    "next_selection_rule": "Select a generic primitive by unlockable_record_count × family breadth × architecture importance ÷ semantic uncertainty; defer narrow unproven shapes.",
}
write_json(arguments.output, payload)
print(json.dumps({
    "output_path": str(arguments.output),
    "coverage": coverage,
    "top_failure_clusters": failure_clusters[:12],
}, ensure_ascii=False, sort_keys=True))
