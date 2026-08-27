"""Audit compiler executable eligibility against SemanticExecutor support.

This checks a deliberately narrow invariant: a compiled
``EXECUTABLE_REFERENCE`` operation kind must have a concrete generic executor
handler and a declared context contract.  It does not claim that every record
can run without scenario inputs; missing declared context remains a hard
execution error by design.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from hsr_battle_agent.game_data.nanoka_content import stable_hash, write_json
from hsr_battle_agent.game_data.reference_execution import SemanticExecutor


def walk(values: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for value in values:
        yield value
        for group in value.get("children", []):
            if isinstance(group, Mapping):
                yield from walk(item for item in group.get("operations", []) if isinstance(item, Mapping))


def main(report_path: Path, output: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    for record in report.get("records", []):
        for entrypoint in record.get("entrypoints", []):
            for operation in walk(item for item in entrypoint.get("operations", []) if isinstance(item, Mapping)):
                if operation.get("disposition") == "EXECUTABLE_REFERENCE":
                    counts[str(operation.get("kind"))] += 1
        for template in record.get("template_definitions", []):
            for operation in walk(item for item in template.get("operations", []) if isinstance(item, Mapping)):
                if operation.get("disposition") == "EXECUTABLE_REFERENCE":
                    counts[str(operation.get("kind"))] += 1
    contract = SemanticExecutor.executable_operation_contract()
    unhandled = sorted(kind for kind in counts if kind not in contract)
    payload = {
        "audit_id": "EXECUTOR-HANDLER-ELIGIBILITY-AUDIT-001",
        "game_version": "4.4.54",
        "input_compiler_report_sha256": report.get("report_sha256"),
        "status": "PASS_ALL_EXECUTABLE_KINDS_HAVE_HANDLER_AND_CONTEXT_CONTRACT" if not unhandled else "FAIL_UNHANDLED_EXECUTABLE_KIND",
        "counting_rule": "Counts compiled operations whose disposition is EXECUTABLE_REFERENCE. This audit validates handler and declared-context surface only; it never upgrades source-backed or Golden status.",
        "executable_operation_counts": dict(sorted(counts.items())),
        "executor_context_contract": {kind: list(contract[kind]) for kind in sorted(counts)},
        "unhandled_kinds": unhandled,
        "missing_context_policy": "SemanticExecutor raises SemanticExecutionError when a selected operation is invoked without its declared scenario/context input; no handler supplies fixture defaults.",
    }
    payload["audit_sha256"] = stable_hash(payload)
    write_json(output, payload)
    if unhandled:
        raise SystemExit(f"unhandled executable kinds: {', '.join(unhandled)}")
    print(json.dumps({"output_path": str(output), "status": payload["status"], "counts": payload["executable_operation_counts"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_002.json"))
    parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/executor_handler_eligibility_audit_001.json"))
    arguments = parser.parse_args()
    main(arguments.report, arguments.output)
