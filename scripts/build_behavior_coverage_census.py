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
families = {owner: {"captured_behavior_denominator": values["captured"], "canonicalized": values["captured"], "structural_compiled": values["structural_compiled"], "executable": 0, "golden_tested": 0, "unsupported_or_uncompiled": values["captured"] - values["structural_compiled"], "full_game_behavior_denominator": "UNKNOWN"} for owner, values in coverage["by_owner_kind"].items()}
for absent in ("Trace", "Eidolon", "LightCone", "RelicSet"):
    families[absent] = {"captured_behavior_denominator": 0, "canonicalized": 0, "structural_compiled": 0, "executable": 0, "golden_tested": 0, "unsupported_or_uncompiled": 0, "full_game_behavior_denominator": "UNKNOWN"}
payload = {
    "report_id": "BEHAVIOR-COVERAGE-CENSUS-001",
    "game_version": "4.4.54",
    "status": "STRICT_REVIEWED_CORPUS_BASELINE",
    "input_compiler_report_sha256": report["report_sha256"],
    "counting_rule": "The reviewed captured corpus (541 BehaviorRecords) is the only declared denominator in this report. It is not a substitute for the full 4.4.54 behavior corpus, whose denominator remains UNKNOWN.",
    "families": dict(sorted(families.items())),
    "overall": {"captured_behavior_denominator": coverage["captured"], "canonicalized": coverage["canonicalized"], "structural_compiled": coverage["structural_compiled"], "executable": 0, "golden_tested": 0, "uncompiled": coverage["captured"] - coverage["structural_compiled"]},
    "failure_clusters": coverage["failure_reasons"],
    "next_high_leverage": {"ticket_id": "COMPILER-MODIFIER-APPLY-001", "reason": "The risk triage contains 203 AddModifier nodes and 29 StackProperty nodes. PRIM-MODIFIER-001 already fixes bounded instance transitions, so compiler binding/target and condition dependencies should be recovered before widening the corpus."},
}
write_json(arguments.output, payload)
print(json.dumps({"output_path": str(arguments.output), "overall": payload["overall"]}, sort_keys=True))
