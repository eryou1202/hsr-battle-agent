# -*- coding: utf-8 -*-
"""Generate data/sandbox/action_execution_runtime_06_report.json.

The script runs the current battle + unpacker + cross-version regression
suites, refuses to write a PASS report on any failure, then records the
catalog-driven registry contents, the Action Execution Bridge 06 execution
chains and the cross-layer composition test built from real recovered
semantics only (ExecutionContext -> Target primitive -> Action primitive).
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
    / "action_execution_bridge_06.json"
)
OUTPUT_PATH = (
    REPO / "data" / "sandbox" / "action_execution_runtime_06_report.json"
)
COMPOSITION_TESTS = (
    {
        "name": "TestCrossLayerComposition.test_context_target_to_action_write_chain",
        "path": "tests/battle_sandbox/test_action_execution_runtime_06.py",
        "chain": [
            "battle.ir.target.select_task_action_target",
            "battle.ir.action.task_executor_init",
            "battle.ir.action.task_begin_select_single_target",
        ],
        "invocation_path": "PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry",
        "note": "real recovered chain shape: ExecutionContext task_action_target -> "
        "Target primitive (Batch 05) -> Action primitive -> selected_target write "
        "+ next_phase Tick; no predicate/fixpoint link was forced because the "
        "accepted leaves contain none.",
    },
    {
        "name": "TestObsoleteActionChainThroughExecutor.test_full_empty_action_chain",
        "path": "tests/battle_sandbox/test_action_execution_runtime_06.py",
        "chain": [
            "battle.ir.action.task_executor_init",
            "battle.ir.action.task_begin_immediate_success",
            "battle.ir.action.task_state_read",
            "battle.ir.action.task_reset_ready",
        ],
        "invocation_path": "PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry",
        "note": "PRIMARY E4 chain: RPG.GameCore.Obsolete -> generated executor -> "
        "TaskState.Success observable result; BattleState untouched.",
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
            "action_execution_runtime_06_report: "
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
                "batch": "action_execution_bridge_06"
                if spec.primitive_id.startswith("battle.ir.action.")
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
    for row in batch.get("deferred_effects", []):
        deferred.append(
            {
                "effect_id": row.get("effect_id"),
                "entry": row.get("entry"),
                "native_rva": row.get("native_rva"),
                "classification": row.get("classification"),
                "dependency": row.get("dependency"),
                "deferral": "not forced: persistent BattleState / component / "
                "damage / event semantics require future semantic batches",
            }
        )

    report = {
        "schema": "battle_sandbox_runtime_report/1",
        "sandbox_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "battle_state_schema_version": BATTLE_STATE_SCHEMA_VERSION,
        "trace_schema": TRACE_SCHEMA,
        "game_semantic_version": catalog.game_version,
        "final_status": "BATTLE_SANDBOX = ACTION_EXECUTION_RUNTIME_06_PROOF",
        "semantic_batch": {
            "path": "data/semantics/4.4.54/action_execution_bridge_06.json",
            "batch_id": batch["batch_id"],
            "accepted_primitives": len(batch["primitives"]),
            "runtime_layer_name": batch["runtime_layer_name"],
        },
        "implemented_primitives": implemented,
        "execution_chains": batch.get("execution_chains", []),
        "action_config_bridge": batch.get("config_runtime_bridge", {}),
        "context_reads": batch.get("context_reads", []),
        "context_writes": batch.get("context_writes", []),
        "state_reads": batch.get("state_reads", []),
        "state_writes": batch.get("state_writes", []),
        "execution_context_additions": [],
        "battle_state_additions": [],
        "task_state_model": batch.get("task_state_model", {}),
        "deferred_effects": deferred,
        "semantic_dependencies": batch.get("semantic_dependencies", []),
        "composition_tests": [
            {**item, "status": "PASS"} for item in COMPOSITION_TESTS
        ],
        "semantic_artifacts": semantic_sources,
        "test_count": test_count,
        "test_pass": test_pass,
        "representation_conflicts": [],
        "rng": {
            "client_rng_algorithm": CLIENT_RNG_ALGORITHM,
            "sandbox_rng": SANDBOX_RNG,
            "sandbox_rng_algorithm": SANDBOX_RNG_ALGORITHM,
        },
        "not_implemented_surfaces": [
            "legal_actions",
            "step",
            "is_terminal",
            "higher-level ActionExecutor (not proven by native evidence)",
            "TaskContext.EvaluateTarget registry dispatcher",
            "SequenceConfig child-task step helper internals",
            "TurnBasedGameMode persistent field identities",
            "Modifier",
            "Damage",
            "DOT",
            "Event listener / NotifyManager",
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
