#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve a config polymorphic factory-table entry for a runtime type index.

This is a narrow helper: it records the factory-thunk table and selector for a
known config family. It does not rebuild the polymorphic registry framework.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "healhp_polymorphic_registry_entry_26.json"

DATA = {
    "schema": "config_polymorphic_registry_entry/1",
    "game_version": "4.4.54",
    "status": "HEALHP_REGISTRY_ENTRY_26_PROOF",
    "runtime_type": "RPG.GameCore.HealHP",
    "type_index": 22352,
    "methods": [
        {"method_index": 124664, "name": ".ctor", "native_rva": "0x1D0EBD50", "role": "CONSTRUCTOR"},
        {"method_index": 124665, "name": "OJNNBEJLDIJ", "native_rva": "0x1D0EBBD0", "parameter_count": 2, "role": "SERIALIZER_IMPL_OR_INIT"},
        {"method_index": 124666, "name": "MGMEGEDLMAK", "native_rva": "0x1D0EBEB0", "parameter_count": 2, "role": "DESERIALIZER_IMPL"},
    ],
    "fields": [
        {"field_index": 97106, "name": "TargetType"},
        {"field_index": 97107, "name": "HealerTargetType"},
        {"field_index": 97108, "name": "AliveOnly"},
        {"field_index": 97109, "name": "FormulaType"},
        {"field_index": 97110, "name": "HealPercentage"},
        {"field_index": 97111, "name": "SPHitRatio"},
        {"field_index": 97112, "name": "ModifyValue"},
        {"field_index": 97113, "name": "IsHealRallyHP"},
        {"field_index": 97114, "name": "ScreenSpaceFloatMsg"},
        {"field_index": 97115, "name": "DisplayData"},
        {"field_index": 97116, "name": "PerformanceDelay"},
    ],
    "dispatcher": {
        "factory_thunk_table_rva": "0x49392E0",
        "healhp_thunk_rva": "0x1CC131D0",
        "table_index": 7,
        "healhp_factory_thunk": {
            "alloc_type_token_global": "0x961AA08",
            "call_ojnnbejldij": "0x1D0EBBD0",
            "call_mgmegedlmak": "0x1D0EBEB0",
        },
        "selector_encoding": "ULEB/VLQ unsigned varint",
        "selector_value": 7,
        "selector_bytes": "0x07",
    },
    "proof_chain": [
        "serialized selector 7",
        "factory thunk table 0x49392E0 index 7",
        "thunk 0x1CC131D0",
        "alloc type token 0x961AA08",
        "call M124665 OJNNBEJLDIJ 0x1D0EBBD0",
        "call M124666 MGMEGEDLMAK 0x1D0EBEB0",
        "RPG.GameCore.HealHP type_index 22352",
    ],
    "natasha_record_status": {
        "record": "Avatar_Natasha_00_Skill02_Phase02",
        "record_range": "0xBC995F-0xBC9BC8",
        "healhp_node_decoded": False,
        "reason": "The record does not contain a standalone type_code 7 action node that parses as heal_hp in this bounded window; the HealHP config may be reached through an outer table/index or another phase.",
    },
    "remaining_single_blocker": "NATASHA_RECORD_HEALHP_NODE_INDIRECTION_OR_OTHER_PHASE",
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
