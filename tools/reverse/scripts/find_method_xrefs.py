#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate static references / direct calls to native method RVAs.

Two cheap and exact scans (no full linear disassembly):

  * absolute qword = image_base + rva anywhere in raw file (pointer tables,
    vtables, registries, static fields);
  * `call rel32` / `jmp rel32` whose resolved target is image_base + rva;
  * common `lea reg, [rip+disp32]` forms whose target is image_base + rva.

This is the bridge xref tool: it turns a parser method RVA into its registry /
caller evidence.
"""
from __future__ import annotations

import argparse
import json
import mmap
import re
import struct
from pathlib import Path

from resolve_il2cpp_get_api_table import PeImage

# 4-byte opcodes with a RIP-relative disp32 in the last 4 bytes:
# 48 8D 0D lea rcx,[rip+disp32]
# 48 8D 05 lea rax, ...
# 48 8D 15 lea rdx, ...
# 48 8D 1D lea rbx, ...
# 48 8D 25 lea rsp?, etc. Register nibble varies: 48 8D (modrm 0x05..0x3D)
LEA_RIP_RE = re.compile(
    rb"\x48\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})",
    re.DOTALL)
# 4C 8D variants: 4C 8D (modrm 0x05..0x3D) use register r8..r15 + rip.
LEA_RIP_RE2 = re.compile(
    rb"\x4c\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})",
    re.DOTALL)
# `mov r64, [rip+disp32]` and `mov [rip+disp32], r64`.
MOV_RIP_RE = re.compile(
    rb"\x48\x8b[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})"
    rb"|\x4c\x8b[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp2>.{4})"
    rb"|\x48\x89[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp3>.{4})"
    rb"|\x4c\x89[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp4>.{4})"
    rb"|\xc7\x05(?P<disp5>.{4}).{4}",
    re.DOTALL)


def section_for_file_offset(pe: PeImage, fo: int):
    for s in pe.sections:
        if s.raw_offset <= fo < s.raw_offset + s.raw_size:
            return s
    return None


def classify_ref(pe: PeImage, fo: int, target_va: int) -> dict:
    sec = section_for_file_offset(pe, fo)
    if sec is None:
        return {"file_offset": fo, "kind": "unmapped"}
    rva = sec.rva + (fo - sec.raw_offset)
    ctx = pe._read(max(0, fo - 8), min(fo + 32, sec.raw_offset + sec.raw_size) - max(0, fo - 8))
    return {
        "rva": f"0x{rva:X}",
        "section": sec.name,
        "section_flags": {
            "executable": bool(sec.is_executable),
            "writable": bool(getattr(sec, "is_writable", False)),
        },
        "file_offset": fo,
        "context_hex": ctx.hex(" "),
        "context_ascii": "".join(chr(b) if 32 <= b <= 126 else "." for b in ctx),
    }


def scan_qword_refs(pe: PeImage, target_va: int) -> list[dict]:
    needle = struct.pack("<Q", target_va)
    out = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        pos = 0
        while True:
            p = raw.find(needle, pos)
            if p < 0:
                break
            sec = section_for_file_offset(pe, p)
            if sec is not None and p % 8 == (sec.raw_offset % 8):
                out.append(classify_ref(pe, p, target_va))
            pos = p + 1
        raw.close()
    return out


def scan_rel32_refs(pe: PeImage, target_va: int) -> list[dict]:
    out = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if not sec.is_executable or sec.raw_size <= 0:
                continue
            data = raw[sec.raw_offset : sec.raw_offset + sec.raw_size]
            for m in re.finditer(rb"[\xe8\xe9](?P<disp>.{4})", data, re.DOTALL):
                pos = sec.raw_offset + m.start()
                if section_for_file_offset(pe, pos + 4) is None:
                    continue
                insn_rva = sec.rva + m.start()
                disp = struct.unpack("<i", m.group("disp"))[0]
                dest_va = pe.image_base + insn_rva + 5 + disp
                if dest_va == target_va:
                    out.append({
                        **classify_ref(pe, pos, target_va),
                        "kind": "rel32_branch",
                        "mnemonic": "call" if data[m.start()] == 0xE8 else "jmp",
                        "instruction_rva": f"0x{insn_rva:X}",
                    })
        raw.close()
    return out


def scan_lea_rip_refs(pe: PeImage, target_va: int) -> list[dict]:
    out = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if not sec.is_executable or sec.raw_size <= 0:
                continue
            data = raw[sec.raw_offset : sec.raw_offset + sec.raw_size]
            for pattern, kind in ((LEA_RIP_RE, "lea64_rip"),
                                  (LEA_RIP_RE2, "lea64_rip_r8")):
                for m in pattern.finditer(data):
                    pos = sec.raw_offset + m.start()
                    insn_rva = sec.rva + m.start()
                    disp = struct.unpack("<i", m.group("disp"))[0]
                    dest_va = pe.image_base + insn_rva + 7 + disp
                    if dest_va == target_va:
                        out.append({
                            **classify_ref(pe, pos, target_va),
                            "kind": kind,
                            "instruction_rva": f"0x{insn_rva:X}",
                        })
        raw.close()
    return out


def scan_mov_rip_refs(pe: PeImage, target_va: int) -> list[dict]:
    out = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if not sec.is_executable or sec.raw_size <= 0:
                continue
            data = raw[sec.raw_offset : sec.raw_offset + sec.raw_size]
            for m in MOV_RIP_RE.finditer(data):
                pos = sec.raw_offset + m.start()
                insn_rva = sec.rva + m.start()
                for name in ("disp", "disp2", "disp3", "disp4", "disp5"):
                    if m.group(name) is None:
                        continue
                    disp = struct.unpack("<i", m.group(name))[0]
                    insn_len = 7 if name != "disp5" else 10
                    dest_va = pe.image_base + insn_rva + insn_len + disp
                    if dest_va == target_va:
                        prefix = data[m.start() : m.start() + 2]
                        kind = "mov_load_rip" if prefix[1] == 0x8B else "mov_store_rip"
                        out.append({
                            **classify_ref(pe, pos, target_va),
                            "kind": kind,
                            "instruction_rva": f"0x{insn_rva:X}",
                        })
        raw.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--rva", type=lambda x: int(x, 0), action="append", required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--qword-only", action="store_true")
    args = ap.parse_args()

    pe = PeImage(args.game)
    report = []
    for rva in sorted(args.rva):
        va = pe.image_base + rva
        qrefs = scan_qword_refs(pe, va)
        relrefs = [] if args.qword_only else scan_rel32_refs(pe, va)
        learefs = [] if args.qword_only else scan_lea_rip_refs(pe, va)
        movrefs = [] if args.qword_only else scan_mov_rip_refs(pe, va)
        report.append({
            "native_rva": f"0x{rva:X}",
            "qword_refs": qrefs,
            "rel32_refs": relrefs,
            "lea_rip_refs": learefs,
            "mov_rip_refs": movrefs,
            "ref_counts": {
                "qword": len(qrefs),
                "rel32": len(relrefs),
                "lea_rip": len(learefs),
                "mov_rip": len(movrefs),
            },
        })
        print(f"0x{rva:X}: qword={len(qrefs)} rel32={len(relrefs)} lea={len(learefs)} mov={len(movrefs)}")
        for ref in qrefs[:8]:
            print(f"  q {ref['rva']} [{ref['section']}] {ref['context_hex'][:96]}")
        for ref in relrefs[:8]:
            print(f"  b {ref['instruction_rva']} {ref['mnemonic']}")
        for ref in learefs[:8]:
            print(f"  l {ref['instruction_rva']}")
        for ref in movrefs[:8]:
            print(f"  m {ref['instruction_rva']} {ref['kind']}")
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"schema": "mhy_method_xref_scan/1",
                   "game": str(args.game.resolve()), "targets": report}, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
