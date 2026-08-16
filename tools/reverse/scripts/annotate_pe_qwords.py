#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Annotate qwords in a PE region with method metadata / section targets."""
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
from analyze_mhy_method_candidate import RULES  # noqa: E402
from build_method_code_registry import (  # noqa: E402
    M32,
    decode_declaring_type,
    decode_method_name,
    resolve_type_name,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--count", type=lambda x: int(x, 0), default=64)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    pe = PeImage(args.game)
    tpl = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    block = pe.read_rva(tpl, 0x208)
    offs = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        if op == "add":
            val = (raw + const) & M32
        else:
            val = raw ^ const
        offs[field] = FILE_HEADER + signed32(val)
    tbase = offs[0x84]
    tnext = offs[0x38]
    mbase = offs[0x14C]
    mnext = offs[0x160]
    nmethods = (mnext - mbase) // 26
    region_base = offs[0x1B4]

    # method RVA -> method_index map from the code table
    by_rva: dict[int, int] = {}
    raw_table = pe.read_rva(args.code_table_rva, nmethods * 8)
    for i in range(nmethods):
        q = struct.unpack_from("<Q", raw_table, i * 8)[0]
        if q:
            by_rva.setdefault(q - pe.image_base, i)

    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        rows = []
        raw_region = pe.read_rva(args.rva, args.count * 8)
        for i in range(args.count):
            q = struct.unpack_from("<Q", raw_region, i * 8)[0]
            rva = args.rva + i * 8
            row = {"rva": f"0x{rva:X}", "qword": f"0x{q:X}", "method": None,
                   "section": None}
            if q:
                trva = q - pe.image_base
                sec = pe.section_at_rva(trva)
                if sec is not None:
                    row["section"] = sec.name
                mi = by_rva.get(trva)
                if mi is not None:
                    declaring = decode_declaring_type(mm, mbase, mi)
                    row["method"] = {
                        "method_index": mi,
                        "name": decode_method_name(mm, mbase, mi, region),
                        "declaring_type_index": declaring,
                        "declaring_type": resolve_type_name(mm, tbase, declaring, region),
                    }
            rows.append(row)
            if row["method"]:
                m = row["method"]
                print(f"{row['rva']}: {row['qword']} -> "
                      f"[{m['declaring_type']}.{m['name']}]")
            else:
                print(f"{row['rva']}: {row['qword']} -> {row['section']}")
        mm.close()

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"schema": "mhy_qword_annotation/1",
                   "region_rva": f"0x{args.rva:X}", "count": args.count,
                   "rows": rows}, f, indent=2)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
