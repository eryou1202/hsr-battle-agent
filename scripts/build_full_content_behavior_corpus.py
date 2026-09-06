"""Normalize all cached, family-scoped behavior documents through the shared IR."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.external_behavior import build_external_behavior_corpus
from hsr_battle_agent.game_data.full_content_behavior_ingestion import (
    build_full_content_behavior_ingestion_manifest,
)


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, default=Path(".external_refs"))
parser.add_argument("--manifest", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_ingestion_manifest_001.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_corpus_001.json"))
arguments = parser.parse_args()

manifest = build_full_content_behavior_ingestion_manifest(
    source_root=arguments.source_root,
    output_path=arguments.manifest,
)
missing = [row["path"] for row in manifest["normalizer_paths"] if row["capture_status"] != "CACHED_VERIFIED"]
if missing:
    raise SystemExit(
        f"full content behavior corpus has {len(missing)} uncached selected payloads; "
        "run fetch_full_content_behavior_families.py first"
    )
result = build_external_behavior_corpus(
    source_root=arguments.source_root,
    output_path=arguments.output,
    behavior_paths=[str(row["path"]) for row in manifest["normalizer_paths"]],
    corpus_id="FULL-CONTENT-BEHAVIOR-CORPUS-001",
)
print(json.dumps({
    "manifest_sha256": manifest["manifest_sha256"],
    **result,
}, ensure_ascii=False, sort_keys=True))
