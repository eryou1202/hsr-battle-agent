#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Census real direct-HP ability content in the 4.4.54 DesignData archive."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "direct_hp_real_content_census_28.json"

DATA = {
    "schema": "direct_hp_real_content_census/1",
    "game_version": "4.4.54",
    "status": "DIRECT_HP_AVATAR_SLICE_NOT_FOUND",
    "direct_hp_type_registry": [
        {
            "config_type": "RPG.GameCore.SetHP",
            "type_index": 22351,
            "methods": [124661, 124662, 124663],
            "factory_table_base": "0x493C000",
            "factory_thunk": "0x1CE5D000",
            "serialized_selector": 5,
            "selector_encoding": "ULEB/VLQ unsigned varint",
        },
        {
            "config_type": "RPG.GameCore.HealHP",
            "type_index": 22352,
            "methods": [124664, 124665, 124666],
            "factory_table_base": "0x49392E0",
            "factory_thunk": "0x1CC131D0",
            "serialized_selector": 7,
            "selector_encoding": "ULEB/VLQ unsigned varint",
        },
        {
            "config_type": "RPG.GameCore.LoseHPByRatio",
            "type_index": 22420,
            "methods": [124874, 124875, 124876],
            "factory_table_base": "0x49398A0",
            "factory_thunk": "0x1CC16410",
            "serialized_selector": 8,
            "selector_encoding": "ULEB/VLQ unsigned varint",
        },
        {
            "config_type": "RPG.GameCore.LoseHP",
            "type_index": 22421,
            "methods": [124877, 124878, 124879],
            "factory_table_base": "0x49398A0",
            "factory_thunk": "0x1CC16360",
            "serialized_selector": 7,
            "selector_encoding": "ULEB/VLQ unsigned varint",
        },
    ],
    "structural_node_hits": [],
    "avatar_mapped_hits": [],
    "ranked_candidates": [],
    "primary_candidate": None,
    "natasha_skill02_status": {
        "assumption": "NOT_PROVEN / DEFERRED",
        "detail": "Natasha Skill02 does not currently have a proven HealHP node; do not force it.",
    },
    "remaining_parser_unknowns": [
        "OUTER_ABILITY_ACTION_CONTAINER_ENCODING_UNKNOWN",
        "REAL_AVATAR_TO_DIRECT_HP_NODE_MAPPING_NOT_FOUND",
        "TARGET_CONFIG_SERIALIZER_TAG_UNKNOWN",
    ],
    "recommended_next_step": "Map the outer ability/action container encoding used by real avatar ability records, then locate structurally valid direct-HP nodes and map them to avatar abilities.",
}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(DATA, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
