#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List recovered types that declare a method with a requested name.

Used to enumerate generated deserializer families (FromBinary,
FromBinaryWithoutNew, obfuscated OJNNBEJLDIJ, ...). Metadata names only;
no semantic mapping is claimed.
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
from build_method_code_registry import (  # noqa: E402
    M32,
    scalar_method_hash32,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

FIELD_NAME_CONST = 0x0E714BC1


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & M32
    return raw ^ const


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--method-name", action="append", required=True)
    ap.add_argument("--type-substr", default=None)
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
    mbase = offs[0x14C]
    mnext = offs[0x160]
    ntypes = (tnext - tbase) // 70
    nmethods = (mnext - mbase) // 26
    region_base = offs[0x1B4]
    wanted = set(args.method_name)

    def type_name(mm, ti, region):
        raw24 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x24)[0]
        raw28 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x28)[0]
        ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & M32, region)
        name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & M32, region)
        ns_s = ns.decode("utf-8", "replace")
        name_s = name.decode("utf-8", "replace")
        return f"{ns_s}.{name_s}" if ns_s else name_s

    hits = {}
    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]
        for mi in range(nmethods):
            h32 = scalar_method_hash32(mi)
            raw_name = struct.unpack_from("<I", mm, mbase + mi * 26)[0]
            name_key = (h32 ^ raw_name ^ FIELD_NAME_CONST) & M32
            name, _ = resolve_identifier(name_key, region)
            name_s = name.decode("utf-8", "replace")
            if name_s not in wanted:
                continue
            raw_decl = struct.unpack_from("<I", mm, mbase + mi * 26 + 0x10)[0]
            ti = (h32 ^ raw_decl ^ 0x2A5FABE8) & M32
            full = type_name(mm, ti, region)
            if args.type_substr and args.type_substr.lower() not in full.lower():
                continue
            hits.setdefault(ti, {"type_index": ti, "full_name": full,
                                 "methods": []})
            hits[ti]["methods"].append({"method_index": mi, "name": name_s})
        mm.close()

    rows = [v for _, v in sorted(hits.items())]
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["type_index", "full_name",
                                               "method_indices", "method_names"])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "type_index": r["type_index"],
                "full_name": r["full_name"],
                "method_indices": "|".join(str(m["method_index"]) for m in r["methods"]),
                "method_names": "|".join(m["name"] for m in r["methods"]),
            })
    print(f"wrote {out} types={len(rows)}")
    for r in rows[:200]:
        print(f"[{r['type_index']}] {r['full_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
