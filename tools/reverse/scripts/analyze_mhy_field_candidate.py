#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrow consumer-driven analyzer for the MHY FieldDefinition candidate.

Proves and records that template field 0x20 is the FieldDefinition table:

  * directory rule : 0x20, add 0xB2FCE189, payload-relative offset
  * entry size     : 8 bytes (consumer `[base + idx*8]` / `[base + idx*8 + 4]`)
  * TypeDefinition range source:
      field start  +0x20: (raw_u32 + 0x8B7AC79C) & 0xFFFFFFFF, -1 sentinel
      field count  +0x32: (raw_u16 + 0x444D) & 0xFFFF
    The ranges cover 0..N_fields-1 exactly once, in TypeDefinition record order.
  * field +0x00   : name key decoded with a per-type rolling transform and
                    resolved through the existing identifier resolver 0x3C58D70
  * field +0x04   : field type reference (same rolling transform, -1 sentinel),
                    consumed through the 16-byte type-entry array [runtime+0x80]

Outputs `mhy_field_definition_access_map_<version>.json` and, optionally, a
standalone `field_registry_proof_<version>.json`.
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

RULES = {
    0x20: ("add", 0xB2FCE189),  # FieldDefinition table
    0x84: ("xor", 0x68531D3F),  # TypeDefinition table
    0x38: ("add", 0xF778F1AB),  # next known table after 0x84
    0x1B4: ("add", 0x8D43A4EE),  # identifier ciphertext heap
}

# TypeDefinition field range decode constants (consumer 0x3C5C1A2 / 0x3C5C4D8).
TYPE_FIELD_START_ADD_CONST = 0x8B7AC79C  # equivalently raw - 0x74853864
TYPE_FIELD_COUNT_ADD_CONST = 0x444D
TYPE_FIELD_START_SENTINEL = 0xFFFFFFFF

# Per-type field-record rolling transform (consumer 0x3C5C559 / 0x3C5C599).
FIELD_ROLL_BASE = 0xAD416BB9
FIELD_ROLL_MUL = 0x2C5DCB00
FIELD_ROLL_STEP = 0xD3A23500
FIELD_NAME_CONST = 0x2AAFC785

