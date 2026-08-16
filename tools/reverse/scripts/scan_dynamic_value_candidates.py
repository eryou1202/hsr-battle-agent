#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DynamicValue Batch 02 candidate complexity scanner.

Read-only inputs:
  - data/normalized/4.4.54/{manifest,methods,parameters,fields}.json
  - GameAssembly.dll from the manifest (bounded capstone scan only)

For every method declared on RPG.GameCore.DynamicValue (type_index 10822) it
writes a summary table and, for the value-shaped subset, bounded disassembly
to data/parsed/4.4.54/dynamic_value_candidate_scan.txt.
"""
from __future__ import annotations

import json
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
PRIMARY_TYPE_INDEX = 10822
OUT = REPO / "data" / "parsed" / "4.4.54" / "dynamic_value_candidate_scan.txt"

DISASSEMBLE_NAMES = (
    "Equals",
    "GetHashCode",
    "ToString",
    "get_",
    "get__",
    "op_Implicit",
)


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


def disasm(pe: PeImage, rva: int, length: int):
    off = pe.rva_to_file_offset(rva)
    if off is None:
        return None, [], 0, 0, 0
    raw = pe._read(off, length)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    lines = []
    branches = 0
    calls = 0
    jumps = 0
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
        if ins.mnemonic.startswith("j") and ins.mnemonic != "jmp":
            branches += 1
        if ins.mnemonic == "call":
            calls += 1
        if ins.mnemonic == "jmp":
            jumps += 1
    return raw, lines, branches, calls, jumps


def main() -> int:
    methods = sorted(
        (r for r in iter_records(BASE / "methods.json")
         if r.get("declaring_type_index") == PRIMARY_TYPE_INDEX),
        key=lambda r: int(r["native_rva"]),
    )
    rvas = [int(r["native_rva"]) for r in methods]
    sizes = {}
    for i, rec in enumerate(methods):
        rva = int(rec["native_rva"])
        size = None
        for other in rvas:
            if other > rva:
                size = other - rva
                break
        sizes[rec["method_index"]] = size
    manifest = json.load((BASE / "manifest.json").open(encoding="utf-8"))
    pe = PeImage(Path(manifest["GameAssembly"]["path"]))

    lines = []
    lines.append(
        "method_index | name | rva | slot_size | insn | branch | call | jmp "
        "| params | ret_ref"
    )
    stats = {}
    for rec in sorted(methods, key=lambda r: r["method_index"]):
        rva = int(rec["native_rva"])
        size = sizes[rec["method_index"]]
        length = size if size and size <= 0x2000 else 0x2000
        raw, dis_lines, branches, calls, jumps = disasm(pe, rva, length)
        stats[rec["method_index"]] = (dis_lines, branches, calls, jumps)
        lines.append(
            f"{rec['method_index']} | {rec['name']} | 0x{rva:X} | {size} | "
            f"{len(dis_lines)} | {branches} | {calls} | {jumps} | "
            f"{rec['parameter_count']} | {rec['return_type_reference']}"
        )
    lines.append("")
    for rec in sorted(methods, key=lambda r: r["method_index"]):
        name = rec["name"]
        if not any(name.startswith(prefix) for prefix in DISASSEMBLE_NAMES):
            continue
        rva = int(rec["native_rva"])
        size = sizes[rec["method_index"]]
        dis_lines, branches, calls, jumps = stats[rec["method_index"]]
        lines.append(
            f"===== {rec['method_index']} {name} "
            f"rva=0x{rva:X} slot_size={size} "
            f"insn={len(dis_lines)} branch={branches} call={calls} jmp={jumps} "
            f"params={rec['parameter_count']} ret_ref={rec['return_type_reference']} ====="
        )
        lines.extend(dis_lines)
        lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
