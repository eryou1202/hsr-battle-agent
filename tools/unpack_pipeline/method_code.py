# -*- coding: utf-8 -*-
"""STAGE 7 - METHOD_CODE_REGISTRY.

Static recovery of the MethodDefinition -> native RVA mapping:

    native_rva = qword(code_table + method_index * 8)   ; 0 == no direct body

The locator is the pure-Python engineering adapter of
`tools/reverse/scripts/build_method_code_registry.py`.  It locates the code
table with structural + semantic anchors and validates the consumer byte
pattern without requiring Capstone.  Capstone is used opportunistically for
human-readable sample disassembly when present.
"""
from __future__ import annotations

import json
import mmap
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np

from .common import PeImage, REPO_ROOT, utc_now, write_json
from .mhy_core import MhyModel, signed32

CONSUMER_NEEDLE = bytes.fromhex("4e8b24f04d85e4")
METHOD_INDEX_MARKERS = (bytes.fromhex("fef57a1a"), bytes.fromhex("935f0000"))
ANCHORS = {
    4: bytes.fromhex("4889c8c3"),   # Locale.GetText(string)
    16: bytes.fromhex("488b01c3"),  # Mono.RuntimeClassHandle.get_Value
    18: bytes.fromhex("8b01c3"),    # Mono.RuntimeClassHandle.GetHashCode
    22: bytes.fromhex("488911c3"),  # Mono.RuntimeGenericParamInfoHandle.ctor
}

try:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "reverse" / "vendor" / "capstone"))
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # type: ignore  # noqa: E402
    CAPSTONE = True
except Exception:  # pragma: no cover - optional enrichment
    CAPSTONE = False


# ---------------------------------------------------------------------------
# Minimal x86-64 decoder for the two instructions directly before the consumer
# needle.  This is intentionally narrow and does not replace the historical
# Capstone evidence; it only lets the pipeline re-derive the field offset.
# ---------------------------------------------------------------------------

def _parse_mov_r64_mem_ending(data: bytes, end: int) -> dict[str, Any] | None:
    """Parse a `mov r64, [r/m64]` instruction whose bytes end at `end`."""
    for start in range(max(0, end - 12), max(0, end - 1)):
        raw = data[start:end]
        if len(raw) < 3:
            continue
        i = 0
        rex = 0
        if 0x40 <= raw[0] <= 0x4F:
            rex = raw[0]
            i = 1
        if i + 1 >= len(raw) or raw[i] != 0x8B:
            continue
        modrm = raw[i + 1]
        i += 2
        mod = (modrm >> 6) & 3
        reg = ((modrm >> 3) & 7) | (8 if rex & 0x04 else 0)
        rm = modrm & 7
        if mod == 3:
            continue
        sib = None
        base_reg = None
        if rm == 4:
            if i >= len(raw):
                continue
            sib = raw[i]
            i += 1
            base_reg = (sib & 7) | (8 if rex & 0x01 else 0)
        else:
            base_reg = rm | (8 if rex & 0x01 else 0)
        disp_len = {0: 0, 1: 1, 2: 4}[mod]
        if mod == 0 and ((rm == 5) or (rm == 4 and base_reg == 5)):
            disp_len = 4
        if i + disp_len != len(raw):
            continue
        disp = int.from_bytes(raw[i:i + disp_len], "little", signed=True)
        rip_relative = (mod == 0 and ((rm == 5) or (rm == 4 and base_reg == 5)))
        return {
            "start": start,
            "size": len(raw),
            "dst_reg": reg,
            "base_reg": 0x29 if rip_relative else base_reg,  # X86_REG_RIP = 0x29
            "disp": disp,
            "rip_relative": rip_relative,
        }
    return None


