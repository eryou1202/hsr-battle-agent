#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Query recovered MHY metadata for DesignData deserializer bridge candidates.

Inputs:
  * GameAssembly.dll + global-metadata.dat (one version at a time)
  * already-recovered template RVA and method code table RVA

Outputs a compact JSON report:
  * type-name candidate distribution for Ability / Mixin / ConfigAbility /
    FromBinary-style row types;
  * method-name distribution for FromBinary / FromBinaryWithoutNew /
    FromTableOffset / Deserialize / Create / Factory / Registry;
  * every matched method automatically joined to the method code registry
    (native RVA), and the full list of candidate records.

This tool only reports metadata candidates. It does NOT claim any mapping;
mapping must be proven by code/dataflow evidence elsewhere.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
import sys
from collections import Counter
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
    scalar_method_hash32,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

TYPE_NEEDLES = (
    "ability",
    "mixin",
    "configability",
    "battleevent",
    "dynamicvalue",
    "predicate",
    "targetselector",
    "modifier",
    "serializ",
    "design",
)
METHOD_NEEDLES = (
    "frombinary",
    "frombinarywithoutnew",
    "fromtableoffset",
    "deserialize",
    "fromtable",
    "frombinarybuffer",
    "create",
    "factory",
    "registry",
    "parse",
)


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & M32
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    out: dict[int, int] = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        out[field] = FILE_HEADER + signed32(decode_rule(raw, op, const))
    return out


def read_code_entry(pe: PeImage, table_rva: int, method_index: int) -> int:
    raw = pe.read_rva(table_rva + method_index * 8, 8)
    return struct.unpack("<Q", raw)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), default=None)
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
    region_base = offs[0x1B4]
    ntypes = (tnext - tbase) // 70
    nmethods = (mnext - mbase) // 26

    type_rows = []
    type_hits: dict[str, list[dict]] = {n: [] for n in TYPE_NEEDLES}
    method_hits: dict[str, list[dict]] = {n: [] for n in METHOD_NEEDLES}
    name_counter: Counter[str] = Counter()

    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        for ti in range(ntypes):
            full = resolve_type_name(mm, tbase, ti, region)
            low = full.lower()
            type_rows.append({"type_index": ti, "full_name": full})
            for needle in TYPE_NEEDLES:
                if needle in low and len(type_hits[needle]) < 400:
                    type_hits[needle].append({"type_index": ti, "full_name": full})

        for mi in range(nmethods):
            name = decode_method_name(mm, mbase, mi, region)
            low = name.lower()
            if low in ("frombinary", "frombinarywithoutnew", "fromtableoffset",
                       "deserialize", "parse", "create", "factory"):
                declaring = decode_declaring_type(mm, mbase, mi)
                declaring_name = resolve_type_name(mm, tbase, declaring, region)
                row = {
                    "method_index": mi,
                    "name": name,
                    "declaring_type_index": declaring,
                    "declaring_type": declaring_name,
                }
                if args.code_table_rva is not None:
                    q = read_code_entry(pe, args.code_table_rva, mi)
                    row["native_rva"] = (
                        f"0x{q - pe.image_base:X}" if q else None)
                name_counter[row["name"]] += 1
                for needle in METHOD_NEEDLES:
                    if needle in low and len(method_hits[needle]) < 10000:
                        method_hits[needle].append(row)
        mm.close()

    # Trim method hit lists to the most common declaring types for display.
    distributions = {}
    for needle, rows in method_hits.items():
        dist = Counter(r["declaring_type"] for r in rows)
        distributions[needle] = {
            "matched": sum(dist.values()),
            "distinct_declaring_types": len(dist),
            "top_declaring_types": [
                {"declaring_type": k, "count": v}
                for k, v in dist.most_common(25)
            ],
        }

    result = {
        "schema": "mhy_bridge_candidate_query/1",
        "game_version": args.version,
        "game": str(args.game.resolve()),
        "metadata": str(args.metadata.resolve()),
        "template_rva": f"0x{tpl:X}",
        "code_table_rva": (f"0x{args.code_table_rva:X}"
                           if args.code_table_rva is not None else None),
        "counts": {
            "types": ntypes,
            "methods": nmethods,
        },
        "type_hits": type_hits,
        "method_hits": {k: v for k, v in method_hits.items() if v},
        "method_distributions": distributions,
    }

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    print(f"types={ntypes} methods={nmethods}")
    for needle in TYPE_NEEDLES:
        rows = type_hits[needle]
        if rows:
            print(f"TYPE {needle}: {len(rows)} shown")
            for row in rows[:12]:
                print(f"  [{row['type_index']}] {row['full_name']}")
    for needle in METHOD_NEEDLES:
        dist = distributions.get(needle)
        if dist and dist["matched"]:
            print(f"METHOD {needle}: matched={dist['matched']} "
                  f"declaring={dist['distinct_declaring_types']}")
            for row in dist["top_declaring_types"][:8]:
                print(f"  {row['declaring_type']}: {row['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
