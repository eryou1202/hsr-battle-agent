"""Publish the first strict compiler coverage census for the reviewed corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import write_json


parser = argparse.ArgumentParser()
parser.add_argument("--report", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_001.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_coverage_census_001.json"))
arguments = parser.parse_args()
report = json.loads(arguments.report.read_text(encoding="utf-8"))
coverage = report["coverage"]
families = {owner: {
    "captured_records": values["captured"],
    "behavior_bearing_denominator": values["behavior_bearing"],
    "static_definition_only": values["static_definition_only"],
    "canonicalized": values["captured"],
    "structural_compiled": values["structural_compiled"],
    "executable": 0,
    "golden_tested": 0,
    "unsupported_or_uncompiled": values["behavior_bearing"] - values["structural_compiled"],
    "full_game_behavior_denominator": "UNKNOWN",
} for owner, values in coverage["by_owner_kind"].items()}
for absent in ("Trace", "Eidolon", "LightCone", "RelicSet"):
    families[absent] = {"captured_records": 0, "behavior_bearing_denominator": 0, "static_definition_only": 0, "canonicalized": 0, "structural_compiled": 0, "executable": 0, "golden_tested": 0, "unsupported_or_uncompiled": 0, "full_game_behavior_denominator": "UNKNOWN"}
payload = {
    "report_id": "BEHAVIOR-COVERAGE-CENSUS-001",
    "game_version": "4.4.54",
    "status": "STRICT_REVIEWED_CORPUS_BASELINE",
    "input_compiler_report_sha256": report["report_sha256"],
    "counting_rule": "The behavior denominator is the reviewed captured records that contain at least one operational entrypoint or TaskListTemplate. Records with no operational behavior are counted separately as static definitions and never deflate the behavior denominator. The full 4.4.54 behavior corpus denominator remains UNKNOWN.",
    "families": dict(sorted(families.items())),
    "overall": {
        "captured_records": coverage["captured"],
        "canonicalized": coverage["canonicalized"],
        "behavior_bearing_denominator": coverage["behavior_bearing"],
        "static_definition_only": coverage["static_definition_only"],
        "structural_compiled": coverage["structural_compiled"],
        "executable": 0,
        "golden_tested": 0,
        "uncompiled": coverage["behavior_bearing"] - coverage["structural_compiled"],
    },
    "failure_clusters": coverage["failure_reasons"],
    "next_high_leverage": {"ticket_id": "TARGET-001 + FORMULA-001 + SCHEDULER-001", "reason": "The repaired census shows 41 unbound DamageRequest, 19 Retarget, 15 InsertAction, 14 ModifyActionState, 13 DelayAction and 87 gating PresentationWait nodes. DynamicValue structural binding and formula decoding are already implemented; the next executable gain is target resolution plus scheduler/action markers."},
}
write_json(arguments.output, payload)
print(json.dumps({"output_path": str(arguments.output), "overall": payload["overall"]}, sort_keys=True))
