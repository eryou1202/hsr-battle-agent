#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the bounded generic property source-slot/materialization bridge.

This captures the reusable storage mechanics below modifier StackProperty.
It deliberately does not assign gameplay names to the opaque fixed-point
operators used by the seven native materialization modes.
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
OUT = REPO / "data" / "semantics" / GAME_VERSION / "generic_property_materialization_10.json"
E4 = "E4_STATIC_MACHINE_CODE"

# Exact first-successful-return windows for registered methods.
REGISTERED = {
    506495: {"native_rva": 0xE72EB90, "body_bytes": 0x267, "abi": "win64"},
    506496: {"native_rva": 0xE731B80, "body_bytes": 0x1FB, "abi": "win64"},
    506497: {"native_rva": 0xE731D90, "body_bytes": 0x2BF, "abi": "win64"},
}

# The helper cluster has no MethodDefinition/code-table slot.  It is still
# directly reached by native relative calls.  ``terminal_kind`` documents the
# bounded normal-path projection rather than pretending these helpers have a
# metadata method identity.
HELPERS = {
    "allocate_source_slot": {
        "rva": 0x15755890, "length": 0x78, "terminal_kind": "ret",
        "semantic_name": "AllocatePropertySourceSlot",
    },
    "update_source_slot": {
        "rva": 0x157559D0, "length": 0x6D, "terminal_kind": "jmp",
        "semantic_name": "UpdatePropertySourceSlot",
    },
    "rebuild_materialized": {
        "rva": 0x15755AE0, "length": 0xEF, "terminal_kind": "jmp",
        "semantic_name": "RebuildMaterializedProperty",
    },
    "remove_source_slot": {
        "rva": 0x15755FD0, "length": 0x5C, "terminal_kind": "jmp",
        "semantic_name": "RemovePropertySourceSlot",
    },
    "materialize_kind_3": {
        "rva": 0x15756820, "length": 0x85, "terminal_kind": "ret",
        "semantic_name": "MaterializeKind3ActiveFold",
    },
    "materialize_kind_4": {
        "rva": 0x157568E0, "length": 0xA2, "terminal_kind": "ret",
        "semantic_name": "MaterializeKind4ActiveFold",
    },
    "materialize_kind_5": {
        "rva": 0x157569C0, "length": 0xAB, "terminal_kind": "ret",
        "semantic_name": "MaterializeKind5ActiveFold",
    },
    "materialize_kind_6": {
        "rva": 0x15756AA0, "length": 0x161, "terminal_kind": "ret",
        "semantic_name": "MaterializeKind6Extremum",
    },
    "materialize_kind_7": {
        "rva": 0x15756C40, "length": 0x161, "terminal_kind": "ret",
        "semantic_name": "MaterializeKind7Extremum",
    },
}


def selected_methods() -> dict[int, dict]:
    wanted = set(REGISTERED)
    found: dict[int, dict] = {}
    for row in iter_records(REPO / "data" / "normalized" / GAME_VERSION / "methods.json"):
        if row["method_index"] in wanted:
            found[row["method_index"]] = row
    if wanted != set(found):
        raise RuntimeError(f"missing method identities: {sorted(wanted - set(found))}")
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
    if not decoded:
        raise RuntimeError(f"no instructions at {key}")
    final = decoded[-1]
    if final["mnemonic"] != spec["terminal_kind"]:
        raise RuntimeError(
            f"{key}: expected terminal {spec['terminal_kind']}, got {final['mnemonic']}"
        )
    end = final["rva"] + final["size"] - spec["rva"]
    if end != spec["length"]:
        raise RuntimeError(f"{key}: terminal length mismatch")
    return {
        "runtime_identity": f"native_helper@0x{spec['rva']:X}",
        "method_index": None,
        "method_identity_status": "UNREGISTERED_NATIVE_HELPER",
        "native_rva": f"0x{spec['rva']:X}",
        "body_length_bytes": spec["length"],
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_projection": (
            "FIRST_SUCCESSFUL_RET"
            if spec["terminal_kind"] == "ret"
            else "NORMAL_PATH_TAIL_JUMP"
        ),
        "instruction_count": len(decoded),
        "conditional_branch_count": sum(
            1 for ins in decoded
            if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
        ),
        "direct_call_count": sum(1 for ins in decoded if ins["mnemonic"] == "call"),
        "direct_jump_count": sum(1 for ins in decoded if ins["mnemonic"] == "jmp"),
        "abi": "win64",
    }


