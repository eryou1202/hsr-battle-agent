"""Materialize selected full-content behavior families from pinned paths only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.external_reconstruction import ExternalReferenceFetcher
from hsr_battle_agent.game_data.full_content_behavior_ingestion import (
    TURN_BASED_SOURCE,
    build_full_content_behavior_ingestion_manifest,
)


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, default=Path(".external_refs"))
parser.add_argument("--manifest", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_ingestion_manifest_001.json"))
parser.add_argument("--family", action="append", dest="families", help="Repeat to select a family; defaults to all discovered families.")
parser.add_argument("--workers", type=int, default=4)
arguments = parser.parse_args()

manifest = build_full_content_behavior_ingestion_manifest(
    source_root=arguments.source_root,
    output_path=arguments.manifest,
)
selected = set(arguments.families or [row["family"] for row in manifest["families"]])
paths = [
    row for row in manifest["paths"]
    if row["family"] in selected or selected.intersection(row.get("families", []))
]
result = ExternalReferenceFetcher(arguments.source_root).fetch_explicit_paths(
    TURN_BASED_SOURCE,
    paths,
    workers=arguments.workers,
)
# Refresh cached/missing counts and raw hashes after materialization.
refreshed = build_full_content_behavior_ingestion_manifest(
    source_root=arguments.source_root,
    output_path=arguments.manifest,
)
print(json.dumps({
    "fetch": result,
    "manifest_sha256": refreshed["manifest_sha256"],
    "selected_families": sorted(selected),
}, ensure_ascii=False, sort_keys=True))
