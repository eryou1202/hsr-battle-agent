#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe callees/constants referenced by DynamicValue Batch 02 candidates.

Read-only. Resolves target VAs back to normalized method indices through
data/parsed/4.4.54/method_code_table.bin + data/normalized/4.4.54/methods.json,
reads PE bytes/float constants, and disassembles a bounded prefix of each
unfamiliar callee.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402

sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

BASE = REPO / "data" / "normalized" / "4.4.54"
CODE_TABLE = REPO / "data" / "parsed" / "4.4.54" / "method_code_table.bin"

TARGET_VAS = {
    "error_log_helper_1": 0x19CFD2950,
    "error_log_helper_2": 0x19CFD2AB0,
    "il2cpp_class_init_like": 0x183C6D0E0,
    "allocator_like": 0x183C736B0,
}
GLOBAL_RVAS = {
    "float_const_1f": (0x4029000, "f"),
    "double_const_1d": (0x40292E8, "d"),
    "fixpoint_scale_a": (0x402AB78, "d"),
    "fixpoint_scale_b": (0x402AB80, "d"),
    "string_int_error": (0x9949AA0, "s"),
    "string_uint_error": (0x997FA40, "s"),
    "string_long_error": (0x9949AC0, "s"),
    "string_float_error": (0x9949AC8, "s"),
    "string_double_error": (0x9949AD0, "s"),
    "string_string_error": (0x994B278, "s"),
    "string_array_error": (0x9949438, "s"),
    "string_map_error": (0x99546C0, "s"),
}


def iter_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        in_records = False
        for line in f:
            if not in_records:
                if '"records": [' in line:
                    in_records = True
                continue
            line = line.strip()
            if not line or line == "]":
                continue
            if line.endswith(","):
                line = line[:-1]
            if line.startswith("{") and line.endswith("}"):
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass


def reverse_code_table(target_vas):
    found = {va: [] for va in target_vas}
    raw = CODE_TABLE.read_bytes()
    count = len(raw) // 8
    for index in range(count):
        va = struct.unpack_from("<Q", raw, index * 8)[0]
        if va in found:
            found[va].append(index)
    return found, count


def read_cstr(pe, rva, max_len=256):
    off = pe.rva_to_file_offset(rva)
    if off is None:
        return None
    raw = pe._read(off, max_len)
    end = raw.find(b"\x00")
    if end >= 0:
        raw = raw[:end]
    return raw


def disasm_prefix(pe, rva, length=96):
    off = pe.rva_to_file_offset(rva)
    if off is None:
        return None, []
    raw = pe._read(off, length)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    lines = []
    for ins in md.disasm(raw, pe.image_base + rva):
        comment = ""
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM:
                if op.mem.base == x86.X86_REG_RIP and op.mem.index == 0:
                    target = ins.address + ins.size + op.mem.disp
                    comment = f" ; [rip]->0x{target:X} (rva 0x{target - pe.image_base:X})"
                    break
        local = rva + (ins.address - (pe.image_base + rva))
        lines.append(
            f"{local:08X}  {ins.bytes.hex(' '):<24}  "
            f"{ins.mnemonic:8} {ins.op_str}{comment}"
        )
    return raw, lines


def main() -> int:
    manifest = json.load((BASE / "manifest.json").open(encoding="utf-8"))
    pe = PeImage(Path(manifest["GameAssembly"]["path"]))
    print(f"image_base=0x{pe.image_base:X}")

    target_vas = sorted(set(TARGET_VAS.values()))
    found, count = reverse_code_table(target_vas)
    print(f"method_code_table slots={count}")
    for name, va in TARGET_VAS.items():
        print(f"callee {name}: va=0x{va:X} rva=0x{va - pe.image_base:X} "
              f"method_indices={found[va]}")

    wanted = set()
    for idxs in found.values():
        wanted.update(idxs)
    identity = {}
    if wanted:
        for rec in iter_records(BASE / "methods.json"):
            if rec["method_index"] in wanted:
                identity[rec["method_index"]] = rec
    for idx in sorted(wanted):
        rec = identity.get(idx)
        print(f"  method {idx}: {json.dumps(rec, ensure_ascii=False) if rec else 'MISSING'}")

    for name, (rva, kind) in GLOBAL_RVAS.items():
        if kind == "f":
            off = pe.rva_to_file_offset(rva)
            raw = pe._read(off, 4) if off is not None else None
            if raw:
                value = struct.unpack("<f", raw)[0]
                print(f"global {name}: rva=0x{rva:X} raw={raw.hex()} float32={value!r}")
            else:
                print(f"global {name}: unmapped")
        elif kind == "d":
            off = pe.rva_to_file_offset(rva)
            raw = pe._read(off, 8) if off is not None else None
            if raw:
                value = struct.unpack("<d", raw)[0]
                print(f"global {name}: rva=0x{rva:X} raw={raw.hex()} float64={value!r}")
            else:
                print(f"global {name}: unmapped")
        else:
            raw = read_cstr(pe, rva)
            print(f"global {name}: rva=0x{rva:X} bytes={raw!r} "
                  f"ascii={raw.decode('ascii', errors='replace')!r} "
                  f"utf8={raw.decode('utf-8', errors='replace')!r} "
                  f"sha256={hashlib.sha256(raw).hexdigest() if raw is not None else None}")

    for name, va in TARGET_VAS.items():
        rva = va - pe.image_base
        raw, lines = disasm_prefix(pe, rva)
        print(f"--- {name} prefix ({len(lines)} insns, sha256={hashlib.sha256(raw).hexdigest() if raw else None}) ---")
        for line in lines:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
