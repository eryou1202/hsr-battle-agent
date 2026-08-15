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
    (0x10, "xor", 0x22E64E71, "u16 table; reader @0x3C8123F"),
    (0x18, "add", 0xE6CD8E6C, "8-byte packed two-range table; reader @0x3C6F7E9"),
    (0x20, "add", 0xB2FCE189, "table candidate (transformed region)"),
    (0x2C, "xor", 0x767BDACA, "8-byte table; reader @0x3C5D467 / 0x3C5D7D5"),
    (0x34, "xor", 0x7FBFB3F8, "u16 table; reader @0x3C5D7A3"),
    (0x38, "add", 0xF778F1AB, "12-byte type-info triples; reader @0x5778"),
    (0x3C, "add", 0x978BE7A5, "type-encoding data stream; reader @0x3C11520"),
    (0x4C, "add", 0xE82C6008, "table candidate; reader @0x3C713B5"),
    (0x54, "add", 0xD43F4844, "size/4 count field; also 12-byte stream @0x386B8"),
    (0x70, "xor", 0x57A78949, "u32 definition index map; reader @0x3C82BAC"),
    (0x78, "xor", 0x67325228, "u32 index table; reader @0x3C811FA"),
    (0x84, "xor", 0x68531D3F, "70-byte definition records; reader @0x3C82BAC"),
    (0x90, "xor", 0x697A7664, "table candidate; reader @0x3C3130C"),
    (0x94, "xor", 0x3D160A8B, "packed range u32 table; reader @0x3C5D8A1"),
    (0x9C, "add", 0xBC7EC9D7, "12-byte records @0xBE1B8C; readers @0x3C5C4FC / 0x3C81392"),
    (0xA8, "xor", 0x2CE30270, "byte table; reader @0x3C5D53F"),
    (0xB0, "add", 0x8B605DE7, "payload-start alias (decoded 0)"),
    (0xC4, "xor", 0x38BDB304, "table candidate; reader @0x3C5D826"),
    (0xD0, "add", 0xDFCFC6B0, "table candidate; reader @0x3C7F528"),
    (0xEC, "xor", 0x67F701BA, "table candidate; reader @0x3C80DD3"),
    (0xF0, "add", 0x9D48920F, "table candidate; readers @0x3C11716 / 0x3C8F396"),
    (0x114, "xor", 0x3EABB25A, "u16 table +4; reader @0x3C5C937"),
    (0x118, "add", 0xF6D615EF, "u32 index table; reader @0x3C811E0"),
    (0x124, "xor", 0x1AFCE463, "byte table; reader @0x3C8FF18"),
    (0x12C, "xor", 0x26F0FC20, "u32 type-index table; reader @0x3C6730A"),
    (0x13C, "xor", 0x46C8010F, "table candidate; reader @0x3C5E141"),
    (0x140, "add", 0xDAAC7309, "payload-start alias (decoded 0)"),
    (0x144, "xor", 0x4CDE6970, "table candidate; reader @0x3C6EF09"),
    (0x148, "xor", 0x329E1172, "usage-like u32 table; reader @0x3C5C340"),
    (0x14C, "add", 0xF3A04294, "26-byte usage records; reader @0x3C66F80"),
    (0x150, "add", 0xD882615E, "startup 40-byte table; reader @0x3C7F193"),
    (0x158, "add", 0xE03EEAC1, "startup table; reader @0x3C7F510"),
    (0x160, "add", 0xC769CD52, "metadata usage table, entry 4; reader @0x5720"),
    (0x164, "xor", 0x7F5C5934, "startup 8-byte table; reader @0x3C7E938"),
    (0x170, "xor", 0x61645FE8, "startup table; reader @0x3C7FACB"),
    (0x180, "add", 0xE4DBE763, "u32 index into 0x9C records; reader @0x3C5C514"),
    (0x184, "add", 0x8709B6A3, "table candidate; reader @0x3C74C90"),
    (0x198, "add", 0xB10C86E7, "8-byte sorted table; reader @0x3C5D833"),
    (0x1AC, "xor", 0x37080D6E, "table candidate; reader @0x3C5E924"),
    (0x1B4, "add", 0x8D43A4EE, "table candidate; reader @0x3C59C5B"),
    (0x1C4, "xor", 0x11531BF7, "12-byte records; reader @0x3C5D7B7"),
    (0x1C8, "xor", 0x042F9275, "table candidate; reader @0x3C5F179"),
    (0x1D0, "add", 0xC9A664A5, "table candidate; reader @0x3C6D109"),
    (0x1DC, "xor", 0x3E0C72F0, "table candidate; readers @0x3C11434 / 0x3C666DC"),
    (0x1E4, "xor", 0x720FEF70, "table candidate; readers @0x3C80DE8 / 0x3C8316F"),
    (0x1EC, "add", 0xA75A2A51, "u32 range target table; reader @0x3C6FA41"),
    (0x1FC, "xor", 0x6238CDB0, "12-byte type lookup map; reader @0x3C11478"),
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
