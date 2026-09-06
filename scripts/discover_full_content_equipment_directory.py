"""Record the direct pinned equipment behavior directory needed by full ingestion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.external_reconstruction import ExternalReferenceFetcher


parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, default=Path(".external_refs"))
parser.add_argument("--output", type=Path, default=Path(".external_refs/TurnBasedGameData/full_content_equipment_directory_001.json"))
arguments = parser.parse_args()

artifact = ExternalReferenceFetcher(arguments.source_root).discover_directory_paths(
    "TurnBasedGameData",
    "Config/ConfigAbility/Equip",
    output_path=arguments.output,
)
print(json.dumps({
    "output_path": str(arguments.output),
    "artifact_sha256": artifact["artifact_sha256"],
    "entry_count": len(artifact["entries"]),
}, ensure_ascii=False, sort_keys=True))
