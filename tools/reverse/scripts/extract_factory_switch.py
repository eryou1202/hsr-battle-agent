#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract a generated polymorphic factory switch into a bridge registry.

Given a factory method (e.g. AbilityConfig.FromBinary) this tool:

  1. resolves the method through the CONFIRMED metadata registries;
  2. locates its `cmp N; ja; lea table; movsxd; add; jmp` dispatcher;
  3. reads the jump table cases;
  4. follows each case block to its tail jump, which is the concrete parser
     method entry, and resolves that parser through the method code registry;
  5. emits `type_code -> parser MethodDefinition -> declaring TypeDefinition`.

This is exactly the DesignData serialized type -> Runtime Class bridge for
switch-style factories. It does not analyze battle semantics.
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
    scalar_method_hash32,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402
from scan_dispatch_tables import find_case_bound, find_lea_before  # noqa: E402

FIELD_NAME_CONST = 0x0E714BC1
FIELD_DECLARING_CONST = 0x2A5FABE8
JUMP_PATTERNS = [
    bytes.fromhex("486304814801c8ffe0"),
    bytes.fromhex("496304814801c8ffe0"),
    bytes.fromhex("486304824801d0ffe0"),
    bytes.fromhex("486304834801d8ffe0"),
    bytes.fromhex("496304804c01c0ffe0"),
    bytes.fromhex("496304814c01c8ffe0"),
    bytes.fromhex("4a6304804c01c0ffe0"),
    bytes.fromhex("4a6304814c01c8ffe0"),
]


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


def load_method_registry(pe: PeImage, code_table_rva: int, nmethods: int) -> dict:
    raw = pe.read_rva(code_table_rva, nmethods * 8)
    by_rva: dict[int, int] = {}
    for i in range(nmethods):
        q = struct.unpack_from("<Q", raw, i * 8)[0]
        if q:
            by_rva.setdefault(q - pe.image_base, i)
    return by_rva


