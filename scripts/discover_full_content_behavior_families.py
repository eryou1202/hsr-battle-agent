"""Run one commit-pinned, family-scoped tree discovery for full-content gaps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.external_reconstruction import ExternalReferenceFetcher


QUERIES = (
    "Config/ConfigAbility/Equipment/",
    "Config/ConfigAbility/LightCone/",
    "Config/ConfigAbility/Relic/",
    "LightCone_Ability",
    "RelicSet",
    "Config/ConfigAbility/Level/Level_Maze",
    "Config/ConfigAbility/Level/Level_Challenge",
    "Config/ConfigAdventureModifier/",
)


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, default=Path(".external_refs"))
parser.add_argument("--output", type=Path, default=Path(".external_refs/TurnBasedGameData/full_content_family_discovery_001.json"))
arguments = parser.parse_args()

artifact = ExternalReferenceFetcher(arguments.source_root).discover_paths(
    "TurnBasedGameData",
    QUERIES,
    output_path=arguments.output,
)
print(json.dumps({
    "output_path": str(arguments.output),
    "artifact_sha256": artifact["artifact_sha256"],
    "tree_truncated": artifact["tree_truncated"],
    "match_counts": {query: len(rows) for query, rows in artifact["matches"].items()},
}, ensure_ascii=False, sort_keys=True))
