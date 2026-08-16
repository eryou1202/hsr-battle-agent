#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect one or more recovered MHY TypeDefinitions and their members.

Reuses the CONFIRMED 0x84 / 0x14C / 0x20 decoders and, when a method code
table RVA is supplied, joins each method to its native RVA automatically
(method_index -> code_table qword). No semantic mapping is claimed here.
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

from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from analyze_mhy_method_candidate import (  # noqa: E402
    METHOD_HASH_ADD,
    RULES,
    FIELD_NAME_CONST,
    FIELD_PARAM_START_CONST,
)
from analyze_mhy_field_candidate import RULES as FIELD_RULES  # noqa: E402

ALL_RULES = {**RULES, **FIELD_RULES}
from build_method_code_registry import scalar_method_hash32  # noqa: E402
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1


def decode_rule(raw: int, op: str, const: int) -> int:
    return (raw + const) & M32 if op == "add" else raw ^ const


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    return {
        field: FILE_HEADER + signed32(decode_rule(raw, op, const))
        for field, (op, const) in ALL_RULES.items()
        for raw in [struct.unpack_from("<I", block, field)[0]]
    }


def type_name(mm, tbase: int, ti: int, region: bytes) -> str:
    raw24 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x24)[0]
    raw28 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x28)[0]
    ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & M32, region)
    name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & M32, region)
    ns_s = ns.decode("utf-8", "replace")
    name_s = name.decode("utf-8", "replace")
    return f"{ns_s}.{name_s}" if ns_s else name_s


def inspect(mm, pe: PeImage, offs: dict[int, int], region: bytes,
            ti: int, code_table_rva: int | None) -> dict:
    tbase = offs[0x84]
    mbase = offs[0x14C]
    fbase = offs[0x20]
    rec_off = tbase + ti * 70

    mstart_raw = struct.unpack_from("<I", mm, rec_off + 0x08)[0]
    mstart = (mstart_raw ^ 0x1A7AF5FE) & M32
    if mstart >= 0x80000000:
        mstart = -1
    mcount = (struct.unpack_from("<H", mm, rec_off + 0x34)[0] + 0x5F93) & 0xFFFF
    fstart = (struct.unpack_from("<I", mm, rec_off + 0x20)[0] + 0x8B7AC79C) & M32
    if fstart >= 0x80000000:
        fstart = -1
    fcount = (struct.unpack_from("<H", mm, rec_off + 0x32)[0] + 0x444D) & 0xFFFF

    methods = []
    if mstart >= 0:
        for mi in range(mstart, mstart + mcount):
            h32 = scalar_method_hash32(mi)
            raw_name = struct.unpack_from("<I", mm, mbase + mi * 26)[0]
            name_key = (h32 ^ raw_name ^ FIELD_NAME_CONST) & M32
            name, _ = resolve_identifier(name_key, region)
            raw_pc = mm[mbase + mi * 26 + 0x18]
            # Correct rule: raw ^ low8(hash32c) ^ 0xA8 where
            # hash32c = low32(rolling_hash + 0x71BC7861); scalar_method_hash32
            # already returns exactly hash32c.
            pc = raw_pc ^ (h32 & 0xFF) ^ 0xA8
            raw_ps = struct.unpack_from("<I", mm, mbase + mi * 26 + 0x04)[0]
            ps = (h32 ^ raw_ps ^ FIELD_PARAM_START_CONST) & M32
            if ps >= 0x80000000:
                ps = -1
            raw_ret = struct.unpack_from("<I", mm, mbase + mi * 26 + 0x08)[0]
            ret = (h32 ^ ((raw_ret + 0x9AC1F4E3) & M32)) & M32
            if ret >= 0x80000000:
                ret = -1
            row = {
                "method_index": mi,
                "name": name.decode("utf-8", "replace"),
                "parameter_count": int(pc),
                "parameter_start": int(ps),
                "return_type_reference": int(ret),
            }
            if code_table_rva is not None:
                q = struct.unpack("<Q", pe.read_rva(
                    code_table_rva + mi * 8, 8))[0]
                row["native_rva"] = f"0x{q - pe.image_base:X}" if q else None
            methods.append(row)

    fields = []
    if fstart >= 0:
        raw_fstart = struct.unpack_from("<I", mm, rec_off + 0x20)[0]
        roll0 = (0xAD416BB9 - (raw_fstart * 0x2C5DCB00 & M32)) & M32
        for fi in range(fstart, fstart + fcount):
            local = fi - fstart
            roll = (roll0 + local * 0xD3A23500) & M32
            raw_name, raw_type = struct.unpack_from("<II", mm, fbase + fi * 8)
            name_key = (raw_name + roll + 0x2AAFC785) & M32
            name, _ = resolve_identifier(name_key, region)
            type_ref = (raw_type + roll) & M32
            if type_ref >= 0x80000000:
                type_ref -= 0x100000000
            fields.append({
                "field_index": fi,
                "name": name.decode("utf-8", "replace"),
                "type_reference": int(type_ref),
            })

    return {
        "type_index": ti,
        "full_name": type_name(mm, tbase, ti, region),
        "method_start": mstart,
        "method_count": mcount,
        "methods": methods,
        "field_start": fstart,
        "field_count": fcount,
        "fields": fields,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--type-index", type=int, action="append", default=[])
    ap.add_argument("--type-name-substr", action="append", default=[])
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    pe = PeImage(args.game)
    tpl = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    offs = table_offsets(pe, tpl)
    tbase = offs[0x84]
    tnext = offs[0x38]
    ntypes = (tnext - tbase) // 70
    region_base = offs[0x1B4]
    size = args.metadata.stat().st_size

    selected = set(args.type_index)
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        if args.type_name_substr:
            for ti in range(ntypes):
                name = type_name(mm, tbase, ti, region).lower()
                if any(s.lower() in name for s in args.type_name_substr):
                    selected.add(ti)
        rows = [inspect(mm, pe, offs, region, ti, args.code_table_rva)
                for ti in sorted(selected)]
        mm.close()

    result = {
        "schema": "mhy_type_inspection/1",
        "game": str(args.game.resolve()),
        "metadata": str(args.metadata.resolve()),
        "template_rva": f"0x{tpl:X}",
        "code_table_rva": (f"0x{args.code_table_rva:X}"
                           if args.code_table_rva is not None else None),
        "types": rows,
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    for row in rows:
        print(f"[{row['type_index']}] {row['full_name']} "
              f"methods={row['method_count']} fields={row['field_count']}")
        for m in row["methods"]:
            print(f"  M {m['method_index']:>7} {m['name']:32} "
                  f"pc={m['parameter_count']:>3} rva={m.get('native_rva')}")
        for fd in row["fields"]:
            print(f"  F {fd['field_index']:>7} {fd['name']:40} "
                  f"typeref={fd['type_reference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
