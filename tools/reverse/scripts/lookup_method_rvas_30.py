#!/usr/bin/env python3
"""Reverse-map native RVAs to recovered MHY MethodDefinitions."""
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
    result = {}
    for field, (operation, constant) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        value = (raw + constant) & M32 if operation == "add" else raw ^ constant
        result[field] = FILE_HEADER + signed32(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--code-table-rva", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--template-rva", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--rva", required=True, action="append", type=lambda value: int(value, 0))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pe = PeImage(args.game)
    template_rva = args.template_rva or locate_template_rva(pe)
    offsets = table_offsets(pe, template_rva)
    method_base = offsets[0x14C]
    method_count = (offsets[0x160] - method_base) // 26
    type_base = offsets[0x84]
    region_base = offsets[0x1B4]
    table = pe.read_rva(args.code_table_rva, method_count * 8)
    wanted = set(args.rva)
    hits: dict[int, list[int]] = {rva: [] for rva in args.rva}
    for method_index in range(method_count):
        pointer = struct.unpack_from("<Q", table, method_index * 8)[0]
        if pointer and pointer - pe.image_base in wanted:
            hits[pointer - pe.image_base].append(method_index)

    rows = []
    size = args.metadata.stat().st_size
    with args.metadata.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as metadata:
        region = metadata[region_base : region_base + min(size - region_base, 1 << 26)]
        for rva in args.rva:
            matches = []
            for method_index in hits[rva]:
                type_index = decode_declaring_type(metadata, method_base, method_index)
                matches.append(
                    {
                        "method_index": method_index,
                        "method_name": decode_method_name(metadata, method_base, method_index, region),
                        "declaring_type_index": type_index,
                        "declaring_type": resolve_type_name(metadata, type_base, type_index, region),
                    }
                )
            rows.append({"native_rva": f"0x{rva:X}", "matches": matches})

    result = {
        "schema": "mhy_method_rva_lookup/1",
        "template_rva": f"0x{template_rva:X}",
        "code_table_rva": f"0x{args.code_table_rva:X}",
        "queries": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(row["native_rva"])
        for match in row["matches"]:
            print(
                f"  M{match['method_index']} {match['declaring_type']}."
                f"{match['method_name']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
