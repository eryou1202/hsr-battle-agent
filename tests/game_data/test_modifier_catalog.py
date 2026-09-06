"""Canonical Modifier catalog tests."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.modifier_catalog import (
    modifier_catalog_from_corpus,
    modifier_catalog_report_from_corpus,
)


class ModifierCatalogTest(unittest.TestCase):
    def test_catalog_only_exposes_explicitly_supported_source_stacking(self) -> None:
        corpus = json.loads(Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json").read_text(encoding="utf-8"))
        catalog = modifier_catalog_from_corpus(corpus)
        self.assertEqual(catalog["MAvatar_BlackSwan_00_DOT"].stacking, "ReplaceByCaster")
        self.assertEqual(catalog["MCommon_BAN_Heal"].stacking, "Merge")
        self.assertNotIn("M_BlackSwan_P01_ListenAddPoison", catalog)

    def test_catalog_reads_embedded_modifier_definitions_and_deduplicates_equivalent_sources(self) -> None:
        corpus = {
            "records": [
                {
                    "behavior_id": "ability:z",
                    "owner_kind": "Avatar",
                    "modifier_definitions": [{
                        "name": "MEmbedded",
                        "payload": {"Stacking": "Replace", "LifeStepMoment": "Phase"},
                    }],
                },
                {
                    "behavior_id": "ability:a",
                    "owner_kind": "Avatar",
                    "modifier_definitions": [{
                        "name": "MEmbedded",
                        "payload": {"Stacking": "Replace", "LifeStepMoment": "Phase"},
                    }],
                },
                {
                    "behavior_id": "ability:unsupported",
                    "owner_kind": "Avatar",
                    "modifier_definitions": [{
                        "name": "MEntityUnique",
                        "payload": {"Stacking": "EntityUnique"},
                    }],
                },
            ],
        }
        catalog = modifier_catalog_from_corpus(corpus)
        self.assertEqual(catalog["MEmbedded"].source_behavior_id, "ability:a")
        self.assertEqual(catalog["MEmbedded"].stacking, "Replace")
        self.assertNotIn("MEntityUnique", catalog)
        self.assertEqual(catalog["MEmbedded"].source_behavior_ids, ("ability:a", "ability:z"))
        report = modifier_catalog_report_from_corpus(corpus)
        self.assertEqual(report["definition_candidate_count"], 3)
        self.assertEqual(report["equivalent_duplicate_count"], 1)
        self.assertEqual(report["true_conflict_count"], 0)
        self.assertEqual(report["supported_catalog_definition_count"], 1)
        self.assertEqual(report["unsupported_definition_count"], 1)

    def test_catalog_excludes_non_equivalent_same_name_variants(self) -> None:
        corpus = {
            "records": [
                {
                    "behavior_id": "ability:a",
                    "owner_kind": "Avatar",
                    "modifier_definitions": [{
                        "name": "MConflict",
                        "payload": {"Stacking": "Replace", "BehaviorFlagList": ["Buff"]},
                    }],
                },
                {
                    "behavior_id": "ability:b",
                    "owner_kind": "Avatar",
                    "modifier_definitions": [{
                        "name": "MConflict",
                        "payload": {"Stacking": "Replace", "BehaviorFlagList": ["Debuff"]},
                    }],
                },
            ],
        }
        self.assertNotIn("MConflict", modifier_catalog_from_corpus(corpus))
        report = modifier_catalog_report_from_corpus(corpus)
        self.assertEqual(report["true_conflict_count"], 1)
        self.assertEqual(report["conflict_clusters"][0]["variant_count"], 2)


if __name__ == "__main__":
    unittest.main()
