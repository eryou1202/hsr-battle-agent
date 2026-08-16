# -*- coding: utf-8 -*-
"""Generate data/sandbox/target_selector_runtime_05_report.json.

The script runs the current battle + unpacker + cross-version regression
suites, refuses to write a PASS report on any failure, then records the
catalog-driven registry contents, the Target Selector Batch 05 selector
chains and the executor-only composition test built from real recovered
semantics only.
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
SEMANTIC_BATCH_PATH = (
    REPO
    / "data"
    / "semantics"
    / "4.4.54"
    / "target_selector_batch_05.json"
)
OUTPUT_PATH = (
    REPO / "data" / "sandbox" / "target_selector_runtime_05_report.json"
)
COMPOSITION_TESTS = (
    {
        "name": "TestCrossBatchComposition.test_selector_to_collapse_composition_chain",
        "path": "tests/battle_sandbox/test_target_selector_runtime_05.py",
        "chain": [
            "battle.ir.target.select_caster",
            "battle.ir.target.collapse_required_single_or_null",
        ],
        "invocation_path": "PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry",
        "note": "no predicate/fixpoint cross-batch link was forced: the recovered "
        "selector leaves contain no predicate call, so the real meaningful chain "
        "is ExecutionContext -> selector -> EntityRef.",
    },
)


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
            "target_selector_runtime_05_report: "
            f"{len(result.failures)} failure(s), {len(result.errors)} error(s); "
            "refusing to write PASS report"
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
                "batch": "target_selector_batch_05"
                if spec.primitive_id.startswith(("battle.ir.target.", "battle.ir.entity."))
                else None,
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

    batch = json.loads(SEMANTIC_BATCH_PATH.read_text(encoding="utf-8"))
    deferred = []
    for row in batch.get("deferred_candidates", []):
        deferred.append(
            {
                "runtime_type": row.get("runtime_type"),
                "method": row.get("method"),
                "method_index": row.get("method_index"),
                "native_rva": row.get("native_rva"),
                "classification": row.get("classification"),
                "reason": row.get("reason"),
                "deferral": "multi-target / filter / dispatcher semantics were not "
                "forced; single-entity selector leaves were recovered instead",
            }
        )

    report = {
        "schema": "battle_sandbox_runtime_report/1",
        "sandbox_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "battle_state_schema_version": BATTLE_STATE_SCHEMA_VERSION,
        "trace_schema": TRACE_SCHEMA,
        "game_semantic_version": catalog.game_version,
        "final_status": "BATTLE_SANDBOX = TARGET_SELECTOR_RUNTIME_05_PROOF",
        "semantic_batch": {
            "path": "data/semantics/4.4.54/target_selector_batch_05.json",
            "batch_id": batch["batch_id"],
            "accepted_primitives": len(batch["primitives"]),
        },
        "implemented_primitives": implemented,
        "selector_chains": batch.get("selector_chains", []),
        "execution_context_additions": [
            {
                "field": "task_action_target",
                "native_source": "TaskContext [+0x48]",
                "snapshot": "transient (not captured)",
                "state_hash": "excluded (single-frame execution input)",
            },
            {
                "field": "owner_entity",
                "native_source": "TaskContext [+0x70]",
                "snapshot": "transient (not captured)",
                "state_hash": "excluded (single-frame execution input)",
            },
            {
                "field": "caster_entity",
                "native_source": "canonical materialization of TaskContext.get_CasterEntity",
                "snapshot": "transient (not captured)",
                "state_hash": "excluded (single-frame execution input)",
            },
        ],
        "battle_state_additions": [],
        "ordering_status": "ORDERED_APPEND",
        "duplicate_status": "PRESERVED_NO_DEDUPLICATION",
        "target_list_model": batch.get("target_list_model", {}),
        "entity_identity": batch.get("entity_identity", {}),
        "deferred_selectors": deferred,
        "semantic_dependencies": batch.get("semantic_dependencies", []),
        "composition_tests": [
            {**item, "status": "PASS"} for item in COMPOSITION_TESTS
        ],
        "semantic_artifacts": semantic_sources,
        "test_count": test_count,
        "test_pass": test_pass,
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
            "TaskContext.EvaluateTarget registry dispatcher",
            "multi-target TargetFetch*/TargetMap*/TargetSort* runtime leaves",
            "TargetQuery / EntityManager roster query",
            "unselectable predicate semantics",
            "Modifier",
            "Damage",
            "DOT",
            "Event listener",
            "Turn / AV",
            "HP / ATK / DEF state",
            "Black Swan full simulation",
            "Planner",
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
        f"(tests={test_count}, pass={test_pass}, "
        f"primitives={len(implemented)})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
