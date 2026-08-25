"""Generate the source-backed KERNEL-EVENT-001 diagnostic trace fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import write_json
from hsr_battle_agent.game_data.semantic_event_trace import DeterministicEventTracer


DEFAULT_CORPUS = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
DEFAULT_OUTPUT = Path("data/semantics/4.4.54/full_reconstruction/kernel_event_trace_fixture_001.json")


def _first(records: list[dict], predicate):
    for record in records:
        if predicate(record):
            return record
    raise ValueError("required source-backed behavior record is unavailable")


def main(corpus_path: Path, output: Path) -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    records = corpus["records"]
    black_swan = _first(records, lambda record: record["owner_ref"] == "Avatar_BlackSwan_00_PassiveSkill01")
    stage_buff = _first(records, lambda record: record["owner_kind"] == "StageBuff" and any(entry.get("source_event") == "OnAdd" for entry in record["entrypoints"]))
    monster = _first(records, lambda record: record["owner_kind"] == "Monster" and any(entry.get("source_event") == "OnStart" for entry in record["entrypoints"]))
    tracer = DeterministicEventTracer()
    tracer.register_behavior_record(black_swan, owner_instance_id="fixture:black_swan")
    tracer.register_behavior_record(stage_buff, owner_instance_id="fixture:stage_buff")
    tracer.register_behavior_record(monster, owner_instance_id="fixture:monster")
    result = tracer.trace(["OnPhase1", "OnAdd", "OnStart"])
    phase_callbacks = [step for step in result.trace if step.event == "ONPHASE1"]
    payload = {
        "fixture_id": "KERNEL-EVENT-TRACE-001",
        "game_version": "4.4.54",
        "status": "DIAGNOSTIC_ORDER_TRACE_NOT_GOLDEN_SEMANTIC_EXECUTION",
        "purpose": "Verify selected KERNEL-EVENT-001 registration/priority/depth-first ordering against captured Black Swan modifier callbacks plus a StageBuff and Monster entrypoint. No operation state mutation is claimed.",
        "input_corpus_sha256": corpus["corpus_sha256"],
        "sources": [black_swan["source_refs"][0], stage_buff["source_refs"][0], monster["source_refs"][0]],
        "selected_records": {"black_swan": black_swan["behavior_id"], "stage_buff": stage_buff["behavior_id"], "monster": monster["behavior_id"]},
        "assertions": {
            "black_swan_onphase1_priorities": [step.priority for step in phase_callbacks],
            "priority_is_ascending": [step.priority for step in phase_callbacks] == sorted(step.priority for step in phase_callbacks),
            "source_order_for_stage_and_monster_present": any(step.event == "ONADD" for step in result.trace) and any(step.event == "ONSTART" for step in result.trace),
            "opaque_or_uncompiled_never_counts_as_executable": not result.executable,
        },
        "trace_result": result.as_json(),
    }
    write_json(output, payload)
    print(json.dumps({"output_path": str(output), "trace_steps": len(result.trace), "blocked": len(result.blocked_operation_ids)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.corpus, arguments.output)
