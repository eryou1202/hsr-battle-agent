"""Build canonical behavior records from the reviewed external raw snapshot."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from hsr_battle_agent.game_data.external_behavior import build_external_behavior_corpus
from hsr_battle_agent.game_data.external_reconstruction import default_external_root

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, default=default_external_root())
parser.add_argument("--output", type=Path)
args = parser.parse_args()
print(json.dumps(build_external_behavior_corpus(source_root=args.source_root, output_path=args.output), ensure_ascii=False, indent=2, sort_keys=True))
