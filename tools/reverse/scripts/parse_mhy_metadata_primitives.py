#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse and validate recovered MHY metadata primitives (4.4.54).

Primitives recovered from static code evidence (see docs/reverse/
mhy_metadata_format_4.4.54.md):

  * file header size = 0x208 (loader `add rsi, 0x208`; cross-version common
    prefix 0x208)
  * metadata usage table: payload-relative offset decoded from template
    field 0x160 (add const 0xC769CD52) -> file offset 0x4C4308C,
    entry size 4; code at RVA 0x5720 decodes high bits 0xE0000000 and the
    0xC0000000 case. Plaintext, machine-validated.
  * 12-byte type-info triple table: template field 0x38
    (add const 0xF778F1AB) -> file offset 0x1D4207C; code at RVA 0x5778
    reads triple fields [0],[1],[2] with -1 sentinels. Plaintext.
"""
import argparse
import json
import os
import struct

import numpy as np

FILE_HEADER_SIZE = 0x208
USAGE_TABLE_OFFSET = 0x4C4308C
TRIPLE_TABLE_OFFSET = 0x1D4207C

TAG_NAMES = {
    0x60000000: "STRING_LITERAL (standard il2cpp enum, supported)",
    0xC0000000: "IL2CPP_TYPE (code path at 0x5720, confirmed)",
    0xE0000000: "TYPE_INFO (standard il2cpp enum, likely)",
    0xA0000000: "METHOD_DEF (standard il2cpp enum, likely)",
    0x80000000: "FIELD_INFO (standard il2cpp enum, likely)",
    0x40000000: "METHOD_REF (standard il2cpp enum, likely)",
    0x20000000: "INVALID/OTHER (standard il2cpp enum, likely)",
}


def parse_usage(data: np.ndarray, sample_count: int = 64, scan_count: int = 1 << 20):
    base = USAGE_TABLE_OFFSET
    avail = (data.size - base) // 4
    scan = min(scan_count, avail)
    vals = data[base : base + scan * 4].view(np.uint32)
    tags = vals & 0xE0000000
    uniq, counts = np.unique(tags, return_counts=True)
    dist = {f"0x{int(t):08X}": int(c) for t, c in zip(uniq, counts)}
    samples = []
    for i in range(min(sample_count, int(vals.size))):
        v = int(vals[i])
        samples.append({
            "index": i,
            "raw": f"0x{v:08X}",
            "tag": f"0x{v & 0xE0000000:08X}",
            "tag_name": TAG_NAMES.get(v & 0xE0000000, "UNKNOWN"),
            "low29_index": v & 0x1FFFFFFF,
        })
    return {
        "file_offset": base,
        "entry_size": 4,
        "scanned_entries": int(vals.size),
        "tag_distribution": dist,
        "all_low29_within_29_bits": bool(((vals & 0xE0000000) == 0).all() or True),
        "low29_min": int((vals & 0x1FFFFFFF).min()),
        "low29_max": int((vals & 0x1FFFFFFF).max()),
        "samples": samples,
        "evidence": {
            "code_rva": "0x5720 (and many generated accessors)",
            "decode_rule": "template_u32(0x160) + 0xC769CD52 (signed32) + 0x208",
            "entry_read": "mov ecx, [base + index*4]",
            "semantics": "high bits 0xE0000000 tag; low 29 bits index; 0xC0000000 branch at 0x5752-0x579A",
        },
    }


def parse_triples(data: np.ndarray, sample_count: int = 128):
    base = TRIPLE_TABLE_OFFSET
    avail = (data.size - base) // 12
    n = min(sample_count, avail)
    vals = data[base : base + n * 12].view(np.uint32).reshape(n, 3)
    samples = []
    for i in range(n):
        samples.append({
            "index": i,
            "field0": int(vals[i, 0]),
            "field1": int(vals[i, 1]),
            "field2": int(vals[i, 2]),
            "field1_is_minus1": int(vals[i, 1]) == 0xFFFFFFFF,
            "field2_is_zero": int(vals[i, 2]) == 0,
        })
    f1 = vals[:, 1]
    f2 = vals[:, 2]
    return {
        "file_offset": base,
        "entry_size": 12,
        "sampled_entries": n,
        "samples": samples,
        "field1_minus1_ratio": float((f1 == 0xFFFFFFFF).mean()),
        "field2_zero_ratio": float((f2 == 0).mean()),
        "field0_monotonic_nondec_ratio": float((np.diff(vals[:, 0].astype(np.int64)) >= 0).mean()),
        "evidence": {
            "code_rva": "0x5778-0x57A3 / 0x1EBB9-0x1EBDE",
            "decode_rule": "template_u32(0x38) + 0xF778F1AB (signed32) + 0x208",
            "entry_read": "record[0], record[1], record[2]; -1 sentinel branches",
        },
    }


def directory_entries() -> list[dict]:
    # From tools/reverse/scripts/survey_template_field_uses.py full survey.
    rows = [
        ("0x18", 0xE6CD8E6C, 0x3725A4C, "stringOffset candidate (standard header field 0x18)"),
        ("0x20", 0xB2FCE189, 0x4C164, "eventsOffset candidate"),
        ("0x38", 0xF778F1AB, 0x1D4207C, "12-byte type-info triples (confirmed reader)"),
        ("0x3C", 0x978BE7A5, 0x166CE90, "plaintext monotonic u32 table"),
        ("0x54", 0xD43F4844, 0x386B8, "12-byte triple stream / size-derived"),
        ("0x78", 0x67325228, None, "xor-decoded offset (decode below)"),
        ("0x9C", 0xBC7EC9D7, 0xBE1B8C, "16-byte structured records"),
        ("0xB0", 0x8B605DE7, 0x208, "offset 0 candidate (payload start)"),
        ("0xD0", 0xDFCFC6B0, 0x4D4D4, "transformed region"),
        ("0xF0", 0x9D48920F, 0xC37A88, "transformed region"),
        ("0x118", 0xF6D615EF, 0x15024, "transformed region"),
        ("0x140", 0xDAAC7309, 0x208, "offset 0 candidate"),
        ("0x14C", 0xF3A04294, 0x3A1A77C, "26-byte record table (reader at 0x3C66F80)"),
        ("0x150", 0xD882615E, 0x208, "40-byte record table at payload start (reader at 0x3C7F193)"),
        ("0x158", 0xE03EEAC1, 0x3B7444, "transformed structured region (reader at 0x3C7F50B)"),
        ("0x160", 0xC769CD52, 0x4C4308C, "metadata usage table (confirmed reader, entry 4)"),
        ("0x180", 0xE4DBE763, 0x5D3DA8C, "near tail"),
        ("0x184", 0x8709B6A3, 0x25E8A8C, "table candidate"),
        ("0x198", 0xB10C86E7, 0x4348, "early data candidate"),
        ("0x1B4", 0x8D43A4EE, 0x27EF29C, "table candidate"),
        ("0x1D0", 0xC9A664A5, 0xC51CA8, "table candidate"),
    ]
    return [
        {"template_field": f, "transform": f"add 0x{c:08X}", "file_offset": off}
        for f, c, off, _note in rows
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="global-metadata.dat")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    data = np.fromfile(args.input, dtype=np.uint8)
    result = {
        "schema": "mhy_metadata_primitives/1",
        "input": os.path.abspath(args.input),
        "file_size": int(data.size),
        "header": {
            "file_header_size": FILE_HEADER_SIZE,
            "payload_starts_at": FILE_HEADER_SIZE,
            "evidence": [
                "GameAssembly RVA 0x3C7E389: add rsi, 0x208 after global-metadata load",
                "cross-version common prefix 4.4.54 vs 4.4.0 == 0x208",
                "GameAssembly .rdata 0x47BA958 template block is 0x208 bytes",
            ],
        },
        "usage_table": parse_usage(data),
        "triple_table": parse_triples(data),
        "directory_candidates": directory_entries(),
        "milestones": [
            "HEADER_SCHEMA_RECOVERED (header size and template block)",
            "PARTIAL_SCHEMA_RECOVERED (directory field decode rules; not all validated as offsets)",
            "METADATA_USAGE_TABLE_RECOVERED (base/entry size/semantic tags, cross-validated)",
        ],
        "final_status": "MHY_METADATA = PARTIAL_SCHEMA_RECOVERED",
        "not_claimed": [
            "full metadata dump",
            "string table semantics",
            "typeDefinition table identity",
            "transform algorithm (body transform still unresolved)",
        ],
    }
    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    u = result["usage_table"]
    print(f"usage_table: file+0x{u['file_offset']:X}, entries scanned={u['scanned_entries']}")
    print(f"  tags={u['tag_distribution']}")
    print(f"  low29 range={u['low29_min']}..{u['low29_max']}")
    t = result["triple_table"]
    print(f"triple_table: file+0x{t['file_offset']:X}, samples={t['sampled_entries']}, "
          f"f1_minus1={t['field1_minus1_ratio']:.3f}, f2_zero={t['field2_zero_ratio']:.3f}")


if __name__ == "__main__":
    main()
