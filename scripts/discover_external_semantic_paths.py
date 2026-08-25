"""Discover bounded behavior-config candidates from pinned external Git trees.

This command reads only commit-addressed tree metadata.  It does not fetch
payload files, build a database, or access local DesignData evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hsr_battle_agent.game_data.external_reconstruction import ExternalReferenceFetcher, default_external_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("data/semantics/4.4.54/full_reconstruction/external_source_expansion_profile_v1.json"),
    )
    parser.add_argument("--root", type=Path, default=default_external_root())
    parser.add_argument("--source", action="append", dest="sources", help="Repeat to discover only selected source IDs")
    args = parser.parse_args()
    profile: dict[str, Any] = json.loads(args.profile.read_text(encoding="utf-8"))
    requested = set(args.sources or ())
    fetcher = ExternalReferenceFetcher(args.root)
    results: dict[str, Any] = {}
    for source in profile.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id", ""))
        source_name = str(source.get("fetcher_source_name", ""))
        if requested and source_id not in requested and source_name not in requested:
            continue
        if not source_name:
            raise ValueError(f"profile source {source_id!r} has no fetcher_source_name")
        result = fetcher.discover_paths(source_name, source.get("tree_discovery_queries", []))
        results[source_id] = {
            "source_name": source_name,
            "tree_blob_count": result["tree_blob_count"],
            "tree_truncated": result["tree_truncated"],
            "match_counts": {term: len(matches) for term, matches in result["matches"].items()},
            "artifact_path": str(args.root / source_name / "semantic_discovery_v1.json"),
        }
    print(json.dumps({"schema": "hsr_battle_agent.external_semantic_discovery_run/1", "results": results}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
