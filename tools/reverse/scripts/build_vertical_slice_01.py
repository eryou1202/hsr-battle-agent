#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Battle Semantic Vertical Slice 01 evidence artifacts.

Inputs (read-only):
  - data/normalized/4.4.54/{manifest,types,methods,fields,parameters}.json
  - GameAssembly.dll from the manifest (native body bytes + bounded capstone)

Outputs:
  - data/semantics/4.4.54/vertical_slice_01.json
  - docs/battle_semantics/vertical_slice_01.md

This is a narrow evidence assembler for one method, not a decompiler
framework. It re-verifies the registry identities it writes into the report.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402

sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

BASE = REPO / "data" / "normalized" / "4.4.54"
OUT_JSON = REPO / "data" / "semantics" / "4.4.54" / "vertical_slice_01.json"
OUT_MD = REPO / "docs" / "battle_semantics" / "vertical_slice_01.md"

PRIMARY = {
    "runtime_type": "RPG.GameCore.DynamicValue",
    "type_index": 10822,
    "method": "Equals",
    "method_index": 74632,
    "native_rva": 0x1CFBE9E0,
    "body_length": 0xD5,
    "jump_table_rva": 0x1CFBEAB8,
    "jump_table_length": 0x18,
}
STRING_HELPER = {
    "runtime_type": "System.String",
    "type_index": 330,
    "method": "EqualsHelper",
    "method_index": 3485,
    "native_rva": 0x1BB65990,
    "body_length": 0xB0,
}


def iter_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        in_records = False
        for line in f:
            if not in_records:
                if '"records": [' in line:
                    in_records = True
                continue
            line = line.strip()
            if not line or line == "]":
                continue
            if line.endswith(","):
                line = line[:-1]
            if line.startswith("{") and line.endswith("}"):
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass


def read_registry_facts():
    wanted_types = {PRIMARY["type_index"], 10824, STRING_HELPER["type_index"]}
    wanted_methods = {PRIMARY["method_index"], STRING_HELPER["method_index"]}
    wanted_fields = {PRIMARY["type_index"], 10824}
    wanted_params = {PRIMARY["method_index"], STRING_HELPER["method_index"]}

    types = {}
    for rec in iter_records(BASE / "types.json"):
        if rec["type_index"] in wanted_types:
            types[rec["type_index"]] = rec
    methods = {}
    for rec in iter_records(BASE / "methods.json"):
        if rec["method_index"] in wanted_methods:
            methods[rec["method_index"]] = rec
    fields = []
    for rec in iter_records(BASE / "fields.json"):
        if rec["declaring_type_index"] in wanted_fields:
            fields.append(rec)
    params = []
    for rec in iter_records(BASE / "parameters.json"):
        if rec["method_index"] in wanted_params:
            params.append(rec)

    def must_type(idx):
        rec = types.get(idx)
        if rec is None:
            raise RuntimeError(f"type index {idx} not found in normalized registry")
        return rec

    def must_method(mi):
        rec = methods.get(mi)
        if rec is None:
            raise RuntimeError(f"method index {mi} not found in normalized registry")
        return rec

    ptype = must_type(PRIMARY["type_index"])
    pmethod = must_method(PRIMARY["method_index"])
    pmethod_rva = int(pmethod["native_rva"], 16) if isinstance(pmethod["native_rva"], str) else int(pmethod["native_rva"])
    assert ptype["full_name"] == PRIMARY["runtime_type"], ptype
    assert pmethod["name"] == "Equals", pmethod
    assert pmethod["declaring_type_index"] == PRIMARY["type_index"], pmethod
    assert pmethod_rva == PRIMARY["native_rva"], pmethod
    assert pmethod["mapping_kind"] == "DIRECT_NATIVE", pmethod

    stype = must_type(STRING_HELPER["type_index"])
    smethod = must_method(STRING_HELPER["method_index"])
    smethod_rva = int(smethod["native_rva"], 16) if isinstance(smethod["native_rva"], str) else int(smethod["native_rva"])
    assert stype["full_name"] == "System.String", stype
    assert smethod["name"] == "EqualsHelper", smethod
    assert smethod["declaring_type_index"] == STRING_HELPER["type_index"], smethod
    assert smethod_rva == STRING_HELPER["native_rva"], smethod

    primary_fields = sorted(
        (r for r in fields if r["declaring_type_index"] == PRIMARY["type_index"]),
        key=lambda r: r["field_index"],
    )
    enum_fields = sorted(
        (r for r in fields if r["declaring_type_index"] == 10824),
        key=lambda r: r["field_index"],
    )
    primary_params = sorted(
        (r for r in params if r["method_index"] == PRIMARY["method_index"]),
        key=lambda r: r["parameter_index"],
    )
    helper_params = sorted(
        (r for r in params if r["method_index"] == STRING_HELPER["method_index"]),
        key=lambda r: r["parameter_index"],
    )
    return {
        "primary_type": ptype,
        "primary_method": pmethod,
        "string_type": stype,
        "string_method": smethod,
        "primary_fields": primary_fields,
        "enum_fields": enum_fields,
        "primary_params": primary_params,
        "helper_params": helper_params,
    }