def _find_consumer(pe: PeImage) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    with open(pe.path, "rb") as fh:
        raw = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        for section in pe.sections:
            if not section.is_executable or section.name == ".upx0" or section.raw_size <= 0:
                continue
            data = raw[section.raw_offset: section.raw_offset + section.raw_size]
            pos = 0
            while True:
                p = data.find(CONSUMER_NEEDLE, pos)
                if p < 0:
                    break
                hit_rva = section.rva + p
                field_load = _parse_mov_r64_mem_ending(data, p)
                if field_load is not None and field_load["rip_relative"]:
                    field_load = None
                global_load = None
                if field_load is not None:
                    global_load = _parse_mov_r64_mem_ending(
                        data, p - field_load["size"])
                    if global_load is not None and not global_load["rip_relative"]:
                        global_load = None
                nearby_start = max(0, p - 96)
                nearby = data[nearby_start: p + 96]
                markers_present = all(marker in nearby for marker in METHOD_INDEX_MARKERS)
                if field_load is None:
                    pos = p + 1
                    continue
                if global_load is not None:
                    global_rva = (section.rva + p - field_load["size"]
                                  + global_load["disp"])
                else:
                    global_rva = None
                hits.append({
                    "consumer_rva": f"0x{hit_rva:X}",
                    "consumer_needle": CONSUMER_NEEDLE.hex(" "),
                    "field_load_bytes": data[p - field_load["size"]: p].hex(" "),
                    "global_load_bytes": (data[p - field_load["size"] - global_load["size"]:
                                                p - field_load["size"]].hex(" ")
                                           if global_load else None),
                    "registry_pointer_global_rva": f"0x{global_rva:X}" if global_rva is not None else None,
                    "registry_code_table_field_offset": field_load["disp"],
                    "method_index_markers_present": markers_present,
                })
                pos = p + 1
        raw.close()
    return hits


def _find_absolute_refs(pe: PeImage, table_rva: int) -> list[int]:
    va = pe.image_base + table_rva
    needle = struct.pack("<Q", va)
    refs: list[int] = []
    with open(pe.path, "rb") as fh:
        raw = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        pos = 0
        while True:
            p = raw.find(needle, pos)
            if p < 0:
                break
            for section in pe.sections:
                if section.raw_offset <= p < section.raw_offset + section.raw_size:
                    refs.append(section.rva + p - section.raw_offset)
                    break
            pos = p + 1
        raw.close()
    return refs


def _executable_pointer_runs(pe: PeImage, min_len: int) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    exec_names = {s.name for s in pe.sections if s.is_executable}
    with open(pe.path, "rb") as fh:
        raw = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        arr = rvas = valid = d = starts = ends = lengths = None
        try:
            for section in pe.sections:
                if section.raw_size < min_len * 8 or section.raw_offset % 8:
                    continue
                count = section.raw_size // 8
                try:
                    arr = np.frombuffer(raw, dtype="<u8", count=count, offset=section.raw_offset)
                except (TypeError, ValueError):
                    arr = None
                    continue
                rvas = arr - pe.image_base
                valid = arr == 0
                for s in pe.sections:
                    if s.name not in exec_names:
                        continue
                    end = s.rva + max(s.raw_size, getattr(s, "vsize", 0))
                    valid |= (rvas >= s.rva) & (rvas < end)
                d = np.diff(valid.astype(np.int8), prepend=0, append=0)
                starts = np.nonzero(d == 1)[0]
                ends = np.nonzero(d == -1)[0]
                lengths = ends - starts
                for gi in np.nonzero(lengths >= min_len)[0]:
                    st = int(starts[gi])
                    en = int(ends[gi])
                    runs.append({
                        "section": section.name,
                        "rva": section.rva + st * 8,
                        "length": int(en - st),
                        "nulls": int((arr[st:en] == 0).sum()),
                    })
                arr = rvas = valid = d = starts = ends = lengths = None
        finally:
            arr = rvas = valid = d = starts = ends = lengths = None
            raw.close()
    return runs


def _field_offset_candidates(consumer: dict[str, Any] | None) -> list[int]:
    if consumer and consumer.get("registry_code_table_field_offset") is not None:
        return [int(consumer["registry_code_table_field_offset"])]
    return list(range(0, 0x88, 8))


