#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Natasha HealHP config payload probe (content 25)."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "natasha_healhp_content_25.json"

DATA = {
    "schema": "natasha_healhp_content/2",
    "game_version": "4.4.54",
    "status": "NATASHA_HEALHP_CONTENT_25_PARTIAL",
    "record": {
        "ability": "Avatar_Natasha_00_Skill02_Phase02",
        "archive": "D:\\StarRail_4.4.53\\StarRail_Data\\Persistent\\DesignData\\Windows\\8625dd99e13b0dfe6b45f47f9bfe3e36.bytes",
        "archive_sha256": "098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B",
        "record_start": "0xBC995F",
        "record_end": "0xBC9BC8",
        "record_length": 617,
    },
    "healhp_serialized_discriminator": {
        "reference_value": 53,
        "reference_source": "tools/reference/DataParser/BinOut/Ability/Temp/Common/disp__config_ability_action.ksy case 53 -> heal_hp",
        "observed_in_record": False,
        "detail": "The 617-byte Skill02_Phase02 record contains no standalone 0x35 byte that parses as a disp__config_ability_action type_code 53.",
        "status": "UNKNOWN",
    },
    "discriminator_to_runtime_type_proof": {
        "status": "INSUFFICIENT",
        "reason": "Reference parser maps 53 -> heal_hp, but it is from an older/other parser family and is not present in this 4.4.54 record. The 4.4.54 polymorphic action registry entry for HealHP is not yet recovered.",
    },
    "target_config": {
        "status": "SUPPORTED_BUT_NOT_DECODED",
        "observed_tokens": ["SkillTargetEntityList", "TargetEntity", "AbilityTargetEntity"],
        "exact_serialized_tag": "UNKNOWN",
    },
    "healhp_populated_fields": {
        "status": "UNKNOWN",
        "note": "No heal_hp-shaped node could be structurally decoded from the record using the reference format.",
    },
    "amount_field_encoded_types": {
        "status": "UNKNOWN",
        "note": "No amount DynamicValue/FixPoint payload was structurally linked to a HealHP node.",
    },
    "decoded_dynamicvalue_fixpoint_values": [],
    "hp_by_max_hp_maxhp_linkage": {
        "status": "UNRELATED_NEARBY_RECORD_DATA_OR_UNKNOWN",
        "detail": "HPByMaxHP and MaxHP appear inside the modifier name MAvatar_Natasha_00_HOT_HPByMaxHP and are not proven to be linked to a decoded HealHP action node.",
    },
    "remaining_parser_unknown": [
        "POLYMORPHIC_REGISTRY_ENTRY_HEALHP_MISSING",
        "TARGET_CONFIG_SERIALIZER_TAG_UNKNOWN",
        "HEALHP_FIELD_BITMAP_UNKNOWN",
    ],
    "recommended_next_step": "Recover the 4.4.54 polymorphic action registry mapping for RPG.GameCore.HealHP (which serialized type code maps to HealHP in this binary), then re-parse the Skill02_Phase02 record.",
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
