# -*- coding: utf-8 -*-
"""Generate data/sandbox/modifier_application_runtime_07_report.json.

The script runs the current battle + unpacker + cross-version regression
suites, refuses to write a PASS report on any failure, then records the
catalog-driven registry contents, the Modifier Application Bridge 07 chain,
the new BattleState.modifier_state_by_entity schema addition and the
state-transition tests built only from recovered semantics.
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
    / "modifier_application_bridge_07.json"
)
OUTPUT_PATH = (
    REPO / "data" / "sandbox" / "modifier_application_runtime_07_report.json"
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
        "note": "regression: Batch 05/06 chain unchanged",
    },
    {
        "name": "TestNormalApplicationThroughExecutor.test_pre_apply_to_post_battle_state_transition",
        "path": "tests/battle_sandbox/test_modifier_application_runtime_07.py",
        "chain": [
            "BattleState v2 (pre)",
            "battle.ir.modifier.apply_modifier_instance",
            "BattleState v2 (post, modifier_state_by_entity)",
        ],
        "invocation_path": "PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry",
        "note": "first real BattleState transition: persistent modifier append",
    },
    {
        "name": "TestNormalApplicationThroughExecutor.test_add_modifier_executor_init_then_task_boundary",
        "path": "tests/battle_sandbox/test_modifier_application_runtime_07.py",
        "chain": [
            "battle.ir.action.add_modifier_executor_init",
            "battle.ir.modifier.add_modifier_task_begin_apply",
        ],
        "invocation_path": "PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry",
        "note": "AddModifier generated executor init -> OnTaskBegin normal-path boundary -> Success + ordered persistent writes",
    },
    {
        "name": "TestNormalApplicationThroughExecutor.test_cross_layer_target_to_modifier_to_persistent_state",
        "path": "tests/battle_sandbox/test_modifier_application_runtime_07.py",
        "chain": [
            "battle.ir.target.select_task_action_target",
            "battle.ir.target.collapse_single_or_null",
            "battle.ir.action.add_modifier_executor_init",
            "battle.ir.modifier.apply_modifier_instance",
        ],
        "invocation_path": "PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry",
        "note": "Action config -> target -> modifier application -> persistent state",
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
            "modifier_application_runtime_07_report: "
            f"{len(result.failures)} failure(s), {len(result.errors)} error(s); "
            "refusing to write PASS report"
        )
        return 1

    registry = PrimitiveRegistry.create_default()
    implemented = []
    for primitive_id in registry.known_primitive_ids:
        registered = registry.resolve(primitive_id)
        spec = registered.spec
        batch = None
        if primitive_id in {
            "battle.ir.action.add_modifier_executor_init",
        } or primitive_id.startswith("battle.ir.modifier."):
            batch = "modifier_application_bridge_07"
        elif primitive_id.startswith("battle.ir.action."):
            batch = "action_execution_bridge_06"
        implemented.append(
            {
                "primitive_id": spec.primitive_id,
                "semantic_name": spec.semantic_name,
                "result": spec.result,
                "determinism": spec.determinism,
                "context_reads": list(spec.context_reads),
                "context_writes": list(spec.context_writes),
                "provenance_ref": registered.provenance_ref,
                "batch": batch,
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
    report = {
        "schema": "battle_sandbox_runtime_report/1",
        "sandbox_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "battle_state_schema_version": BATTLE_STATE_SCHEMA_VERSION,
        "trace_schema": TRACE_SCHEMA,
        "game_semantic_version": catalog.game_version,
        "final_status": "BATTLE_SANDBOX = MODIFIER_APPLICATION_RUNTIME_07_PROOF",
        "semantic_batch": {
            "path": "data/semantics/4.4.54/modifier_application_bridge_07.json",
            "batch_id": batch["batch_id"],
            "accepted_primitives": len(batch["primitives"]),
            "runtime_layer_name": batch["runtime_layer_name"],
        },
        "implemented_primitives": implemented,
        "application_chains": batch.get("application_chains", []),
        "battle_state_additions": [
            {
                "field": "modifier_state_by_entity",
                "schema_version": BATTLE_STATE_SCHEMA_VERSION,
                "canonical_shape": (
                    "dict[str(entity runtime_id), list[ModifierState dict]]; "
                    "ordered list, duplicates preserved, positional reads"
                ),
                "native_evidence": (
                    "AbilityComponent._ModifierList [+0x38] append leaf "
                    "(M520236) + owner entity component slot [+0x10] "
                    "(M506418) + instance owner component [+0x198] (M506159)"
                ),
            }
        ],
        "modifier_identity": batch.get("modifier_identity", []),
        "container_semantics": {
            "native_container": "RPG.GameCore.AbilityComponent._ModifierList",
            "native_slot": "+0x38",
            "ordering": "ORDERED_APPEND",
            "duplicates": "PRESERVED_NO_DEDUPLICATION at the accepted append leaf",
            "canonical_type": "ModifierContainer(tuple[ModifierState, ...])",
            "note": "never an unordered Python set",
        },
        "stack_policy_status": batch.get("stack_policy", []),
        "lifetime_status": batch.get("lifetime_semantics", []),
        "event_dependency": batch.get("event_dependencies", []),
        "effect_dependency": batch.get("deferred_effects", []),
        "state_transition_tests": [
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
            "TaskContext.EvaluateTarget registry dispatcher internals",
            "TryAddModifierInstance full stack/lifetime/event dispatcher",
            "Modifier effects (property stacks / DOT / damage hooks)",
            "Turn expiration / duration triggers",
            "Damage",
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
