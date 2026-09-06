"""Build the reproducible family-scoped full-content ingestion manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.full_content_behavior_ingestion import (
    build_full_content_behavior_ingestion_manifest,
)


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, default=Path(".external_refs"))
parser.add_argument("--output", type=Path)
arguments = parser.parse_args()

payload = build_full_content_behavior_ingestion_manifest(
    source_root=arguments.source_root,
    output_path=arguments.output,
)
print(json.dumps({
    "output_path": str(arguments.output) if arguments.output else "data/semantics/4.4.54/full_reconstruction/full_content_behavior_ingestion_manifest_001.json",
    "manifest_sha256": payload["manifest_sha256"],
    "families": payload["families"],
    "normalizer_path_count": len(payload["normalizer_paths"]),
}, ensure_ascii=False, sort_keys=True))
