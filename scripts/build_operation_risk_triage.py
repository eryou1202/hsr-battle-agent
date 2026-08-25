"""Classify non-compiled canonical operations by reconstruction risk."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from hsr_battle_agent.game_data.nanoka_content import write_json


DEFAULT_CORPUS = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
DEFAULT_OUTPUT = Path("data/semantics/4.4.54/full_reconstruction/operation_risk_triage_001.json")


def walk(operations: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for operation in operations:
        yield operation
        for group in operation.get("children", []):
            if isinstance(group, Mapping):
                yield from walk(item for item in group.get("operations", []) if isinstance(item, Mapping))


def main(corpus_path: Path, output: Path) -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in corpus["records"]:
        for entrypoint in record["entrypoints"]:
            for operation in walk(item for item in entrypoint["operations"] if isinstance(item, Mapping)):
                status = str(operation.get("semantic_status", "OPAQUE"))
                risk = str(operation.get("gating_risk", "UNKNOWN"))
                if status == "MODELLED" or (status == "PRESENTATION" and risk == "NONE"):
                    continue
                key = (str(operation.get("source_type", "UNKNOWN")), str(operation.get("kind", "OPAQUE")), str(operation.get("semantic_importance", "P1_UNCLASSIFIED_SEMANTIC")))
                bucket = grouped.setdefault(key, {"source_type": key[0], "canonical_kind": key[1], "importance": key[2], "count": 0, "semantic_statuses": set(), "gating_risks": set(), "sample_operation_ids": []})
                bucket["count"] += 1
                bucket["semantic_statuses"].add(status)
                bucket["gating_risks"].add(risk)
                if len(bucket["sample_operation_ids"]) < 3:
                    bucket["sample_operation_ids"].append(operation["operation_id"])
    entries = []
    for bucket in grouped.values():
        bucket["semantic_statuses"] = sorted(bucket["semantic_statuses"])
        bucket["gating_risks"] = sorted(bucket["gating_risks"])
        entries.append(bucket)
    entries.sort(key=lambda item: (item["importance"], -item["count"], item["source_type"]))
    by_importance: dict[str, int] = defaultdict(int)
    for entry in entries:
        by_importance[entry["importance"]] += entry["count"]
    write_json(output, {
        "report_id": "OPERATION-RISK-TRIAGE-001",
        "game_version": "4.4.54",
        "input_corpus_sha256": corpus["corpus_sha256"],
        "status": "RECURSIVE_INITIAL_CORPUS_TRIAGED",
        "counting_rule": "Counts are recursively lifted operation/predicate nodes in the current reviewed external slice, not a complete game denominator.",
        "historical_note": "The original entrypoint-only scan reported 22 OPAQUE nodes. Recursive lifting replaces that misleading count; every behavior-affecting OPAQUE/REQUIRES_PACKET node is classified here and remains non-executable.",
        "compiler_policy": {"OPAQUE": "hard compile failure; never a no-op", "REQUIRES_PACKET": "hard compile failure until its named packet/primitive exists", "PRESENTATION_GATING_RISK": "hard compile failure until proven non-gating", "PRESENTATION_ONLY": "may be headlessly omitted only with explicit compiler trace"},
        "by_importance": dict(sorted(by_importance.items())),
        "entries": entries,
    })
    print(json.dumps({"output_path": str(output), "groups": len(entries), "by_importance": dict(by_importance)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.corpus, arguments.output)
