"""Unit coverage for deterministic full-content family selection."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from hsr_battle_agent.game_data.full_content_behavior_ingestion import (
    TURN_BASED_COMMIT,
    _expanded_level_rows,
)


class FullContentBehaviorIngestionTest(unittest.TestCase):
    def test_expansion_deduplicates_overlapping_level_queries_and_excludes_layouts(self) -> None:
        artifact = {
            "selected_commit": TURN_BASED_COMMIT,
            "matches": {
                "Config/ConfigAbility/Level/Level_Maze": [
                    {"path": "Config/ConfigAbility/Level/Level_MazeBuff_Ability.json", "git_blob_sha": "a", "size": 1},
                    {"path": "Config/ConfigAbility/Level/Level_MazeBuff_Ability.layout.json", "git_blob_sha": "b", "size": 2},
                ],
                "Config/ConfigAbility/Level/Level_Challenge": [
                    {"path": "Config/ConfigAbility/Level/Level_MazeBuff_Ability.json", "git_blob_sha": "a", "size": 1},
                    {"path": "Config/ConfigAbility/Level/Level_RogueChallengeMode_Ability.json", "git_blob_sha": "c", "size": 3},
                ],
                "Config/ConfigAdventureModifier/": [
                    {"path": "Config/ConfigAdventureModifier/AdventureModifier_Rogue.json", "git_blob_sha": "d", "size": 4},
                    {"path": "Config/ConfigAdventureModifier/AdventureModifier_Rogue.layout.json", "git_blob_sha": "e", "size": 5},
                ],
            },
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "discovery.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            rows = _expanded_level_rows(path)
        self.assertEqual(
            [row["path"] for row in rows["LEVEL_ABILITY"]],
            [
                "Config/ConfigAbility/Level/Level_MazeBuff_Ability.json",
                "Config/ConfigAbility/Level/Level_RogueChallengeMode_Ability.json",
            ],
        )
        self.assertEqual(
            [row["path"] for row in rows["ADVENTURE_MODIFIER"]],
            ["Config/ConfigAdventureModifier/AdventureModifier_Rogue.json"],
        )


if __name__ == "__main__":
    unittest.main()
