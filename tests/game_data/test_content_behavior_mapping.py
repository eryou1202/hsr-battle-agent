"""Conservative static-content to canonical-behavior mapping tests."""
from __future__ import annotations

import unittest

from hsr_battle_agent.game_data.content_behavior_mapping import (
    build_content_behavior_mapping,
    character_tag_index,
)


class ContentBehaviorMappingTest(unittest.TestCase):
    def test_avatar_filename_tag_is_candidate_not_direct_id(self) -> None:
        tags = character_tag_index({"1105": {"tag": "natasha"}})
        static_ids = {
            "Avatar": ["1105", "1307"], "Skill": ["110501"], "Trace": ["1105:point01:1"],
            "Eidolon": ["110501"], "LightCone": ["20000"], "RelicSet": ["101"],
            "Monster": ["1002011"], "MonsterSkill": ["100201101"], "StageBuff": ["3110001"],
        }
        corpus = {
            "game_version": "4.4.54", "records": [{
                "behavior_id": "behavior:natasha", "owner_kind": "Avatar",
                "owner_ref": "Avatar_Natasha_00_Skill02_Phase02",
                "entrypoints": [{"operations": []}],
                "source_refs": [{"path": "Config/Avatar_Natasha.json"}],
            }],
        }
        report = {"records": [{
            "behavior_id": "behavior:natasha", "behavior_bearing": True,
            "compile_status": "EXECUTABLE_REFERENCE", "executable": True,
            "entrypoints": [{"executable_reference": True, "operations": []}],
        }]}
        payload = build_content_behavior_mapping(
            corpus, report, static_ids, tags, source_metadata={"fixture": True},
        )
        avatar = payload["static_family_coverage"]["Avatar"]
        self.assertEqual(avatar["static_entities_directly_linked"], 0)
        self.assertEqual(avatar["static_entities_representation_transform_candidates"], 1)
        self.assertEqual(avatar["behavior_records_representation_transform_candidate"], 1)
        self.assertEqual(payload["record_links"][0]["static_link"]["candidate_entity_ids"], ["1105"])

    def test_name_only_monster_is_not_a_static_id_link(self) -> None:
        tags = character_tag_index({})
        static_ids = {
            "Avatar": [], "Skill": [], "Trace": [], "Eidolon": [], "LightCone": [], "RelicSet": [],
            "Monster": ["1002011"], "MonsterSkill": ["100201101"], "StageBuff": ["3110001"],
        }
        corpus = {"game_version": "4.4.54", "records": [{
            "behavior_id": "behavior:monster", "owner_kind": "Monster",
            "owner_ref": "Monster_AML_Minion01_00_Skill01_Phase02", "entrypoints": [],
            "source_refs": [{"path": "Config/Monster_AML_Minion01_00_Ability.json"}],
        }]}
        payload = build_content_behavior_mapping(corpus, {"records": []}, static_ids, tags, source_metadata={})
        link = payload["record_links"][0]["static_link"]
        self.assertEqual(link["classification"], "UNMAPPED")
        self.assertEqual(payload["static_family_coverage"]["Monster"]["static_entities_directly_linked"], 0)
