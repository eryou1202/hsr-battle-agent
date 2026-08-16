#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the minimal Type -> Method -> Field member registry proof.

Inputs are the two machine access maps produced by
`analyze_mhy_method_candidate.py` and `analyze_mhy_field_candidate.py`, plus the
existing Type Registry proof (used only to pick already-found semantic type
samples; no new Battle DSL / RVA work is performed).

The output is deliberately a limited proof sample, not a full dump:

  * validation summary carried over from both access maps;
  * first 24 MethodDefinition identifier samples;
  * selected game types (DynamicValue / Ability / Mixin / Modifier / Predicate /
    Target / BattleEvent) with method names, parameter counts, field names and
    stable field type references.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1

RULES = {
    0x84: ("xor", 0x68531D3F),
    0x14C: ("add", 0xF3A04294),
    0x20: ("add", 0xB2FCE189),
    0x1B4: ("add", 0x8D43A4EE),
}

SEARCH_ORDER = ["DynamicValue", "Ability", "BattleEvent", "Mixin",
                "Modifier", "Predicate", "Target"]


def method_hash32(idx: int) -> int:
    x = ((idx * 0x31E1) & M64) ^ 0x33914937
    x = (x * 0x2C03F17D) & M64
    x >>= 0x17
    x = (x * 0x540CC9F4) & M64
    x >>= 0x15
    return (x + 0x71BC7861) & M32


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & M32
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def resolve_type_name(mm, tbase: int, ti: int, region: bytes) -> str:
    raw24 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x24)[0]
    raw28 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x28)[0]
    ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & M32, region)
    name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & M32, region)
    ns_s = ns.decode("utf-8", "replace")
    name_s = name.decode("utf-8", "replace")
    return f"{ns_s}.{name_s}" if ns_s else name_s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", help="GameAssembly.dll")
    ap.add_argument("--metadata", required=True, help="global-metadata.dat")
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--method-map", required=True)
    ap.add_argument("--field-map", required=True)
    ap.add_argument("--type-proof", required=True,
                    help="existing type_registry_proof JSON (semantic samples only)")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    method_map = json.load(open(args.method_map, encoding="utf-8"))
    field_map = json.load(open(args.field_map, encoding="utf-8"))
    type_proof = json.load(open(args.type_proof, encoding="utf-8"))

    pe = PeImage(Path(args.game))
    tpl_rva = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    block = pe.read_rva(tpl_rva, 0x208)
    offsets: dict[int, int] = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        offsets[field] = FILE_HEADER + signed32(decode_rule(raw, op, const))
    tbase = offsets[0x84]
    mbase = offsets[0x14C]
    fbase = offsets[0x20]
    region_base = offsets[0x1B4]

    # Collect already-found semantic type samples. Keep hit order stable and
    # unique; prefer the task's requested keyword order.
    search_hits = type_proof.get("semantic_sanity_search") or {}
    chosen: dict[int, dict] = {}
    for word in SEARCH_ORDER:
        for hit in search_hits.get(word, []):
            ti = int(hit["record_index"])
            chosen.setdefault(ti, {
                "type_index": ti,
                "name": hit["identifier"],
                "namespace": hit.get("namespace", ""),
            })

    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        size = Path(args.metadata).stat().st_size
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        type_members = []
        total_methods = 0
        total_fields = 0
        for ti in list(chosen.keys())[:16]:
            rec_off = tbase + ti * 70
            mstart = struct.unpack_from("<I", mm, rec_off + 0x08)[0]
            mstart = mstart ^ 0x1A7AF5FE
            mstart = mstart - 0x100000000 if mstart & 0x80000000 else mstart
            mcount = (struct.unpack_from("<H", mm, rec_off + 0x34)[0] + 0x5F93) & 0xFFFF
            fstart = (struct.unpack_from("<I", mm, rec_off + 0x20)[0]
                      + 0x8B7AC79C) & M32
            fcount = (struct.unpack_from("<H", mm, rec_off + 0x32)[0] + 0x444D) & 0xFFFF

            methods = []
            if mstart >= 0:
                for mi in range(mstart, min(mstart + mcount, mstart + 8)):
                    h = method_hash32(mi)
                    raw_name = struct.unpack_from("<I", mm, mbase + mi * 26)[0]
                    name_key = (h ^ raw_name ^ 0x0E714BC1) & M32
                    name, _ = resolve_identifier(name_key, region)
                    raw_pc = mm[mbase + mi * 26 + 0x18]
                    low = (h + 0x71BC7861) & 0xFF
                    pc = raw_pc ^ low ^ 0xA8
                    methods.append({
                        "method_index": mi,
                        "name": name.decode("utf-8", "replace"),
                        "parameter_count": int(pc),
                    })
                    total_methods += 1

            fields = []
            if fstart != M32:
                raw_fstart = struct.unpack_from("<I", mm, rec_off + 0x20)[0]
                roll0 = (0xAD416BB9 - (raw_fstart * 0x2C5DCB00 & M32)) & M32
                for fi in range(fstart, min(fstart + fcount, fstart + 8)):
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
                    total_fields += 1

            type_members.append({
                "type_index": ti,
                "namespace": chosen[ti]["namespace"],
                "name": chosen[ti]["name"],
                "full_name": (f"{chosen[ti]['namespace']}.{chosen[ti]['name']}"
                              if chosen[ti]["namespace"] else chosen[ti]["name"]),
                "method_start": int(mstart) if mstart >= 0 else -1,
                "method_count": int(mcount),
                "methods": methods,
                "field_start": int(fstart) if fstart != M32 else -1,
                "field_count": int(fcount),
                "fields": fields,
            })

        checks = {
            "method_table_confirmed": bool(method_map["validations"]["declaring_type_match"]["all_match"]
                                          and method_map["validations"]["method_partition"]["covered_exactly_once"]
                                          and method_map["validations"]["parameter_partition"]["covered_exactly_once"]),
            "field_table_confirmed": bool(field_map["validations"]["field_range"]["covered_exactly_once"]
                                          and field_map["validations"]["identifier_samples"]["all_checked_printable"]),
            "type_samples_resolved": bool(type_members),
        }
        status = ("MHY_METADATA = MEMBER_REGISTRY_PROOF"
                  if all(checks.values()) else "MHY_METADATA = MEMBER_SCHEMA_PARTIAL")

    proof = {
        "schema": "mhy_member_registry_proof/1",
        "status": status,
        "game": str(Path(args.game).resolve()),
        "metadata": str(Path(args.metadata).resolve()),
        "template_rva": f"0x{tpl_rva:X}",
        "registry": {
            "type_definition": {
                "table": "0x84 (entry_size 70)",
                "method_range": "+0x08 ^ 0x1A7AF5FE / +0x34 + 0x5F93",
                "field_range": "+0x20 + 0x8B7AC79C / +0x32 + 0x444D",
            },
            "method_definition": {
                "table": "0x14C (entry_size 26)",
                "name": "+0x00 -> 0x3C58D70 identifier resolver",
                "declaring_type_index": "+0x10",
                "parameter_start": "+0x04",
                "parameter_count": "+0x18",
                "return_type_reference": "+0x08",
            },
            "parameter_definition": {
                "table": "0x30 (entry_size 8)",
                "range_source": "MethodDefinition +0x04/+0x18",
                "name": "+0x04 -> 0x3C58D70 (all observed keys are 0xFFFFFFFF)",
                "type_reference": "+0x00",
            },
            "field_definition": {
                "table": "0x20 (entry_size 8)",
                "name": "+0x00 -> 0x3C58D70 identifier resolver",
                "type_reference": "+0x04 -> [runtime + 0x80] 16-byte type entries",
            },
        },
        "counts": {
            "type_records": int(method_map["type_range_source"]["rows_with_methods"]
                                + method_map["validations"]["method_partition"]["rows_without_methods"]),
            "methods": int(method_map["method_table"]["record_count"]),
            "parameters": int(method_map["validations"]["parameter_partition"]["parameter_total"]),
            "fields": int(field_map["field_table"]["record_count"]),
        },
        "validation_summary": {
            "method_partition_exact_once": method_map["validations"]["method_partition"]["covered_exactly_once"],
            "method_declaring_type_all_match": method_map["validations"]["declaring_type_match"]["all_match"],
            "parameter_partition_exact_once": method_map["validations"]["parameter_partition"]["covered_exactly_once"],
            "field_partition_exact_once": field_map["validations"]["field_range"]["covered_exactly_once"],
            "field_names_printable": field_map["validations"]["identifier_samples"]["all_checked_printable"],
        },
        "method_samples": method_map["method_registry_proof"]["samples"][:24],
        "field_samples": field_map["field_registry_proof"]["samples"][:24],
        "semantic_battle_sanity": type_members,
        "sample_totals": {
            "semantic_types": len(type_members),
            "methods": total_methods,
            "fields": total_fields,
        },
        "checks": checks,
        "not_claimed": [
            "MethodDefinition -> GameAssembly RVA mapping",
            "return type / field type semantic names",
            "parameter names (observed sentinel-only)",
            "Image / Assembly recovery",
            "Battle DSL / ability logic / Black Swan analysis",
        ],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(proof, f, indent=2)
    print(f"wrote {out}")
    print(f"status={status}")
    print(f"methods={proof['counts']['methods']} parameters={proof['counts']['parameters']} "
          f"fields={proof['counts']['fields']}")
    for tm in type_members:
        print(f"  {tm['full_name']}: methods={len(tm['methods'])} fields={len(tm['fields'])}")
        for m in tm["methods"]:
            print(f"    M {m['name']}({m['parameter_count']})")
        for fd in tm["fields"]:
            print(f"    F {fd['name']} -> {fd['type_reference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
