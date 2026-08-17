#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the bounded generic source-0 property mutation bridge.

This deliberately scopes out entries with a non-null post-transform and the
property IDs with dedicated branches in ModifyProperty.  It records the
native-common path, rather than inventing those unrecovered policies.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    build_native_evidence,
    disasm_window,
    iter_records,
    load_manifest,
    load_pe,
)


GAME_VERSION = "4.4.54"
OUT = REPO / "data" / "semantics" / GAME_VERSION / "generic_property_mutation_11.json"
E4 = "E4_STATIC_MACHINE_CODE"

REGISTERED = {
    506503: {"native_rva": 0xE72DCE0, "body_bytes": 0x8E6, "abi": "win64"},
}

HELPERS = {
    "modify_value": {
        "rva": 0xE4410D0,
        "length": 0x1C0,
        "semantic_name": "ApplyPropertyModifyFunction",
    },
    "fixedpoint_add": {
        "rva": 0x1D65EF80,
        "length": 0x123,
        "semantic_name": "FixedPointAdd",
    },
    "fixedpoint_mul": {
        "rva": 0x1D661A00,
        "length": 0x15A,
        "semantic_name": "FixedPointMultiply",
    },
    "fixedpoint_sub": {
        "rva": 0x1D661B60,
        "length": 0x6F,
        "semantic_name": "FixedPointSubtract",
    },
}


def selected_methods() -> dict[int, dict]:
    found: dict[int, dict] = {}
    for row in iter_records(REPO / "data" / "normalized" / GAME_VERSION / "methods.json"):
        if row["method_index"] in REGISTERED:
            found[row["method_index"]] = row
    missing = set(REGISTERED) - set(found)
    if missing:
        raise RuntimeError(f"missing method identities: {sorted(missing)}")
    return found


def registered_evidence(pe, methods: dict[int, dict], method_index: int) -> dict:
    evidence = build_native_evidence(pe, {
        "method_index": method_index,
        **REGISTERED[method_index],
    }, methods[method_index])
    evidence.pop("disassembly")
    evidence["body_projection"] = "FIRST_SUCCESSFUL_RET"
    return evidence


def helper_evidence(pe, key: str) -> dict:
    spec = HELPERS[key]
    raw, decoded = disasm_window(pe, spec["rva"], spec["length"])
    if not decoded or decoded[-1]["mnemonic"] != "ret":
        got = decoded[-1]["mnemonic"] if decoded else "none"
        raise RuntimeError(f"{key}: expected ret, got {got}")
    final_end = decoded[-1]["rva"] + decoded[-1]["size"] - spec["rva"]
    if final_end != spec["length"]:
        raise RuntimeError(f"{key}: terminal length mismatch")
    return {
        "native_rva": f"0x{spec['rva']:X}",
        "body_length_bytes": spec["length"],
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_projection": "FIRST_SUCCESSFUL_RET",
        "instruction_count": len(decoded),
        "conditional_branch_count": sum(
            1 for ins in decoded
            if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
        ),
        "direct_call_count": sum(1 for ins in decoded if ins["mnemonic"] == "call"),
        "direct_jump_count": sum(1 for ins in decoded if ins["mnemonic"] == "jmp"),
        "abi": "win64",
    }


def helper_primitive(pe, key: str, **body: object) -> dict:
    evidence = helper_evidence(pe, key)
    return {
        "primitive_id": body.pop("primitive_id"),
        "semantic_name": HELPERS[key]["semantic_name"],
        "evidence_level": E4,
        "runtime_identity": {
            "runtime_type": "native fixed-point/property helper",
            "method_index": None,
            "method_name": None,
            "identity_status": "UNREGISTERED_NATIVE_HELPER",
        },
        "native_rva": evidence["native_rva"],
        "native_body_hash": evidence["body_sha256"],
        "native_evidence": evidence,
        "determinism": "DETERMINISTIC_SATURATING_FIXEDPOINT",
        **body,
    }