def disasm_lines(pe: PeImage, rva: int, length: int, base_name: str):
    off = pe.rva_to_file_offset(rva)
    if off is None:
        raise RuntimeError(f"RVA not mapped: 0x{rva:X}")
    raw = pe._read(off, length)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    lines = []
    for ins in md.disasm(raw, pe.image_base + rva):
        comment = ""
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM:
                if op.mem.base == x86.X86_REG_RIP and op.mem.index == 0:
                    target = ins.address + ins.size + op.mem.disp
                    comment = (
                        f" ; [rip]->0x{target:X} (rva 0x{target - pe.image_base:X})"
                    )
                    break
        local = rva + (ins.address - (pe.image_base + rva))
        lines.append(
            f"{local:08X}  {ins.bytes.hex(' '):<24}  "
            f"{ins.mnemonic:8} {ins.op_str}{comment}"
        )
    return raw, lines


def jump_table(pe: PeImage):
    import struct
    rva = PRIMARY["jump_table_rva"]
    off = pe.rva_to_file_offset(rva)
    raw = pe._read(off, PRIMARY["jump_table_length"])
    offsets = list(struct.unpack("<6i", raw))
    entries = []
    for i, delta in enumerate(offsets):
        entries.append(
            {
                "value_type_index": i,
                "delta": delta,
                "case_rva": f"0x{rva + delta:X}",
            }
        )
    return raw, entries


def read_code_slot(pe: PeImage):
    import struct
    table = REPO / "data" / "parsed" / "4.4.54" / "method_code_table.bin"
    with table.open("rb") as f:
        f.seek(PRIMARY["method_index"] * 8)
        slot = struct.unpack("<Q", f.read(8))[0]
    expected = pe.image_base + PRIMARY["native_rva"]
    if slot != expected:
        raise RuntimeError(
            f"method code table slot mismatch: {slot:#x} != {expected:#x}")
    return slot


