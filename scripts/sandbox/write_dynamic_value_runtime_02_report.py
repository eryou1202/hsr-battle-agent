# -*- coding: utf-8 -*-
"""Generate data/sandbox/dynamic_value_runtime_02_report.json from real inputs.

The script discovers and runs the current battle regression suites, then
writes the machine report only when all of them pass.  Implemented primitives
are taken from the frozen default registry (catalog-driven bootstrap), never
hardcoded by name.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.catalog import load_semantic_catalog  # noqa: E402
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.rng import (  # noqa: E402
    CLIENT_RNG_ALGORITHM,
    SANDBOX_RNG,
    SANDBOX_RNG_ALGORITHM,
)
from hsr_battle_agent.battle_sandbox.snapshot import SNAPSHOT_SCHEMA_VERSION  # noqa: E402
from hsr_battle_agent.battle_sandbox.state import BATTLE_STATE_SCHEMA_VERSION  # noqa: E402
from hsr_battle_agent.battle_sandbox.trace import TRACE_SCHEMA  # noqa: E402

TEST_DIRS = (
    REPO / "tests" / "battle_ir",
    REPO / "tests" / "battle_runtime",
    REPO / "tests" / "battle_sandbox",
    REPO / "tests" / "unpacker",
    REPO / "tests" / "cross_version",
)
OUTPUT_PATH = REPO / "data" / "sandbox" / "dynamic_value_runtime_02_report.json"


def main() -> int:
    suite = unittest.TestSuite()
    for directory in TEST_DIRS:
        top_level_dir = REPO if (directory / "__init__.py").is_file() else directory
        suite.addTests(
            unittest.defaultTestLoader.discover(
                start_dir=str(directory),
                top_level_dir=str(top_level_dir),
                pattern="test_*.py",
            )
        )

    result = unittest.TestResult()
    suite.run(result)
    test_count = result.testsRun
    test_pass = test_count - len(result.failures) - len(result.errors)

    if result.failures or result.errors:
        print(
            f"dynamic_value_runtime_02_report: {len(result.failures)} failure(s), "
            f"{len(result.errors)} error(s); refusing to write PASS report"
        )
        return 1

    registry = PrimitiveRegistry.create_default()
    implemented = []
    for primitive_id in registry.known_primitive_ids:
        registered = registry.resolve(primitive_id)
        spec = registered.spec
        implemented.append(
            {
                "primitive_id": spec.primitive_id,
                "semantic_name": spec.semantic_name,
                "result": spec.result,
                "determinism": spec.determinism,
                "context_reads": list(spec.context_reads),
                "context_writes": list(spec.context_writes),
                "provenance_ref": registered.provenance_ref,
            }
        )

    catalog = load_semantic_catalog()
    semantic_sources = []
    for entry in catalog.artifacts:
        semantic_sources.append(
            {
                "path": entry.path,
                "schema": entry.schema,
                "sha256": entry.sha256,
                "enabled": entry.enabled,
            }
        )

    batch = json.loads(
        (REPO / "data" / "semantics" / "4.4.54" / "dynamic_value_batch_02.json").read_text(
            encoding="utf-8"
        )
    )
    skipped = [
        {
            "method_index": row["method_index"],
            "name": row["name"],
            "native_rva": row["native_rva"],
            "classification": row["classification"],
            "reason": row["reason"],
        }
        for row in batch["skipped_candidates"]
    ]

    report = {
        "schema": "battle_sandbox_runtime_report/1",
        "sandbox_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "battle_state_schema_version": BATTLE_STATE_SCHEMA_VERSION,
        "trace_schema": TRACE_SCHEMA,
        "game_semantic_version": catalog.game_version,
        "final_status": "BATTLE_SANDBOX = DYNAMIC_VALUE_RUNTIME_02_PROOF",
        "implemented_primitives": implemented,
        "semantic_artifacts": semantic_sources,
        "test_count": test_count,
        "test_pass": test_pass,
        "skipped_primitives": skipped,
        "representation_conflicts": batch.get("representation_conflicts", []),
        "rng": {
            "client_rng_algorithm": CLIENT_RNG_ALGORITHM,
            "sandbox_rng": SANDBOX_RNG,
            "sandbox_rng_algorithm": SANDBOX_RNG_ALGORITHM,
        },
        "not_implemented_surfaces": [
            "legal_actions",
            "step",
            "is_terminal",
        ],
        "known_unknowns": batch.get("unknowns", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {OUTPUT_PATH.relative_to(REPO)} "
        f"(tests={test_count}, pass={test_pass}, primitives={len(implemented)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