def build() -> dict:
    pe = load_pe()
    methods = selected_methods()
    modify_evidence = registered_evidence(pe, methods, 506503)
    primitives = [
        helper_primitive(
            pe,
            "fixedpoint_add",
            primitive_id="battle.ir.fixedpoint.add",
            inputs=["left", "right"],
            output="saturating fixed-point sum",
            reads=[],
            writes=[],
            exact_semantics=["Native fast path computes left + right; overflow/non-immediate paths saturate through the same fixed-point representation."],
            pseudocode=["return saturating_fixedpoint_add(left, right)"],
        ),
        helper_primitive(
            pe,
            "fixedpoint_sub",
            primitive_id="battle.ir.fixedpoint.subtract",
            inputs=["left", "right"],
            output="saturating fixed-point difference",
            reads=[],
            writes=[],
            exact_semantics=["Native fast path computes left - right; overflow/non-immediate paths saturate through the same fixed-point representation."],
            pseudocode=["return saturating_fixedpoint_subtract(left, right)"],
        ),
        helper_primitive(
            pe,
            "fixedpoint_mul",
            primitive_id="battle.ir.fixedpoint.multiply",
            inputs=["left", "right"],
            output="saturating fixed-point product",
            reads=[],
            writes=[],
            exact_semantics=["Native path multiplies the encoded fixed-point operands and saturates on range overflow."],
            pseudocode=["return saturating_fixedpoint_multiply(left, right)"],
        ),
        helper_primitive(
            pe,
            "modify_value",
            primitive_id="battle.ir.property.apply_modify_function",
            inputs=["function_id", "old_materialized_value", "operand"],
            output="pre-post-transform candidate",
            reads=[],
            writes=[],
            exact_semantics=[
                "function_id 1 returns operand (Set).",
                "function_id 2 calls FixedPointAdd(old, operand).",
                "function_id 3 calls FixedPointMultiply(old, operand).",
                "function_id 4 returns min(old, operand) under fixed-point comparison.",
                "function_id 5 returns max(old, operand) under fixed-point comparison.",
                "An out-of-range function_id follows the same return-operand fallthrough as Set in this helper.",
            ],
            pseudocode=[
                "switch function_id:",
                "  case 1: return operand",
                "  case 2: return fp_add(old, operand)",
                "  case 3: return fp_mul(old, operand)",
                "  case 4: return fp_min(old, operand)",
                "  case 5: return fp_max(old, operand)",
                "  default: return operand",
            ],
        ),
        {
            "primitive_id": "battle.ir.property.modify_source_zero_untransformed",
            "semantic_name": "ModifyPropertySourceZeroUntransformed",
            "evidence_level": E4,
            "runtime_identity": {
                "runtime_type": "RPG.GameCore.TurnBasedAbilityComponent",
                "method_index": 506503,
                "method_name": methods[506503]["name"],
                "declaring_type_index": methods[506503]["declaring_type_index"],
            },
            "native_rva": modify_evidence["body_rva"],
            "native_body_hash": modify_evidence["body_sha256"],
            "native_evidence": modify_evidence,
            "inputs": ["component", "property_id", "function_id", "operand", "context_token"],
            "output": "bool changed",
            "reads": [
                "component property-entry table at +0xA0",
                "selected entry[+0x78] old materialized value",
                "selected entry[+0x40] post-transform context",
                "component/property acceptance guards",
            ],
            "writes": [
                "selected entry source slot 0 through 0x1957559D0",
                "selected entry[+0x78] through the existing materialization runtime",
                "post-change call M506625 _AfterPropertyChanged",
            ],
            "determinism": "DETERMINISTIC_WHEN_ACCEPTANCE_GUARDS_AND_CONTEXT_ARE_FIXED",
            "scope_preconditions": [
                "The selected property entry exists and native acceptance guards admit the mutation.",
                "entry[+0x40] is null, making 0x19CAF14A0 an observed no-op.",
                "property_id is outside {10,12,14,16,18,20,22,24,26,28,30,32}, so the native special-property jump table takes its common path.",
            ],
            "exact_semantics": [
                "Captures old = entry[+0x78].",
                "Computes candidate with ApplyPropertyModifyFunction(function_id, old, operand).",
                "For the scoped null post-transform, candidate is unchanged by 0x19CAF14A0.",
                "Calls the stable-slot updater with source_index=0 and candidate; this rebuilds entry[+0x78] immediately.",
                "Computes materialized_delta = entry[+0x78] - old and invokes M506625 with old/new/context data before returning true.",
                "A normal guard rejection reaches the false return path without this source-0 write.",
            ],
            "pseudocode": [
                "entry = require_mutable_property_entry(component, property_id)",
                "old = entry.materialized",
                "candidate = apply_modify_function(function_id, old, operand)",
                "assert entry.post_transform_context is null  # scoped contract",
                "update_source_slot(entry, source_index=0, source_value=candidate)",
                "new = entry.materialized",
                "after_property_changed(component, property_id, old, new, context_token)",
                "return true",
            ],
            "unknowns": [
                "Non-null entry[+0x40] invokes the distinct post-transform family at 0x19CAF14A0.",
                "The special property IDs have dedicated policy branches and are intentionally excluded from this capability.",
                "The downstream listener/event semantics of _AfterPropertyChanged are not asserted here; the observable contract ends at the persistent materialized write.",
            ],
        },
    ]
    return {
        "schema": "battle_semantic_bridge/1",
        "game_version": GAME_VERSION,
        "capability_id": "GENERIC_PROPERTY_MUTATION_SOURCE0_11_PROOF",
        "status": "CONFIRMED_SCOPED_UNTRANSFORMED_COMMON_PROPERTY_MUTATION",
        "evidence_level": E4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {"GameAssembly_sha256": load_manifest()["GameAssembly"]["sha256"]},
        "config_bindings": [
            {
                "config_source": "RPG.GameCore.PropertyModifyFunction enum (type 15455; native arithmetic is primary evidence)",
                "serialized_fields": ["property_id", "function_id", "operand"],
                "runtime_inputs": ["M506503 edx=property_id", "r8d=function_id", "r9=operand", "stack=context_token"],
                "enum_mapping": {"1": "Set", "2": "Add", "3": "Mul", "4": "MinSet", "5": "MaxSet"},
            }
        ],
        "primitives": primitives,
        "semantic_chains": [
            {
                "chain_id": "untransformed_common_property_mutation",
                "steps": [
                    "M506503 ModifyProperty",
                    "0xE4410D0 ApplyPropertyModifyFunction",
                    "0x19CAF14A0 null-context no-op",
                    "0x1957559D0 UpdatePropertySourceSlot(entry, 0, candidate)",
                    "entry[+0x78] materialized persistent result",
                    "M506625 _AfterPropertyChanged call",
                ],
                "observable_result": "selected property entry's persistent materialized value changes through source slot 0",
            }
        ],
        "persistent_state_requirements": [
            "Reuse Generic Property Materialization 10's source arrays and entry[+0x78].",
            "Source index 0 is the native mutable base/update slot in this path; do not allocate or shift it.",
            "Persist the selected entry's post-transform context so unsupported non-null contexts can be rejected rather than silently ignored.",
        ],
        "dependencies": [
            "GENERIC_PROPERTY_SOURCE_SLOT_MATERIALIZATION_10_PROOF",
            "FixedPoint runtime and comparison primitives (Batches 03-04)",
        ],
        "unknowns": [
            "0x19CAF14A0 non-null post-transform contract",
            "CurrentHP/NegativeHP and other special-property branch policies",
            "Config-to-M506503 action executor bridge",
            "_AfterPropertyChanged listener/event consumers",
        ],
        "must_not_implement": [
            "Do not apply the scoped path when entry[+0x40] is non-null.",
            "Do not treat source slot 0 as a disposable modifier contribution key.",
            "Do not apply this generic common path to the listed special property IDs.",
            "Do not invent callback/event behavior after M506625 from its name alone.",
        ],
    }


if __name__ == "__main__":
    artifact = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
