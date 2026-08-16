#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fingerprint generated DesignData parser methods.

For a list of candidate methods (CSV produced by query_types_by_method.py)
read each native entry from the method code registry, disassemble a bounded
prefix, and search for event sequences:

  * calls to the CONFIRMED ULEB128 reader (0x1CB8A410) / string reader
    (0x1CBA4E70) / generic object readers;
  * immediate constants in `cmp` instructions, optionally restricted to a
    caller-provided ordered list (e.g. the Black Swan type-2 prefix tags
    0x31, 0x0A, 0x0C, 0x01, 0x04).

This is anchor-based candidate discovery only; a hit is not a mapping.
"""
from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vendor" / "capstone"))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

READ_ULEB_RVA = 0x1CB8A410
READ_STRING_RVA = 0x1CBA4E70
READ_OBJECT_RVAS = {0x16C86A10, 0x16C8E0D0, 0x16C8E4C0}


def disasm_events(pe: PeImage, rva: int, length: int) -> dict:
    raw = pe.read_rva(rva, length)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    calls = []
    cmps = []
    imms = []
    rets = 0
    jumps = []
    insn_count = 0
    for ins in md.disasm(raw, pe.image_base + rva):
        insn_count += 1
        if ins.mnemonic == "call":
            op = ins.operands[0]
            if op.type == x86.X86_OP_IMM:
                calls.append(int(op.imm) - pe.image_base)
        elif ins.mnemonic == "cmp":
            for op in ins.operands:
                if op.type == x86.X86_OP_IMM:
                    cmps.append(int(op.imm))
                    imms.append(int(op.imm))
        elif ins.mnemonic in ("mov", "test"):
            for op in ins.operands:
                if op.type == x86.X86_OP_IMM:
                    imms.append(int(op.imm))
        elif ins.mnemonic == "ret":
            rets += 1
            if rets >= 2:
                break
        elif ins.mnemonic.startswith("j"):
            for op in ins.operands:
                if op.type == x86.X86_OP_IMM:
                    jumps.append(int(op.imm) - pe.image_base)
    return {
        "calls": calls,
        "cmps": cmps,
        "imms": imms,
        "jumps": jumps,
        "insn_count": insn_count,
    }


def ordered_subseq(needle: list[int], hay: list[int]) -> bool:
    it = iter(hay)
    return all(any(v == n for v in it) for n in needle)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--candidates", required=True, type=Path,
                    help="CSV from query_types_by_method.py")
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--method-prefix-length", type=lambda x: int(x, 0), default=0x400)
    ap.add_argument("--needle", nargs="*", type=lambda x: int(x, 0), default=[])
    ap.add_argument("--call-needle", default=None,
                    help="e.g. U,U,S,U,S (U=ReadUleb, S=ReadString)")
    ap.add_argument("--min-read-uleb", type=int, default=2)
    ap.add_argument("--min-read-string", type=int, default=1)
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    pe = PeImage(args.game)
    rows = []
    with open(args.candidates, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for mi_s in row["method_indices"].split("|"):
                if not mi_s:
                    continue
                rows.append({
                    "type_index": int(row["type_index"]),
                    "full_name": row["full_name"],
                    "method_index": int(mi_s),
                })
    print(f"candidates={len(rows)}")

    hits = []
    total = 0
    for row in rows:
        raw = pe.read_rva(args.code_table_rva + row["method_index"] * 8, 8)
        q = struct.unpack("<Q", raw)[0]
        if not q:
            continue
        rva = q - pe.image_base
        if pe.section_at_rva(rva) is None or not pe.section_at_rva(rva).is_executable:
            continue
        total += 1
        ev = disasm_events(pe, rva, args.method_prefix_length)
        if ev["calls"].count(READ_ULEB_RVA) < args.min_read_uleb:
            continue
        if args.min_read_string and ev["calls"].count(READ_STRING_RVA) < args.min_read_string:
            continue
        if args.needle and not ordered_subseq(args.needle, ev["imms"]):
            continue
        if args.call_needle:
            wanted = [READ_ULEB_RVA if c == "U" else READ_STRING_RVA
                      for c in args.call_needle.split(",")]
            if not ordered_subseq(wanted, ev["calls"]):
                continue
        hits.append({
            "type_index": row["type_index"],
            "full_name": row["full_name"],
            "method_index": row["method_index"],
            "native_rva": f"0x{rva:X}",
            "read_uleb_calls": ev["calls"].count(READ_ULEB_RVA),
            "read_string_calls": ev["calls"].count(READ_STRING_RVA),
            "call_rvas": [f"0x{r:X}" for r in ev["calls"][:24]],
            "cmp_immediates": ev["cmps"][:48],
            "ordered_immediates": ev["imms"][:80],
            "jump_rvas": [f"0x{r:X}" for r in ev["jumps"][:16]],
        })
        if len(hits) >= 2000:
            break

    result = {
        "schema": "mhy_parser_fingerprint_scan/1",
        "game": str(args.game.resolve()),
        "candidate_count": len(rows),
        "methods_with_code": total,
        "needle": args.needle,
        "hit_count": len(hits),
        "hits": hits,
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out} hits={len(hits)}/{total}")
    for h in hits[:60]:
        print(f"{h['native_rva']} [{h['type_index']}] {h['full_name']} "
              f"uleb={h['read_uleb_calls']} str={h['read_string_calls']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
