#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find static xrefs to MHY metadata anchors inside GameAssembly.dll.

Anchors are the exact `MHY\\0` magic word, the `global-metadata.dat` string
and the `startup-metadata.dat` string found in `.rdata`.  The tool searches
executable sections for RIP-relative operands and absolute 64-bit image
addresses that resolve to those anchors.  It only reports references whose
computed target matches an anchor exactly; no decryption is attempted.

Uses the minimal decoder from resolve_il2cpp_get_api_table.py.
"""

from __future__ import annotations

import argparse
import json
import mmap
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_il2cpp_get_api_table import PeImage, decode_one  # noqa: E402

RIP_MODRM_BYTES = (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D)


def make_patterns() -> list[bytes]:
    patterns: list[bytes] = []
    # lea r64, [rip+disp32]
    for rex in (None, *range(0x40, 0x50)):
        for modrm in RIP_MODRM_BYTES:
            prefix = bytes([rex, 0x8D, modrm]) if rex is not None else bytes([0x8D, modrm])
            patterns.append(prefix)
    # mov r64, [rip+disp32] and mov [rip+disp32], r64 (8B / 89)
    for op in (0x8B, 0x89):
        for rex in (None, *range(0x40, 0x50)):
            for modrm in RIP_MODRM_BYTES:
                prefix = bytes([rex, op, modrm]) if rex is not None else bytes([op, modrm])
                patterns.append(prefix)
    # cmp [rip+disp32], r64 (39) and cmp r64, [rip+disp32] (3B)
    for op in (0x39, 0x3B):
        for modrm in RIP_MODRM_BYTES:
            patterns.append(bytes([0x48, op, modrm]))
    # group1 / group2 with rip-relative memory and imm (81 / 83 / C7)
    for op in (0x81, 0x83, 0xC7):
        for modrm in RIP_MODRM_BYTES:
            patterns.append(bytes([0x48, op, modrm]))
            patterns.append(bytes([op, modrm]))
    # indirect call/jmp [rip+disp32]
    for modrm in RIP_MODRM_BYTES:
        patterns.append(bytes([0xFF, modrm]))
        patterns.append(bytes([0x41, 0xFF, modrm]))
    # deduplicate
    return list(dict.fromkeys(patterns))


def scan_rip_patterns(raw: mmap.mmap, section_base_va: int, section_rva_start: int,
                      raw_offset: int, section_end: int, anchor_vas: dict[str, int],
                      patterns: list[bytes],
                      max_hits_per_anchor: int = 100) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = {name: [] for name in anchor_vas}
    anchor_set = {va: name for name, va in anchor_vas.items()}
    for pat in patterns:
        pos = raw_offset
        while True:
            p = raw.find(pat, pos)
            if p < 0 or p >= section_end:
                break
            rel = p - raw_offset
            # decode at candidate instruction start
            start_va = section_base_va + rel
            insn = decode_one(raw[p : p + 16], start_va)
            if insn is not None and insn.rip_relative and insn.rip_target is not None:
                name = anchor_set.get(insn.rip_target)
                if name is not None and len(hits[name]) < max_hits_per_anchor:
                    hits[name].append({
                        "kind": "rip_relative",
                        "file_offset": p,
                        "rva": section_rva_start + rel,
                        "va": start_va,
                        "mnemonic": insn.mnemonic,
                        "operands": insn.op_str,
                    })
            pos = p + 1
    return hits


def scan_absolute(pe: PeImage, raw: mmap.mmap, anchor_vas: dict[str, int],
                  max_hits_per_anchor: int = 100) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = {name: [] for name in anchor_vas}
    for name, va in anchor_vas.items():
        # 64-bit absolute VA, little-endian
        needle = struct.pack("<Q", va)
        pos = 0
        while True:
            p = raw.find(needle, pos)
            if p < 0:
                break
            rva = None
            sec = pe.section_at_rva(p)
            # file offset equals rva only for raw-identity sections; compute real RVA
            for s in pe.sections:
                if s.raw_offset <= p < s.raw_offset + s.raw_size:
                    rva = s.rva + (p - s.raw_offset)
                    sec = s
                    break
            hits[name].append({
                "kind": "absolute_va64",
                "file_offset": p,
                "rva": rva,
                "va": pe.image_base + rva if rva is not None else None,
                "section": sec.name if sec else None,
            })
            pos = p + 1
            if len(hits[name]) >= max_hits_per_anchor:
                break
        # 32-bit absolute RVA
        needle32 = struct.pack("<I", va - pe.image_base)
        pos = 0
        while True:
            p = raw.find(needle32, pos)
            if p < 0:
                break
            rva = None
            sec = None
            for s in pe.sections:
                if s.raw_offset <= p < s.raw_offset + s.raw_size:
                    rva = s.rva + (p - s.raw_offset)
                    sec = s
                    break
            hits[name].append({
                "kind": "absolute_rva32",
                "file_offset": p,
                "rva": rva,
                "va": pe.image_base + rva if rva is not None else None,
                "section": sec.name if sec else None,
            })
            pos = p + 1
            if len(hits[name]) >= max_hits_per_anchor:
                break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", help="GameAssembly.dll path")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--max-hits-per-anchor", type=int, default=100)
    ap.add_argument("--extra-rva", action="append", default=[],
                    help="extra anchor name=0xRVA to scan, repeatable")
    args = ap.parse_args()
    pe = PeImage(Path(args.game))
    anchor_vas = {
        "mhy_magic": pe.image_base + 0x47BA958,
        "global-metadata.dat": pe.image_base + 0x5A929C7,
        "startup-metadata.dat": pe.image_base + 0x5A929B2,
    }
    for spec in args.extra_rva:
        if "=" not in spec:
            ap.error("--extra-rva expects name=0xRVA")
        name, val = spec.split("=", 1)
        anchor_vas[name] = pe.image_base + int(val, 0)
    result = {
        "schema": "mhy_metadata_anchor_xrefs/1",
        "input": os.path.abspath(args.game),
        "image_base": pe.image_base,
        "anchors": {k: {"va": v, "rva": v - pe.image_base} for k, v in anchor_vas.items()},
        "absolute_hits": {},
        "rip_relative_hits": {},
        "sections_scanned": [],
    }
    with open(args.game, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        result["absolute_hits"] = scan_absolute(pe, raw, anchor_vas,
                                                max_hits_per_anchor=args.max_hits_per_anchor)
        patterns = make_patterns()
        rip_hits: dict[str, list[dict]] = {name: [] for name in anchor_vas}
        for sec in pe.sections:
            if not sec.is_executable:
                continue
            if sec.name in (".upx0",):
                # Raw .upx0 bytes are transformed on disk; static raw scan has no
                # plaintext instructions. Record and skip.
                result["sections_scanned"].append(
                    {"section": sec.name, "status": "skipped_transformed_raw"})
                continue
            if sec.raw_size <= 0:
                continue
            result["sections_scanned"].append(
                {"section": sec.name, "rva": sec.rva, "raw_size": sec.raw_size,
                 "status": "scanned"})
            section_base_va = pe.image_base + sec.rva
            section_end = sec.raw_offset + sec.raw_size
            local = scan_rip_patterns(raw, section_base_va, sec.rva, sec.raw_offset,
                                      section_end, anchor_vas, patterns,
                                      max_hits_per_anchor=args.max_hits_per_anchor)
            for name, recs in local.items():
                for rec in recs:
                    rec["target_rva"] = (anchor_vas[name] - pe.image_base)
                    rec["target_name"] = name
                    rec["section"] = sec.name
                rip_hits[name].extend(recs)
        raw.close()
    result["rip_relative_hits"] = rip_hits

    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"wrote {out}")
    for name in anchor_vas:
        print(f"{name}: absolute={len(result['absolute_hits'][name])} "
              f"rip_relative={len(rip_hits[name])}")
        for rec in (result["absolute_hits"][name] + rip_hits[name])[:12]:
            rva = rec.get("rva")
            print(f"  {rec.get('kind')} @ file+0x{rec['file_offset']:X}"
                  f" rva=0x{rva:X}" if rva is not None else f"  {rec.get('kind')} @ file+0x{rec['file_offset']:X}",
                  end="")
            if rec.get("mnemonic"):
                print(f" {rec['mnemonic']} {rec['operands']}", end="")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
