#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrow runtime class/header slot probe.

Given a runtime type index and a slot offset, this script checks the type's
own native methods for direct accesses to that slot and reports whether a
static writer/initializer is visible. It does not build a generic IL2CPP
framework.
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64, x86  # noqa: E402

sys.path.insert(0, str(HERE))
from semantic_batch_evidence import CODE_TABLE, NORMALIZED_BASE, iter_records, load_pe  # noqa: E402
from global_static_writer_classifier import MethodIndex  # noqa: E402


def load_type_methods(type_index: int) -> list[dict]:
    out = []
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        if rec["declaring_type_index"] == type_index:
            out.append(rec)
    return out


def probe_type_slot(type_index: int, slot_offset: int) -> dict:
    pe = load_pe()
    mi = MethodIndex.from_code_table(pe, CODE_TABLE)
    methods = load_type_methods(type_index)
    starts = sorted(mi.rvas)
    accesses = []
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for rec in methods:
        rva = rec.get("native_rva")
        if not isinstance(rva, int):
            continue
        i = bisect.bisect_right(starts, rva) - 1
        nxt = starts[i + 1] if i + 1 < len(starts) else rva + 0x200
        raw = pe.read_rva(rva, min(nxt - rva, 0x4000))
        if not raw:
            continue
        for ins in md.disasm(raw, pe.image_base + rva):
            ir = ins.address - pe.image_base
            for op in ins.operands:
                if op.type == x86.X86_OP_MEM and op.mem.disp == slot_offset:
                    acc = int(getattr(op, "access", 0))
                    accesses.append({
                        "method_index": rec["method_index"],
                        "method_name": rec["name"],
                        "rva": f"0x{ir:X}",
                        "form": f"{ins.mnemonic} {ins.op_str}",
                        "access": "read" if acc == 1 else "write" if acc == 2 else "read-write" if acc == 3 else "unknown",
                    })
    return {
        "type_index": type_index,
        "slot_offset": f"0x{slot_offset:X}",
        "method_count": len(methods),
        "direct_accesses": accesses,
        "direct_writer_found": any(a["access"] in ("write", "read-write") for a in accesses),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--type-index", type=int, required=True)
    ap.add_argument("--slot-offset", type=lambda x: int(x, 0), required=True)
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()
    result = probe_type_slot(args.type_index, args.slot_offset)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
            f.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
