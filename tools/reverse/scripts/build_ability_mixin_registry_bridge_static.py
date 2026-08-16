#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the MKIOEPLIEIH polymorphic registry bridge WITHOUT a runtime read.

For versions whose registry .data qwords are encrypted placeholders and whose
client is not running, the discriminator -> helper-method relation is already
static:

    cctor allocates N entries and fills slot i (i>=1) with the descriptor whose
    +0x08 points at MKIOEPLIEIH method (cctor_method_index + 1 + i);
    each helper body allocates from its type_global and calls the concrete
    Runtime Class parser method.

This tool resolves every helper statically through the CONFIRMED method code
table and metadata registries, and recovers each cctor source global RVA.
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


def extract_cctor_source_globals(pe: PeImage, cctor_rva: int, cctor_end_rva: int,
                                 entry_count: int) -> list[dict]:
    raw = pe.read_rva(cctor_rva, cctor_end_rva - cctor_rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    rows = []
    pending = None
    for ins in md.disasm(raw, pe.image_base + cctor_rva):
        if ins.address >= pe.image_base + cctor_end_rva:
            break
        if ins.mnemonic == "mov" and len(ins.operands) == 2:
            dst, src = ins.operands
            if (src.type == x86.X86_OP_MEM and src.mem.base == x86.X86_REG_RIP
                    and dst.type == x86.X86_OP_REG
                    and dst.reg in (x86.X86_REG_RDX, x86.X86_REG_RCX)):
                pending = ins.address + ins.size + src.mem.disp - pe.image_base
                continue
            if (pending is not None and dst.type == x86.X86_OP_MEM
                    and dst.mem.base == x86.X86_REG_RAX and src.type == x86.X86_OP_REG
                    and src.reg in (x86.X86_REG_RDX, x86.X86_REG_RCX)
                    and dst.mem.disp >= 0x20):
                slot = dst.mem.disp - 0x20
                if slot % 8 == 0 and slot // 8 < entry_count:
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
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--version", default="4.4.0")
    ap.add_argument("--cctor-method-index", type=int, required=True)
    ap.add_argument("--dispatcher-method-index", type=int, required=True)
    ap.add_argument("--registry-global-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--registry-slot-offset", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--entry-count", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--cctor-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--cctor-end-rva", type=lambda x: int(x, 0), required=True)
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

    by_rva: dict[int, int] = {}
    raw_table = pe.read_rva(args.code_table_rva, nmethods * 8)
    for mi in range(nmethods):
        q = struct.unpack_from("<Q", raw_table, mi * 8)[0]
        if q:
            rva = q - pe.image_base
            if rva not in by_rva:
                by_rva[rva] = mi

    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True

        def decode_call(mi: int, rva: int) -> dict:
            declaring = decode_declaring_type(mm, mbase, mi)
            return {
                "method_index": mi,
                "native_rva": f"0x{rva:X}",
                "name": decode_method_name(mm, mbase, mi, region),
                "declaring_type_index": declaring,
                "declaring_type": resolve_type_name(mm, tbase, declaring, region),
            }

        mappings = []
        for disc in range(args.entry_count):
            row = {
                "discriminator": disc,
                "entry_pointer": None,
                "parser_native_rva": None,
                "parser_method_index": None,
                "parser_method_name": None,
                "parser_declaring_type_index": None,
                "runtime_type_name": None,
                "runtime_type_namespace": None,
                "mapping_kind": None,
                "descriptor_global_rva": None,
                "cctor_store_rva": None,
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
                "structure_status": None,
            }
            if disc == 0:
                row.update({"mapping_kind": "NULL_ENTRY",
                            "structure_status": "NULL_REGISTRY_SLOT"})
                mappings.append(row)
                continue
            helper_mi = args.cctor_method_index + 1 + disc
            q = struct.unpack_from("<Q", raw_table, helper_mi * 8)[0]
            helper_rva = q - pe.image_base if q else None
            row.update({
                "mapping_kind": "STATIC_HELPER_INDEX",
                "helper_method_index": helper_mi,
                "helper_method_rva": f"0x{helper_rva:X}" if helper_rva else None,
                "parser_native_rva": f"0x{helper_rva:X}" if helper_rva else None,
                "parser_method_index": helper_mi,
                "parser_method_name": decode_method_name(mm, mbase, helper_mi, region),
                "parser_declaring_type_index": decode_declaring_type(mm, mbase, helper_mi),
                "runtime_type_name": resolve_type_name(
                    mm, tbase, decode_declaring_type(mm, mbase, helper_mi), region),
                "runtime_type_namespace": resolve_type_name(
                    mm, tbase, decode_declaring_type(mm, mbase, helper_mi), region).split(".")[0],
            })
            if helper_rva is None:
                row["structure_status"] = "NO_NATIVE_HELPER"
                mappings.append(row)
                continue
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
                            and dst.type == x86.X86_OP_REG
                            and dst.reg == x86.X86_REG_RCX and type_global is None):
                        type_global = ins.address + ins.size + src.mem.disp - pe.image_base
                elif ins.mnemonic in ("call", "jmp"):
                    op = ins.operands[0]
                    if op.type == x86.X86_OP_IMM:
                        target_rva = int(op.imm) - pe.image_base
                        mi = by_rva.get(target_rva)
                        if mi is not None and mi != helper_mi:
                            calls.append((target_rva, mi))
                elif ins.mnemonic == "ret":
                    break
            decoded_calls = [decode_call(mi, rva) for rva, mi in calls]
            row["internal_calls"] = decoded_calls
            concrete = None
            for dec in reversed(decoded_calls):
                if dec["declaring_type"] != "MKIOEPLIEIH":
                    concrete = dec
                    break
            if concrete is None and decoded_calls:
                concrete = decoded_calls[-1]
            if concrete is not None:
                row.update({
                    "concrete_parser_method_index": concrete["method_index"],
                    "concrete_parser_method_name": concrete["name"],
                    "concrete_runtime_type_index": concrete["declaring_type_index"],
                    "concrete_runtime_type_name": concrete["declaring_type"],
                    "concrete_parser_native_rva": concrete["native_rva"],
                    "structure_status": "ALLOC_AND_CONCRETE_PARSER",
                })
            else:
                row["structure_status"] = "NO_INTERNAL_PARSER_CALL"
            row["type_descriptor_global_rva"] = (
                f"0x{type_global:X}" if type_global is not None else None)
            mappings.append(row)

        cctor_q = struct.unpack_from(
            "<Q", raw_table, args.cctor_method_index * 8)[0]
        cctor_rva = cctor_q - pe.image_base
        dispatcher_q = struct.unpack_from(
            "<Q", raw_table, args.dispatcher_method_index * 8)[0]
        dispatcher_rva = dispatcher_q - pe.image_base
        mm.close()

    sources = extract_cctor_source_globals(
        pe, args.cctor_rva, args.cctor_end_rva, args.entry_count)
    src_by_disc = {s["discriminator"]: s for s in sources}
    for m in mappings:
        s = src_by_disc.get(m["discriminator"])
        if s:
            m["descriptor_global_rva"] = s["descriptor_global_rva"]
            m["cctor_store_rva"] = s["cctor_store_rva"]

    resolved = sum(1 for m in mappings if m.get("concrete_parser_method_index"))
    result = {
        "schema": "ability_mixin_type_bridge/1",
        "game_version": args.version,
        "serialized_domain": "mkioeplieih_polymorphic_parser_registry",
        "registry": {
            "builder_type": "MKIOEPLIEIH",
            "builder_method": ".cctor",
            "builder_method_index": args.cctor_method_index,
            "builder_native_rva": f"0x{cctor_rva:X}",
            "dispatcher_type": "MKIOEPLIEIH",
            "dispatcher_method": "OJNNBEJLDIJ",
            "dispatcher_method_index": args.dispatcher_method_index,
            "dispatcher_native_rva": f"0x{dispatcher_rva:X}",
            "registry_global_rva": f"0x{args.registry_global_rva:X}",
            "registry_slot_offset": f"0x{args.registry_slot_offset:X}",
            "entry_count": args.entry_count,
            "array_slots_offset": "0x20",
            "entry_parser_slot_offset": "0x08",
            "discriminator_reader": "ULEB128 (MOMNMLHNPLH.BIKABOFADBP)",
            "dispatch_shape": "mov rax,[[global]+slot]; bounds; entry=[rax+0x20+code*8]; call [entry+8]",
        },
        "mappings": mappings,
        "statistics": {
            "mapping_count": len(mappings),
            "resolved_exact": 0,
            "resolved_containing": 0,
            "null_entries": sum(1 for m in mappings if m["mapping_kind"] == "NULL_ENTRY"),
            "non_executable_or_null": 0,
            "unmapped_parser": 0,
            "concrete_parser_resolved": resolved,
            "concrete_parser_unresolved": len(mappings) - resolved,
            "duplicate_discriminator": [],
            "duplicate_runtime_type": [],
            "descriptor_global_sources_recovered": len(sources),
        },
        "evidence": {
            "builder": "E4 machine-code cctor allocates entry_count array and fills slots from static descriptor globals",
            "dispatcher": "E4 machine-code discriminator -> array slot -> [entry+8] parser call",
            "parser_identity": "E3 MethodDefinition/TypeDefinition registry + CONFIRMED method code table",
            "runtime_values": "not read (static-only bridge; .data qwords are encrypted placeholders)",
        },
        "semantic_status": {
            "ability_mixin_subset": "NOT_YET_SCOPED",
            "note": "Registry identity is code-proven; no runtime read performed for this version.",
        },
        "not_claimed": [
            "battle Execute semantics",
            "element field-level payload parsing beyond registry dispatch",
        ],
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out} entries={len(mappings)} resolved={resolved} "
          f"descriptor_globals={len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