def tail_jump_target(pe: PeImage, case_rva: int, max_len: int = 0x180) -> int | None:
    """Find the first direct `jmp` target that is a method entry-ish tail."""
    raw = pe.read_rva(case_rva, max_len)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for ins in md.disasm(raw, pe.image_base + case_rva):
        if ins.mnemonic == "jmp" and ins.operands and ins.operands[0].type == x86.X86_OP_IMM:
            return int(ins.operands[0].imm) - pe.image_base
        if ins.mnemonic == "ret":
            return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--factory-type", required=True)
    ap.add_argument("--factory-method", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--version", default="unknown")
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
    by_rva = load_method_registry(pe, args.code_table_rva, nmethods)

    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        factory_mi = None
        factory_ti = None
        for mi in range(nmethods):
            h32 = scalar_method_hash32(mi)
            raw_name = struct.unpack_from("<I", mm, mbase + mi * 26)[0]
            name_key = (h32 ^ raw_name ^ FIELD_NAME_CONST) & M32
            name, _ = resolve_identifier(name_key, region)
            if name.decode("utf-8", "replace") != args.factory_method:
                continue
            raw_decl = struct.unpack_from("<I", mm, mbase + mi * 26 + 0x10)[0]
            ti = (h32 ^ raw_decl ^ FIELD_DECLARING_CONST) & M32
            full = resolve_type_name(mm, tbase, ti, region)
            if full == args.factory_type:
                factory_mi = mi
                factory_ti = ti
                break
        if factory_mi is None:
            raise SystemExit(f"factory method not found: {args.factory_type}.{args.factory_method}")

        factory_q = struct.unpack("<Q", pe.read_rva(
            args.code_table_rva + factory_mi * 8, 8))[0]
        factory_rva = factory_q - pe.image_base if factory_q else None
        if factory_rva is None:
            raise SystemExit("factory method has no direct native code")

        code = pe.read_rva(factory_rva, 0x800)
        switch = None
        for pattern in JUMP_PATTERNS:
            p = code.find(pattern)
            if p < 0:
                continue
            lea = find_lea_before(code, p)
            bound = find_case_bound(code, p)
            if lea is None or bound is None:
                continue
            _, table_off = lea
            table_va = pe.image_base + factory_rva + table_off
            table_raw = pe.read_rva(table_va - pe.image_base, (bound + 1) * 4)
            if table_raw is None:
                continue
            entries = struct.unpack(f"<{bound + 1}i", table_raw)
            switch = {
                "pattern_offset": p,
                "jump_table_rva": table_va - pe.image_base,
                "case_bound": bound,
                "entries": entries,
            }
            break
        if switch is None:
            raise SystemExit("switch dispatcher not found in factory prologue")

        mappings = []
        for case, entry in enumerate(switch["entries"]):
            case_rva = (table_va + entry - pe.image_base) & 0xFFFFFFFF
            tail = tail_jump_target(pe, case_rva)
            tail_mi = by_rva.get(tail) if tail is not None else None
            parser_type = None
            parser_name = None
            parser_ti = None
            if tail_mi is not None:
                parser_name = decode_method_name(mm, mbase, tail_mi, region)
                parser_ti = decode_declaring_type(mm, mbase, tail_mi)
                parser_type = resolve_type_name(mm, tbase, parser_ti, region)
            mappings.append({
                "type_code": case,
                "case_block_rva": f"0x{case_rva:X}",
                "parser_tail_rva": f"0x{tail:X}" if tail is not None else None,
                "parser_method_index": tail_mi,
                "parser_method_name": parser_name,
                "runtime_type_index": parser_ti,
                "runtime_type_name": parser_type,
                "runtime_type_namespace": (parser_type.split(".")[0]
                                            if parser_type and "." in parser_type else ""),
                "parser_native_rva": f"0x{tail:X}" if tail is not None else None,
                "mapping_kind": ("SWITCH_CASE_TO_METHOD"
                                 if tail_mi is not None else "UNRESOLVED_TAIL"),
            })
        mm.close()

    result = {
        "schema": "mhy_design_runtime_bridge/1",
        "game_version": args.version,
        "serialized_domain": args.domain,
        "factory": {
            "runtime_type_index": factory_ti,
            "runtime_type_name": args.factory_type,
            "method_name": args.factory_method,
            "method_index": factory_mi,
            "native_rva": f"0x{factory_rva:X}",
        },
        "mechanism": {
            "kind": "STATIC_SWITCH_FACTORY",
            "type_tag_reader": "ULEB128 (MOMNMLHNPLH.BIKABOFADBP @ 0x1CB8A410)",
            "dispatch_shape": "cmp eax, N; ja default; movsxd [table+idx*4]; add table; jmp",
            "jump_table_rva": f"0x{switch['jump_table_rva']:X}",
            "case_bound": switch["case_bound"],
        },
        "mappings": mappings,
        "statistics": {
            "mapping_count": len(mappings),
            "resolved": sum(1 for m in mappings if m["parser_method_index"] is not None),
            "duplicate_code": 0,
            "duplicate_class": None,
            "unknown_entries": sum(1 for m in mappings if m["parser_method_index"] is None),
            "null_entries": 0,
        },
        "evidence_level": ("E4 machine-code serializer/factory dataflow + "
                           "E3 MHY TypeDefinition/MethodDefinition registry"),
        "not_claimed": [
            "battle Execute semantics",
            "field-level payload parsing beyond factory dispatch",
            "type_tag meaning outside this serialized domain",
        ],
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    print(f"factory={factory_mi}@{factory_rva:X} table={switch['jump_table_rva']:X} "
          f"cases={len(mappings)}")
    for m in mappings:
        print(f"  type_code {m['type_code']:>3} -> "
              f"{m['runtime_type_name']}.{m['parser_method_name']} "
              f"[{m['parser_method_index']}] {m['parser_native_rva']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