def _locate_code_table(pe: PeImage, method_count: int,
                       consumer: dict[str, Any] | None) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for run in _executable_pointer_runs(pe, method_count):
        max_offset = min(0x80, (run["length"] - method_count) * 8)
        for off in range(0, max_offset + 1, 8):
            table_rva = run["rva"] + off
            head = pe.read_rva(table_rva, 64)
            if head is None:
                continue
            first4_zero = all(struct.unpack_from("<Q", head, i * 8)[0] == 0 for i in range(4))
            anchor_hits: dict[str, bool] = {}
            for idx, signature in ANCHORS.items():
                raw = pe.read_rva(table_rva + idx * 8, 8)
                if raw is None:
                    continue
                q = struct.unpack("<Q", raw)[0]
                rva = q - pe.image_base
                section = pe.section_at_rva(rva)
                if q == 0 or section is None or not section.is_executable:
                    continue
                code = pe.read_rva(rva, max(4, len(signature)))
                if code and code[: len(signature)] == signature:
                    anchor_hits[str(idx)] = True
            struct_hits: list[int] = []
            for ref_rva in _find_absolute_refs(pe, table_rva):
                for field_off in _field_offset_candidates(consumer):
                    struct_start = ref_rva - field_off
                    if struct_start < 0:
                        continue
                    block = pe.read_rva(struct_start, max(0x100, field_off + 8))
                    if block is None or len(block) <= field_off:
                        continue
                    if struct.unpack_from("<Q", block, field_off)[0] == pe.image_base + table_rva:
                        struct_hits.append(struct_start)
                        break
            score = 0
            if first4_zero:
                score += 100
            if struct_hits:
                score += 200
            if anchor_hits:
                score += 50 * len(anchor_hits)
            if run["length"] - off // 8 >= method_count:
                score += 50
            if score:
                candidates.append({
                    "code_table_rva": table_rva,
                    "score": score,
                    "first_4_slots_zero": first4_zero,
                    "semantic_anchor_hits": anchor_hits,
                    "registry_struct_rvas": struct_hits,
                    "run": run,
                })
            if anchor_hits and struct_hits and first4_zero:
                break
        if candidates and candidates[-1]["score"] >= 500:
            break
    if not candidates:
        raise RuntimeError("no plausible method code table found")
    candidates.sort(key=lambda c: -c["score"])
    best = candidates[0]
    return {
        "code_table_rva": best["code_table_rva"],
        "score": best["score"],
        "first_4_slots_zero": best["first_4_slots_zero"],
        "semantic_anchor_hits": best["semantic_anchor_hits"],
        "registry_struct_rvas": best["registry_struct_rvas"],
        "run": best["run"],
        "candidate_count": len(candidates),
        "best_candidate": {
            "code_table_rva": best["code_table_rva"],
            "score": best["score"],
        },
    }


def _disasm_first(pe: PeImage, rva: int, max_insns: int = 6) -> list[str]:
    if not CAPSTONE:
        return []
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    raw = pe.read_rva(rva, 32)
    if not raw:
        return []
    out = []
    for ins in md.disasm(raw, pe.image_base + rva):
        out.append(f"{ins.mnemonic} {ins.op_str}")
        if len(out) >= max_insns:
            break
    return out


def _mapping_kind(q: int, slot: int, first_bytes: bytes, asm_lines: list[str]) -> str:
    if q != 0:
        if asm_lines and asm_lines[0].startswith("jmp"):
            return "THUNK"
        if first_bytes and (first_bytes[0] == 0xE9 or first_bytes[0] == 0xEB
                            or first_bytes[:2] == b"\xff\x25"):
            return "THUNK"
        return "DIRECT_NATIVE"
    return "VIRTUAL_VTABLE" if slot >= 0 else "NO_BODY"


