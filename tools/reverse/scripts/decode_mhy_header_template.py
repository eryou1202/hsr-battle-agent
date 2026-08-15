#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decode the per-build MHY header template fields referenced by GameAssembly.

Extracts the 0x208-byte template at .rdata RVA 0x47BA958 and evaluates the
loader transformations observed in disasm_mhy_loader_capstone.txt
(xor / sar / unsigned-mul / shift / align).  This is arithmetic emulation
of specific code snippets, not key guessing.
"""
import argparse
import json
import struct
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

MHY_BLOCK_RVA = 0x47BA958
MHY_BLOCK_SIZE = 0x208


def u32(raw: bytes, off: int) -> int:
    return struct.unpack_from("<I", raw, off)[0]


def mul_hi(x: int, m: int) -> int:
    return ((x & 0xFFFFFFFFFFFFFFFF) * (m & 0xFFFFFFFFFFFFFFFF)) >> 64


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    pe = PeImage(Path(args.game))
    block = pe.read_rva(MHY_BLOCK_RVA, MHY_BLOCK_SIZE)
    assert block is not None and len(block) == MHY_BLOCK_SIZE
    out = {
        "schema": "mhy_header_template_decode/1",
        "game": str(Path(args.game).resolve()),
        "template_rva": MHY_BLOCK_RVA,
        "template_size": MHY_BLOCK_SIZE,
        "magic": block[:8].hex(" ").upper(),
        "fields": {},
    }
    # Field transformations copied from the capstone disassembly.
    raw_178 = u32(block, 0x178)
    dec_178 = ((raw_178 & 0xFFFFFFFF) >> 4) ^ 0x05CC1AE1  # sar by 4 on positive value
    out["fields"]["0x178"] = {
        "raw": raw_178,
        "transform": "sar 4; xor 0x05CC1AE1",
        "decoded": dec_178,
        "entry_size": 0x58,
        "allocation_size": dec_178 * 0x58,
        "global_written": 0x9D387F0,
    }
    raw_1A8 = u32(block, 0x1A8)
    x = (raw_1A8 ^ 0x729B1A9E) & 0xFFFFFFFF
    hi = mul_hi(x, 0x0EA0EA0EA0EA0EA0F)
    size = (hi >> 3) & 0xFFFFFFFFFFFFFFF8
    out["fields"]["0x1a8"] = {
        "raw": raw_1A8,
        "transform": "xor 0x729B1A9E; mul 0xEA..0F; hi>>3; and ~7",
        "decoded": x,
        "derived_size": size,
        "derived_size_is_multiple_of_8": size % 8 == 0,
        "compare_threshold_0x46": x >= 0x46,
        "global_written": 0x9D387C8,
    }
    raw_1F8 = u32(block, 0x1F8)
    x = (raw_1F8 ^ 0x1608C2C8) & 0xFFFFFFFF
    hi = mul_hi(x, 0x4EC4EC4EC4EC4EC5)
    size = hi & 0xFFFFFFFFFFFFFFF8
    out["fields"]["0x1f8"] = {
        "raw": raw_1F8,
        "transform": "xor 0x1608C2C8; mul 0x4EC4..C5; hi; and ~7",
        "decoded": x,
        "derived_size": size,
        "derived_size_is_multiple_of_8": size % 8 == 0,
        "compare_threshold_0x1a": x >= 0x1A,
        "global_written": 0x9D387D0,
    }
    raw_74 = u32(block, 0x74)
    x = (raw_74 ^ 0x080EF250) & 0xFFFFFFFF
    hi = mul_hi(x, 0xAAAAAAAAAAAAAAAB)
    aligned = hi & 0xFFFFFFFFFFFFFFF8
    # shl 29 / sar 29 net effect for positive values
    back = (aligned << 29) >> 29
    out["fields"]["0x74"] = {
        "raw": raw_74,
        "transform": "xor 0x080EF250; mul 0xAAA..AB; hi; and ~7; shl/sar 29",
        "decoded": x,
        "derived_size": back,
        "global_written": 0x9D387D8,
    }
    raw_134 = u32(block, 0x134)
    x = (raw_134 ^ 0x10210728) & 0xFFFFFFFF
    hi = mul_hi(x, 0xCCCCCCCCCCCCCCCD)
    count = hi >> 5
    out["fields"]["0x134"] = {
        "raw": raw_134,
        "transform": "xor 0x10210728; mul 0xCCC..CD; hi>>5",
        "decoded": x,
        "derived_count": count,
        "entry_size": 0x48,
        "allocation_size": count * 0x48,
        "global_written": 0x9D387E8,
    }
    # count from pointer table @0x483BA98, field +0x48 (low dword)
    raw_pt = pe.read_rva(0x483BA98 + 0x48, 4)
    assert raw_pt is not None
    raw_pt_val = struct.unpack("<I", raw_pt)[0]
    dec_pt = (raw_pt_val + 0xA94544C4) & 0xFFFFFFFF
    out["fields"]["pointer_table_0x483BA98+0x48"] = {
        "raw": raw_pt_val,
        "transform": "add 0xA94544C4",
        "decoded": dec_pt,
        "entry_size": 8,
        "allocation_size": dec_pt * 8,
        "global_written": 0x9D387C0,
    }
    print(json.dumps(out, indent=2))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
