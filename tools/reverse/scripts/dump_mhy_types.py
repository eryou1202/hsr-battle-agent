#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump the full recovered TypeDefinition name table as CSV/JSON.

Names are decoded with the CONFIRMED 0x3C58D70 identifier resolver. This is a
machine index, not a semantic mapping.
"""
from __future__ import annotations

import argparse
import csv
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
from analyze_mhy_method_candidate import RULES  # noqa: E402
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
    ntypes = (tnext - tbase) // 70
    region_base = offs[0x1B4]
    size = args.metadata.stat().st_size

    rows = []
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        for ti in range(ntypes):
            rec_off = tbase + ti * 70
            raw24 = struct.unpack_from("<I", mm, rec_off + 0x24)[0]
            raw28 = struct.unpack_from("<I", mm, rec_off + 0x28)[0]
            ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & M32, region)
            name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & M32, region)
            mstart = (struct.unpack_from("<I", mm, rec_off + 0x08)[0]
                      ^ 0x1A7AF5FE) & M32
            mstart = mstart - 0x100000000 if mstart & 0x80000000 else mstart
            mcount = (struct.unpack_from("<H", mm, rec_off + 0x34)[0] + 0x5F93) & 0xFFFF
            rows.append({
                "type_index": ti,
                "namespace": ns.decode("utf-8", "replace"),
                "name": name.decode("utf-8", "replace"),
                "full_name": (f"{ns.decode('utf-8', 'replace')}."
                              f"{name.decode('utf-8', 'replace')}"
                              if ns else name.decode("utf-8", "replace")),
                "method_start": int(mstart),
                "method_count": int(mcount),
            })
        mm.close()

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out} types={ntypes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
