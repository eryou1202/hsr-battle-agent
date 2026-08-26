"""Canonical Modifier catalog tests."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.modifier_catalog import modifier_catalog_from_corpus


class ModifierCatalogTest(unittest.TestCase):
    def test_catalog_only_exposes_explicitly_supported_source_stacking(self) -> None:
        corpus = json.loads(Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json").read_text(encoding="utf-8"))
        catalog = modifier_catalog_from_corpus(corpus)
        self.assertEqual(catalog["MAvatar_BlackSwan_00_DOT"].stacking, "ReplaceByCaster")
        self.assertEqual(catalog["MCommon_BAN_Heal"].stacking, "Merge")
        self.assertNotIn("M_BlackSwan_P01_ListenAddPoison", catalog)


if __name__ == "__main__":
    unittest.main()
