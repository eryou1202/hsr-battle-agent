"""Offline contract tests for bounded external semantic-path discovery."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hsr_battle_agent.game_data.external_reconstruction import ExternalReferenceFetcher


class ExternalSemanticDiscoveryTest(unittest.TestCase):
    def test_discovery_records_only_matching_blob_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fetcher = ExternalReferenceFetcher(Path(temporary))
            fetcher._request_json = lambda _url: {  # type: ignore[method-assign]
                "truncated": False,
                "tree": [
                    {"path": "ExcelOutput/AvatarSkillConfig.json", "type": "blob", "sha": "a", "size": 10},
                    {"path": "ExcelOutput/MonsterSkillConfig.json", "type": "blob", "sha": "b", "size": 20},
                    {"path": "README.md", "type": "blob", "sha": "c", "size": 30},
                    {"path": "ExcelOutput", "type": "tree", "sha": "d"},
                ],
            }
            artifact = fetcher.discover_paths("TurnBasedGameData", ["AvatarSkillConfig", "Monster Skill"])
            self.assertEqual(artifact["tree_blob_count"], 3)
            self.assertFalse(artifact["tree_truncated"])
            self.assertEqual(artifact["matches"]["AvatarSkillConfig"][0]["path"], "ExcelOutput/AvatarSkillConfig.json")
            self.assertEqual(artifact["matches"]["Monster Skill"][0]["git_blob_sha"], "b")
            self.assertTrue((Path(temporary) / "TurnBasedGameData" / "semantic_discovery_v1.json").exists())
