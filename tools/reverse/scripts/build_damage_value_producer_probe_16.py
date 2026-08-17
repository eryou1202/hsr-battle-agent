#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the damage value producer probe artifact."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "damage_value_producer_probe_16.json"

DATA = {
    "schema": "damage_value_producer_probe/1",
    "game_version": "4.4.54",
    "status": "PREPROCESS_ONLY",
    "request_identity": {
        "observed_as": "M507308 r8 object",
        "evidence_level": "SUPPORTED",
        "allocation_or_materialization_site": "M507296 OnTaskBegin at 0xC30EC14 calls 0x183C736B0 with type token global 0x962F8E0 and stores into a request-like object",
        "normalized_type_match": "UNKNOWN; no type containing DamageRequest/DamageResult matched the runtime object in the current normalized type set",
        "declared_field_0x2D8": "UNKNOWN; +0x2D8 is treated as a native/runtime slot in this probe",
        "note": "The same +0x2D8 offset is used by multiple object families; only methods on the M507308/M504579/M504598/M508236 chain are treated as request-family evidence here.",
    },
    "slot_0x2D8": {
        "reads": [
            {"method_index": 507308, "method_name": "NNGMOCFGPBN", "rva": "0xC3125F4"},
            {"method_index": 507308, "method_name": "NNGMOCFGPBN", "rva": "0xC3135FA"},
            {"method_index": 507308, "method_name": "NNGMOCFGPBN", "rva": "0xC31367F"},
            {"method_index": 508236, "method_name": "OnTaskBegin", "rva": "0xB3DC7FC"},
        ],
        "writes": [
            {"method_index": 508236, "method_name": "OnTaskBegin", "rva": "0xB3DC80C", "form": "mov qword ptr [r12 + 0x2d8], rax", "class": "ACCUMULATION_WRITE"},
            {"method_index": 504557, "method_name": "RecomputeShieldCost", "rva": "0xE4650B9", "form": "mov qword ptr [rax + 0x2d8], rcx", "class": "POSTPROCESS_WRITE"},
            {"method_index": 504598, "method_name": "_MortallyWondedProcess", "rva": "0xE465C77", "form": "mov qword ptr [rax + 0x2d8], rcx", "class": "POSTPROCESS_WRITE"},
            {"method_index": 504550, "method_name": "DamageFormula", "rva": "0xE462D51", "form": "mov qword ptr [rbp + 0x2d8], rbx", "class": "UNKNOWN_LIKELY_STACK_LOCAL"},
            {"method_index": 504576, "method_name": "SnapshotDamageMod", "rva": "0xE46AB2A", "form": "mov qword ptr [rsi + 0x2d8], rax", "class": "UNKNOWN_POINTER_WRITE"},
            {"method_index": 504500, "method_name": "ModifyEntitiesActionDelay", "rva": "0xE458491", "form": "mov qword ptr [rbp + 0x2d8], rdx", "class": "UNKNOWN_LIKELY_STACK_LOCAL"},
        ],
        "pre_postprocess_writers": [
            {
                "method_index": 508236,
                "method_name": "OnTaskBegin",
                "declaring_type": "AABAELPKKGK",
                "config": "RPG.GameCore.ProcessStoredDamage",
                "instruction_rva": "0xB3DC80C",
                "classification": "ACCUMULATION_WRITE",
                "source": "reads existing [r12+0x2D8], adds r13 via 0x19D661A00, writes back",
            }
        ],
        "postprocess_writers": [
            {"method_index": 504557, "method_name": "RecomputeShieldCost", "instruction_rva": "0xE4650B9"},
            {"method_index": 504598, "method_name": "_MortallyWondedProcess", "instruction_rva": "0xE465C77"},
        ],
    },
    "writer_clusters": [
        {
            "name": "PROCESS_STORED_DAMAGE_ACCUMULATOR",
            "members": [508236],
            "reason": "M508236 OnTaskBegin reads/writes request[+0x2D8] and then calls M508237 -> M507308.",
        },
        {
            "name": "ABILITY_STATIC_POSTPROCESS",
            "members": [504557, 504598],
            "reason": "Both write +0x2D8 inside AbilityStatic post-process helpers; they are downstream of the original producer.",
        },
        {
            "name": "STACK_LOCAL_OR_OTHER_OBJECT_FAMILY",
            "members": [504550, 504576, 504500],
            "reason": "Writes to +0x2D8 on stack frames or to a pointer-typed slot; not yet proven to be the same request FixPoint slot.",
        },
    ],
    "ranked_candidates": [
        {
            "rank": 1,
            "classification": "DAMAGE_VALUE_ACCUMULATOR_CANDIDATE",
            "method_index": 508236,
            "method_name": "OnTaskBegin",
            "rva": "0xB3DC5B0",
            "instruction_rva": "0xB3DC80C",
            "body_hash": "5fa81c58bac1420f8527951e2f7551d5584a6b9df886e3274079bf3aa0f48d87",
            "representative_callers": [
                {"executor_type": "AABAELPKKGK", "config": "RPG.GameCore.ProcessStoredDamage", "caller_method": "OnTaskBegin"},
            ],
            "source_value_provenance": "existing request[+0x2D8] + r13 via 0x19D661A00",
            "preceding_helpers": ["0x19D661A00"],
            "upstream_executor_config_evidence": "ProcessStoredDamage executor path; calls M508237 FENDMHJDPJD which calls M507308.",
            "reason": "Only confirmed pre-postprocess writer that writes +0x2D8 before M507308 in a generated executor path.",
        },
        {
            "rank": 2,
            "classification": "REQUEST_INITIALIZER",
            "method_index": 507296,
            "method_name": "OnTaskBegin",
            "rva": "0xC30D850",
            "instruction_rva": "0xC30EC14",
            "body_hash": None,
            "representative_callers": [
                {"executor_type": "PGOOHIHKHNJ", "config": "RPG.GameCore.DamageByAttackProperty", "caller_method": "OnTaskBegin"},
            ],
            "source_value_provenance": "allocates request-like object via 0x183C736B0 with type token 0x962F8E0; +0x2D8 not directly written in this method",
            "preceding_helpers": ["0x183C736B0"],
            "upstream_executor_config_evidence": "DamageByAttackProperty executor path; calls M507304 -> M507308.",
            "reason": "Closest DamageByAttackProperty request-object materialization site; actual +0x2D8 value source remains unresolved.",
        },
        {
            "rank": 3,
            "classification": "POSTPROCESS_ONLY",
            "method_index": 504557,
            "method_name": "RecomputeShieldCost",
            "rva": "0xE464D20",
            "instruction_rva": "0xE4650B9",
            "body_hash": "f4b8931c72e5a5044edb36fb72e282528ff80d75d929073a05fddd006ecf29e7",
            "representative_callers": [],
            "source_value_provenance": "[rsp+0x38] after fixed-point calls; writes to [rax+0x2D8]",
            "preceding_helpers": ["0x19D661B60", "0x19D65EF80"],
            "upstream_executor_config_evidence": "AbilityStatic post-process / shield cost path.",
            "reason": "Writes +0x2D8 but is a post-process writer, not the original pre-M507308 producer.",
        },
        {
            "rank": 4,
            "classification": "POSTPROCESS_ONLY",
            "method_index": 504598,
            "method_name": "_MortallyWondedProcess",
            "rva": "0xE465660",
            "instruction_rva": "0xE465C77",
            "body_hash": "6fac82d4e55bcdad1366184fdd1a133fce5b7f511e012d75c3226be2943efe0a",
            "representative_callers": [{"caller_method": "DamagePostProcess", "caller_method_index": 504559}],
            "source_value_provenance": "FixPoint(0) from global 0x95B1DE0 in one branch",
            "preceding_helpers": ["0x95B1DE0"],
            "upstream_executor_config_evidence": "M507308 calls M504559 -> M504598 before forwarding V.",
            "reason": "Post-process writer explicitly separated from the original producer.",
        },
        {
            "rank": 5,
            "classification": "UNKNOWN",
            "method_index": 504550,
            "method_name": "DamageFormula",
            "rva": "0xE460BE0",
            "instruction_rva": "0xE462D51",
            "body_hash": "0d49400e9a0466e497520bddea20a5318d6a8ee84e00d981641c48a0becde986",
            "representative_callers": [],
            "source_value_provenance": "[rsp+0x38] after two 0x19D661A00 calls; writes to [rbp+0x2D8]",
            "preceding_helpers": ["0x19D661A00", "0x19D661A00"],
            "upstream_executor_config_evidence": "AbilityStatic.DamageFormula; likely a stack-local FixPoint result, not proven request slot.",
            "reason": "Name is suggestive but the write target is a stack frame slot; needs disambiguation before promotion.",
        },
        {
            "rank": 6,
            "classification": "UNKNOWN",
            "method_index": 504576,
            "method_name": "SnapshotDamageMod",
            "rva": "0xE468AC0",
            "instruction_rva": "0xE46AB2A",
            "body_hash": "adf12edbadb2a2d560b26153728c4c7a9cc871c18b4bac0e043326f22245439d",
            "representative_callers": [],
            "source_value_provenance": "allocated object pointer via 0x183C736B0; writes [rsi+0x2D8] = pointer",
            "preceding_helpers": ["0x183C736B0"],
            "upstream_executor_config_evidence": "AbilityStatic.SnapshotDamageMod; likely a different object family where +0x2D8 is a reference.",
            "reason": "Writes a pointer, not a FixPoint; not promoted as damage value producer.",
        },
    ],
    "recommended_v4p_entry": {
        "primary": {
            "method_index": 508236,
            "method_name": "OnTaskBegin",
            "rva": "0xB3DC5B0",
            "instruction_rva": "0xB3DC80C",
            "reason": "Only confirmed pre-postprocess +0x2D8 writer on a generated executor path that calls M507308.",
        },
        "alternates": [
            {"method_index": 507296, "method_name": "OnTaskBegin", "rva": "0xC30D850", "reason": "DamageByAttackProperty request materialization site; +0x2D8 source still unresolved."},
            {"method_index": 504557, "method_name": "RecomputeShieldCost", "rva": "0xE464D20", "reason": "Post-process writer that may overwrite +0x2D8."},
            {"method_index": 504598, "method_name": "_MortallyWondedProcess", "rva": "0xE465660", "reason": "Post-process writer explicitly separated from original producer."},
        ],
        "minimal_unresolved_input_output_contract": "For DamageByAttackProperty, locate the actual +0x2D8 initialization before M507308; trace the object allocated at 0xC30EC14 (type token 0x962F8E0) to its field-write site.",
    },
    "remaining_ambiguity": [
        "No direct +0x2D8 writer was found inside M507296/M507304/M507308 for DamageByAttackProperty; the request object may be populated before OnTaskBegin or via an indirect helper.",
        "M504550/M504500 writes are on stack frames and are not proven to target the request object.",
        "M504576 writes a pointer into +0x2D8 and is likely a different object family.",
    ],
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