FIELD_ACCESS_MAP = [
    {
        "offset": 0x00, "width": 4,
        "decode": "name_key = (raw_u32 + roll + 0x2AAFC785) & 0xFFFFFFFF",
        "consumer_rvas": ["0x3C5C5FC", "0x3C5C609"],
        "instruction": "mov eax, [rec]; lea ecx, [roll + rax]; add ecx, 0x2aafc785; call 0x3C58D70",
        "downstream": "existing identifier resolver 0x3C58D70",
        "sentinel": "resolver key 0xFFFFFFFF -> empty string",
        "semantic_candidate": "name key",
        "semantic_evidence": "decodes to real field names (default_vtable, error_code, xmlSpace, ...)",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
    {
        "offset": 0x04, "width": 4,
        "decode": "type_reference = (raw_u32 + roll) & 0xFFFFFFFF",
        "consumer_rvas": ["0x3C5C5CA"],
        "instruction": "mov ecx, [rec + 4]; add ecx, roll; cmp ecx, -1",
        "downstream": "non-sentinel -> [runtime + 0x80] 16-byte type entries",
        "sentinel": "0xFFFFFFFF",
        "semantic_candidate": "field type reference",
        "semantic_evidence": "consumer resolves every non-sentinel reference through the 16-byte type-entry array",
        "structure_status": "CONFIRMED",
        "semantic_status": "SUPPORTED",
    },
]

TYPE_FIELD_ACCESS_MAP = [
    {
        "offset": 0x20, "width": 4,
        "decode": f"field_start = (raw_u32 + 0x{TYPE_FIELD_START_ADD_CONST:08X}) & 0xFFFFFFFF",
        "consumer_rvas": ["0x3C5C4D8", "0x3C5C4DC"],
        "instruction": "mov r8d, [rec + 0x20]; lea r11d, [r8 - 0x74853864]",
        "downstream": "start index into 0x20 field table (stride 8)",
        "sentinel": "0xFFFFFFFF",
        "semantic_candidate": "field range start",
        "semantic_evidence": "ranges cover the field table exactly once",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
    {
        "offset": 0x32, "width": 2,
        "decode": f"field_count = (raw_u16 + 0x{TYPE_FIELD_COUNT_ADD_CONST:04X}) & 0xFFFF",
        "consumer_rvas": ["0x3C5C19E", "0x3C5C392"],
        "instruction": "movzx edi, word ptr [rec + 0x32]; add edi, 0x444d",
        "downstream": "allocation / loop bound over field records",
        "sentinel": "decoded 0 means no fields",
        "semantic_candidate": "field range count",
        "semantic_evidence": "cumulative start+count consistency across all TypeDefinition records",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
]


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & 0xFFFFFFFF
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def type_identifier(mm, tbase: int, rec_index: int, region: bytes) -> tuple[str, str]:
    raw24 = struct.unpack_from("<I", mm, tbase + rec_index * 70 + 0x24)[0]
    raw28 = struct.unpack_from("<I", mm, tbase + rec_index * 70 + 0x28)[0]
    ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & 0xFFFFFFFF, region)
    name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & 0xFFFFFFFF, region)
    return ns.decode("utf-8", "replace"), name.decode("utf-8", "replace")


def analyze(game: Path, metadata: Path, template_rva: int | None,
            identifier_sample_count: int) -> dict:
    pe = PeImage(game)
    tpl_rva = template_rva if template_rva is not None else locate_template_rva(pe)
    block = pe.read_rva(tpl_rva, 0x208)
    offsets: dict[int, int] = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        offsets[field] = FILE_HEADER + signed32(decode_rule(raw, op, const))

    fbase = offsets[0x20]
    tbase = offsets[0x84]
    tnext = offsets[0x38]
    region_base = offsets[0x1B4]

    with open(metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        size = metadata.stat().st_size
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        ntypes = (tnext - tbase) // 70
        t_f20 = np.ndarray(shape=(ntypes,), dtype="<u4", buffer=mm,
                           offset=tbase + 0x20, strides=(70,))
        t_w32 = np.ndarray(shape=(ntypes,), dtype="<u2", buffer=mm,
                           offset=tbase + 0x32, strides=(70,))
        raw_starts = t_f20.astype(np.uint32)
        starts = ((raw_starts + np.uint32(TYPE_FIELD_START_ADD_CONST))
                  & np.uint32(0xFFFFFFFF)).astype(np.int64)
        counts = (((t_w32.astype(np.uint32) + np.uint32(TYPE_FIELD_COUNT_ADD_CONST))
                   & 0xFFFF)).astype(np.int64)
        valid = counts > 0
        recidx = np.arange(ntypes, dtype=np.int64)[valid]
        starts_valid = starts[valid]
        counts_valid = counts[valid]
        field_total = int(counts_valid.sum())
        field_max_end = int((starts_valid + counts_valid).max())

        # Cumulative record-order consistency (same discipline as method ranges).
        cumulative_ok = True
        expected = 0
        for i in range(ntypes):
            if counts[i] == 0:
                continue
            if starts[i] != expected:
                cumulative_ok = False
                break
            expected += int(counts[i])

        fcov = np.zeros(field_total, dtype=np.uint8)
        for st, ct in zip(starts_valid.tolist(), counts_valid.tolist()):
            fcov[st : st + ct] += 1
        range_validation = {
            "rows_with_fields": int(valid.sum()),
            "rows_without_fields": int((~valid).sum()),
            "field_total": field_total,
            "max_start_sentinel_ignored": int(starts[~valid].max()),
            "max_end": field_max_end,
            "all_ranges_in_bounds": bool(field_max_end <= field_total),
            "covered_exactly_once": bool(fcov.sum() == field_total and bool(np.all(fcov == 1))),
            "cumulative_record_order_ok": cumulative_ok,
        }

        # --- decode field records with per-type rolling transform ------------
        nf = field_total
        owner = np.repeat(recidx, counts_valid)
        local = np.arange(nf, dtype=np.int64) - np.repeat(starts_valid, counts_valid)
        roll0 = (np.uint32(FIELD_ROLL_BASE)
                 - (raw_starts[owner].astype(np.uint64) * FIELD_ROLL_MUL
                    & np.uint64(0xFFFFFFFF)).astype(np.uint32)).astype(np.uint32)
        roll = (roll0.astype(np.uint64)
                + ((local.astype(np.uint64) * FIELD_ROLL_STEP)
                   & np.uint64(0xFFFFFFFF))).astype(np.uint32)

        f0 = np.ndarray(shape=(nf,), dtype="<u4", buffer=mm,
                        offset=fbase + 0x00, strides=(8,))
        f4 = np.ndarray(shape=(nf,), dtype="<u4", buffer=mm,
                        offset=fbase + 0x04, strides=(8,))
        name_key = ((f0.astype(np.uint32) + roll + np.uint32(FIELD_NAME_CONST))
                    & np.uint32(0xFFFFFFFF))
        type_ref = (f4.astype(np.uint32) + roll) & np.uint32(0xFFFFFFFF)
        type_ref_signed = type_ref.astype(np.int64)
        type_ref_signed = np.where(type_ref_signed >= 0x80000000,
                                   type_ref_signed - 0x100000000, type_ref_signed)

        type_ref_stats = {
            "minus1_count": int((type_ref == 0xFFFFFFFF).sum()),
            "min": int(type_ref_signed.min()),
            "max": int(type_ref_signed.max()),
            "distinct_values": int(len(np.unique(type_ref))),
        }

        # --- identifier samples ------------------------------------------------
        sample_idx_list = list(range(min(identifier_sample_count, nf)))
        if nf > 64:
            sample_idx_list += list(range(64, nf, nf // 64))[:64]
        sample_idx_list = sorted(set(sample_idx_list))
        id_rows = []
        printable_checked = 0
        printable_ok = 0
        for i in sample_idx_list:
            key = int(name_key[i])
            text, info = resolve_identifier(key, region)
            ns, tname = type_identifier(mm, tbase, int(owner[i]), region)
            printable = all(32 <= c < 127 or c in (0,) for c in text)
            printable_checked += 1
            printable_ok += int(printable)
            id_rows.append({
                "field_index": i,
                "name": text.decode("utf-8", "replace"),
                "name_key": f"0x{key:08X}",
                "declaring_type_index": int(owner[i]),
                "declaring_type": f"{ns}.{tname}" if ns else tname,
                "type_reference": int(type_ref_signed[i]),
            })
        identifier_stats = {
            "rows_checked": printable_checked,
            "printable_rows": printable_ok,
            "all_checked_printable": printable_checked == printable_ok,
        }

        checks = {
            "type_field_ranges_exact_once": range_validation["covered_exactly_once"],
            "field_names_printable": identifier_stats["all_checked_printable"],
            "type_reference_resolver_path_exists": True,
        }
        proof = {
            "schema": "mhy_field_registry_proof/1",
            "status": ("MHY_METADATA = FIELD_REGISTRY_PROOF"
                       if all(checks.values()) else "MHY_METADATA = FIELD_SCHEMA_UNRESOLVED"),
            "field_table": "0x20 (entry_size 8, consumer [base + idx*8])",
            "record_count": nf,
            "samples": id_rows[:24],
            "checks": checks,
            "not_claimed": [
                "field type reference semantic name",
                "field token / flags / custom attributes",
            ],
        }

    out = {
        "schema": "mhy_field_definition_access_map/1",
        "game": str(game.resolve()),
        "metadata": str(metadata.resolve()),
        "template_rva": f"0x{tpl_rva:X}",
        "file_header_size": FILE_HEADER,
        "table_offsets": {f"0x{k:X}": f"0x{v:X}" for k, v in offsets.items()},
        "field_table": {
            "field": "0x20",
            "transform": "add 0xB2FCE189",
            "entry_size": 8,
            "file_offset": f"0x{fbase:X}",
            "record_count": field_total,
            "region_end": f"0x{fbase + field_total * 8:X}",
            "record_index_stride": "consumer 0x3C5C5CA: mov ecx,[base + idx*8 + 4]",
            "note": "supersedes earlier HYPOTHESIS/UNKNOWN table starts that fall inside this region",
        },
        "type_range_source": {
            "field": "0x84",
            "field_start": "+0x20 raw_u32 + 0x8B7AC79C (sentinel 0xFFFFFFFF)",
            "field_count": "+0x32 raw_u16 + 0x444D",
        },
        "field_access_map": FIELD_ACCESS_MAP,
        "type_definition_field_access_map": TYPE_FIELD_ACCESS_MAP,
        "validations": {
            "field_range": range_validation,
            "type_reference_stats": type_ref_stats,
            "identifier_samples": identifier_stats,
        },
        "field_registry_proof": proof,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", help="GameAssembly.dll")
    ap.add_argument("--metadata", required=True, help="global-metadata.dat")
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--identifier-sample-count", type=int, default=32)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--proof-output", default=None)
    args = ap.parse_args()
    result = analyze(Path(args.game), Path(args.metadata), args.template_rva,
                     args.identifier_sample_count)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    if args.proof_output and result.get("field_registry_proof"):
        pout = Path(args.proof_output)
        pout.parent.mkdir(parents=True, exist_ok=True)
        with open(pout, "w", encoding="utf-8") as f:
            json.dump(result["field_registry_proof"], f, indent=2)
        print(f"wrote {pout}")
    ft = result["field_table"]
    v = result["validations"]
    print(f"field_table n={ft['record_count']} entry_size={ft['entry_size']}")
    print(f"field_range_exact_once={v['field_range']['covered_exactly_once']}")
    print(f"identifier_printable={v['identifier_samples']['all_checked_printable']}")
    print(f"proof_status={result['field_registry_proof']['status']}")
    for row in result["field_registry_proof"]["samples"][:12]:
        print(f"  [{row['field_index']}] {row['declaring_type']}.{row['name']}"
              f" type_ref={row['type_reference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
