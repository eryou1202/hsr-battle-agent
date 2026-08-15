#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accurate linear disassembler for GameAssembly.dll using vendored Capstone."""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402

sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--length", type=lambda x: int(x, 0), default=0x100)
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()
    pe = PeImage(Path(args.game))
    off = pe.rva_to_file_offset(args.rva)
    if off is None:
        raise SystemExit("RVA not mapped")
    raw = pe._read(off, args.length)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    lines = []
    for insn in md.disasm(raw, pe.image_base + args.rva):
        comment = ""
        # Decode rip-relative target for memory operands
        if insn.operands:
            for op in insn.operands:
                if op.type == 2:  # X86_OP_MEM
                    if op.mem.base == 0 and op.mem.index == 0:  # rip-based: base reg id?
                        # Capstone X86_REG_RIP is 0x29; check from op.mem.base enum
                        if op.mem.base == 0x29:
                            target = pe.image_base + args.rva + insn.size + op.mem.disp
                            comment = f" ; [rip] -> 0x{target:X} (rva 0x{target - pe.image_base:X})"
        lines.append(f"{args.rva + insn.address - (pe.image_base + args.rva):08X}  "
                     f"{insn.bytes.hex(' '):<30}  {insn.mnemonic:8} {insn.op_str}{comment}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"wrote {args.output} ({len(lines)} lines)")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
