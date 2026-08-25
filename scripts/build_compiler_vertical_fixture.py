"""Record the strict cross-family compiler vertical result without false success."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import write_json


DEFAULT_REPORT = Path("data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_001.json")
DEFAULT_OUTPUT = Path("data/semantics/4.4.54/full_reconstruction/compiler_vertical_fixture_001.json")


def first(records: list[dict], owner: str, status: str) -> dict:
    return next(record for record in records if record["owner_kind"] == owner and record["compile_status"] == status)


parser = argparse.ArgumentParser()
parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
arguments = parser.parse_args()
report = json.loads(arguments.report.read_text(encoding="utf-8"))
records = report["records"]
avatar = first(records, "Avatar", "COMPILED_STRUCTURE_ONLY")
monster = first(records, "Monster", "COMPILED_STRUCTURE_ONLY")
environment = first(records, "Modifier", "COMPILED_STRUCTURE_ONLY")
stage_buff = first(records, "StageBuff", "REJECTED")
payload = {
    "fixture_id": "COMPILER-VERTICAL-001",
    "game_version": "4.4.54",
    "status": "PARTIAL_STRICT_CROSS_FAMILY_IR_ONLY",
    "input_report_sha256": report["report_sha256"],
    "pipeline": ["canonical BehaviorRecord", "strict BehaviorCompiler", "source-independent Behavior IR", "KERNEL-EVENT / PRIM-MODIFIER packet dependencies", "ScenarioCompiler static assembly"],
    "compiled_structure_only": {
        "avatar": {"behavior_id": avatar["behavior_id"], "owner_ref": avatar["owner_ref"], "ir_sha256": avatar["ir_sha256"]},
        "monster": {"behavior_id": monster["behavior_id"], "owner_ref": monster["owner_ref"], "ir_sha256": monster["ir_sha256"]},
        "environment_modifier": {"behavior_id": environment["behavior_id"], "owner_ref": environment["owner_ref"], "ir_sha256": environment["ir_sha256"]},
    },
    "explicit_stage_buff_blocker": {"behavior_id": stage_buff["behavior_id"], "owner_ref": stage_buff["owner_ref"], "compile_status": stage_buff["compile_status"], "blockers": stage_buff["execution_blockers"]},
    "verification": {"static_scenario_compiler":"tests/game_data/test_scenario_compiler.py validates free player/enemy/wave/Buff assembly and Stage template overrides", "event_trace":"tests/game_data/test_semantic_event_trace.py validates source callback ordering only", "modifier_reference":"tests/game_data/test_modifier_lifecycle_reference.py validates bounded instance transitions", "semantic_execution": "NOT_AVAILABLE; no compiled record is golden/executable"},
    "coverage_interpretation": "The vertical slice proves canonical-to-IR compilation and explicit blocking across Avatar, Monster and environment Modifier. It does not claim a StageBuff behavior is compiled, nor that the assembled ScenarioPackage can run.",
}
write_json(arguments.output, payload)
print(json.dumps({"output_path": str(arguments.output), "status": payload["status"]}, sort_keys=True))
