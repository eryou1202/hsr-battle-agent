#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List recovered fields whose decoded name matches a substring."""
from __future__ import annotations

import argparse
import csv
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
from analyze_mhy_field_candidate import RULES  # noqa: E402
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

M32 = 0xFFFFFFFF


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & M32
    return raw ^ const


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--field-substr", action="append", required=True)
    ap.add_argument("--limit-per-needle", type=int, default=200)
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    pe = PeImage(args.game)
    tpl = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    block = pe.read_rva(tpl, 0x208)
    offs = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        offs[field] = FILE_HEADER + signed32(decode_rule(raw, op, const))
    tbase = offs[0x84]
    tnext = offs[0x38]
    fbase = offs[0x20]
    ntypes = (tnext - tbase) // 70
    region_base = offs[0x1B4]

    def type_name(mm, ti, region):
        raw24 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x24)[0]
        raw28 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x28)[0]
        ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & M32, region)
        name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & M32, region)
        ns_s = ns.decode("utf-8", "replace")
        name_s = name.decode("utf-8", "replace")
        return f"{ns_s}.{name_s}" if ns_s else name_s

    hits = {s.lower(): [] for s in args.field_substr}
    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        for ti in range(ntypes):
            rec_off = tbase + ti * 70
            raw_fstart = struct.unpack_from("<I", mm, rec_off + 0x20)[0]
            fstart = (raw_fstart + 0x8B7AC79C) & M32
            fcount = (struct.unpack_from("<H", mm, rec_off + 0x32)[0] + 0x444D) & 0xFFFF
            if fstart >= 0x80000000 or fcount == 0:
                continue
            roll0 = (0xAD416BB9 - (raw_fstart * 0x2C5DCB00 & M32)) & M32
            full = type_name(mm, ti, region)
            for fi in range(fstart, fstart + fcount):
                local = fi - fstart
                roll = (roll0 + local * 0xD3A23500) & M32
                raw_name, raw_type = struct.unpack_from("<II", mm, fbase + fi * 8)
                name_key = (raw_name + roll + 0x2AAFC785) & M32
                name, _ = resolve_identifier(name_key, region)
                name_s = name.decode("utf-8", "replace")
                low = name_s.lower()
                for needle, rows in hits.items():
                    if needle in low and len(rows) < args.limit_per_needle:
                        type_ref = (raw_type + roll) & M32
                        if type_ref >= 0x80000000:
                            type_ref -= 0x100000000
                        rows.append({
                            "declaring_type_index": ti,
                            "declaring_type": full,
                            "field_index": fi,
                            "field_name": name_s,
                            "type_reference": int(type_ref),
                        })
        mm.close()

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["needle", "declaring_type_index", "declaring_type",
                         "field_index", "field_name", "type_reference"])
        for needle, rows in hits.items():
            for r in rows:
                writer.writerow([needle, r["declaring_type_index"],
                                 r["declaring_type"], r["field_index"],
                                 r["field_name"], r["type_reference"]])
    print(f"wrote {out}")
    for needle, rows in hits.items():
        print(f"== {needle}: {len(rows)}")
        for r in rows[:40]:
            print(f"  [{r['declaring_type_index']}] {r['declaring_type']}.{r['field_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