def registered_primitive(pe, methods: dict[int, dict], method_index: int, **body) -> dict:
    method = methods[method_index]
    evidence = registered_evidence(pe, methods, method_index)
    return {
        "primitive_id": body.pop("primitive_id"),
        "semantic_name": body.pop("semantic_name"),
        "evidence_level": E4,
        "runtime_identity": {
            "runtime_type": body.pop("runtime_type"),
            "method_index": method_index,
            "method_name": method["name"],
            "declaring_type_index": method["declaring_type_index"],
        },
        "native_rva": evidence["body_rva"],
        "native_body_hash": evidence["body_sha256"],
        "native_evidence": evidence,
        "determinism": "DETERMINISTIC",
        **body,
    }


def helper_primitive(pe, key: str, **body) -> dict:
    evidence = helper_evidence(pe, key)
    return {
        "primitive_id": body.pop("primitive_id"),
        "semantic_name": HELPERS[key]["semantic_name"],
        "evidence_level": E4,
        "runtime_identity": {
            "runtime_type": "PropertyEntry (native layout; metadata type unresolved)",
            "method_index": None,
            "method_name": None,
            "identity_status": "UNREGISTERED_NATIVE_HELPER",
        },
        "native_rva": evidence["native_rva"],
        "native_body_hash": evidence["body_sha256"],
        "native_evidence": evidence,
        "determinism": "DETERMINISTIC",
        **body,
    }


