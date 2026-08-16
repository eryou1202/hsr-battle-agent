#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recover static jump-table dispatchers and connect every case to metadata.

Generated C# deserializers use the classic x64 shape:

    cmp  eax, N
    ja   default
    movsxd rax, dword ptr [table + rax*4]   ; table = [rip + disp]
    add  rax, table
    jmp  rax

This tool locates that shape, reads the jump table, and resolves every case
target through the CONFIRMED method code registry (method_index -> native RVA)
back to a TypeDefinition + MethodDefinition. This is the primary mechanism
locator for serialized-type -> Runtime Class bridges.
"""
from __future__ import annotations

import argparse
import bisect
import json
import mmap
import re
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

JUMP_PATTERNS = [
    bytes.fromhex("486304814801c8ffe0"),  # rax = [rcx + rax*4]; add rax, rcx
    bytes.fromhex("496304814801c8ffe0"),  # REX.WB movsxd variant
    bytes.fromhex("486304824801d0ffe0"),  # base rdx
    bytes.fromhex("486304834801d8ffe0"),  # base rbx
    bytes.fromhex("496304804c01c0ffe0"),  # base r8
    bytes.fromhex("496304814c01c8ffe0"),  # base r9
    bytes.fromhex("4a6304804c01c0ffe0"),  # base r8, REX.X variant
    bytes.fromhex("4a6304814c01c8ffe0"),  # base r9, REX.X variant
    bytes.fromhex("486304864801f0ffe0"),  # base rsi
    bytes.fromhex("486304874801f8ffe0"),  # base rdi
]

MIN_TABLE_ENTRIES = 2
MAX_TABLE_ENTRIES = 4096
MAX_HITS_PER_SECTION = 200000


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


def load_code_registry(pe: PeImage, code_table_rva: int, nmethods: int) -> dict:
    raw = pe.read_rva(code_table_rva, nmethods * 8)
    if raw is None or len(raw) != nmethods * 8:
        raise SystemExit("code table read failed")
    by_rva: dict[int, int] = {}
    rva_list: list[int] = []
    for i in range(nmethods):
        q = struct.unpack_from("<Q", raw, i * 8)[0]
        if q:
            rva = q - pe.image_base
            if rva not in by_rva:
                by_rva[rva] = i
                rva_list.append(rva)
    rva_list.sort()
    return {"by_rva": by_rva, "sorted_rvas": rva_list}


def containing_method(code: dict, rva: int) -> int | None:
    pos = bisect.bisect_right(code["sorted_rvas"], rva) - 1
    if pos < 0:
        return None
    return code["by_rva"][code["sorted_rvas"][pos]]


def find_lea_before(data: bytes, hit_end: int, window: int = 64) -> tuple[int, int] | None:
    """Find nearest `lea reg, [rip+disp32]` before hit_end (byte-level).

    Returns (lea_offset_in_data, table_offset_in_data); offsets are relative to
    the start of `data`.
    """
    start = max(0, hit_end - window)
    best = None
    for m in re.finditer(
            rb"\x48\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})"
            rb"|\x4c\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp2>.{4})",
            data[start:hit_end], re.DOTALL):
        disp = m.group("disp") or m.group("disp2")
        off = start + m.start()
        if off + 7 <= hit_end:
            best = (off, off + 7 + struct.unpack("<i", disp)[0])
    return best


def find_case_bound(data: bytes, hit_start: int, window: int = 80) -> int | None:
    """Look backwards for `cmp reg, imm; ja/jbe default` before hit_start."""
    start = max(0, hit_start - window)
    seg = data[start:hit_start]
    # Nearest conditional branch before the table dispatch. The cmp immediate
    # directly precedes the branch in the observed generated code.
    branch = -1
    for m in re.finditer(rb"\x0f[\x87\x86\x82\x83]", seg):
        branch = start + m.start()
    if branch < 0:
        return None
    cmp_start = max(start, branch - 16)
    cand = None
    pos = cmp_start
    while pos < branch:
        b = data[pos]
        if b == 0x83 and pos + 2 < branch and data[pos + 1] in range(0xF8, 0x100):
            cand = data[pos + 2]
            pos += 3
            continue
        if b == 0x3D and pos + 5 <= branch:
            cand = struct.unpack("<I", data[pos + 1 : pos + 5])[0]
            pos += 5
            continue
        if b == 0x81 and pos + 6 <= branch and data[pos + 1] in range(0xF8, 0x100):
            cand = struct.unpack("<I", data[pos + 2 : pos + 6])[0]
            pos += 6
            continue
        pos += 1
    if cand is not None and MIN_TABLE_ENTRIES <= cand <= MAX_TABLE_ENTRIES:
        return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--max-hits", type=int, default=5000)
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
    code = load_code_registry(pe, args.code_table_rva, nmethods)

    hits = []
    with open(args.game, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if not sec.is_executable or sec.raw_size <= 0 or sec.name == ".upx0":
                continue
            data = raw[sec.raw_offset : sec.raw_offset + sec.raw_size]
            for pattern in JUMP_PATTERNS:
                pos = 0
                section_hits = 0
                while True:
                    p = data.find(pattern, pos)
                    if p < 0 or section_hits >= MAX_HITS_PER_SECTION:
                        break
                    hit_rva = sec.rva + p
                    lea = find_lea_before(data, p)
                    if lea is None:
                        pos = p + 1
                        continue
                    _, table_off = lea
                    table_va = pe.image_base + sec.rva + table_off
                    bound = find_case_bound(data, p)
                    if bound is None:
                        pos = p + 1
                        continue
                    table_rva = table_va - pe.image_base
                    table_raw = pe.read_rva(table_rva, (bound + 1) * 4)
                    if table_raw is None or len(table_raw) != (bound + 1) * 4:
                        pos = p + 1
                        continue
                    entries = struct.unpack(f"<{bound + 1}i", table_raw)
                    targets = []
                    valid = True
                    for entry in entries:
                        tva = (table_va + entry) & 0xFFFFFFFFFFFFFFFF
                        trva = tva - pe.image_base
                        sec_t = pe.section_at_rva(trva)
                        if sec_t is None or not sec_t.is_executable:
                            valid = False
                            break
                        mi = code["by_rva"].get(trva)
                        if mi is not None:
                            method_index = mi
                        else:
                            method_index = containing_method(code, trva)
                        targets.append({"case": len(targets), "native_rva": f"0x{trva:X}",
                                        "method_index": method_index})
                    if not valid:
                        pos = p + 1
                        continue
                    hits.append({
                        "dispatch_rva": f"0x{hit_rva:X}",
                        "section": sec.name,
                        "jump_table_rva": f"0x{table_rva:X}",
                        "case_bound": bound,
                        "case_count": bound + 1,
                        "containing_method_index": containing_method(code, hit_rva),
                        "targets": targets,
                    })
                    section_hits += 1
                    pos = p + 1
                    if len(hits) >= args.max_hits:
                        break
                if len(hits) >= args.max_hits:
                    break
            if len(hits) >= args.max_hits:
                break
        raw.close()

    # Decode metadata names for each hit and its targets.
    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        decoded_hits = []
        for hit in hits:
            mi = hit.get("containing_method_index")
            if mi is None:
                hit["containing_method"] = None
            else:
                declaring = decode_declaring_type(mm, mbase, mi)
                hit["containing_method"] = {
                    "method_index": mi,
                    "name": decode_method_name(mm, mbase, mi, region),
                    "declaring_type_index": declaring,
                    "declaring_type": resolve_type_name(mm, tbase, declaring, region),
                }
            for t in hit["targets"]:
                mi = t.get("method_index")
                if mi is None:
                    t["name"] = None
                    t["declaring_type_index"] = None
                    t["declaring_type"] = None
                    continue
                declaring = decode_declaring_type(mm, mbase, mi)
                t["name"] = decode_method_name(mm, mbase, mi, region)
                t["declaring_type_index"] = declaring
                t["declaring_type"] = resolve_type_name(mm, tbase, declaring, region)
            decoded_hits.append(hit)
        mm.close()

    result = {
        "schema": "mhy_dispatch_table_scan/1",
        "game": str(args.game.resolve()),
        "metadata": str(args.metadata.resolve()),
        "template_rva": f"0x{tpl:X}",
        "code_table_rva": f"0x{args.code_table_rva:X}",
        "method_count": nmethods,
        "dispatch_count": len(decoded_hits),
        "dispatchers": decoded_hits,
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out} dispatchers={len(decoded_hits)}")
    for hit in decoded_hits[:40]:
        cm = hit.get("containing_method") or {}
        print(f"  {hit['dispatch_rva']} cases={hit['case_count']} "
              f"{cm.get('declaring_type')}.{cm.get('name')} "
              f"table={hit['jump_table_rva']}")
        for t in hit["targets"][:6]:
            print(f"      case {t['case']:>3} -> {t['declaring_type']}.{t['name']} "
                  f"{t['native_rva']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
