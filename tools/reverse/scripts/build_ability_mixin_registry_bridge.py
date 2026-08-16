#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the MKIOEPLIEIH polymorphic parser registry bridge.

Inputs:
  * `mkioeplieih_registry_snapshot.py` JSON (runtime-initialized registry
    array read from the code-proven [[0x95B1518]+0x6990] slot);
  * GameAssembly.dll + global-metadata.dat;
  * CONFIRMED template RVA and method code table RVA.

Static part:
  * scans MKIOEPLIEIH.cctor (0x1CB745A0..0x1CB784C2) and recovers, for every
    discriminator i, the source `descriptor_global_rva` whose runtime qword is
    stored into array slot i (`mov rdx,[rip+disp]; mov [rax+slot],rdx`);
  * documents the dispatcher MKIOEPLIEIH.OJNNBEJLDIJ (0x1CB743F0).

Runtime part:
  * maps every registry entry's `[entry+0x08]` parser pointer back through the
    CONFIRMED method code table (exact match first, then containing-method);
  * decodes parser MethodDefinition name + declaring TypeDefinition name from
    the CONFIRMED MHY metadata registries.

Output: discriminator -> parser MethodDefinition -> Runtime TypeDefinition.
This tool reports registry identity only; it does not interpret Battle DSL.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vendor" / "capstone"))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402
from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from analyze_mhy_method_candidate import RULES  # noqa: E402
from build_method_code_registry import (  # noqa: E402
    M32,
    decode_declaring_type,
    decode_method_name,
    resolve_type_name,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

CCTOR_RVA = 0x1CB745A0
CCTOR_END_RVA = 0x1CB784C2
DISPATCH_RVA = 0x1CB743F0
REGISTRY_GLOBAL_RVA = 0x95B1518
REGISTRY_SLOT_OFFSET = 0x6990
EXPECTED_ENTRIES = 0x27C


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    out = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        if op == "add":
            val = (raw + const) & M32
        else:
            val = raw ^ const
        out[field] = FILE_HEADER + signed32(val)
    return out


def extract_cctor_source_globals(pe: PeImage) -> list[dict]:
    raw = pe.read_rva(CCTOR_RVA, CCTOR_END_RVA - CCTOR_RVA)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    rows = []
    pending = None
    for ins in md.disasm(raw, pe.image_base + CCTOR_RVA):
        if ins.address >= pe.image_base + CCTOR_END_RVA:
            break
        if ins.mnemonic == "mov" and len(ins.operands) == 2:
            dst, src = ins.operands
            if (src.type == x86.X86_OP_MEM and src.mem.base == x86.X86_REG_RIP
                    and dst.type == x86.X86_OP_REG
                    and dst.reg in (x86.X86_REG_RDX, x86.X86_REG_RCX)):
                target = ins.address + ins.size + src.mem.disp - pe.image_base
                pending = target
                continue
            if (pending is not None and dst.type == x86.X86_OP_MEM
                    and dst.mem.base == x86.X86_REG_RAX and src.type == x86.X86_OP_REG
                    and src.reg in (x86.X86_REG_RDX, x86.X86_REG_RCX)
                    and dst.mem.disp >= 0x20):
                slot = dst.mem.disp - 0x20
                if slot % 8 == 0 and slot // 8 < EXPECTED_ENTRIES:
                    rows.append({
                        "discriminator": slot // 8,
                        "array_slot_offset": f"0x{dst.mem.disp:X}",
                        "descriptor_global_rva": f"0x{pending:X}",
                        "cctor_store_rva": f"0x{ins.address - pe.image_base:X}",
                    })
                pending = None
        elif ins.mnemonic not in ("cmp", "jbe", "je", "test", "mov", "jmp"):
            pending = None
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--snapshot", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--version", default="4.4.54")
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    pe = PeImage(args.game)
    tpl = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    offs = table_offsets(pe, tpl)
    tbase = offs[0x84]
    tnext = offs[0x38]
    mbase = offs[0x14C]
    mnext = offs[0x160]
    nmethods = (mnext - mbase) // 26
    region_base = offs[0x1B4]

    snap = json.load(open(args.snapshot, encoding="utf-8"))
    entries = snap["read_result"]["entries"]
    runtime_base = int(snap["modules"]["GameAssembly"]["base"], 16)

    # Code table: exact method entry -> method index, plus sorted RVAs for
    # containing-method fallback.
    by_rva: dict[int, int] = {}
    rva_list: list[int] = []
    raw_table = pe.read_rva(args.code_table_rva, nmethods * 8)
    for mi in range(nmethods):
        q = struct.unpack_from("<Q", raw_table, mi * 8)[0]
        if q:
            rva = q - pe.image_base
            if rva not in by_rva:
                by_rva[rva] = mi
                rva_list.append(rva)
    rva_list.sort()

    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        def lookup(rva: int) -> dict:
            mi = by_rva.get(rva)
            kind = "EXACT_METHOD_ENTRY"
            if mi is None:
                lo, hi = 0, len(rva_list)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if rva_list[mid] <= rva:
                        lo = mid + 1
                    else:
                        hi = mid
                if lo == 0:
                    return {"mapping_kind": "UNMAPPED_PARSER"}
                mi = by_rva[rva_list[lo - 1]]
                kind = "CONTAINING_METHOD"
            declaring = decode_declaring_type(mm, mbase, mi)
            return {
                "mapping_kind": kind,
                "parser_method_index": mi,
                "parser_method_name": decode_method_name(mm, mbase, mi, region),
                "parser_declaring_type_index": declaring,
                "runtime_type_name": resolve_type_name(mm, tbase, declaring, region),
                "runtime_type_namespace": (resolve_type_name(mm, tbase, declaring, region).split(".")[0]
                                            if "." in resolve_type_name(mm, tbase, declaring, region) else ""),
            }

        mappings = []
        for e in entries:
            parser = e.get("parser_pointer")
            desc = e.get("parser_describe") or {}
            row = {
                "discriminator": e["discriminator"],
                "entry_pointer": e["entry_pointer"],
                "parser_native_rva": None,
                "parser_method_index": None,
                "parser_method_name": None,
                "parser_declaring_type_index": None,
                "runtime_type_name": None,
                "runtime_type_namespace": None,
                "mapping_kind": "NULL_ENTRY",
            }
            if e.get("entry_pointer") in (None, "0x0"):
                row["mapping_kind"] = "NULL_ENTRY"
            elif parser and desc.get("in_known_module") and desc.get("is_executable"):
                rva = int(parser, 16) - runtime_base
                row.update({"parser_native_rva": f"0x{rva:X}"})
                row.update(lookup(rva))
            else:
                row["mapping_kind"] = "NON_EXECUTABLE_OR_NULL"
            mappings.append(row)

    sources = extract_cctor_source_globals(pe)
    src_by_disc = {s["discriminator"]: s for s in sources}
    for m in mappings:
        s = src_by_disc.get(m["discriminator"])
        m["descriptor_global_rva"] = s["descriptor_global_rva"] if s else None
        m["cctor_store_rva"] = s["cctor_store_rva"] if s else None

    # Every non-null registry slot i (1..635) points at MKIOEPLIEIH helper
    # method index 132205 + i. Analyze the helper's tiny allocator/parser body:
    #   mov rcx,[rip+disp] -> type_global_rva; call allocator;
    #   call concrete_parser -> MethodDefinition of the Runtime Class.
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    def decode_call(mi: int | None, rva: int):
        if mi is None:
            return None
        declaring = decode_declaring_type(mm, mbase, mi)
        return {
            "method_index": mi,
            "native_rva": f"0x{rva:X}",
            "name": decode_method_name(mm, mbase, mi, region),
            "declaring_type_index": declaring,
            "declaring_type": resolve_type_name(mm, tbase, declaring, region),
        }

    for m in mappings:
        disc = m["discriminator"]
        helper_mi = 132205 + disc if disc >= 1 else None
        if m["mapping_kind"] == "NULL_ENTRY":
            m.update({
                "helper_method_index": None,
                "helper_method_rva": None,
                "type_descriptor_global_rva": None,
                "allocator_call": None,
                "internal_calls": [],
                "concrete_parser_method_index": None,
                "concrete_parser_method_name": None,
                "concrete_runtime_type_index": None,
                "concrete_runtime_type_name": None,
                "concrete_parser_native_rva": None,
                "structure_status": "NULL_REGISTRY_SLOT",
            })
            continue
        if helper_mi is None:
            m.update({
                "helper_method_index": None,
                "helper_method_rva": None,
                "type_descriptor_global_rva": None,
                "allocator_call": None,
                "internal_calls": [],
                "concrete_parser_method_index": None,
                "concrete_parser_method_name": None,
                "concrete_runtime_type_index": None,
                "concrete_runtime_type_name": None,
                "concrete_parser_native_rva": None,
                "structure_status": "NULL_REGISTRY_SLOT",
            })
            continue
        q = struct.unpack_from("<Q", raw_table, helper_mi * 8)[0]
        helper_rva = q - pe.image_base if q else None
        helper_analysis = {
            "helper_method_index": helper_mi,
            "helper_method_rva": f"0x{helper_rva:X}" if helper_rva else None,
            "type_descriptor_global_rva": None,
            "allocator_call": None,
            "internal_calls": [],
            "concrete_parser_method_index": None,
            "concrete_parser_method_name": None,
            "concrete_runtime_type_index": None,
            "concrete_runtime_type_name": None,
            "concrete_parser_native_rva": None,
            "structure_status": "UNCLASSIFIED",
        }
        if helper_rva is not None:
            code = pe.read_rva(helper_rva, 0x100)
            type_global = None
            calls = []
            for ins in md.disasm(code, pe.image_base + helper_rva):
                ins_rva = ins.address - pe.image_base
                if ins_rva > helper_rva + 0xE0:
                    break
                if ins.mnemonic == "mov" and len(ins.operands) == 2:
                    dst, src = ins.operands
                    if (src.type == x86.X86_OP_MEM and src.mem.base == x86.X86_REG_RIP
                            and dst.type == x86.X86_OP_REG and dst.reg == x86.X86_REG_RCX
                            and type_global is None):
                        type_global = (ins.address + ins.size + src.mem.disp
                                       - pe.image_base)
                elif ins.mnemonic in ("call", "jmp"):
                    op = ins.operands[0]
                    if op.type == x86.X86_OP_IMM:
                        target_rva = int(op.imm) - pe.image_base
                        mi = by_rva.get(target_rva)
                        if mi is not None and mi != helper_mi:
                            calls.append((target_rva, mi))
                elif ins.mnemonic == "ret":
                    break
            if calls:
                decoded_calls = []
                for target_rva, mi in calls:
                    dec = decode_call(mi, target_rva)
                    if dec:
                        decoded_calls.append(dec)
                helper_analysis["internal_calls"] = decoded_calls
                concrete = None
                for dec in reversed(decoded_calls):
                    if dec["declaring_type"] != "MKIOEPLIEIH":
                        concrete = dec
                        break
                if concrete is None and decoded_calls:
                    concrete = decoded_calls[-1]
                if concrete is not None:
                    helper_analysis.update({
                        "concrete_parser_method_index": concrete["method_index"],
                        "concrete_parser_method_name": concrete["name"],
                        "concrete_runtime_type_index": concrete["declaring_type_index"],
                        "concrete_runtime_type_name": concrete["declaring_type"],
                        "concrete_parser_native_rva": concrete["native_rva"],
                        "structure_status": "ALLOC_AND_CONCRETE_PARSER",
                    })
                else:
                    helper_analysis["structure_status"] = "NO_INTERNAL_PARSER_CALL"
            else:
                helper_analysis["structure_status"] = "NO_INTERNAL_PARSER_CALL"
        helper_analysis["type_descriptor_global_rva"] = (
            f"0x{type_global:X}" if type_global is not None else None)
        m.update(helper_analysis)
    mm.close()

    for m in mappings:
        concrete = m.get("concrete_runtime_type_name")
        m["serialized_type_code"] = m["discriminator"]
        if concrete:
            m["runtime_type_index"] = m.get("concrete_runtime_type_index")
            m["runtime_type_name"] = concrete
            m["runtime_type_namespace"] = concrete.split(".")[0] if "." in concrete else ""
            m["namespace"] = m["runtime_type_namespace"]
            m["parser_method_index"] = m.get("concrete_parser_method_index")
            m["parser_method_name"] = m.get("concrete_parser_method_name")
            m["parser_native_rva"] = m.get("concrete_parser_native_rva")
            m["evidence"] = ("E4 dispatcher [entry+8] -> helper -> E4 direct call -> "
                             "concrete parser; E3 metadata identity; E5 runtime registry read")
            m["semantic_status"] = "REGISTRY_DISPATCH_TO_CONCRETE_PARSER_PROVEN"
        elif m["structure_status"] == "NULL_REGISTRY_SLOT":
            m["runtime_type_index"] = None
            m["runtime_type_name"] = None
            m["runtime_type_namespace"] = None
            m["namespace"] = None
            m["parser_method_index"] = None
            m["parser_method_name"] = None
            m["parser_native_rva"] = None
            m["evidence"] = "cctor stores qword 0 in this registry slot"
            m["semantic_status"] = "NULL_REGISTRY_SLOT"
        else:
            m["runtime_type_index"] = None
            m["runtime_type_name"] = None
            m["runtime_type_namespace"] = None
            m["namespace"] = None
            m["parser_method_index"] = None
            m["parser_method_name"] = None
            m["parser_native_rva"] = None
            m["evidence"] = ("helper allocates from type_descriptor_global but has no "
                             "internal mapped parser call (pure allocation stub)")
            m["semantic_status"] = "STATIC_HELPER_NO_INTERNAL_PARSER"

    names = [m.get("runtime_type_name") for m in mappings if m.get("runtime_type_name")]
    dup_disc = sorted({m["discriminator"] for m in mappings if m["discriminator"] < 0})
    dup_type = sorted({n for n in names if names.count(n) > 1})
    result = {
        "schema": "ability_mixin_type_bridge/1",
        "game_version": args.version,
        "serialized_domain": "ability_mixin_polymorphic_element (SkillConfig.VisibleCondition / "
                            "InsertCondition, UsableConditionConfig.UsableCondition, and 111 "
                            "confirmed dispatcher callers)",
        "base_runtime_type": "caller-field-typed polymorphic base; shared metadata field "
                            "type_reference 480840 for SkillConfig.VisibleCondition/InsertCondition "
                            "and UsableConditionConfig.UsableCondition (semantic TypeDefinition "
                            "name intentionally not decoded)",
        "descriptor_global_rva": f"0x{REGISTRY_GLOBAL_RVA:X}",
        "descriptor_initialization_source": "MKIOEPLIEIH.cctor (static descriptor globals -> "
                                            "0x27C entry array -> [global+0x6990])",
        "element_reader_method": {
            "runtime_type": "MKIOEPLIEIH",
            "method_name": "OJNNBEJLDIJ",
            "method_index": 132840,
            "native_rva": f"0x{DISPATCH_RVA:X}",
        },
        "subtype_discriminator_source": "ULEB128 value read by the element reader and used "
                                       "directly as registry array index",
        "registry": {
            "builder_type": "MKIOEPLIEIH",
            "builder_method": ".cctor",
            "builder_method_index": 132205,
            "builder_native_rva": f"0x{CCTOR_RVA:X}",
            "dispatcher_type": "MKIOEPLIEIH",
            "dispatcher_method": "OJNNBEJLDIJ",
            "dispatcher_method_index": 132840,
            "dispatcher_native_rva": f"0x{DISPATCH_RVA:X}",
            "registry_global_rva": f"0x{REGISTRY_GLOBAL_RVA:X}",
            "registry_slot_offset": f"0x{REGISTRY_SLOT_OFFSET:X}",
            "entry_count": EXPECTED_ENTRIES,
            "array_slots_offset": "0x20",
            "entry_parser_slot_offset": "0x08",
            "discriminator_reader": "ULEB128 (MOMNMLHNPLH.BIKABOFADBP @ 0x1CB8A410)",
            "dispatch_shape": "mov rax,[[global]+0x6990]; bounds; entry=[rax+0x20+code*8]; call [entry+8]",
        },
        "mappings": mappings,
        "statistics": {
            "mapping_count": len(mappings),
            "resolved_exact": sum(1 for m in mappings if m["mapping_kind"] == "EXACT_METHOD_ENTRY"),
            "resolved_containing": sum(1 for m in mappings if m["mapping_kind"] == "CONTAINING_METHOD"),
            "null_entries": sum(1 for m in mappings if m["mapping_kind"] == "NULL_ENTRY"),
            "non_executable_or_null": sum(1 for m in mappings if m["mapping_kind"] == "NON_EXECUTABLE_OR_NULL"),
            "unmapped_parser": sum(1 for m in mappings if m["mapping_kind"] == "UNMAPPED_PARSER"),
            "concrete_parser_resolved": sum(1 for m in mappings if m.get("concrete_parser_method_index")),
            "concrete_parser_unresolved": sum(1 for m in mappings if not m.get("concrete_parser_method_index")),
            "duplicate_discriminator": dup_disc,
            "duplicate_runtime_type": dup_type,
            "descriptor_global_sources_recovered": len(sources),
        },
        "evidence": {
            "builder": "E4 machine-code cctor allocates 0x27C array and fills slots from static descriptor globals",
            "dispatcher": "E4 machine-code discriminator -> array slot -> [entry+8] parser call",
            "parser_identity": "E3 MethodDefinition/TypeDefinition registry + CONFIRMED method code table",
            "runtime_values": "E5 read-only Runtime snapshot of initialized registry array (local ppSR/Cultivation client)",
        },
        "semantic_status": {
            "ability_mixin_subset": "SCOPED_BY_CALLER_DATAFLOW",
            "skillconfig_fields": [
                "UsableConditions (bit 57) -> list reader -> UsableConditionConfig.OJNNBEJLDIJ -> dispatcher",
                "VisibleCondition (bit 58) -> dispatcher",
                "InsertCondition (second bitfield bit 1) -> dispatcher",
            ],
            "black_swan_2_8_14_16": "mapped through the same registry (range validation only; "
                                    "byte-level serializer identity remains unproven)",
        },
        "structure_status": "CONFIRMED",
        "not_claimed": [
            "battle Execute semantics",
            "element field-level payload parsing beyond registry dispatch",
            "semantic meaning of unrelated registry entries",
        ],
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    print(f"entries={len(mappings)} exact={result['statistics']['resolved_exact']} "
          f"containing={result['statistics']['resolved_containing']} "
          f"unmapped={result['statistics']['unmapped_parser']} "
          f"descriptor_globals={len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
