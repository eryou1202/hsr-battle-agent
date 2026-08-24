#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Natasha HealHP content probe artifact."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "natasha_healhp_content_24.json"

DATA = {
    "schema": "natasha_healhp_content/1",
    "game_version": "4.4.54",
    "status": "NATASHA_HEALHP_CONTENT_24_PARTIAL",
    "chosen_ability": "Avatar_Natasha_00_Skill02_Phase02",
    "record": {
        "archive": "D:\\StarRail_4.4.53\\StarRail_Data\\Persistent\\DesignData\\Windows\\8625dd99e13b0dfe6b45f47f9bfe3e36.bytes",
        "archive_sha256": "098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B",
        "record_start": "0xBC995F",
        "record_end": "0xBC9BC8",
        "record_length": 617,
        "wrapper_type": 0,
        "bitfield": 51,
        "header_size": 3,
        "path_index_evidence": "edd7d527b0962f4ec2e49789746fb0d2.bytes offset 0x8896 contains Avatar_Natasha_00_Ability.json path",
    },
    "healhp_node_identity": {
        "status": "SUPPORTED",
        "evidence": "The chosen Skill02_Phase02 record contains Heal prefab reference, SkillTargetEntityList, TargetEntity, HPByMaxHP, and MaxHP tokens.",
        "exact_polymorphic_config_tag": "UNKNOWN",
    },
    "target_config": {
        "status": "SUPPORTED",
        "observed_tokens": ["SkillTargetEntityList", "TargetEntity", "AbilityTargetEntity"],
        "exact_target_config_object": "UNKNOWN",
        "note": "Token presence does not prove the exact target selector object; a polymorphic tag decode is required.",
    },
    "amount_inputs": [
        {
            "field_candidate": "HPByMaxHP",
            "status": "DISCOVERY_EVIDENCE_ONLY",
            "record_offset": "0xBC9AF5",
            "classification": "UNKNOWN",
        },
        {
            "field_candidate": "MaxHP",
            "status": "DISCOVERY_EVIDENCE_ONLY",
            "record_offset": "0xBC9AF9",
            "classification": "PROPERTY_REFERENCE_CANDIDATE",
        },
        {
            "field_candidate": "M_SkillTree_HealRatioUp",
            "status": "DISCOVERY_EVIDENCE_ONLY",
            "record_offset": "near 0xBCA87D in adjacent Natasha records",
            "classification": "UNKNOWN",
        },
    ],
    "nested_values": [],
    "source": {
        "archive": "D:\\StarRail_4.4.53\\StarRail_Data\\Persistent\\DesignData\\Windows\\8625dd99e13b0dfe6b45f47f9bfe3e36.bytes",
        "record_offset": "0xBC995F",
        "record_length": 617,
        "sha256": "098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B",
    },
    "unresolved_parser_primitives": [
        "UNKNOWN_POLYMORPHIC_TAG_FOR_HEALHP",
        "UNKNOWN_DYNAMICVALUE_ENCODING_FOR_HEAL_AMOUNT",
        "UNKNOWN_TARGET_SELECTOR_TAG",
    ],
    "recommended_next_step": "Decode the polymorphic config tag inside Avatar_Natasha_00_Skill02_Phase02 that maps to RPG.GameCore.HealHP, then parse its target selector and amount fields.",
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
