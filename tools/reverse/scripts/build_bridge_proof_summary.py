#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Combine domain bridge proofs and the ability-mixin structural status into
one session-level bridge proof JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ability-config-new", required=True, type=Path)
    ap.add_argument("--modifier-config-new", required=True, type=Path)
    ap.add_argument("--cross-version", required=True, type=Path)
    ap.add_argument("--ability-headers", required=True, type=Path)
    ap.add_argument("--game-version", default="4.4.54")
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    ability = json.load(open(args.ability_config_new, encoding="utf-8"))
    modifier = json.load(open(args.modifier_config_new, encoding="utf-8"))
    cross = json.load(open(args.cross_version, encoding="utf-8"))
    headers = json.load(open(args.ability_headers, encoding="utf-8"))

    mixin_codes = sorted({int(r["first_mixin_type"]) for r in headers
                          if r.get("first_mixin_type") != ""})
    wrapper_codes = sorted({int(r["wrapper_type_code"]) for r in headers})
    proof = {
        "schema": "mhy_design_runtime_bridge_proof/1",
        "session_status": "DESIGN_RUNTIME_BRIDGE = PARTIAL_MAPPING_RECOVERED",
        "game_version": args.game_version,
        "summary": {
            "bridge_level_1_deserializer_located": True,
            "bridge_level_2_discriminator_recovered": True,
            "bridge_level_3_discriminator_to_runtime_type": True,
            "bridge_level_4_multiple_codes_validated": True,
            "bridge_level_5_cross_version_automated": True,
            "note": ("LEVEL 4/5 are proven for the static-switch domains "
                     "ability_config and modifier_config. The Black Swan "
                     "ability_mixin codes 2/8/14/16 are NOT yet mapped to "
                     "runtime classes; see ability_mixin_status."),
        },
        "confirmed_domains": [
            {
                "serialized_domain": ability["serialized_domain"],
                "mapping_kind": "STATIC_SWITCH_FACTORY",
                "factory": ability["factory"],
                "mechanism": ability["mechanism"],
                "mappings": ability["mappings"],
                "statistics": ability["statistics"],
                "status": "CONFIRMED",
            },
            {
                "serialized_domain": modifier["serialized_domain"],
                "mapping_kind": "STATIC_SWITCH_FACTORY",
                "factory": modifier["factory"],
                "mechanism": modifier["mechanism"],
                "mappings": modifier["mappings"],
                "statistics": modifier["statistics"],
                "status": "CONFIRMED",
            },
        ],
        "cross_version": {
            "file": str(args.cross_version),
            "all_ok": cross.get("all_ok"),
            "results": cross.get("results"),
        },
        "ability_record_structural_status": {
            "sample_domain": "black_swan_ability_records (4.4.53/4.4.54, 15/15)",
            "observed_outer_codes": wrapper_codes,
            "observed_first_mixin_type_codes": mixin_codes,
            "correction": (
                "The first two ULEB128 values of each ability record are "
                "field-presence bitfields in generated binary parsers "
                "(two-bitfield shape, e.g. SkillConfig.FromBinary reads two "
                "ULEBs then tests bits). 'wrapper_type_code' and "
                "'first_mixin_type' are NOT proven Runtime Type indices."),
            "mapping_status": "ABILITY_MIXIN_TYPE_MAPPING_UNRESOLVED",
            "evidence": [
                "SkillAbilityConfig.OJNNBEJLDIJ is the only static direct-call target of the nested CommonSkill parser; it reads one bitfield (Name + AbilityList shape) and is a candidate for the post-outer-header record body",
                "CommonSkill.OJNNBEJLDIJ (0x1CF60710) reads a bitfield and calls SkillConfig.FromBinary / SkillAbilityConfig.OJNNBEJLDIJ / 0x1CFC5830",
                "SkillConfig.FromBinary (0x1D4AAEE0) reads exactly two ULEB bitfields followed by 64+13 optional-field branches (77 fields)",
                "AbilityConfig.FromBinary and ModifierConfig.OJNNBEJLDIJ are static 0..3 switch factories recovered in this session; the Black Swan mixin codes 2/8/14/16 do not fit those switches",
                "No static jump-table switch with case coverage matching 2/8/14/16 and core ability semantics was found in the 4.4.54 il2cpp scan",
                "Generic list/object readers (0x16C86A10/0x16C8E0D0) dispatch element parsers through runtime type descriptors; descriptor slots are BSS-initialized, so static recovery of the mixin element class needs the runtime registry initializer path (not opened in this session)",
            ],
        },
        "evidence_level": ("E4 machine-code serializer/factory dataflow for the "
                           "two confirmed domains; E2 structural for ability "
                           "records; E3 metadata registry used throughout"),
        "not_claimed": [
            "ability_mixin type codes 2/8/14/16 -> Runtime Class mapping",
            "battle Execute / damage / modifier settlement semantics",
            "full DesignData parsing",
            "dynamic runtime type descriptor registry internals",
        ],
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(proof, f, indent=2)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