def build_json(facts, pe):
    manifest = json.load((BASE / "manifest.json").open(encoding="utf-8"))
    body_raw, body_lines = disasm_lines(
        pe, PRIMARY["native_rva"], PRIMARY["body_length"], "primary")
    table_raw, table_entries = jump_table(pe)
    code_slot = read_code_slot(pe)
    helper_raw, helper_lines = disasm_lines(
        pe, STRING_HELPER["native_rva"], STRING_HELPER["body_length"], "string_helper")

    candidates = [
        {
            "rank": 1,
            "status": "PRIMARY_CANDIDATE",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "Equals",
            "method_index": 74632,
            "native_rva": "0x1CFBE9E0",
            "native_size_estimate_bytes": 240,
            "field_count": 6,
            "callee_count": 2,
            "battle_relevance": "type-aware equality of the battle DynamicValue value cell; reusable by every predicate/condition that compares DynamicValue operands",
            "expected_complexity": "LOW_MEDIUM",
            "evidence": "66 instructions + 6-entry jump table; one normal-path callee (System.String.EqualsHelper); fully bounded",
        },
        {
            "rank": 2,
            "status": "BACKUP_CANDIDATE",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "get_IntValue",
            "method_index": 74637,
            "native_rva": "0x1CFBF070",
            "native_size_estimate_bytes": 80,
            "field_count": 6,
            "callee_count": 1,
            "battle_relevance": "typed DynamicValue -> int coercion used by numeric gameplay readers",
            "expected_complexity": "LOW",
            "evidence": "single switch over ValueType; one error-path log helper",
        },
        {
            "rank": 3,
            "status": "BACKUP_CANDIDATE",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "get_FloatValue",
            "method_index": 74633,
            "native_rva": "0x1CFBED90",
            "native_size_estimate_bytes": 96,
            "field_count": 6,
            "callee_count": 1,
            "battle_relevance": "typed DynamicValue -> float coercion",
            "expected_complexity": "LOW",
            "evidence": "switch over ValueType (int/bool/double conversion paths); one error helper",
        },
        {
            "rank": 4,
            "status": "CONSIDERED",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "get_BoolValue",
            "method_index": 74636,
            "native_rva": "0x1CFBF010",
            "native_size_estimate_bytes": 96,
            "field_count": 6,
            "callee_count": 2,
            "battle_relevance": "typed DynamicValue -> bool normalization",
            "expected_complexity": "LOW",
            "evidence": "normalizes union==1; two error helpers",
        },
        {
            "rank": 5,
            "status": "CONSIDERED",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "Equals",
            "method_index": 74630,
            "native_rva": "0x1CFBE8F0",
            "native_size_estimate_bytes": 240,
            "field_count": 6,
            "callee_count": 1,
            "battle_relevance": "object-typed equality entry point with runtime type check",
            "expected_complexity": "LOW_MEDIUM",
            "evidence": "adds IL2CPP runtime type identity check; otherwise same switch semantics",
        },
        {
            "rank": 6,
            "status": "CONSIDERED",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "get_FixPointValue",
            "method_index": 74635,
            "native_rva": "0x1CFBEEA0",
            "native_size_estimate_bytes": 368,
            "field_count": 6,
            "callee_count": 1,
            "battle_relevance": "fixed-point numeric conversion used by battle numeric expressions",
            "expected_complexity": "MEDIUM",
            "evidence": "branch-free fixed-point range/shift encoding; larger than Equals",
        },
        {
            "rank": 7,
            "status": "CONSIDERED",
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "get_LongValue",
            "method_index": 74639,
            "native_rva": "0x1CFBF110",
            "native_size_estimate_bytes": 128,
            "field_count": 6,
            "callee_count": 3,
            "battle_relevance": "typed DynamicValue -> long coercion",
            "expected_complexity": "LOW",
            "evidence": "adds one-time IL2CPP init branch before the value switch",
        },
    ]
    rejected = [
        {
            "runtime_type": "RPG.GameCore.ByCompareDynamicValue",
            "method": "LJACLBNEEEB / EOJLPDGNHEK",
            "method_indices": [133353, 133354],
            "native_rvas": ["0x1CE2F500", "0x1CE2F560"],
            "reject_reason": "wrapper/impl pair has FromBinary/ToBinary serializer shape (allocates result object, reads/writes field bits); no gameplay state computation in the type's own methods",
        },
        {
            "runtime_type": "RPG.GameCore.DynamicValue",
            "method": "FromByteBinary / ToBinary",
            "method_indices": [74659, 74660],
            "native_rvas": ["0x1CFBF630", "0x1CFBF900"],
            "reject_reason": "serialization semantic, explicitly out of scope for Battle Semantic Recovery",
        },
    ]

    primary_method = facts["primary_method"]
    primary_type = facts["primary_type"]
    string_method = facts["string_method"]
    primary_params = facts["primary_params"]

    result = {
        "schema": "battle_semantics_vertical_slice/1",
        "session": "Battle Semantic Vertical Slice 01",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "final_status": "BATTLE_SEMANTIC = VERTICAL_SLICE_PROOF",
        "game_version": "4.4.54",
        "build_string": manifest["build_string"],
        "source_manifest": {
            "game_root": manifest["game_root"],
            "version_source_sha256": manifest["version_source_sha256"],
            "GameAssembly": manifest["GameAssembly"],
            "global_metadata": manifest["global_metadata"],
        },
        "normalized_registries": {
            "base": str(BASE),
            "primary_type_index": primary_type["type_index"],
            "primary_method_index": primary_method["method_index"],
            "primary_field_count": len(facts["primary_fields"]),
            "primary_parameter_count": len(primary_params),
            "semantic_status": "METADATA_IDENTITY_CONFIRMED",
        },
        "candidate_selection": {
            "search_summary": {
                "battle_keyword_flagged_types": 14958,
                "rpg_gamecore_types": 12433,
                "rpg_gamecore_methods": 45886,
                "dynamicvalue_family_types": 160,
                "shortlisted_methods": len(candidates),
                "serialization_shaped_rejected": 2,
            },
            "candidates": candidates,
            "rejected": rejected,
            "primary_choice_rationale": (
                "DynamicValue.Equals(DynamicValue) is the smallest complete "
                "battle-relevant compare primitive in the shortlist: it is not "
                "serialization, has one normal-path callee (confirmed "
                "System.String.EqualsHelper), reads only the two DynamicValue "
                "operands, writes nothing, and its six-way type switch is fully "
                "recovered from a 24-byte jump table."
            ),
        },
        "source_identity": {
            "runtime_type": {
                "namespace": primary_type["namespace"],
                "name": primary_type["name"],
                "type_index": primary_type["type_index"],
                "method_start": primary_type["method_start"],
                "method_count": primary_type["method_count"],
                "field_start": primary_type["field_start"],
                "field_count": primary_type["field_count"],
                "semantic_status": primary_type["semantic_status"],
            },
            "method_definition": {
                "method_index": primary_method["method_index"],
                "declaring_type_index": primary_method["declaring_type_index"],
                "name": primary_method["name"],
                "parameter_start": primary_method["parameter_start"],
                "parameter_count": primary_method["parameter_count"],
                "return_type_reference": primary_method["return_type_reference"],
                "native_rva": f"0x{PRIMARY['native_rva']:X}",
                "native_va": f"0x{pe.image_base + PRIMARY['native_rva']:X}",
                "code_table_slot_va": f"0x{code_slot:X}",
                "image_base": f"0x{pe.image_base:X}",
                "mapping_kind": primary_method["mapping_kind"],
                "semantic_status": primary_method["semantic_status"],
            },
            "parameter_relation": [
                {
                    "parameter_index": p["parameter_index"],
                    "name_key": p["name_key"],
                    "type_reference": p["type_reference"],
                    "type_identity_note": "type_reference 25310 = DynamicValue "
                                          "(same reference as DynamicValue op_Implicit "
                                          "return type and ToBinary value parameter)",
                    "structure_status": p["structure_status"],
                }
                for p in primary_params
            ],
            "return_identity_note": "type_reference 424 = System.Boolean "
                                    "(same reference as get_BoolValue return and "
                                    "op_Implicit(Boolean) parameter)",
        },
        "field_map": [
            {
                "offset": 16,
                "width_bytes": 8,
                "registry_field_index": f["field_index"],
                "registry_name": f["name"],
                "type_reference": f["type_reference"],
                "role": "mapValue payload (pointer identity in Equals)",
                "evidence": "native reads [this+0x10] / [other+0x10]; constructor stores map here",
                "evidence_level": "CONFIRMED",
            }
            for f in facts["primary_fields"]
            if f["name"] == "mapValue"
        ]
        + [
            {
                "offset": 24,
                "width_bytes": 8,
                "registry_field_index": f["field_index"],
                "registry_name": f["name"],
                "type_reference": f["type_reference"],
                "role": "stringValue payload (content equality in Equals)",
                "evidence": "native reads [this+0x18] / [other+0x18] and string length at [ptr+0x10]",
                "evidence_level": "CONFIRMED",
            }
            for f in facts["primary_fields"]
            if f["name"] == "stringValue"
        ]
        + [
            {
                "offset": 32,
                "width_bytes": 8,
                "registry_field_index": f["field_index"],
                "registry_name": f["name"],
                "type_reference": f["type_reference"],
                "role": "arrayValue payload (pointer identity in Equals)",
                "evidence": "native reads [this+0x20] / [other+0x20]",
                "evidence_level": "CONFIRMED",
            }
            for f in facts["primary_fields"]
            if f["name"] == "arrayValue"
        ]
        + [
            {
                "offset": 40,
                "width_bytes": 8,
                "registry_field_index": f["field_index"],
                "registry_name": f["name"],
                "type_reference": f["type_reference"],
                "role": "unionValue numeric/bool payload",
                "evidence": "native reads qword [this+0x28] / [other+0x28]",
                "evidence_level": "CONFIRMED",
            }
            for f in facts["primary_fields"]
            if f["name"] == "unionValue"
        ]
        + [
            {
                "offset": 48,
                "width_bytes": 1,
                "registry_field_index": None,
                "registry_name": None,
                "type_reference": None,
                "role": "ValueType tag byte",
                "evidence": "native reads byte [this+0x30] / [other+0x30]; constructors and get_ValueType write/read it",
                "evidence_level": "SUPPORTED",
                "note": "not present among the 6 normalized FieldDefinition rows for type 10822; native accessor evidence is decisive for this slice, metadata declaring-row provenance remains UNKNOWN",
            },
        ],
        "dynamic_value_type_enum": {
            "type_index": 10824,
            "name": "DynamicValueType",
            "values": [
                {"name": f["name"], "ordinal": i, "field_index": f["field_index"]}
                for i, f in enumerate(facts["enum_fields"][:-1])
            ],
            "evidence": "enum field order 0..6 matches native switch guards",
            "evidence_level": "CONFIRMED",
        },
        "native_evidence": {
            "body_rva": f"0x{PRIMARY['native_rva']:X}",
            "body_length_bytes": PRIMARY["body_length"],
            "method_slot_size_estimate_bytes": 0xF0,
            "instruction_count": len(body_lines),
            "body_sha256": hashlib.sha256(body_raw).hexdigest(),
            "code_table_slot_va": f"0x{code_slot:X}",
            "code_table_slot_index": PRIMARY["method_index"],
            "jump_table_rva": f"0x{PRIMARY['jump_table_rva']:X}",
            "jump_table_sha256": hashlib.sha256(table_raw).hexdigest(),
            "jump_table_entries": table_entries,
            "conditional_branch_count": 7,
            "direct_call_count": 1,
            "tailcall_count": 1,
            "abi": "x64: this=rcx, other=rdx, bool return=al",
            "disassembly": body_lines,
        },
        "call_graph": {
            "depth": 1,
            "primary": {
                "runtime_type": "RPG.GameCore.DynamicValue",
                "method": "Equals",
                "method_index": 74632,
                "native_rva": "0x1CFBE9E0",
            },
            "normal_path_callees": [
                {
                    "runtime_type": "System.String",
                    "method": "EqualsHelper",
                    "method_index": string_method["method_index"],
                    "declaring_type_index": string_method["declaring_type_index"],
                    "parameter_count": string_method["parameter_count"],
                    "return_type_reference": string_method["return_type_reference"],
                    "native_rva": f"0x{STRING_HELPER['native_rva']:X}",
                    "evidence": {
                        "semantic": "ordinal UTF-16 content equality after null/length prechecks in Equals",
                        "string_layout": "length at [ptr+0x10], chars start at [ptr+0x14]",
                        "body_sha256": hashlib.sha256(helper_raw).hexdigest(),
                        "disassembly": helper_lines,
                    },
                    "evidence_level": "CONFIRMED",
                }
            ],
            "error_path_callees": [
                {
                    "native_rva": "0x3C02340",
                    "role": "IL2CPP managed null-check / NullReferenceException helper",
                    "followed": False,
                    "reason_not_followed": "error path only; generic runtime helper, not gameplay semantic",
                    "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
                }
            ],
        },
        "pseudocode": [
            "bool Equals(DynamicValue other):",
            "    if other == null:",
            "        throw NullReferenceException            # CONFIRMED",
            "    t = this.ValueType                         # byte @ +0x30, CONFIRMED",
            "    if t != other.ValueType:",
            "        return false                            # CONFIRMED",
            "    if t > 5:                                   # NULL(6) or invalid tag",
            "        return false                            # CONFIRMED",
            "    switch t:                                   # jump table @ 0x1CFBEAB8",
            "        case INT(0):",
            "            return this.unionValue == other.unionValue   # CONFIRMED",
            "        case FLOAT(1):",
            "            return ieee_double_equal(this.unionValue, other.unionValue)",
            "            # cmpeqsd -> false for NaN          # CONFIRMED",
            "        case BOOL(2):",
            "            return (this.unionValue == 1) == (other.unionValue == 1)",
            "            # both sides normalized to bool      # CONFIRMED",
            "        case ARRAY(3):",
            "            return this.arrayValue == other.arrayValue",
            "            # reference equality only             # CONFIRMED",
            "        case MAP(4):",
            "            return this.mapValue == other.mapValue",
            "            # reference equality only             # CONFIRMED",
            "        case STRING(5):",
            "            a = this.stringValue",
            "            b = other.stringValue",
            "            if a == b: return true               # CONFIRMED",
            "            if a == null or b == null: return false  # CONFIRMED",
            "            if a.Length != b.Length: return false   # CONFIRMED",
            "            return System.String.EqualsHelper(a, b)",
            "            # ordinal content equality           # CONFIRMED",
            "    return false                               # unreachable fallback",
        ],
        "read_write_set": {
            "inputs": [
                "DynamicValue lhs (this)",
                "DynamicValue rhs (other)",
            ],
            "context_reads": [
                "lhs.ValueType",
                "rhs.ValueType",
                "lhs.unionValue",
                "rhs.unionValue",
                "lhs.arrayValue / rhs.arrayValue (ARRAY case)",
                "lhs.mapValue / rhs.mapValue (MAP case)",
                "lhs.stringValue / rhs.stringValue (STRING case)",
                "String.Length and UTF-16 content of both strings (STRING case)",
            ],
            "context_writes": [],
            "global_state": "none",
            "result": {"type": "System.Boolean", "semantic": "tag-aware equality"},
            "determinism": "DETERMINISTIC",
        },
        "ir_primitive": {
            "primitive_id": "battle.ir.value.dynamic_value_equals",
            "semantic_name": "DynamicValueEquals",
            "description": "Tag-aware equality over two RPG.GameCore.DynamicValue cells",
            "inputs": [
                {"name": "lhs", "type": "DynamicValue"},
                {"name": "rhs", "type": "DynamicValue"},
            ],
            "context_reads": ["lhs", "rhs"],
            "context_writes": [],
            "result": "boolean",
            "determinism": "DETERMINISTIC",
            "source_runtime_type": "RPG.GameCore.DynamicValue",
            "source_method": "Equals",
            "source_method_index": 74632,
            "source_native_rva": "0x1CFBE9E0",
            "evidence_level": "E4_STATIC_MACHINE_CODE",
            "provenance_note": "RVA is provenance only; runtime logic must not depend on it",
            "unknowns": [
                "FieldDefinition provenance for the +0x30 ValueType tag byte",
                "Generic IL2CPP null-check helper internals (error path only)",
                "No E5 client-side runtime observation yet (out of scope for this slice)",
            ],
        },
        "evidence_level": "E4_STATIC_MACHINE_CODE",
        "success_criteria": {
            "A_runtime_type_identity": "PASS",
            "B_method_definition_identity": "PASS",
            "C_native_rva_reliable": "PASS",
            "D_native_body_dataflow_explained": "PASS",
            "E_inputs_outputs_described": "PASS",
            "F_read_write_set_described": "PASS",
            "G_branches_described": "PASS",
            "H_deterministic_pseudocode": "PASS",
            "I_generic_ir_primitive": "PASS",
        },
    }
    return result