def build_registry(model: MhyModel, output_dir: Path,
                   consumer_override: dict[str, Any] | None = None) -> dict[str, Any]:
    pe = model.pe
    n = model.nmethods
    consumer = consumer_override or (sorted(
        _find_consumer(pe), key=lambda c: c["method_index_markers_present"], reverse=True)[:1] or [None])[0]
    locator = _locate_code_table(pe, n, consumer)
    table_rva = locator["code_table_rva"]
    raw_table = pe.read_rva(table_rva, n * 8)
    if raw_table is None or len(raw_table) != n * 8:
        raise RuntimeError(f"code table at 0x{table_rva:X} does not cover {n} methods")
    ptrs = np.frombuffer(raw_table, dtype="<u8", count=n)

    null_mask = ptrs == 0
    nonnull = int((~null_mask).sum())
    unique = len(set(int(q) for q in ptrs if q != 0))
    bad = 0
    sections: dict[str, int] = {}
    for i, q in enumerate(ptrs):
        if q == 0:
            continue
        rva = int(q - pe.image_base)
        section = pe.section_at_rva(rva)
        if section is None or not section.is_executable:
            bad += 1
            continue
        sections[section.name] = sections.get(section.name, 0) + 1
    virtual = int((model.m_slot14 >= 0).sum())
    no_body = int(null_mask.sum()) - virtual
    duplicate = nonnull - unique

    sample_indices = sorted(set(list(range(min(24, n))) + [89, 96, 516, 632, 656, 769, 784, 804, 821, 839, 854]))[:80]
    samples = []
    for mi in sample_indices:
        if mi >= n:
            continue
        q = int(ptrs[mi])
        slot = int(model.m_slot14[mi])
        native_rva = q - pe.image_base if q else None
        first_bytes = b""
        asm_lines: list[str] = []
        if native_rva is not None:
            raw = pe.read_rva(native_rva, 32) or b""
            first_bytes = raw[:16]
            asm_lines = _disasm_first(pe, native_rva)
        samples.append({
            "method_index": mi,
            "declaring_type": model.type_name(int(model.m_declaring_type[mi])),
            "method_name": model.identifier(int(model.m_name_key[mi])),
            "mapping_kind": _mapping_kind(q, slot, first_bytes, asm_lines),
            "slot_0x14": slot,
            "native_rva": f"0x{native_rva:X}" if native_rva is not None else None,
            "native_section": pe.section_at_rva(native_rva).name if native_rva is not None and pe.section_at_rva(native_rva) else None,
            "first_bytes": first_bytes.hex(" ") if first_bytes else "",
            "first_instructions": asm_lines,
        })

    checks = {
        "table_slots_equal_method_defs": bool(nonnull + int(null_mask.sum()) == n),
        "all_nonnull_point_to_executable_section": bad == 0,
        "all_nonnull_unique": duplicate == 0,
        "consumer_found": consumer is not None,
        "consumer_method_index_markers_present": bool(consumer and consumer.get("method_index_markers_present")),
        "registry_struct_reference_found": bool(locator["registry_struct_rvas"]),
        "semantic_anchor_hits_present": bool(locator["semantic_anchor_hits"]),
    }
    status = "METHOD_CODE = RVA_REGISTRY_PROOF" if all(checks.values()) else "METHOD_CODE = PARTIAL_MAPPING_RECOVERED"

    result: dict[str, Any] = {
        "schema": "unpack_pipeline_method_code_registry/1",
        "generated_at": utc_now(),
        "status": status,
        "method_definition": {
            "table_field": "0x14C",
            "entry_size": 26,
            "record_count": n,
        },
        "mapping_rule": {
            "native_rva": "qword(code_table + method_index * 8)",
            "null_slot_semantic": "no direct native body; see mapping_kind",
            "consumer": consumer,
            "locator": {
                "code_table_rva": f"0x{table_rva:X}",
                "score": locator["score"],
                "first_4_slots_zero": locator["first_4_slots_zero"],
                "semantic_anchor_hits": locator["semantic_anchor_hits"],
                "registry_struct_rvas": [f"0x{r:X}" for r in locator["registry_struct_rvas"]],
                "candidate_count": locator["candidate_count"],
            },
        },
        "statistics": {
            "total_method_defs": n,
            "table_slots": n,
            "null_slots": int(null_mask.sum()),
            "direct_native_slots": nonnull,
            "virtual_vtable_slots": virtual,
            "no_direct_body_slots": no_body,
            "unique_native_rvas": unique,
            "duplicate_native_pointer_slots": duplicate,
            "out_of_range_nonnull_slots": bad,
            "native_sections": sections,
        },
        "classification": {
            "DIRECT_NATIVE": "slot < 0 and code_table[method_index] != 0",
            "VIRTUAL_VTABLE": "slot >= 0; direct table entry is 0",
            "NO_BODY": "slot < 0 and code_table[method_index] == 0",
            "THUNK": "first instruction is a direct jump; stable entry RVA only",
        },
        "samples": samples,
        "checks": checks,
        "evidence_level": "E3 structural + E4 consumer/code-table evidence (Capstone optional)",
    }
    write_json(output_dir / "method_code_registry.json", result)
    # Raw qword table for downstream tools; JSON keeps only statistics/samples.
    raw_path = output_dir / "method_code_table.bin"
    raw_path.write_bytes(raw_table)
    result["_raw_table_path"] = str(raw_path)
    return result
