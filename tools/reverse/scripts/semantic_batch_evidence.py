#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared, read-only evidence helpers for battle semantic batch builders.

Small, explicit helpers only (not a decompiler framework):

  - normalized registry record streaming
  - manifest / PE / method-code-table facts
  - bounded capstone disassembly + body metrics
  - method identity / code-slot validation used by every E4 batch builder

Batch builders must not re-implement these locally.
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

NORMALIZED_BASE = REPO / "data" / "normalized" / "4.4.54"
CODE_TABLE = REPO / "data" / "parsed" / "4.4.54" / "method_code_table.bin"


def iter_records(path: Path):
    """Stream one JSON record per line from normalized registry files."""
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


def load_manifest() -> dict:
    return json.load((NORMALIZED_BASE / "manifest.json").open(encoding="utf-8"))


def load_pe() -> PeImage:
    manifest = load_manifest()
    return PeImage(Path(manifest["GameAssembly"]["path"]))


def disasm_window(pe: PeImage, rva: int, length: int):
    """Decode an exact byte window at `rva`.

    Returns ``(raw, decoded)`` where every decoded instruction is a small
    dict containing capstone fields plus local `rva` and a RIP comment.
    """
    off = pe.rva_to_file_offset(rva)
    if off is None:
        raise RuntimeError(f"RVA not mapped: 0x{rva:X}")
    raw = pe._read(off, length)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    decoded = []
    for ins in md.disasm(raw, pe.image_base + rva):
        comment = ""
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM:
                if op.mem.base == x86.X86_REG_RIP and op.mem.index == 0:
                    target = ins.address + ins.size + op.mem.disp
                    comment = (
                        f" ; [rip]->0x{target:X} (rva 0x{target - pe.image_base:X})"
                    )
                    break
        local = rva + (ins.address - (pe.image_base + rva))
        decoded.append(
            {
                "address": ins.address,
                "size": ins.size,
                "mnemonic": ins.mnemonic,
                "op_str": ins.op_str,
                "bytes": ins.bytes,
                "rva": local,
                "comment": comment,
            }
        )
    return raw, decoded


def line_for(ins) -> str:
    return (
        f"{ins['rva']:08X}  {bytes(ins['bytes']).hex(' '):<24}  "
        f"{ins['mnemonic']:8} {ins['op_str']}{ins['comment']}"
    )


def bounded_body_metrics(raw: bytes, decoded, rva: int, expected_length: int):
    """Metrics for a pre-bounded exact native body window.

    The caller has already recovered the true body end from a ``ret`` that
    terminates exactly at the window end (possibly preceded by alignment).
    This helper verifies that contract instead of silently mixing a following
    method into the body.
    """
    if not decoded:
        raise RuntimeError(f"no instructions decoded at 0x{rva:X}")
    if len(raw) != expected_length:
        raise RuntimeError(
            f"body window length {len(raw)} != expected {expected_length} at 0x{rva:X}"
        )
    if decoded[-1]["mnemonic"] != "ret":
        raise RuntimeError(
            f"bounded window does not end in ret at 0x{rva:X}: "
            f"{decoded[-1]['mnemonic']}"
        )
    last_end = decoded[-1]["rva"] + decoded[-1]["size"] - rva
    if last_end != expected_length:
        raise RuntimeError(
            f"final ret ends at +0x{last_end:X}, expected +0x{expected_length:X} "
            f"at 0x{rva:X}"
        )
    branch_count = sum(
        1
        for ins in decoded
        if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
    )
    call_count = sum(1 for ins in decoded if ins["mnemonic"] == "call")
    jmp_count = sum(1 for ins in decoded if ins["mnemonic"] == "jmp")
    return {
        "body_length": expected_length,
        "body_raw": raw,
        "body_insns": decoded,
        "instruction_count": len(decoded),
        "branch_count": branch_count,
        "call_count": call_count,
        "jmp_count": jmp_count,
    }


def read_code_slot(pe: PeImage, method_index: int) -> int:
    with CODE_TABLE.open("rb") as f:
        f.seek(method_index * 8)
        raw = f.read(8)
    if len(raw) != 8:
        raise RuntimeError(f"method code table too short for index {method_index}")
    return struct.unpack("<Q", raw)[0]


def validate_code_slot(pe: PeImage, method_index: int, rva: int) -> int:
    slot = read_code_slot(pe, method_index)
    expected_va = pe.image_base + rva
    if slot != expected_va:
        raise RuntimeError(
            f"method {method_index}: code table slot {slot:#x} != {expected_va:#x}"
        )
    return slot


def build_native_evidence(pe: PeImage, cand: dict, method: dict):
    """Assemble one E4 native-evidence block from an exact bounded window."""
    rva = cand["native_rva"]
    raw, decoded = disasm_window(pe, rva, cand["body_bytes"])
    metrics = bounded_body_metrics(raw, decoded, rva, cand["body_bytes"])
    slot = validate_code_slot(pe, cand["method_index"], rva)
    body_sha = hashlib.sha256(metrics["body_raw"]).hexdigest()
    return {
        "body_rva": f"0x{rva:X}",
        "body_length_bytes": metrics["body_length"],
        "body_sha256": body_sha,
        "code_table_slot_va": f"0x{slot:X}",
        "code_table_slot_index": cand["method_index"],
        "image_base": f"0x{pe.image_base:X}",
        "mapping_kind": method["mapping_kind"],
        "instruction_count": metrics["instruction_count"],
        "conditional_branch_count": metrics["branch_count"],
        "direct_call_count": metrics["call_count"],
        "direct_jump_count": metrics["jmp_count"],
        "abi": cand["abi"],
        "disassembly": [line_for(ins) for ins in metrics["body_insns"]],
    }


def load_registry_facts(
    type_indexes: set[int],
) -> tuple[dict[int, dict], list[dict], list[dict]]:
    """Load selected types, their methods and fields from normalized registry."""
    types: dict[int, dict] = {}
    methods: list[dict] = []
    fields: list[dict] = []
    for rec in iter_records(NORMALIZED_BASE / "types.json"):
        if rec["type_index"] in type_indexes:
            types[rec["type_index"]] = rec
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        if rec["declaring_type_index"] in type_indexes:
            methods.append(rec)
    for rec in iter_records(NORMALIZED_BASE / "fields.json"):
        if rec["declaring_type_index"] in type_indexes:
            fields.append(rec)
    return types, methods, fields


def load_parameter_refs(method_indexes: set[int]) -> dict[int, list[dict]]:
    """Load parameter relation rows for selected methods."""
    by_method: dict[int, list[dict]] = {mi: [] for mi in method_indexes}
    for rec in iter_records(NORMALIZED_BASE / "parameters.json"):
        mi = rec["method_index"]
        if mi in by_method:
            by_method[mi].append(rec)
    return by_method
