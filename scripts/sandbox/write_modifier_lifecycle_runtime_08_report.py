# -*- coding: utf-8 -*-
"""Generate data/sandbox/modifier_lifecycle_runtime_08_report.json.

The script runs the current battle + unpacker + cross-version regression
suites, refuses to write a PASS report on any failure, then records the
catalog-driven registry contents, the duplicate decision tree, removal
semantics and the state-transition tests built only from recovered semantics.
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
    / "modifier_lifecycle_bridge_08.json"
)
DISCOVERY_PATH = (
    REPO / "data" / "raw" / "4.4.54" / "modifier_lifecycle_discovery_08.json"
)
OUTPUT_PATH = (
    REPO / "data" / "sandbox" / "modifier_lifecycle_runtime_08_report.json"
)

LIFECYCLE_IDS = {
    "battle.ir.modifier.try_add_modifier_instance",
    "battle.ir.modifier.container_find_modifier_instance",
    "battle.ir.modifier.match_modifier_search",
    "battle.ir.modifier.lifecycle_destroy",
    "battle.ir.modifier.container_remove_dirty",
    "battle.ir.modifier.lifecycle_process_redd",
    "battle.ir.modifier.lifecycle_on_added",
    "battle.ir.modifier.lifecycle_on_activate",
}

STATE_TRANSITION_TESTS = (
    {
        "name": "TestLifecycleThroughExecutor.test_apply_to_empty_changes_state_hash",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "apply_to_empty",
    },
    {
        "name": "TestLifecycleThroughExecutor.test_duplicate_application_branch",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "duplicate_application (Multiple(4) append)",
    },
    {
        "name": "TestLifecycleThroughExecutor.test_retain_global_latest_replace_branch",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "replace (RetainGlobalLatest(11) destroy + append)",
    },
    {
        "name": "TestLifecycleThroughExecutor.test_refresh_branch_updates_life_and_count",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "refresh in place (Refresh(2) life/count core)",
    },
    {
        "name": "TestLifecycleThroughExecutor.test_destroy_and_remove_dirty_branch_preserves_order",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "remove (RemoveDirtyModifiers shift-left ordering)",
    },
    {
        "name": "TestLifecycleThroughExecutor.test_not_found_behavior_is_append",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "not_found",
    },
    {
        "name": "TestCloneSnapshotHashReplay.test_clone_divergence_is_isolated",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "clone_divergence",
    },
    {
        "name": "TestCloneSnapshotHashReplay.test_snapshot_roundtrip_restores_lifecycle_state",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "snapshot_roundtrip",
    },
    {
        "name": "TestCloneSnapshotHashReplay.test_deterministic_replay",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "deterministic_replay",
    },
    {
        "name": "TestCrossLayerChain.test_executor_init_try_add_remove_dirty_formal_path",
        "path": "tests/battle_sandbox/test_modifier_lifecycle_runtime_08.py",
        "branch": "cross_layer Action/ExecutionContext -> modifier lifecycle -> BattleState",
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
            "modifier_lifecycle_runtime_08_report: "
            f"{len(result.failures)} failure(s), {len(result.errors)} error(s); "
            "refusing to write PASS report"
        )
        return 1

    registry = PrimitiveRegistry.create_default()
    implemented = []
    for primitive_id in registry.known_primitive_ids:
        if primitive_id not in LIFECYCLE_IDS:
            continue
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
                "batch": "modifier_lifecycle_bridge_08",
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
    discovery = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
    report = {
        "schema": "battle_sandbox_runtime_report/1",
        "sandbox_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "battle_state_schema_version": BATTLE_STATE_SCHEMA_VERSION,
        "trace_schema": TRACE_SCHEMA,
        "game_semantic_version": catalog.game_version,
        "final_status": "BATTLE_SANDBOX = MODIFIER_LIFECYCLE_RUNTIME_08_PROOF",
        "semantic_batch": {
            "path": "data/semantics/4.4.54/modifier_lifecycle_bridge_08.json",
            "batch_id": batch["batch_id"],
            "accepted_primitives": len(batch["primitives"]),
            "runtime_layer_name": batch["runtime_layer_name"],
        },
        "implemented_primitives": implemented,
        "duplicate_policy": {
            "decision_tree": "TryAddModifierInstance ModifierStacking switch",
            "multiple": "APPEND_DUPLICATE_KEEP_EXISTING",
            "retain_global_latest": "DESTROY_EXISTING_THEN_APPEND",
            "retain_global_latest_unique": (
                "CASTER_IS_OWNER_REFRESH_EXISTING_ELSE_DESTROY_AND_APPEND"
            ),
            "other_stackings": "PROCESS_EXISTING_IN_PLACE",
            "cases": batch.get("duplicate_application_cases", []),
        },
        "match_identity": batch.get("duplicate_match_identity", []),
        "removal_semantics": {
            "destroy": "State [+0x80] = ToBeRemoved(2); idempotent for state > 1",
            "container_removal": (
                "RemoveDirtyModifiers: non-Alive & destroy_guard==0 removed; "
                "shift-left, remaining order preserved"
            ),
            "chains": batch.get("removal_chains", []),
        },
        "ordering": {
            "append": "ORDERED_APPEND (Batch 07 reuse)",
            "removal": "SHIFT_LEFT_PRESERVE_REMAINING_ORDER (List<T>.RemoveAt equivalent)",
            "global_scope_projection": (
                "deterministic runtime-id ascending order; native global-list "
                "order UNKNOWN and recorded"
            ),
        },
        "battle_state_changes": {
            "schema_version": BATTLE_STATE_SCHEMA_VERSION,
            "changed": False,
            "modifier_representation_additions": [
                "ModifierState.previous_life [+0x2e4] (E4 ProcessRedd)",
                "ModifierState.is_max_layer [+0x8e] (E4 ProcessRedd/TryAdd)",
                "ModifierState.destroy_guard [+0x94] (E4 Destroy/RemoveDirty)",
                "ModifierState.source_provider_ref (sandbox ObjectRef materialization of native source-provider pointer identity)",
                "ModifierConfigRef.stacking (ModifierConfig [+0x18], E4 parser + switches)",
            ],
            "note": "BattleState v2 top-level schema unchanged; no forced version bump",
        },
        "stack_status": batch.get("stack_semantics", []),
        "duration_status": batch.get("duration_semantics", []),
        "lifecycle_callback_status": batch.get("lifecycle_chains", []),
        "deferred_effects": batch.get("effect_dependencies", []),
        "deferred_events": batch.get("event_dependencies", []),
        "deferred_turn_dependencies": batch.get("turn_dependencies", []),
        "state_transition_tests": [
            {**item, "status": "PASS"} for item in STATE_TRANSITION_TESTS
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
            "full Modifier effect system",
            "DOT",
            "Damage",
            "Event listener runtime",
            "Turn expiration engine",
            "AV / action queue",
            "Planner",
        ],
        "known_unknowns": batch.get("unknowns", []),
        "candidate_discovery": {
            "path": "data/raw/4.4.54/modifier_lifecycle_discovery_08.json",
            "candidate_count": len(discovery["candidate_table"]),
            "shortlist": discovery["shortlist_method_indexes"],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"wrote {OUTPUT_PATH} tests={test_count} pass={test_pass} "
        f"primitives={len(implemented)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
