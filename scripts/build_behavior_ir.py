"""Compile the reviewed canonical corpus into strict source-independent IR."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.behavior_compiler import BehaviorCompiler
from hsr_battle_agent.game_data.nanoka_content import write_json


parser = argparse.ArgumentParser()
parser.add_argument("--corpus", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_001.json"))
arguments = parser.parse_args()
corpus = json.loads(arguments.corpus.read_text(encoding="utf-8"))
result = BehaviorCompiler().compile_corpus(corpus)
write_json(arguments.output, result)
print(json.dumps({"output_path": str(arguments.output), "coverage": result["coverage"], "report_sha256": result["report_sha256"]}, sort_keys=True))