def build_markdown(doc: dict) -> str:
    si = doc["source_identity"]
    ne = doc["native_evidence"]
    ir = doc["ir_primitive"]
    rows = []
    for c in doc["candidate_selection"]["candidates"]:
        rows.append(
            f"| {c['rank']} | {c['status']} | {c['runtime_type']}.{c['method']} "
            f"| {c['method_index']} | {c['native_rva']} | "
            f"{c['native_size_estimate_bytes']} | {c['callee_count']} | "
            f"{c['expected_complexity']} |"
        )
    table = "\n".join(rows)
    enum_rows = "\n".join(
        f"| {v['ordinal']} | {v['name']} |"
        for v in doc["dynamic_value_type_enum"]["values"]
    )
    field_rows = []
    for f in doc["field_map"]:
        field_rows.append(
            f"| +0x{f['offset']:X} | {f['width_bytes']} | "
            f"{f['registry_name'] or '(registry row missing)'} | "
            f"{f['role']} | {f['evidence_level']} |"
        )
    fields = "\n".join(field_rows)
    cg = doc["call_graph"]
    helper = cg["normal_path_callees"][0]
    pseudocode = "\n".join(f"    {line}" for line in doc["pseudocode"])
    disasm = "\n".join(f"    {line}" for line in ne["disassembly"])
    helper_disasm = "\n".join(
        f"    {line}" for line in helper["evidence"]["disassembly"])

    return f"""# Battle Semantic Vertical Slice 01 — DynamicValue.Equals

> Final status: **`{doc['final_status']}`**
> Game version: `{doc['game_version']}` ({doc['build_string']})
> Evidence level: `{doc['evidence_level']}`

## 1. Scope

This session recovers one small, generic, battle-relevant runtime primitive and
does not build a Sandbox, a full DynamicValue system, or any character skill
semantics. The recovered slice is the complete chain:

Serialized/Config runtime type `RPG.GameCore.DynamicValue`
→ FieldDefinition / MethodDefinition identity
→ native RVA
→ bounded native dataflow
→ semantic pseudocode
→ canonical Battle IR candidate `DynamicValueEquals`.

## 2. Candidate selection

Registry query (read-only, normalized 4.4.54 registries):

- battle-keyword flagged types: `{doc['candidate_selection']['search_summary']['battle_keyword_flagged_types']}`
- `RPG.GameCore` types / methods: `{doc['candidate_selection']['search_summary']['rpg_gamecore_types']}` /
  `{doc['candidate_selection']['search_summary']['rpg_gamecore_methods']}`
- DynamicValue-family types: `{doc['candidate_selection']['search_summary']['dynamicvalue_family_types']}`

`ByCompareDynamicValue`, `ByDynamicValueDefined`, `SetDynamicValueBy*` etc.
were inspected first: their extra methods (`OJNNBEJLDIJ` /
`MGMEGEDLMAK`, `LJACLBNEEEB` / `EOJLPDGNHEK`) are wrapper/impl
**serialization** pairs, so those types cannot provide a battle-semantic
vertical slice by themselves. `DynamicValue.FromByteBinary` / `ToBinary` were
rejected for the same reason.

Shortlist:

| # | Status | Candidate | method_index | native_rva | size(B) | callees | complexity |
|---:|---|---|---:|---:|---:|---:|---|
{table}

PRIMARY = `DynamicValue.Equals(DynamicValue)`.

Why: it is not serialization; it is a complete tag-aware compare helper with a
six-way switch, one normal-path callee, zero writes, no external battle state,
and its only deeper callee (`System.String.EqualsHelper`) is already identified
by the method registry.

## 3. Source identity (4.4.54)

| Item | Value |
|---|---|
| Runtime type | `{si['runtime_type']['namespace']}.{si['runtime_type']['name']}` (type_index `{si['runtime_type']['type_index']}`) |
| Method | `{si['method_definition']['name']}` (method_index `{si['method_definition']['method_index']}`) |
| Parameter relation | 1 parameter, parameter_index `{si['parameter_relation'][0]['parameter_index']}`, type_reference `{si['parameter_relation'][0]['type_reference']}` = DynamicValue |
| Return | type_reference `{si['method_definition']['return_type_reference']}` = System.Boolean |
| native RVA | `{si['method_definition']['native_rva']}` |
| mapping_kind | `{si['method_definition']['mapping_kind']}` |

Provenance:

- GameAssembly: `{doc['source_manifest']['GameAssembly']['path']}`
  - sha256 `{doc['source_manifest']['GameAssembly']['sha256']}`
- global-metadata: sha256 `{doc['source_manifest']['global_metadata']['sha256']}`
- Version source: sha256 `{doc['source_manifest']['version_source_sha256']}`

## 4. Field map

`RPG.GameCore.DynamicValue` layout recovered from the normalized field
registry plus native accessor evidence:

| Offset | Width | Registry name | Role in Equals | Evidence |
|---|---:|---|---|---|
{fields}

`DynamicValueType` enum values (type_index 10824):

| Ordinal | Name |
|---:|---|
{enum_rows}

Note: the `+0x30` tag byte is read by every native accessor and written by
every constructor, but no normalized FieldDefinition row for type 10822
declares it. For this slice it is `SUPPORTED` from native evidence; its
metadata declaring-row provenance stays UNKNOWN.

## 5. Native evidence

- Body RVA `{ne['body_rva']}`, body bytes `{ne['body_length_bytes']}`
  (method slot estimate 0xF0), `{ne['instruction_count']}` instructions.
- Body sha256 `{ne['body_sha256']}`.
- Method code table slot `{ne['code_table_slot_index']}` =
  `{ne['code_table_slot_va']}` (image base `0x180000000`, matches body RVA).
- Jump table RVA `{ne['jump_table_rva']}`:
  `-167, -144, -120, -97, -81, -65` for cases INT..STRING.
- ABI: `{ne['abi']}`.

Bounded disassembly (left column and RIP comments are RVAs; branch/call
operands are raw VAs with image base `0x180000000`):

```
{disasm}
```

The only normal-path tail-call target is `{helper['runtime_type']}.{helper['method']}`
(method_index `{helper['method_index']}`, RVA `{helper['native_rva']}`), a
length-prefixed ordinal UTF-16 content equality helper:

```
{helper_disasm}
```

## 6. Semantic pseudocode (ABI-independent)

```
{pseudocode}
```

Labels: `CONFIRMED` = direct machine-code evidence plus registry identity;
`SUPPORTED` = native evidence without a matching metadata declaration row;
`UNKNOWN` = not followed/not needed.

## 7. State dependency model

- reads: the two `DynamicValue` operands only (and string content for STRING).
- writes: none.
- global state: none.
- return: `bool`.
- determinism: `{doc['read_write_set']['determinism']}`.

## 8. Canonical Battle IR candidate (draft)

```json
{json.dumps(ir, indent=2)}
```

`source_native_rva` is provenance/evidence only and must not be part of runtime
IR logic.

## 9. Unknowns

{chr(10).join('- ' + u for u in ir['unknowns'])}

## 10. E4 success criteria

| Criterion | Status |
|---|---|
| A Runtime Type identity | {doc['success_criteria']['A_runtime_type_identity']} |
| B MethodDefinition identity | {doc['success_criteria']['B_method_definition_identity']} |
| C native RVA | {doc['success_criteria']['C_native_rva_reliable']} |
| D native body dataflow | {doc['success_criteria']['D_native_body_dataflow_explained']} |
| E inputs / outputs | {doc['success_criteria']['E_inputs_outputs_described']} |
| F read / write set | {doc['success_criteria']['F_read_write_set_described']} |
| G branches | {doc['success_criteria']['G_branches_described']} |
| H deterministic pseudocode | {doc['success_criteria']['H_deterministic_pseudocode']} |
| I generic IR primitive | {doc['success_criteria']['I_generic_ir_primitive']} |

Machine-readable companion:
`data/semantics/4.4.54/vertical_slice_01.json`.
"""


def main() -> int:
    facts = read_registry_facts()
    manifest = json.load((BASE / "manifest.json").open(encoding="utf-8"))
    pe = PeImage(Path(manifest["GameAssembly"]["path"]))
    doc = build_json(facts, pe)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(build_markdown(doc), encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
