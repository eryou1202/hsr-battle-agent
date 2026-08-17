#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preprocess two bounded damage helpers for later semantic analysis.

Produces `data/raw/4.4.54/damage_helper_preprocess_14.json`.

This is mechanical extraction only. It does not assign gameplay semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402

sys.path.insert(0, str(HERE))
from semantic_batch_evidence import CODE_TABLE, NORMALIZED_BASE, disasm_window, load_pe  # noqa: E402
from global_static_writer_classifier import MethodIndex  # noqa: E402

REPO = HERE.parents[2]
OUTPUT = REPO / "data" / "raw" / "4.4.54" / "damage_helper_preprocess_14.json"

# Actual RVAs in this PE (the historical 0x195... / 0x19D... spellings are
# not section-mapped; the mapped forms below are used).
HELPERS = [
    {
        "key": "GOCKCOMLFEO",
        "method_index": 530155,
        "method_name": "GOCKCOMLFEO",
        "rva": 0x154B9420,
        "length": 0x1F8,
        "declaring_type_index": 57813,
    },
    {
        "key": "MortallyWondedProcess",
        "method_index": 504598,
        "method_name": "_MortallyWondedProcess",
        "rva": 0xE465660,
        "length": 0x7EC,
        "declaring_type_index": None,
    },
]

KNOWN_FIXEDPOINT_CALLS = {
    0x1D660C50: "fp_ge",
    0x1D6645B0: "fp_gt",
    0x1D669330: "fp_max",
    0x1D6693F0: "fp_min",
    0x1D65EF80: "fp_add_or_binary_unknown",
    0x1D661A00: "fp_binary_unknown",
    0x1D661B60: "fp_binary_unknown",
    0x1CAF14A0: "post_transform_helper",
    0x157559D0: "update_property_source_slot",
}


def reg_name(ins, reg):
    try:
        return ins.reg_name(reg)
    except Exception:
        return f"reg{reg}"


def mem_text(op) -> str:
    base = op.mem.base
    index = op.mem.index
    disp = op.mem.disp
    scale = op.mem.scale
    parts = []
    if base:
        parts.append(reg_name(None, base) if False else f"r{base}")
    # We will instead use capstone op_str for exact text.
    return f"mem(base={base},index={index},scale={scale},disp={disp:#x})"


def parse_rip_rva(comment: str):
    m = re.search(r"rva 0x([0-9A-Fa-f]+)", comment or "")
    if m:
        return int(m.group(1), 16)
    return None


def analyze_body(pe, mi, rva: int, length: int) -> dict:
    raw = pe.read_rva(rva, length)
    if raw is None:
        raise RuntimeError(f"cannot read body at 0x{rva:X}")
    body_hash = hashlib.sha256(raw).hexdigest()

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    dec = list(md.disasm(raw, pe.image_base + rva))

    rva_to_index = {start: idx for start, idx in zip(mi.rvas, mi.indices)}

    calls = []
    branches = []
    rets = []
    tail_transfers = []
    rip_globals = {}
    field_accesses = {}
    rax_writes = []
    instructions = []
    body_start = rva
    body_end = rva + length

    for ins in dec:
        ins_rva = ins.address - pe.image_base
        entry = {
            "rva": f"0x{ins_rva:X}",
            "mnemonic": ins.mnemonic,
            "op_str": ins.op_str,
            "bytes": ins.bytes.hex(" "),
            "comment": "",
        }
        # Build a RIP comment matching the existing disasm_window style.
        for op in ins.operands:
            if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
                target = ins.address + ins.size + op.mem.disp
                entry["comment"] = (
                    f" ; [rip]->0x{target:X} (rva 0x{target - pe.image_base:X})"
                )
                break
        instructions.append(entry)

        if ins.mnemonic == "call":
            target = None
            for op in ins.operands:
                if op.type == x86.X86_OP_IMM:
                    target = op.imm
                    break
            if target is not None:
                trva = target - pe.image_base
                calls.append({
                    "rva": f"0x{ins_rva:X}",
                    "target_rva": f"0x{trva:X}",
                    "target_va": f"0x{target:X}",
                    "method_index": rva_to_index.get(trva),
                    "known_fixedpoint": KNOWN_FIXEDPOINT_CALLS.get(trva),
                })

        if ins.mnemonic.startswith("j") or ins.mnemonic == "jmp":
            target = None
            for op in ins.operands:
                if op.type == x86.X86_OP_IMM:
                    target = op.imm
                    break
            branches.append({
                "rva": f"0x{ins_rva:X}",
                "mnemonic": ins.mnemonic,
                "target_rva": f"0x{target - pe.image_base:X}" if target is not None else None,
                "condition": ins.mnemonic if ins.mnemonic != "jmp" else "unconditional",
            })
            if ins.mnemonic == "jmp" and target is not None:
                trva = target - pe.image_base
                if not (body_start <= trva < body_end):
                    tail_transfers.append({
                        "rva": f"0x{ins_rva:X}",
                        "target_rva": f"0x{trva:X}",
                    })

        if ins.mnemonic == "ret":
            rets.append(f"0x{ins_rva:X}")

        rip_rva = parse_rip_rva(entry.get("comment", ""))
        if rip_rva is not None:
            rip_globals.setdefault(rip_rva, []).append(f"0x{ins_rva:X}")

        # Track register writes to rax/eax/al for return-value approximation.
        for op in ins.operands:
            if op.type == x86.X86_OP_REG and op.access & 2:
                rn = reg_name(ins, op.reg)
                if rn in ("rax", "eax", "al"):
                    rax_writes.append({"rva": f"0x{ins_rva:X}", "form": f"{ins.mnemonic} {ins.op_str}", "reg": rn})

            if op.type == x86.X86_OP_MEM and op.mem.base != x86.X86_REG_RIP:
                acc = int(getattr(op, "access", 0))
                access = "read" if acc == 1 else "write" if acc == 2 else "read-write" if acc == 3 else "unknown"
                text = f"{ins.mnemonic} {ins.op_str}"
                key = (text, access)
                field_accesses.setdefault(key, []).append(f"0x{ins_rva:X}")

    return_paths = []
    for r in rets:
        rv = int(r, 16)
        candidates = [w for w in rax_writes if int(w["rva"], 16) < rv]
        return_paths.append({
            "ret_rva": r,
            "last_rax_write": candidates[-1] if candidates else None,
        })
    for t in tail_transfers:
        return_paths.append({
            "tail_transfer_rva": t["rva"],
            "target_rva": t["target_rva"],
        })

    return {
        "identity": {
            "method_index": None,  # filled by caller
            "rva": f"0x{rva:X}",
            "body_length": length,
            "body_sha256": body_hash,
            "instruction_count": len(dec),
        },
        "instructions": instructions,
        "calls": calls,
        "fixedpoint_calls": [c for c in calls if c.get("known_fixedpoint")],
        "branches": branches,
        "rets": rets,
        "tail_transfers": tail_transfers,
        "return_paths": return_paths,
        "rax_writes": rax_writes,
        "rip_globals": {f"0x{k:X}": vs for k, vs in rip_globals.items()},
        "field_accesses": [
            {"form": form, "access": access, "rvAs": rvs}
            for (form, access), rvs in field_accesses.items()
        ],
    }


