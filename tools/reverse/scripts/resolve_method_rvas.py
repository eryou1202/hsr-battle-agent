#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reverse-lookup native RVAs in the recovered method code registry.

Given one or more native RVAs, scan `code_table` (method_index -> qword RVA,
already CONFIRMED by METHOD_CODE = RVA_REGISTRY_PROOF) and decode the owning
MethodDefinition names from global-metadata.dat. This is the automatic
"native address -> metadata method" connector used by the bridge work.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--rva", type=lambda x: int(x, 0), action="append", required=True)
    ap.add_argument("--containing-rva", type=lambda x: int(x, 0), action="append", default=[])
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    pe = PeImage(args.game)
    tpl = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    offs = table_offsets(pe, tpl)
    tbase = offs[0x84]
    tnext = offs[0x38]
    mbase = offs[0x14C]
    mnext = offs[0x160]
    ntypes = (tnext - tbase) // 70
    nmethods = (mnext - mbase) // 26
    region_base = offs[0x1B4]

    targets = {int(r) & 0xFFFFFFFF for r in args.rva}
    containing_targets = sorted({int(r) & 0xFFFFFFFF for r in args.containing_rva})
    containing_hits: dict[int, list[dict]] = {r: [] for r in containing_targets}
    entries: list[tuple[int, int, str]] = []  # (native_rva, method_index, name)
    hits: dict[int, list[dict]] = {}
    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        for mi in range(nmethods):
            raw = pe.read_rva(args.code_table_rva + mi * 8, 8)
            q = struct.unpack("<Q", raw)[0]
            if not q:
                continue
            rva = q - pe.image_base
            name = decode_method_name(mm, mbase, mi, region)
            entries.append((rva, mi, name))
            if rva in targets:
                declaring = decode_declaring_type(mm, mbase, mi)
                row = {
                    "method_index": mi,
                    "native_rva": f"0x{rva:X}",
                    "name": decode_method_name(mm, mbase, mi, region),
                    "declaring_type_index": declaring,
                    "declaring_type": resolve_type_name(mm, tbase, declaring, region),
                }
                hits.setdefault(rva, []).append(row)
        for target in containing_targets:
            if not entries:
                continue
            # Entries are appended in method-index order; native RVAs are not
            # guaranteed sorted, so find the closest entry <= target with
            # largest native_rva.
            best = None
            for rva, mi, name in entries:
                if rva <= target and (best is None or rva > best[0]):
                    best = (rva, mi, name)
            if best is not None:
                rva, mi, name = best
                declaring = decode_declaring_type(mm, mbase, mi)
                containing_hits[target].append({
                    "containing_method_index": mi,
                    "containing_method_native_rva": f"0x{rva:X}",
                    "offset_from_entry": target - rva,
                    "containing_method_name": name,
                    "declaring_type_index": declaring,
                    "declaring_type": resolve_type_name(mm, tbase, declaring, region),
                })
        mm.close()

    result = {
        "schema": "mhy_method_rva_reverse_lookup/1",
        "game": str(args.game.resolve()),
        "metadata": str(args.metadata.resolve()),
        "template_rva": f"0x{tpl:X}",
        "code_table_rva": f"0x{args.code_table_rva:X}",
        "lookups": [
            {
                "rva": f"0x{r:X}",
                "matches": hits.get(r, []),
            }
            for r in sorted(targets)
        ],
        "containing_lookups": [
            {
                "rva": f"0x{r:X}",
                "matches": containing_hits.get(r, []),
            }
            for r in containing_targets
        ],
        "unmatched": [f"0x{r:X}" for r in sorted(targets) if r not in hits],
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    for r, rows in hits.items():
        print(f"0x{r:X}:")
        for row in rows:
            print(f"  method_index={row['method_index']} "
                  f"{row['declaring_type']}.{row['name']}")
    for r, rows in containing_hits.items():
        print(f"containing 0x{r:X}:")
        for row in rows:
            print(f"  method_index={row['containing_method_index']} "
                  f"{row['declaring_type']}.{row['containing_method_name']} "
                  f"offset=+0x{row['offset_from_entry']:X}")
    for r in sorted(targets):
        if r not in hits:
            print(f"0x{r:X}: UNMATCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
