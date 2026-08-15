#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decode MHY per-build header-template directory fields (4.4.54).

Each rule was recovered from GameAssembly code (see
docs/reverse/mhy_metadata_format_4.4.54.md).  A rule is
(transform, constant) applied to the u32 at template_field; if the code
then adds the metadata payload pointer, the value is a payload-relative
offset and `file_offset = 0x208 + signed32(decoded)`.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

TEMPLATE_RVA = 0x47BA958
FILE_HEADER = 0x208

RULES = [
    # (field, op, const, notes)
    (0x18, "add", 0xE6CD8E6C, "8-byte record table; reader @0x3BFB762 uses [base + idx*8]"),
    (0x20, "add", 0xB2FCE189, "table candidate (transformed region)"),
    (0x38, "add", 0xF778F1AB, "12-byte type-info triples; reader @0x5778"),
    (0x3C, "add", 0x978BE7A5, "plaintext monotonic u32 table @0x166CE90"),
    (0x54, "add", 0xD43F4844, "12-byte triple stream @0x386B8; also used as size/4"),
    (0x78, "xor", 0x67325228, "offset candidate; reader @0x3BFB73F"),
    (0x84, "xor", 0x68531D3F, "offset candidate; reader @0x3BFB73F"),
    (0x9C, "add", 0xBC7EC9D7, "16-byte structured records @0xBE1B8C"),
    (0xB0, "add", 0x8B605DE7, "offset 0 (payload start) candidate"),
    (0xD0, "add", 0xDFCFC6B0, "transformed region"),
    (0xF0, "add", 0x9D48920F, "transformed region"),
    (0x118, "add", 0xF6D615EF, "transformed region"),
    (0x140, "add", 0xDAAC7309, "offset 0 candidate"),
    (0x14C, "add", 0xF3A04294, "26-byte record table; reader @0x3C66F80"),
    (0x150, "add", 0xD882615E, "40-byte record table at payload start; reader @0x3C7F193"),
    (0x158, "add", 0xE03EEAC1, "transformed structured region; reader @0x3C7F50B"),
    (0x160, "add", 0xC769CD52, "metadata usage table, entry 4; reader @0x5720"),
    (0x180, "add", 0xE4DBE763, "near-tail table candidate"),
    (0x184, "add", 0x8709B6A3, "table candidate"),
    (0x198, "add", 0xB10C86E7, "early data candidate"),
    (0x1B4, "add", 0x8D43A4EE, "table candidate"),
    (0x1D0, "add", 0xC9A664A5, "table candidate"),
]


def signed32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    pe = PeImage(Path(args.game))
    block = pe.read_rva(TEMPLATE_RVA, 0x208)
    rows = []
    for field, op, const, note in RULES:
        raw = struct.unpack_from("<I", block, field)[0]
        if op == "add":
            dec = (raw + const) & 0xFFFFFFFF
        elif op == "xor":
            dec = raw ^ const
        else:
            raise ValueError(op)
        signed = signed32(dec)
        rows.append({
            "template_field": f"0x{field:X}",
            "raw_u32": f"0x{raw:08X}",
            "transform": f"{op} 0x{const:08X}",
            "decoded_u32": f"0x{dec:08X}",
            "signed32": signed,
            "payload_relative_offset": f"0x{signed:X}" if signed >= 0 else f"-0x{-signed:X}",
            "file_offset_if_table_start": f"0x{FILE_HEADER + signed:X}",
            "notes": note,
        })
    rows.sort(key=lambda r: int(r["file_offset_if_table_start"], 16))
    out = {
        "schema": "mhy_directory_decode/1",
        "game": str(Path(args.game).resolve()),
        "template_rva": TEMPLATE_RVA,
        "template_size": 0x208,
        "file_header_size": FILE_HEADER,
        "directory": rows,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {args.output}")
    for r in rows:
        print(f"{r['template_field']} {r['transform']:20s} raw={r['raw_u32']} "
              f"dec={r['decoded_u32']} file={r['file_offset_if_table_start']}  {r['notes']}")


if __name__ == "__main__":
    main()
