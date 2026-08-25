"""Generate a source-backed StackProperty modifier-body reference trace.

The callback operations come from the real canonical
``MCommon_AttackRatioUp`` record.  Property base values and DynamicHash
resolution are explicit fixture inputs, so the trace is
SOURCE_BACKED_REFERENCE_NOT_GOLDEN.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from hsr_battle_agent.game_data.cross_family_execution_reference import (
    EntityState,
    ReferenceBattleState,
    execute_operations,
)
from hsr_battle_agent.game_data.damage_survival_reference import SurvivalState
from hsr_battle_agent.game_data.dynamic_value_reference import DynamicValueStore
from hsr_battle_agent.game_data.nanoka_content import stable_hash, write_json
from hsr_battle_agent.game_data.property_contribution_reference import PropertyState
from hsr_battle_agent.game_data.rng_semantics_reference import rng_01_from_seed


DEFAULT_CORPUS = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
DEFAULT_OUTPUT = Path("data/semantics/4.4.54/full_reconstruction/source_backed_property_reference_001.json")


def main(corpus_path: Path, output: Path) -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    record = next(record for record in corpus["records"] if record["owner_ref"] == "MCommon_AttackRatioUp")
    entrypoint = record["entrypoints"][0]
    state = ReferenceBattleState(
        entities={"p1": EntityState("p1", SurvivalState(Decimal("1000"), Decimal("1000")))},
        dynamic_store=DynamicValueStore.empty(),
        modifier_names={"p1": {record["owner_ref"]}},
        rng=lambda: Decimal(str(rng_01_from_seed(7))),
        dynamic_values={"2128130574": "0.12"},
        property_state=PropertyState.empty({"AttackAddedRatio": "0"}),
    )
    final = execute_operations(
        state,
        entrypoint["operations"],
        caster_id="p1",
        ability_target_id=None,
        modifier_context_id=record["owner_ref"],
    )
    payload = {
        "fixture_id": "SOURCE-BACKED-PROPERTY-REFERENCE-001",
        "game_version": "4.4.54",
        "status": "SOURCE_BACKED_REFERENCE_NOT_GOLDEN",
        "purpose": "Execute the real canonical MCommon_AttackRatioUp OnStack callback: StackProperty evaluates its DynamicValue formula and writes a stable modifier-owned contribution slot.",
        "input_corpus_sha256": corpus["corpus_sha256"],
        "source": {
            "behavior_id": record["behavior_id"],
            "source_refs": record["source_refs"],
            "entrypoint_event": entrypoint["event"],
            "entrypoint_source_event": entrypoint["source_event"],
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