def build() -> dict:
    pe = load_pe()
    methods = selected_methods()
    helpers = {key: helper_evidence(pe, key) for key in HELPERS}
    primitives = [
        registered_primitive(
            pe, methods, 506495,
            primitive_id="battle.ir.property.component_stack_source",
            semantic_name="ComponentStackPropertySource",
            runtime_type="RPG.GameCore.TurnBasedAbilityComponent",
            inputs=["component", "property_id", "runtime_value", "context_token"],
            output="source_index",
            reads=["component property entry", "entry[+0x78] pre-materialized value"],
            writes=["allocates one active source slot through 0x15755890", "notifies through _AfterPropertyChanged"],
            exact_semantics=[
                "Fetches the selected property entry.",
                "Routes the input through a bounded native value/context adapter at 0x15C6E450.",
                "Passes the adapter result to AllocatePropertySourceSlot; its returned int is the source_index tracked by ModifierStackProperty.",
                "Reads entry[+0x78] before and after the source allocation and forwards both values to _AfterPropertyChanged.",
            ],
            pseudocode=[
                "entry = safe_fetch(component, property_id)",
                "source_value = native_property_value_adapter(component, property_id, runtime_value, context_token)",
                "source_index = allocate_source_slot(entry, source_value)",
                "notify_after_property_changed(component, property_id, old_materialized, entry.materialized, context_token)",
                "return source_index",
            ],
            unknowns=["The adapter's per-property transformation is not part of this capability; raw DynamicValue is not proven identical to stored source_value."],
        ),
        registered_primitive(
            pe, methods, 506497,
            primitive_id="battle.ir.property.update_contribution_source",
            semantic_name="UpdateStackPropertySource",
            runtime_type="RPG.GameCore.TurnBasedAbilityComponent",
            inputs=["component", "property_id", "source_index", "new_source_value", "context_token"],
            output="none",
            reads=["property entry[+0x78] old value"],
            writes=["source slot at source_index through 0x157559D0", "entry[+0x78] materialized value"],
            exact_semantics=["Updates the existing source_index, rebuilds immediately, then notifies old/new materialized values."],
            pseudocode=[
                "entry = safe_fetch(component, property_id)",
                "old = entry.materialized",
                "update_source_slot(entry, source_index, new_source_value)",
                "notify_after_property_changed(component, property_id, old, entry.materialized, context_token)",
            ],
        ),
        registered_primitive(
            pe, methods, 506496,
            primitive_id="battle.ir.property.remove_contribution_source",
            semantic_name="UnStackPropertySource",
            runtime_type="RPG.GameCore.TurnBasedAbilityComponent",
            inputs=["component", "property_id", "source_index", "context_token"],
            output="none",
            reads=["property entry[+0x78] old value"],
            writes=["source active/version records at source_index through 0x15755FD0", "entry[+0x78] materialized value"],
            exact_semantics=["Disables the source_index rather than shift-removing it, rebuilds immediately, then notifies old/new materialized values."],
            pseudocode=[
                "entry = safe_fetch(component, property_id)",
                "old = entry.materialized",
                "remove_source_slot(entry, source_index)",
                "notify_after_property_changed(component, property_id, old, entry.materialized, context_token)",
            ],
        ),
        helper_primitive(
            pe, "allocate_source_slot",
            primitive_id="battle.ir.property.allocate_source_slot",
            inputs=["property_entry", "source_value"],
            output="source_index:int32",
            reads=["entry[+0x10] source generation array", "entry[+0x20] active-bit array", "entry[+0x30] source-value array", "entry[+0x5C] generation counter"],
            writes=["entry[+0x30][source_index] = source_value", "entry[+0x20][source_index] = true", "entry[+0x10][source_index] = ++entry[+0x5C]", "entry[+0x64] = source_index", "entry[+0x78] through rebuild"],
            exact_semantics=["Allocates a source index via 0x15755F00, stores the source value, marks it active/versioned, then immediately rebuilds."],
            pseudocode=[
                "source_index = allocate_entry_index(entry)",
                "entry.source_values[source_index] = source_value",
                "entry.source_active[source_index] = true",
                "entry.source_generation[source_index] = ++entry.generation",
                "entry.last_changed_source = source_index",
                "rebuild_materialized(entry)",
                "return source_index",
            ],
        ),
        helper_primitive(
            pe, "update_source_slot",
            primitive_id="battle.ir.property.update_source_slot",
            inputs=["property_entry", "source_index", "source_value"],
            output="none",
            reads=["entry source arrays", "entry[+0x5C] generation counter"],
            writes=["entry[+0x30][source_index] = source_value", "entry[+0x20][source_index] = true", "entry[+0x10][source_index] = ++entry[+0x5C]", "entry[+0x64] = source_index", "entry[+0x78] through rebuild"],
            exact_semantics=["Overwrites a stable source index and rebuilds; it does not allocate a new index."],
            pseudocode=[
                "entry.source_values[source_index] = source_value",
                "entry.source_active[source_index] = true",
                "entry.source_generation[source_index] = ++entry.generation",
                "entry.last_changed_source = source_index",
                "rebuild_materialized(entry)",
            ],
        ),
        helper_primitive(
            pe, "remove_source_slot",
            primitive_id="battle.ir.property.remove_source_slot",
            inputs=["property_entry", "source_index"],
            output="none",
            reads=["entry[+0x60] active-source extent", "entry source arrays"],
            writes=["entry[+0x20][source_index] = false", "entry[+0x10][source_index] = 0", "entry[+0x78] through rebuild"],
            exact_semantics=["Does not shift source slots or clear the stale source value; only active/version state changes before rebuild."],
            pseudocode=[
                "if entry.active_source_extent <= 0: return",
                "entry.source_active[source_index] = false",
                "entry.source_generation[source_index] = 0",
                "refresh_source_extent(entry)",
                "rebuild_materialized(entry)",
            ],
        ),
        helper_primitive(
            pe, "rebuild_materialized",
            primitive_id="battle.ir.property.rebuild_materialized",
            inputs=["property_entry"],
            output="materialized_fixedpoint",
            reads=["entry[+0x58] materialization_kind", "entry[+0x20] active sources", "entry[+0x30] source values", "entry[+0x40], [+0x48], [+0x50], [+0x64], [+0x70]"],
            writes=["entry[+0x78]"],
            exact_semantics=[
                "Kinds 1 and 2 are inline source selections (source 0 and last-changed source respectively).",
                "Kinds 3..7 dispatch to five native reducers over active source slots in ascending index order.",
                "After the reducer, a further native transform consumes entry[+0x48]/[+0x50] before the final value is written to +0x78; a tail call consumes entry[+0x40].",
            ],
            pseudocode=[
                "candidate = materialize_by_kind(entry.materialization_kind, entry.active_source_slots)",
                "entry.materialized = native_post_transform(candidate, entry.slot_48, entry.slot_50)",
                "native_post_materialization_hook(&entry.materialized, entry.slot_40)",
                "return entry.materialized",
            ],
            unknowns=["The gameplay names of materialization kinds and the exact fixed-point operator names are intentionally not inferred from helper addresses."],
        ),
    ]
    for key, primitive_id, exact in [
        ("materialize_kind_3", "battle.ir.property.materialize_kind_3", "forward active-slot fold using direct callee 0x19D65EF80"),
        ("materialize_kind_4", "battle.ir.property.materialize_kind_4", "forward active-slot fold using direct callee 0x19D661A00; no-active path falls back to entry[+0x70]"),
        ("materialize_kind_5", "battle.ir.property.materialize_kind_5", "forward active-slot fold using 0x19D661B60 then 0x19D661A00"),
        ("materialize_kind_6", "battle.ir.property.materialize_kind_6", "forward active-slot extremum reducer; direction is deliberately unnamed"),
        ("materialize_kind_7", "battle.ir.property.materialize_kind_7", "forward active-slot extremum reducer complementary to kind 6; direction is deliberately unnamed"),
    ]:
        primitives.append(helper_primitive(
            pe, key,
            primitive_id=primitive_id,
            inputs=["property_entry"],
            output="entry[+0x78] materialized_fixedpoint",
            reads=["entry[+0x20] active slots", "entry[+0x30] source values", "entry[+0x60] active-source extent", "entry[+0x70] base/fallback"],
            writes=["entry[+0x78]"],
            exact_semantics=[exact],
            pseudocode=["fold active source slots in ascending source_index", "write the reducer result to entry.materialized"],
        ))

    return {
        "schema": "battle_semantic_bridge/1",
        "game_version": GAME_VERSION,
        "capability_id": "GENERIC_PROPERTY_SOURCE_SLOT_MATERIALIZATION_10_PROOF",
        "status": "CONFIRMED_SOURCE_SLOT_LIFECYCLE_AND_MATERIALIZATION_FRAMEWORK__PER_KIND_FIXEDPOINT_OPERATOR_NAMES_DEFERRED",
        "evidence_level": E4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {"GameAssembly_sha256": load_manifest()["GameAssembly"]["sha256"]},
        "property_entry_state": {
            "source_generation_by_index": "entry[+0x10][index]:int32; zero disables the index",
            "source_active_by_index": "entry[+0x20][index]:bool",
            "source_value_by_index": "entry[+0x30][index]:fixedpoint-like runtime numeric",
            "post_hook_context": "entry[+0x40]:opaque",
            "post_transform_a": "entry[+0x48]:opaque",
            "post_transform_b": "entry[+0x50]:opaque",
            "materialization_kind": "entry[+0x58]:enum 1..7",
            "generation_counter": "entry[+0x5C]:int32",
            "active_source_extent": "entry[+0x60]:int32",
            "last_changed_source": "entry[+0x64]:int32",
            "base_or_fallback": "entry[+0x70]:runtime numeric",
            "materialized_value": "entry[+0x78]:runtime numeric",
        },
        "config_bindings": [
            {
                "config_type": "RPG.GameCore.StackProperty",
                "config_fields": ["TargetType", "Property", "PropertyValue", "Silence", "IsRefresh"],
                "runtime_fields": {"target": "+0x18", "property_id": "+0x20", "dynamic_value": "+0x28"},
                "semantic_input": "M506082 evaluates PropertyValue and M506199 forwards it to M506495; M506495's native adapter remains a separate dependency.",
            },
        ],
        "primitives": primitives,
        "semantic_chains": [
            {
                "chain_id": "modifier_stack_property_add",
                "steps": ["M506082 task target/value evaluation", "M506199 modifier tracking", "M506495 component stack", "0x15755890 allocate source slot", "0x15755AE0 rebuild", "entry[+0x78] observable materialized value"],
            },
            {
                "chain_id": "modifier_stack_property_refresh",
                "steps": ["M506199 finds same property+component tracked record", "M506497", "0x157559D0 update stable source_index", "0x15755AE0 rebuild", "entry[+0x78]"],
            },
            {
                "chain_id": "modifier_stack_property_remove",
                "steps": ["M506312 iterates tracked records", "M506496", "0x15755FD0 disables stable source_index", "0x15755AE0 rebuild", "entry[+0x78]"],
            },
        ],
        "dependencies": ["DynamicValue runtime (Batch 02)", "Target selector runtime (Batch 05)", "modifier application/lifecycle (Batches 07-08)"],
        "unknowns": [
            "The generic adapter at 0x15C6E450 is a real pre-source dependency; its per-property value transform is not restated as raw DynamicValue assignment.",
            "Names/formulas of the fixed-point operators in materialization kinds 3..7 are not yet canonical.",
            "The design-data/runtime source that initializes each PropertyEntry materialization_kind/base/post-transform fields is not recovered here.",
        ],
        "must_not_implement": [
            "Do not represent contributions as final_value += value / final_value -= value.",
            "Do not shift source indices on removal; modifier tracked keys remain stable source indices.",
            "Do not assign named SUM/MUL/MIN/MAX semantics to materialization kinds solely from current helper addresses.",
            "Do not bypass native post-transform/post-hook state when materializing a property entry.",
        ],
    }


if __name__ == "__main__":
    artifact = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
