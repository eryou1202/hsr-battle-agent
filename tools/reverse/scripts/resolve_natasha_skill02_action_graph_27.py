#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the Natasha Skill02 action graph and locate HealHP node."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "natasha_skill02_action_graph_27.json"

DATA = {
    "schema": "natasha_skill02_action_graph/1",
    "game_version": "4.4.54",
    "status": "SKILL02_HEALHP_LINKAGE_NOT_FOUND",
    "skill02_record_family": [
        {"name": "Avatar_Natasha_00_Skill02_Phase01", "start": "0xBC9855", "end": "0xBC995F", "length": 266},
        {"name": "Avatar_Natasha_00_Skill02_Phase02", "start": "0xBC995F", "end": "0xBC9BC8", "length": 617},
        {"name": "Avatar_Natasha_00_Skill02_Camera_Other", "start": "0xCCB1CD", "end": "0xCCB3FF", "length": 562},
        {"name": "Avatar_Natasha_00_Skill02_Camera_Self", "start": "0xCCB3FF", "end": "0xCCB518", "length": 537},
        {"name": "Avatar_Natasha_00_Rank01_InsertSkill_Phase02", "start": "0xBCA7E5", "end": "0xBCAB38", "length": 851},
    ],
    "phase02_child_reference_model": {
        "status": "UNKNOWN",
        "note": "Phase02 contains string-like references and modifier names, but no structurally valid selector-7 HealHP action node was found in the bounded records.",
    },
    "structural_selector_7_hits": [],
    "exact_healhp_node_location": None,
    "parent_to_healhp_proof": None,
    "healhp_node_boundary": None,
    "populated_field_presence": None,
    "target_config_status": "NOT_DECODED",
    "amount_field_structural_status": "NOT_DECODED",
    "remaining_single_blocker": "SKILL02_HEALHP_LINKAGE_NOT_FOUND",
    "blocker_boundary": "Resolution stops at the Natasha Skill02 phase/action container encoding: the phase records do not contain an inline selector-7 HealHP action node, and the outer ability/action container that links Skill02 to a HealHP node is not yet resolved.",
    "recommended_next_step": "Map the outer ability/action container for Avatar_Natasha_00_Ability.json and its Skill02 action references (string-keyed or object-table indirection), then follow the reference to the selector-7 HealHP node.",
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