def store_windows_from_instructions(instructions: list[dict], stores: list[int],
                                    before: int = 10, after: int = 4) -> list[dict]:
    rvas = [int(i["rva"], 16) for i in instructions]
    out = []
    for srva in stores:
        idx = rvas.index(srva)
        window = instructions[max(0, idx - before):idx + after + 1]
        out.append({"store_rva": f"0x{srva:X}", "window": window})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, default=OUTPUT)
    args = ap.parse_args()

    pe = load_pe()
    mi = MethodIndex.from_code_table(pe, CODE_TABLE)
    report = {}

    for spec in HELPERS:
        key = spec["key"]
        body = analyze_body(pe, mi, spec["rva"], spec["length"])
        body["identity"]["method_index"] = spec["method_index"]
        body["identity"]["method_name"] = spec["method_name"]
        body["identity"]["declaring_type_index"] = spec["declaring_type_index"]
        body["identity"]["va"] = f"0x{pe.image_base + spec['rva']:X}"
        report[key] = body

    # Attach exact output-store windows for M504598.
    report["MortallyWondedProcess"]["output_stores"] = store_windows_from_instructions(
        report["MortallyWondedProcess"]["instructions"],
        [0xE465931, 0xE465A3F, 0xE465C61])

    # Global writer-probe summaries from the existing classifier (mechanical).
    report["GOCKCOMLFEO"]["writer_probe"] = {
        "data_rva": "0x95B1E18",
        "storage_classification": ["UNKNOWN"],
        "direct_writer_count": 0,
        "writer_initializer_candidate": None,
        "initialized_raw_value": "0xCC0A1BA48763671C",
        "disk_bytes": "1c 67 63 87 a4 1b 0a cc",
        "read_xref_count": 59,
        "static_constructor_readers": [
            {"method_index": 68317, "method_rva": "0x1D66D2E0", "runtime_type": "RPG.GameCore.FixVec2"},
            {"method_index": 68378, "method_rva": "0x1D670BE0", "runtime_type": "RPG.GameCore.FixVec3"},
        ],
        "note": "no direct writer found by the classifier; disk image only, no semantic meaning assigned",
    }
    report["optional_global_0x95C1CC0"] = {
        "data_rva": "0x95C1CC0",
        "storage_classification": ["DIRECT_RUNTIME_WRITTEN_GLOBAL", "STATIC_FIELD_BACKING"],
        "direct_writer_count": 1,
        "writer_initializer_candidate": {
            "method_index": 530122,
            "method_rva": "0x154B96E0",
            "runtime_type": "FJNAOAEPNJF",
            "direct_store_rva": "0x154B96FD",
            "instruction_form": "mov qword ptr [rip - 0xbef7a44], rax",
        },
        "initialized_raw_value": "0x1C95E9C65A78289C",
        "disk_bytes": "9c 28 78 5a c6 e9 95 1c",
        "read_xref_count": 3,
        "note": "mechanical initializer evidence only; no semantic name assigned",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")

    for key in ("GOCKCOMLFEO", "MortallyWondedProcess"):
        b = report[key]
        print(f"{key}: len={b['identity']['body_length']:#x} hash={b['identity']['body_sha256']}")
        print(f"  calls={len(b['calls'])} branches={len(b['branches'])} rets={len(b['rets'])} globals={len(b['rip_globals'])}")
        print(f"  call targets: {', '.join(c['target_rva'] for c in b['calls'][:20])}")
        print(f"  global rvas: {', '.join(b['rip_globals'].keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
