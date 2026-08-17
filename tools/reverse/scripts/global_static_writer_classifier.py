#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable global/static data-RVA writer and initializer classifier.

This is a narrow static PE/IL2CPP helper.  Given a writable data RVA in
GameAssembly.dll it produces deterministic machine-readable evidence about:

  * direct RIP-relative readers / writers / address references
  * enclosing registered native methods
  * absolute qword pointer/table references to the data slot
  * narrow one-hop indirect writer candidates
  * static constructor (``.cctor``) candidates
  * neutral classification values

It intentionally does not recover runtime values, does not execute code, and
does not guess gameplay semantics.
"""
from __future__ import annotations

import argparse
import bisect
import json
import mmap
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402

sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage, PeSection  # noqa: E402
from find_method_xrefs import LEA_RIP_RE, LEA_RIP_RE2, MOV_RIP_RE  # noqa: E402
from semantic_batch_evidence import CODE_TABLE, NORMALIZED_BASE, iter_records, load_manifest  # noqa: E402

SCHEMA = "global_static_writer_classifier/1"

# Neutral classification vocabulary from the task.  The tool only selects
# values supported by mechanical evidence.
CLASSIFICATION_VALUES = (
    "DIRECT_STATIC_SCALAR",
    "DIRECT_RUNTIME_WRITTEN_GLOBAL",
    "STATIC_FIELD_BACKING",
    "POINTER_TO_RUNTIME_OBJECT",
    "TABLE_ENTRY",
    "RELOCATION_INITIALIZED",
    "GENERATED_GLOBAL_CACHE",
    "INDIRECT_INITIALIZER",
    "UNKNOWN",
)

# Extra RIP-relative forms not covered by find_method_xrefs' core mov/lea
# patterns.  Each entry is (regex, instruction_length, kind).
EXTRA_RIP_PATTERNS: list[tuple[re.Pattern[bytes], int, str]] = [
    (re.compile(rb"\x8b[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})", re.DOTALL),
     6, "mov32_load_rip"),
    (re.compile(rb"\x89[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})", re.DOTALL),
     6, "mov32_store_rip"),
    # REX.W mov qword ptr [rip+disp32], imm32
    (re.compile(rb"\x48\xc7\x05(?P<disp>.{4}).{4}", re.DOTALL),
     11, "mov64_imm_store_rip"),
    # Common 64-bit read-modify-write / compare forms using RIP-relative memory.
    (re.compile(
        rb"\x48[\x01\x03\x09\x0b\x21\x23\x29\x2b\x31\x33\x39\x3b\x85]"
        rb"[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})", re.DOTALL),
     7, "rmw64_rip"),
    (re.compile(
        rb"\x4c[\x01\x03\x09\x0b\x21\x23\x29\x2b\x31\x33\x39\x3b\x85]"
        rb"[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})", re.DOTALL),
     7, "rmw64_rip"),
]


# ---------------------------------------------------------------------------
# Small PE-section helpers (raw-backed so tests can use synthetic bytes)
# ---------------------------------------------------------------------------

def section_at_rva(sections: list[PeSection], rva: int) -> PeSection | None:
    for s in sections:
        if s.rva <= rva < s.rva + s.size:
            return s
    return None


def section_for_file_offset(sections: list[PeSection], fo: int) -> PeSection | None:
    for s in sections:
        if s.raw_offset <= fo < s.raw_offset + s.raw_size:
            return s
    return None


def read_rva_bytes(raw, sections: list[PeSection], rva: int, size: int) -> bytes | None:
    s = section_at_rva(sections, rva)
    if s is None:
        return None
    off = s.raw_offset + (rva - s.rva)
    end = off + size
    if end > len(raw):
        return None
    return bytes(raw[off:end])


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def _ref_from_hit(raw, sections, image_base, target_va, sec, data, m,
                  insn_len: int, kind: str, disp: int) -> dict | None:
    pos = sec.raw_offset + m.start()
    insn_rva = sec.rva + m.start()
    dest_va = image_base + insn_rva + insn_len + disp
    if dest_va != target_va:
        return None
    ctx_start = max(0, pos - 8)
    ctx_end = min(len(raw), pos + 32)
    ctx = bytes(raw[ctx_start:ctx_end])
    return {
        "instruction_rva": f"0x{insn_rva:X}",
        "rva": f"0x{insn_rva:X}",
        "file_offset": pos,
        "section": sec.name,
        "section_flags": {
            "executable": bool(sec.is_executable),
            "writable": bool(getattr(sec, "is_writable", False)),
        },
        "kind": kind,
        "reference_class": "direct",
        "context_hex": ctx.hex(" "),
        "context_ascii": "".join(chr(b) if 32 <= b <= 126 else "." for b in ctx),
    }


def scan_rip_refs(raw, sections: list[PeSection], image_base: int,
                  target_rva: int) -> list[dict]:
    """Return all common RIP-relative references to ``target_rva``.

    Operates on raw bytes (or an mmap object) and section metadata only, so it
    is deterministic and unit-testable without opening a real PE file.
    """
    target_va = image_base + target_rva
    out: list[dict] = []

    for sec in sections:
        if not sec.is_executable or sec.raw_size <= 0:
            continue
        data = raw[sec.raw_offset:sec.raw_offset + sec.raw_size]

        # LEA forms (existing reusable patterns).
        for pattern, kind in ((LEA_RIP_RE, "lea64_rip"),
                              (LEA_RIP_RE2, "lea64_rip_r8")):
            for m in pattern.finditer(data):
                disp = struct.unpack("<i", m.group("disp"))[0]
                ref = _ref_from_hit(raw, sections, image_base, target_va,
                                    sec, data, m, 7, kind, disp)
                if ref is not None:
                    out.append(ref)

        # Core 64-bit mov forms (existing reusable pattern).
        for m in MOV_RIP_RE.finditer(data):
            # Avoid the known false start when the same bytes are part of
            # `48 C7 05 ...` (REX.W mov qword ptr [rip], imm32).  The extra
            # pattern below handles that form from its true start.
            if (m.lastgroup == "disp5" and m.start() > 0
                    and data[m.start() - 1] == 0x48):
                continue
            for name in ("disp", "disp2", "disp3", "disp4", "disp5"):
                if m.group(name) is None:
                    continue
                disp = struct.unpack("<i", m.group(name))[0]
                insn_len = 7 if name != "disp5" else 10
                ref = _ref_from_hit(raw, sections, image_base, target_va,
                                    sec, data, m, insn_len, "mov_rip", disp)
                if ref is not None:
                    out.append(ref)
                break

        # Extra 32-bit / REX.W immediate / RMW forms.
        for pattern, insn_len, kind in EXTRA_RIP_PATTERNS:
            for m in pattern.finditer(data):
                # A bare 32-bit mov must not be reported when it is actually
                # the ModRM byte of a REX.W 64-bit mov (`48 8b` / `48 89`).
                if kind in ("mov32_load_rip", "mov32_store_rip"):
                    if m.start() > 0 and 0x40 <= data[m.start() - 1] <= 0x4F:
                        continue
                disp = struct.unpack("<i", m.group("disp"))[0]
                ref = _ref_from_hit(raw, sections, image_base, target_va,
                                    sec, data, m, insn_len, kind, disp)
                if ref is not None:
                    out.append(ref)

    # Deterministic order: file offset order per section.
    out.sort(key=lambda r: (r["section"], r["file_offset"], r["kind"]))
    return out


def scan_qword_refs(raw, sections: list[PeSection], image_base: int,
                    target_rva: int) -> list[dict]:
    """Return aligned absolute qword references to ``image_base + target_rva``."""
    target_va = image_base + target_rva
    needle = struct.pack("<Q", target_va)
    out: list[dict] = []
    pos = 0
    while True:
        p = raw.find(needle, pos)
        if p < 0:
            break
        sec = section_for_file_offset(sections, p)
        if sec is not None and p % 8 == (sec.raw_offset % 8):
            rva = sec.rva + (p - sec.raw_offset)
            ctx_start = max(0, p - 8)
            ctx_end = min(len(raw), p + 32)
            ctx = bytes(raw[ctx_start:ctx_end])
            out.append({
                "rva": f"0x{rva:X}",
                "file_offset": p,
                "section": sec.name,
                "section_flags": {
                    "executable": bool(sec.is_executable),
                    "writable": bool(getattr(sec, "is_writable", False)),
                },
                "kind": "absolute_qword_pointer",
                "reference_class": "indirect",
                "context_hex": ctx.hex(" "),
                "context_ascii": "".join(chr(b) if 32 <= b <= 126 else "." for b in ctx),
            })
        pos = p + 1
    out.sort(key=lambda r: (r["section"], r["file_offset"]))
    return out


# ---------------------------------------------------------------------------
# Instruction decoding / access classification
# ---------------------------------------------------------------------------

def decode_instruction(raw, sections: list[PeSection], image_base: int,
                       rva: int) -> dict | None:
    code = read_rva_bytes(raw, sections, rva, 16)
    if code is None:
        return None
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    ins = next(md.disasm(code, image_base + rva), None)
    if ins is None:
        return None
    mem_access: str | None = None
    for op in ins.operands:
        if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
            acc = int(getattr(op, "access", 0))
            if acc == 1:
                mem_access = "read"
            elif acc == 2:
                mem_access = "write"
            elif acc == 3:
                mem_access = "read-write"
            break
    if ins.mnemonic == "lea":
        mem_access = "address"
    return {
        "mnemonic": ins.mnemonic,
        "op_str": ins.op_str,
        "bytes": ins.bytes.hex(" "),
        "size": ins.size,
        "access": mem_access,
        "instruction_form": f"{ins.mnemonic} {ins.op_str}",
    }


def enrich_rip_refs(raw, sections: list[PeSection], image_base: int,
                    refs: list[dict]) -> list[dict]:
    out = []
    for ref in refs:
        rva = int(ref["instruction_rva"], 0)
        ins = decode_instruction(raw, sections, image_base, rva)
        if ins is not None:
            ref["mnemonic"] = ins["mnemonic"]
            ref["op_str"] = ins["op_str"]
            ref["instruction_form"] = ins["instruction_form"]
            ref["access"] = ins["access"] or (
                "address" if ins["mnemonic"] == "lea" else "read")
        else:
            ref["instruction_form"] = ref.get("kind", "")
            ref["access"] = "read"
        out.append(ref)
    return out


def split_refs(refs: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    reads = [r for r in refs if r.get("access") == "read"]
    writes = [r for r in refs if r.get("access") in ("write", "read-write")]
    addresses = [r for r in refs if r.get("access") == "address"]
    return reads, writes, addresses


# ---------------------------------------------------------------------------
# Registered method interval index
# ---------------------------------------------------------------------------

class MethodIndex:
    """Sorted registered native-method start index for site -> method mapping."""

    def __init__(self, rvas: list[int], indices: list[int]):
        self.rvas = rvas
        self.indices = indices

    @classmethod
    def from_code_table(cls, pe: PeImage, code_table_path: Path) -> "MethodIndex":
        import numpy as np

        arr = np.fromfile(code_table_path, dtype="<u8")
        mask = arr != 0
        rvas = (arr[mask].astype(np.int64) - pe.image_base).astype(np.int64)
        idxs = np.flatnonzero(mask)
        order = np.argsort(rvas, kind="stable")
        return cls(rvas[order].tolist(), idxs[order].tolist())

    @classmethod
    def from_normalized_methods(cls, methods_path: Path) -> "MethodIndex":
        rvas: list[int] = []
        indices: list[int] = []
        for rec in iter_records(methods_path):
            rva = rec.get("native_rva")
            if isinstance(rva, int):
                rvas.append(rva)
                indices.append(int(rec["method_index"]))
        order = sorted(range(len(rvas)), key=lambda i: rvas[i])
        return cls([rvas[i] for i in order], [indices[i] for i in order])

    def for_site(self, site_rva: int) -> dict | None:
        if not self.rvas:
            return None
        i = bisect.bisect_right(self.rvas, site_rva) - 1
        if i < 0:
            return None
        start = self.rvas[i]
        if i + 1 < len(self.rvas) and site_rva >= self.rvas[i + 1]:
            return None
        return {
            "method_start_rva": start,
            "method_index": self.indices[i],
            "offset_from_start": site_rva - start,
        }


def load_method_and_type_metadata(method_indices: set[int]) -> tuple[dict[int, dict], dict[int, dict]]:
    if not method_indices:
        return {}, {}
    methods: dict[int, dict] = {}
    type_indices: set[int] = set()
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        mi = rec.get("method_index")
        if mi in method_indices:
            methods[mi] = rec
            type_indices.add(rec.get("declaring_type_index"))
    types: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "types.json"):
        ti = rec.get("type_index")
        if ti in type_indices:
            types[ti] = rec
    return methods, types


# ---------------------------------------------------------------------------
# Decoration
# ---------------------------------------------------------------------------

def decorate_ref(ref: dict, method_index: MethodIndex | None,
                 methods_meta: dict[int, dict],
                 types_meta: dict[int, dict]) -> dict:
    out = dict(ref)
    site = int(ref["instruction_rva"], 0)
    if method_index is None:
        out["enclosing_method"] = None
        out["method_index"] = None
        return out
    owner = method_index.for_site(site)
    if owner is None:
        out["enclosing_method"] = None
        out["method_index"] = None
        return out
    rec = methods_meta.get(owner["method_index"])
    if rec is None:
        out["enclosing_method"] = {
            "method_start_rva": f"0x{owner['method_start_rva']:X}",
            "method_index": owner["method_index"],
            "offset_from_start": f"0x{owner['offset_from_start']:X}",
            "name": None,
            "declaring_type_index": None,
            "declaring_type": None,
        }
        out["method_index"] = owner["method_index"]
        return out
    type_rec = types_meta.get(rec.get("declaring_type_index"), {})
    out["enclosing_method"] = {
        "method_start_rva": f"0x{owner['method_start_rva']:X}",
        "method_index": rec["method_index"],
        "offset_from_start": f"0x{owner['offset_from_start']:X}",
        "name": rec.get("name"),
        "declaring_type_index": rec.get("declaring_type_index"),
        "declaring_type": type_rec.get("full_name"),
        "mapping_kind": rec.get("mapping_kind"),
    }
    out["method_index"] = rec["method_index"]
    return out


# ---------------------------------------------------------------------------
# Indirect one-hop candidates
# ---------------------------------------------------------------------------

def _loaded_register(ins: dict) -> str | None:
    # Only a simple `mov reg, qword ptr [rip+...]` / `mov reg, dword ptr [rip+...]`
    # is treated as a pointer load.  LEA yields an address, not a loaded value.
    if ins.get("mnemonic") != "mov":
        return None
    m = re.match(r"^mov\s+([a-z0-9]+),", ins.get("instruction_form", ""))
    return m.group(1) if m else None


def _find_store_through_register(raw, sections, image_base, start_rva: int,
                                 reg: str, max_bytes: int = 64) -> dict | None:
    code = read_rva_bytes(raw, sections, start_rva, max_bytes)
    if code is None:
        return None
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for ins in md.disasm(code, image_base + start_rva):
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM and op.mem.base != x86.X86_REG_RIP:
                base_name = ins.reg_name(op.mem.base) if op.mem.base != 0 else None
                if base_name == reg:
                    acc = int(getattr(op, "access", 0))
                    if acc & 2:  # write or read-write through the loaded pointer
                        return {
                            "rva": ins.address - image_base,
                            "instruction_form": f"{ins.mnemonic} {ins.op_str}",
                            "access": "write" if acc == 2 else "read-write",
                        }
        if ins.address + ins.size - (image_base + start_rva) >= max_bytes:
            break
    return None


def find_indirect_writer_candidates(raw, sections, image_base, qword_refs,
                                    method_index, methods_meta, types_meta,
                                    max_pointer_sources: int = 64) -> list[dict]:
    out: list[dict] = []
    for qr in qword_refs[:max_pointer_sources]:
        ptr_slot_rva = int(qr["rva"], 0)
        ptr_refs = scan_rip_refs(raw, sections, image_base, ptr_slot_rva)
        ptr_refs = enrich_rip_refs(raw, sections, image_base, ptr_refs)
        for pref in ptr_refs:
            if pref.get("access") != "read":
                continue
            ins_form = pref.get("instruction_form", "")
            reg = _loaded_register({"mnemonic": pref.get("mnemonic"),
                                    "instruction_form": ins_form})
            if reg is None:
                continue
            site_rva = int(pref["instruction_rva"], 0)
            store = _find_store_through_register(
                raw, sections, image_base,
                site_rva + int(pref.get("size", 7)), reg)
            if store is None:
                continue
            decorated = decorate_ref(pref, method_index, methods_meta, types_meta)
            out.append({
                "source_global_rva": qr["rva"],
                "source_section": qr["section"],
                "pointer_load_rva": pref["instruction_rva"],
                "pointer_load_form": ins_form,
                "indirect_store_rva": f"0x{store['rva']:X}",
                "indirect_store_form": store["instruction_form"],
                "indirect_store_access": store["access"],
                "enclosing_method": decorated.get("enclosing_method"),
                "method_index": decorated.get("method_index"),
            })
    return out


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def _target_info(raw, sections, image_base, data_rva: int) -> dict:
    sec = section_at_rva(sections, data_rva)
    if sec is None:
        return {
            "data_rva": f"0x{data_rva:X}",
            "data_va": f"0x{image_base + data_rva:X}",
            "section": None,
            "section_flags": None,
            "file_offset": None,
            "disk_raw_qword": None,
            "disk_bytes": None,
            "mapped": False,
        }
    file_offset = sec.raw_offset + (data_rva - sec.rva)
    raw_qword = None
    # Some protected builds have file bytes past the nominal section raw_size
    # (e.g. .data virtual tail).  The known raw qword is still on disk, so read
    # it whenever the file itself contains the bytes.
    if file_offset >= 0 and file_offset + 8 <= len(raw):
        raw_qword = struct.unpack("<Q", bytes(raw[file_offset:file_offset + 8]))[0]
    return {
        "data_rva": f"0x{data_rva:X}",
        "data_va": f"0x{image_base + data_rva:X}",
        "section": sec.name,
        "section_flags": {
            "executable": bool(sec.is_executable),
            "writable": bool(getattr(sec, "is_writable", False)),
        },
        "file_offset": f"0x{file_offset:X}",
        "disk_raw_qword": f"0x{raw_qword:016X}" if raw_qword is not None else None,
        "disk_bytes": raw_qword.to_bytes(8, "little").hex(" ") if raw_qword is not None else None,
        "mapped": True,
    }


def _method_ref(method: dict | None) -> dict | None:
    if method is None:
        return None
    return {
        "method_index": method.get("method_index"),
        "name": method.get("name"),
        "native_rva": method.get("native_rva") or method.get("method_start_rva"),
        "declaring_type": method.get("declaring_type"),
        "declaring_type_index": method.get("declaring_type_index"),
        "mapping_kind": method.get("mapping_kind"),
    }


def build_report(
    *,
    game_path: str,
    image_base: int,
    raw,
    sections: list[PeSection],
    data_rva: int,
    method_index: MethodIndex | None,
    methods_meta: dict[int, dict],
    types_meta: dict[int, dict],
    game_sha256: str | None = None,
    version: str | None = None,
    relocations: list[dict] | None = None,
    rip_refs: list[dict] | None = None,
) -> dict:
    relocations = relocations or []

    target = _target_info(raw, sections, image_base, data_rva)
    if rip_refs is None:
        refs = scan_rip_refs(raw, sections, image_base, data_rva)
        refs = enrich_rip_refs(raw, sections, image_base, refs)
    else:
        refs = rip_refs
    read_refs, write_refs, address_refs = split_refs(refs)

    read_refs = [decorate_ref(r, method_index, methods_meta, types_meta) for r in read_refs]
    write_refs = [decorate_ref(r, method_index, methods_meta, types_meta) for r in write_refs]
    address_refs = [decorate_ref(r, method_index, methods_meta, types_meta) for r in address_refs]

    qword_refs = scan_qword_refs(raw, sections, image_base, data_rva)
    indirect = find_indirect_writer_candidates(
        raw, sections, image_base, qword_refs,
        method_index, methods_meta, types_meta)

    # Static constructor candidates: any registered .cctor that mechanically
    # touches this data slot.
    cctor_candidates: list[dict] = []
    seen_cctors: set[int] = set()
    for ref in read_refs + write_refs + address_refs:
        owner = ref.get("enclosing_method")
        if not owner or owner.get("name") != ".cctor":
            continue
        mi = owner.get("method_index")
        if mi in seen_cctors:
            continue
        seen_cctors.add(mi)
        cctor_candidates.append({
            "runtime_type": owner.get("declaring_type"),
            "declaring_type_index": owner.get("declaring_type_index"),
            "method_index": mi,
            "method_rva": owner.get("method_start_rva"),
            "method_name": ".cctor",
            "evidence": "registered .cctor contains a direct RIP-relative access to this data RVA",
        })

    # Initializer candidates: direct writers first, then indirect writer sites.
    initializer_candidates: list[dict] = []
    seen_init: set[tuple] = set()
    for w in write_refs:
        owner = w.get("enclosing_method")
        key = (w.get("method_index"), w["instruction_rva"])
        if key in seen_init:
            continue
        seen_init.add(key)
        initializer_candidates.append({
            "candidate_method": _method_ref(owner),
            "method_index": w.get("method_index"),
            "rva": w["instruction_rva"],
            "reason": "direct RIP-relative write/read-modify-write to target data RVA",
            "classification": "DIRECT_RUNTIME_WRITTEN_GLOBAL",
            "confidence": "HIGH" if owner is not None else "MEDIUM",
            "evidence_level": "E4_DIRECT_WRITE",
            "instruction_form": w.get("instruction_form"),
        })
    for ind in indirect:
        owner = ind.get("enclosing_method")
        key = ("indirect", ind.get("method_index"), ind["indirect_store_rva"])
        if key in seen_init:
            continue
        seen_init.add(key)
        initializer_candidates.append({
            "candidate_method": _method_ref(owner),
            "method_index": ind.get("method_index"),
            "rva": ind["indirect_store_rva"],
            "reason": "one-hop pointer load from source global then store through loaded pointer",
            "classification": "INDIRECT_INITIALIZER",
            "confidence": "MEDIUM" if owner is not None else "LOW",
            "evidence_level": "E4_INDIRECT_WRITE",
            "instruction_form": ind.get("indirect_store_form"),
            "source_global_rva": ind.get("source_global_rva"),
        })

    classification: list[str] = []
    if write_refs:
        classification.append("DIRECT_RUNTIME_WRITTEN_GLOBAL")
        if any("imm" in w.get("kind", "") for w in write_refs):
            classification.append("DIRECT_STATIC_SCALAR")
        if any((w.get("enclosing_method") or {}).get("name") == ".cctor"
               for w in write_refs):
            classification.append("STATIC_FIELD_BACKING")
    if qword_refs:
        # Absolute pointers to the target are mechanical table/object-pointer
        # evidence.  Prefer TABLE_ENTRY when the pointer lives in a writable
        # data section, otherwise POINTER_TO_RUNTIME_OBJECT.
        if any(q.get("section_flags", {}).get("writable") for q in qword_refs):
            classification.append("TABLE_ENTRY")
        else:
            classification.append("POINTER_TO_RUNTIME_OBJECT")
    if relocations:
        classification.append("RELOCATION_INITIALIZED")
    if indirect:
        classification.append("INDIRECT_INITIALIZER")
    if not classification:
        classification.append("UNKNOWN")

    next_inspection: list[dict] = []
    for w in write_refs:
        next_inspection.append({
            "rva": w["instruction_rva"],
            "kind": "direct_write",
            "reason": w.get("instruction_form", ""),
            "method_index": w.get("method_index"),
            "method_name": (w.get("enclosing_method") or {}).get("name"),
        })
    for ind in indirect:
        next_inspection.append({
            "rva": ind["indirect_store_rva"],
            "kind": "indirect_write",
            "reason": ind.get("indirect_store_form", ""),
            "method_index": ind.get("method_index"),
            "method_name": (ind.get("enclosing_method") or {}).get("name"),
            "source_global_rva": ind.get("source_global_rva"),
        })
    for c in cctor_candidates:
        next_inspection.append({
            "rva": c["method_rva"],
            "kind": "static_constructor",
            "reason": ".cctor touches target data RVA",
            "method_index": c["method_index"],
            "method_name": c["method_name"],
        })
    for q in qword_refs:
        next_inspection.append({
            "rva": q["rva"],
            "kind": "pointer_source",
            "reason": "absolute qword pointer to target data RVA",
            "method_index": None,
            "method_name": None,
        })
    if not write_refs and not indirect:
        for r in read_refs[:50]:
            next_inspection.append({
                "rva": r["instruction_rva"],
                "kind": "read_consumer",
                "reason": r.get("instruction_form", ""),
                "method_index": r.get("method_index"),
                "method_name": (r.get("enclosing_method") or {}).get("name"),
            })
    # Deterministic ordering: rank by kind, then RVA.
    rank = {
        "direct_write": 0,
        "indirect_write": 1,
        "static_constructor": 2,
        "pointer_source": 3,
        "read_consumer": 4,
    }
    next_inspection.sort(key=lambda x: (rank.get(x["kind"], 99), int(x["rva"], 0)))

    return {
        "schema": SCHEMA,
        "game": game_path,
        "game_sha256": game_sha256,
        "version": version,
        "image_base": f"0x{image_base:X}",
        "target": target,
        "read_xrefs": read_refs,
        "write_xrefs": write_refs,
        "address_xrefs": address_refs,
        "qword_refs": qword_refs,
        "indirect_initialization_candidates": indirect,
        "initializer_candidates": initializer_candidates,
        "static_constructor_candidates": cctor_candidates,
        "relocations": relocations,
        "normalized_metadata": {
            "mapping_found": False,
            "note": "normalized field metadata does not expose a data-RVA mapping for this tool",
        },
        "counts": {
            "read_xrefs": len(read_refs),
            "write_xrefs": len(write_refs),
            "address_xrefs": len(address_refs),
            "qword_refs": len(qword_refs),
            "indirect_writer_candidates": len(indirect),
            "initializer_candidates": len(initializer_candidates),
            "static_constructor_candidates": len(cctor_candidates),
        },
        "classification": classification,
        "next_inspection": next_inspection,
    }


# ---------------------------------------------------------------------------
# PE relocation directory helper (bounded, read-only)
# ---------------------------------------------------------------------------

def scan_relocations_for_rva(pe: PeImage, data_rva: int) -> list[dict]:
    reloc_rva, reloc_size = pe.data_directories[5]
    if reloc_rva == 0 or reloc_size == 0:
        return []
    out: list[dict] = []
    off = pe.rva_to_file_offset(reloc_rva)
    if off is None:
        return []
    end_off = off + reloc_size
    while off + 8 <= end_off:
        block = pe._read(off, 8)
        if len(block) != 8:
            break
        page_rva, block_size = struct.unpack("<II", block)
        if block_size < 8 or off + block_size > end_off:
            break
        entries = (block_size - 8) // 2
        for i in range(entries):
            entry_off = off + 8 + i * 2
            raw = pe._read(entry_off, 2)
            if len(raw) != 2:
                break
            val = struct.unpack("<H", raw)[0]
            typ = val >> 12
            slot = page_rva + (val & 0xFFF)
            if slot == data_rva:
                out.append({
                    "rva": f"0x{slot:X}",
                    "type": typ,
                    "type_name": {
                        0: "ABSOLUTE",
                        3: "HIGHLOW",
                        10: "DIR64",
                    }.get(typ, f"UNKNOWN_{typ}"),
                    "block_rva": f"0x{page_rva:X}",
                })
        off += block_size
    out.sort(key=lambda r: int(r["rva"], 0))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_pe(gameassembly: str) -> PeImage:
    if gameassembly.lower() == "manifest":
        manifest = load_manifest()
        return PeImage(Path(manifest["GameAssembly"]["path"]))
    return PeImage(Path(gameassembly))


def _resolve_sha256(pe: PeImage) -> str | None:
    try:
        manifest = load_manifest()
        if Path(manifest["GameAssembly"]["path"]).resolve() == Path(pe.path).resolve():
            return manifest["GameAssembly"]["sha256"]
    except Exception:
        pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Classify global/static data-RVA writers and initializers in GameAssembly.dll")
    ap.add_argument("--gameassembly", default="manifest",
                    help="Path to GameAssembly.dll, or 'manifest' to use normalized manifest")
    ap.add_argument("--data-rva", required=True, type=lambda x: int(x, 0),
                    help="Target .data RVA, e.g. 0x95B1E80")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--code-table", type=Path, default=None,
                    help="Path to method_code_table.bin (default: parsed 4.4.54 table)")
    ap.add_argument("--normalized-base", type=Path, default=None,
                    help="Path to normalized JSON directory (default: data/normalized/4.4.54)")
    args = ap.parse_args()

    global NORMALIZED_BASE
    if args.normalized_base is not None:
        NORMALIZED_BASE = Path(args.normalized_base)

    pe = _resolve_pe(args.gameassembly)
    default_code_table = (
        NORMALIZED_BASE.parents[1] / "parsed" / NORMALIZED_BASE.name / "method_code_table.bin"
        if NORMALIZED_BASE.parent.name == "normalized" else CODE_TABLE
    )
    code_table_path = args.code_table or default_code_table
    if not Path(code_table_path).exists():
        # Fall back to the normalized methods stream; slower but version-flexible.
        method_index = MethodIndex.from_normalized_methods(NORMALIZED_BASE / "methods.json")
    else:
        method_index = MethodIndex.from_code_table(pe, Path(code_table_path))

    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            # First pass: collect method indices touched by direct references.
            refs = scan_rip_refs(raw, pe.sections, pe.image_base, args.data_rva)
            refs = enrich_rip_refs(raw, pe.sections, pe.image_base, refs)
            touched: set[int] = set()
            for ref in refs:
                site = int(ref["instruction_rva"], 0)
                owner = method_index.for_site(site)
                if owner is not None:
                    touched.add(owner["method_index"])
            methods_meta, types_meta = load_method_and_type_metadata(touched)

            relocations = scan_relocations_for_rva(pe, args.data_rva)
            report = build_report(
                game_path=str(Path(pe.path).resolve()),
                image_base=pe.image_base,
                raw=raw,
                sections=pe.sections,
                data_rva=args.data_rva,
                method_index=method_index,
                methods_meta=methods_meta,
                types_meta=types_meta,
                game_sha256=_resolve_sha256(pe),
                version=NORMALIZED_BASE.name,
                relocations=relocations,
                rip_refs=refs,
            )
        finally:
            raw.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")

    c = report["counts"]
    print(f"wrote {args.output}")
    print(f"target 0x{args.data_rva:X}: reads={c['read_xrefs']} "
          f"writes={c['write_xrefs']} address={c['address_xrefs']} "
          f"qword={c['qword_refs']} indirect={c['indirect_writer_candidates']} "
          f"cctor={c['static_constructor_candidates']}")
    print("classification=" + ",".join(report["classification"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
