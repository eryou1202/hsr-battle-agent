"""Generate a deterministic cross-family interaction reference fixture.

The fixture composes real corpus predicate and formula payloads with an
explicit synthetic battle state.  It is a verification scaffold for
subsystem interaction, NOT a source-backed golden battle trace.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.game_data.cross_family_execution_reference import (
    EntityState,
    ReferenceBattleState,
    execute_operations,
)
from hsr_battle_agent.game_data.dynamic_value_reference import DynamicValueStore, dynamic_key_from_payload
from hsr_battle_agent.game_data.nanoka_content import stable_hash, write_json
from hsr_battle_agent.game_data.damage_survival_reference import SurvivalState
from hsr_battle_agent.game_data.rng_semantics_reference import rng_01_from_seed


DEFAULT_CORPUS = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
DEFAULT_OUTPUT = Path("data/semantics/4.4.54/full_reconstruction/cross_family_interaction_fixture_001.json")


def walk(operations):
    for operation in operations:
        if isinstance(operation, Mapping):
            yield operation
            for group in operation.get("children", []):
                if isinstance(group, Mapping):
                    yield from walk(group.get("operations", []))


def main(corpus_path: Path, output: Path) -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    all_operations = [operation for record in corpus["records"] for entrypoint in record["entrypoints"] for operation in walk(entrypoint.get("operations", []))]
    predicate = next(operation for operation in all_operations if operation.get("source_type") == "RPG.GameCore.ByTargetTeam" and operation.get("arguments", {}).get("Team") == "TeamLight")
    formula = next(operation for operation in all_operations if operation.get("kind") == "SET_DYNAMIC_VALUE" and operation.get("arguments", {}).get("Value", {}).get("PostfixExpr", {}).get("OpCodes") == "AQAR")

    dynamic_hash = formula["arguments"]["Value"]["PostfixExpr"]["DynamicHashes"][0]
    store = DynamicValueStore.empty()
    store = store.set_value("p1", str(dynamic_hash), Decimal("500")).store
    state = ReferenceBattleState(
        entities={
            "p1": EntityState("p1", SurvivalState(Decimal("1000"), Decimal("1000"))),
            "e1": EntityState("e1", SurvivalState(Decimal("1000"), Decimal("1000"), shield=Decimal("100"))),
        },
        dynamic_store=store,
        modifier_names={"p1": set(), "e1": set()},
        rng=lambda: Decimal(str(rng_01_from_seed(42))),
    )
    operations: list[dict[str, Any]] = [
        {"operation_id": "fixture:define-layer", "kind": "DEFINE_DYNAMIC_VALUE", "semantic_status": "REQUIRES_PACKET", "arguments": {"DynamicKey": formula["arguments"]["DynamicKey"], "ResetValue": {"IsDynamic": False, "FixedValue": {"Value": 0}}}},
        {"operation_id": "fixture:set-layer", "kind": "SET_DYNAMIC_VALUE", "semantic_status": "REQUIRES_PACKET", "arguments": formula["arguments"]},
        {"operation_id": "fixture:branch", "kind": "CONDITIONAL", "semantic_status": "REQUIRES_PACKET", "arguments": {}, "children": [
            {"field_path": "SuccessTaskList", "operations": [
                {"operation_id": "fixture:damage", "kind": "DAMAGE_REQUEST", "semantic_status": "REQUIRES_PACKET", "arguments": {"amount": 300}},
                {"operation_id": "fixture:damage-complete", "kind": "DAMAGE_COMPLETION_MARKER", "semantic_status": "REQUIRES_PACKET", "arguments": {}},
            ]},
            {"field_path": "FailedTaskList", "operations": []},
        ]},
    ]
    # Attach the real predicate payload to the branch operation.
    operations[2]["arguments"] = {"Predicate": {"$type": predicate["source_type"], **predicate["arguments"]}}

    final = execute_operations(state, operations, caster_id="p1", ability_target_id="e1")
    payload = {
        "fixture_id": "CROSS-FAMILY-INTERACTION-001",
        "game_version": "4.4.54",
        "status": "REFERENCE_INTERACTION_NOT_SOURCE_GOLDEN",
        "purpose": "Compose DynamicValue formula evaluation, Predicate branching, TargetAlias resolution, Damage/Survival commit, marker ordering and seeded RNG in one deterministic reference trace. The operation payloads are real corpus payloads; the battle state is an explicit synthetic fixture.",
        "input_corpus_sha256": corpus["corpus_sha256"],
        "sources": {
            "predicate_operation_id": predicate["operation_id"],
            "formula_operation_id": formula["operation_id"],
            "formula_dynamic_hash": dynamic_hash,
        },
        "selected_state": final.as_json(),
        "trace": final.trace,
        "trace_sha256": stable_hash(final.trace),
        "state_sha256": stable_hash(final.as_json()),
    }
    write_json(output, payload)
    print(json.dumps({"output_path": str(output), "trace_sha256": payload["trace_sha256"], "state_sha256": payload["state_sha256"], "trace_steps": len(final.trace)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.corpus, arguments.output)
