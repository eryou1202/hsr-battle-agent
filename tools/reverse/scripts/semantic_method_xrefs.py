#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrow reusable caller/xref helper for battle semantic batch builders.

This module does exactly one thing: turn a list of native method RVAs into a
small *bounded* caller graph fragment.  It reuses:

  - normalized method identity (``data/normalized/4.4.54/methods.json``)
  - normalized type identity for caller labels
  - the raw PE scanning primitives from ``find_method_xrefs.py``
  - ``semantic_batch_evidence.PeImage`` provenance facts

It deliberately does not build a full call graph, does not follow callees and
does not decompile: output is (target RVA -> caller method -> ref kind/site).
"""
from __future__ import annotations

import bisect
import json
import mmap
import re
import struct
from pathlib import Path

from find_method_xrefs import (
    LEA_RIP_RE,
    LEA_RIP_RE2,
    MOV_RIP_RE,
    classify_ref,
    section_for_file_offset,
)
from semantic_batch_evidence import NORMALIZED_BASE, iter_records
from resolve_il2cpp_get_api_table import PeImage

CALL_RE = re.compile(rb"[\xe8\xe9](?P<disp>.{4})", re.DOTALL)


def load_type_index() -> dict[int, dict]:
    """Return ``type_index -> {full_name, namespace, name}`` for every type."""
    out: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "types.json"):
        out[rec["type_index"]] = {
            "full_name": rec["full_name"],
            "namespace": rec["namespace"],
            "name": rec["name"],
        }
    return out


def load_method_rva_index() -> tuple[list[int], dict[int, dict]]:
    """Build an RVA-ordered index of DIRECT_NATIVE methods.

    ``rvas`` is sorted ascending; ``methods[rva]`` is the normalized method
    record.  A containing method for an interior site is found by the greatest
    method start <= site RVA and < the next method start (native methods do not
    overlap in this binary).
    """
    rvas: list[int] = []
    methods: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        rva = rec.get("native_rva")
        if not isinstance(rva, int) or rec.get("mapping_kind") != "DIRECT_NATIVE":
            continue
        methods[rva] = rec
        rvas.append(rva)
    rvas.sort()
    return rvas, methods


def method_for_site(
    site_rva: int, rvas: list[int], methods: dict[int, dict]
) -> dict | None:
    i = bisect.bisect_right(rvas, site_rva) - 1
    if i < 0:
        return None
    start = rvas[i]
    if i + 1 < len(rvas) and site_rva >= rvas[i + 1]:
        return None
    return {"method_start_rva": start, "method": methods[start]}


def _scan_sections(pe: PeImage, needle_family: str, target_vas: set[int]) -> list[dict]:
    """Single pass over executable sections for one RIP-relative family."""
    out: list[dict] = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if not sec.is_executable or sec.raw_size <= 0:
                continue
            data = raw[sec.raw_offset : sec.raw_offset + sec.raw_size]

            if needle_family == "call":
                for m in CALL_RE.finditer(data):
                    pos = sec.raw_offset + m.start()
                    if section_for_file_offset(pe, pos + 4) is None:
                        continue
                    insn_rva = sec.rva + m.start()
                    disp = struct.unpack("<i", m.group("disp"))[0]
                    dest_va = pe.image_base + insn_rva + 5 + disp
                    if dest_va not in target_vas:
                        continue
                    out.append({
                        **classify_ref(pe, pos, dest_va),
                        "_target_va": dest_va,
                        "kind": "rel32_branch",
                        "mnemonic": "call" if data[m.start()] == 0xE8 else "jmp",
                        "instruction_rva": f"0x{insn_rva:X}",
                    })

            elif needle_family == "lea":
                for pattern, kind in ((LEA_RIP_RE, "lea64_rip"),
                                      (LEA_RIP_RE2, "lea64_rip_r8")):
                    for m in pattern.finditer(data):
                        pos = sec.raw_offset + m.start()
                        insn_rva = sec.rva + m.start()
                        disp = struct.unpack("<i", m.group("disp"))[0]
                        dest_va = pe.image_base + insn_rva + 7 + disp
                        if dest_va not in target_vas:
                            continue
                        out.append({
                            **classify_ref(pe, pos, dest_va),
                            "_target_va": dest_va,
                            "kind": kind,
                            "instruction_rva": f"0x{insn_rva:X}",
                        })

            else:  # mov
                for m in MOV_RIP_RE.finditer(data):
                    pos = sec.raw_offset + m.start()
                    insn_rva = sec.rva + m.start()
                    for name in ("disp", "disp2", "disp3", "disp4", "disp5"):
                        if m.group(name) is None:
                            continue
                        disp = struct.unpack("<i", m.group(name))[0]
                        insn_len = 7 if name != "disp5" else 10
                        dest_va = pe.image_base + insn_rva + insn_len + disp
                        if dest_va not in target_vas:
                            continue
                        prefix = data[m.start() : m.start() + 2]
                        kind = (
                            "mov_load_rip"
                            if prefix[1] == 0x8B
                            else "mov_store_rip"
                        )
                        out.append({
                            **classify_ref(pe, pos, dest_va),
                            "_target_va": dest_va,
                            "kind": kind,
                            "instruction_rva": f"0x{insn_rva:X}",
                        })
        raw.close()
    return out


def build_caller_report(game: Path | str, target_rvas: list[int]) -> dict:
    """Scan one pass per reference family and attach caller identities."""
    if str(game).lower() == "manifest":
        from semantic_batch_evidence import load_pe

        pe = load_pe()
    else:
        pe = PeImage(Path(game))
    type_index = load_type_index()
    rvas, methods = load_method_rva_index()
    target_vas = {pe.image_base + rva for rva in target_rvas}
    rel32 = _scan_sections(pe, "call", target_vas)
    lea = _scan_sections(pe, "lea", target_vas)
    mov = _scan_sections(pe, "mov", target_vas)
    qword: list[dict] = []
    for rva in target_rvas:
        for ref in _scan_qword_refs_for_target(pe, pe.image_base + rva):
            ref["_target_va"] = pe.image_base + rva
            qword.append(ref)

    def decorate(refs: list[dict]) -> list[dict]:
        out = []
        for ref in refs:
            site = int(ref["instruction_rva"], 0)
            owner = method_for_site(site, rvas, methods)
            decorated = dict(ref)
            if owner is None:
                decorated["caller_method"] = None
                decorated["caller_type"] = None
            else:
                method = owner["method"]
                type_info = type_index.get(method["declaring_type_index"], {})
                decorated["caller_method"] = {
                    "method_index": method["method_index"],
                    "declaring_type_index": method["declaring_type_index"],
                    "name": method["name"],
                    "native_rva": f"0x{owner['method_start_rva']:X}",
                    "parameter_count": method["parameter_count"],
                    "return_type_reference": method["return_type_reference"],
                    "mapping_kind": method["mapping_kind"],
                }
                decorated["caller_type"] = type_info
            out.append(decorated)
        return out

    targets = []
    for rva in target_rvas:
        va = pe.image_base + rva
        branches = decorate([r for r in rel32 if r["_target_va"] == va])
        leas = decorate([r for r in lea if r["_target_va"] == va])
        movs = decorate([r for r in mov if r["_target_va"] == va])
        qrefs = decorate([r for r in qword if r["_target_va"] == va])
        targets.append({
            "native_rva": f"0x{rva:X}",
            "rel32_refs": branches,
            "lea_rip_refs": leas,
            "mov_rip_refs": movs,
            "qword_refs": qrefs,
            "ref_counts": {
                "rel32": len(branches),
                "lea_rip": len(leas),
                "mov_rip": len(movs),
                "qword": len(qrefs),
            },
        })

    return {
        "schema": "semantic_method_xrefs/1",
        "game": str(Path(pe.path).resolve()),
        "image_base": f"0x{pe.image_base:X}",
        "targets": targets,
    }


def _scan_qword_refs_for_target(pe: PeImage, target_va: int) -> list[dict]:
    """Exact aligned qword references (vtable / registry style)."""
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
                ref = classify_ref(pe, p, target_va)
                ref["instruction_rva"] = ref.get("rva", "0x0")
                out.append(ref)
            pos = p + 1
        raw.close()
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--rva", type=lambda x: int(x, 0), action="append",
                    required=True)
    ap.add_argument("--game", default="manifest")
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()
    report = build_caller_report(args.game, args.rva)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    for target in report["targets"]:
        print(
            f"{target['native_rva']}: rel32={target['ref_counts']['rel32']} "
            f"lea={target['ref_counts']['lea_rip']} "
            f"mov={target['ref_counts']['mov_rip']} "
            f"qword={target['ref_counts']['qword']}"
        )
