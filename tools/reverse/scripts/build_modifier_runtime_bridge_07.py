#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Characterize the Modifier config -> runtime instance bridge (4.4.54).

Unlike Target Selector Batch 05 / Action Execution Batch 06 there is **no**
generated modifier implementation class per config type_reference.  The real
rule is name/config-object dispatch:

    TryAddModifierInstance(this, string name, ModifierConfig config,
                           ability instance, param, bool)
      -> TurnBasedModifierInstance allocation
      -> AbilityComponent._ModifierList append

This script writes that negative/positive characterization instead of forcing
a fake per-config generated bridge.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = REPO / "data" / "raw" / "4.4.54" / "modifier_runtime_bridge_07.json"


def main() -> int:
    report = {
        "schema": "modifier_runtime_bridge/1",
        "game_version": "4.4.54",
        "bridge_status": "NO_GENERATED_CONFIG_TO_INSTANCE_BRIDGE",
        "identity_rule": (
            "runtime ModifierConfig (typeref 104288) + modifier name string "
            "(typeref 37) flow into TurnBasedAbilityComponent."
            "TryAddModifierInstance; the runtime creates a "
            "TurnBasedModifierInstance and appends it to "
            "AbilityComponent._ModifierList. There is no config type_ref -> "
            "generated modifier class row, unlike target/action bridges."
        ),
        "config_factory": {
            "domain": "modifier_config",
            "factory_runtime_type": "RPG.GameCore.ModifierConfig",
            "factory_method": "OJNNBEJLDIJ",
            "method_index": 103116,
            "native_rva": "0x1D21C470",
            "variants": [
                {
                    "serialized_discriminator": 0,
                    "runtime_type": "RPG.GameCore.ModifierConfig",
                    "parser_method_index": 103117,
                    "parser_native_rva": "0x1D21C7D0",
                },
                {
                    "serialized_discriminator": 1,
                    "runtime_type": "RPG.GameCore.AdventureModifierConfig",
                    "parser_method_index": 107223,
                    "parser_native_rva": "0x1CD63BA0",
                },
                {
                    "serialized_discriminator": 2,
                    "runtime_type": "RPG.GameCore.RtModifierConfig",
                    "parser_method_index": 107548,
                    "parser_native_rva": "0x1D4219B0",
                },
                {
                    "serialized_discriminator": 3,
                    "runtime_type": "RPG.GameCore.TurnBasedModifierConfig",
                    "parser_method_index": 108955,
                    "parser_native_rva": "0x1D5810E0",
                },
            ],
            "source": "data/normalized/4.4.54/design_runtime_registry.json",
        },
        "runtime_instance_family": [
            {
                "runtime_type": "RPG.GameCore.BaseModifierInstance",
                "type_index": 54598,
                "method_count": 51,
                "field_count": 24,
                "identity_slots": {
                    "Name": "+0x60 (string, get_Name 0xE4EEF10)",
                    "Count": "+0x7c (int32, get_Count 0xE4EF0E0)",
                    "State": "+0x80 (raw int32, get_State 0xE4EEF40)",
                    "StackingFlag": "+0x88 (raw int32, get_StackingFlag 0xE4EEF60)",
                    "CasterEntity": "+0x58 cache / +0x48 lazy resolver (get_CasterEntity 0xE4EEFC0)",
                },
            },
            {
                "runtime_type": "RPG.GameCore.AdventureModifierInstance",
                "type_index": 54579,
                "method_count": 45,
                "field_count": 24,
            },
            {
                "runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
                "type_index": 55002,
                "method_count": 243,
                "field_count": 109,
                "identity_slots": {
                    "ConfigRef": "+0xa0 (ModifierConfig, get_ConfigRef 0xE78E3E0)",
                    "SourceEntity": "+0x100 cache / +0x48 lazy resolver (get_SourceEntity 0xE78A810)",
                    "Layer": "+0x288 (int32, get_Layer 0xE78E480)",
                    "CurrentLife": "+0x2c4 (int32, get_CurrentLife 0xE78E5C0)",
                    "MaxLayer": "max(1, [+0x2e0] + [+0x270]) (get_MaxLayer 0xE78E500)",
                    "OwnerAbilityComponent": "+0x198 (GetOwnerAbilityComponent 0xE740660)",
                },
            },
            {
                "runtime_type": "ModifierSequenceComposite",
                "type_index": 55003,
                "method_count": 17,
                "field_count": 14,
            },
        ],
        "persistent_container": {
            "runtime_type": "RPG.GameCore.AbilityComponent",
            "type_index": 56973,
            "method_count": 50,
            "field_count": 15,
            "list_slot": "_ModifierList at component [+0x38]",
            "append_leaf": {
                "method": "AddModifierInstance",
                "method_index": 520236,
                "native_rva": "0xE431890",
                "writes": "list [+0x1c] version++, items [array + count*8 + 0x20], count [+0x18]++",
            },
            "owner_component": {
                "runtime_type": "RPG.GameCore.TurnBasedAbilityComponent",
                "type_index": 55009,
                "owner_entity_slot": "component [+0x10] (_OnInitOwnerRef 0xE723BB0)",
            },
        },
        "application_helper": {
            "runtime_type": "RPG.GameCore.TurnBasedAbilityComponent",
            "method": "TryAddModifierInstance",
            "method_index": 506463,
            "native_rva": "0xE729500",
            "parameter_relations": [
                {"parameter_index": 465460, "type_reference": 37, "role": "string modifier name"},
                {"parameter_index": 465461, "type_reference": 104288, "role": "ModifierConfig"},
                {"parameter_index": 465462, "type_reference": 286703, "role": "ability instance (consumer-anchored)"},
                {"parameter_index": 465463, "type_reference": 608873, "role": "UNKNOWN_NAME param"},
                {"parameter_index": 465464, "type_reference": 433618, "role": "bool guard (same typeref as AddModifierInstance bool arg)"},
            ],
            "return_type_reference": 231567,
            "return_type_status": "UNKNOWN_NAME_CONSUMER_ANCHORED",
            "allocation_evidence": (
                "allocates class global 0x95CAFF8 at 0xE729890 and calls "
                "TurnBasedModifierInstance ctor 0xE77EB00 at 0xE7298AE"
            ),
        },
        "evidence_level": "E4_STATIC_MACHINE_CODE + E3 normalized registries",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
