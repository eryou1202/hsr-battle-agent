#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Map RPG.GameCore.SkillConfig.FromBinary optional-field branches to metadata
field names.

Generated parser shape (4.4.54):
  * two ULEB128 field-presence bitfields are read into rbx / r14;
  * 64 bits of rbx are tested first, then 13 bits of r14 (77 fields);
  * each bit block writes exactly one SkillConfig object field, in metadata
    FieldDefinition declaration order.

This tool:
  * disassembles SkillConfig.FromBinary (method index located by type+name);
  * enumerates `test`/`bt` bit checks in code order and maps ordinal -> bit;
  * captures the first `[rdi+disp]` object-field access per block when the
    generated code uses that shape;
  * joins ordinal to the CONFIRMED FieldDefinition registry by name.

Output is field-name evidence for the SkillConfig parser; it does not decode
field payloads or battle semantics.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vendor" / "capstone"))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402
from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from analyze_mhy_method_candidate import RULES, FIELD_NAME_CONST  # noqa: E402
from analyze_mhy_field_candidate import RULES as FIELD_RULES  # noqa: E402
from build_method_code_registry import (  # noqa: E402
    M32,
    scalar_method_hash32,
    resolve_type_name,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

TYPE_NAME = "RPG.GameCore.SkillConfig"
METHOD_NAME = "FromBinary"
MAX_FUNCTION = 0x4000


RULES_ALL = {**RULES, **FIELD_RULES}


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    out = {}
    for field, (op, const) in RULES_ALL.items():
        raw = struct.unpack_from("<I", block, field)[0]
        if op == "add":
            val = (raw + const) & M32
        else:
            val = raw ^ const
        out[field] = FILE_HEADER + signed32(val)
    return out


def reg_name(ins, reg: int) -> str:
    return ins.reg_name(reg).lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--version", default="4.4.54")
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    pe = PeImage(args.game)
    tpl = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    offs = table_offsets(pe, tpl)
    tbase = offs[0x84]
    tnext = offs[0x38]
    mbase = offs[0x14C]
    mnext = offs[0x160]
    fbase = offs[0x20]
    ntypes = (tnext - tbase) // 70
    nmethods = (mnext - mbase) // 26
    region_base = offs[0x1B4]

    size = args.metadata.stat().st_size
    with open(args.metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        target_ti = None
        target_mi = None
        for ti in range(ntypes):
            if resolve_type_name(mm, tbase, ti, region) != TYPE_NAME:
                continue
            mstart = (struct.unpack_from("<I", mm, tbase + ti * 70 + 0x08)[0]
                      ^ 0x1A7AF5FE) & M32
            mstart = mstart - 0x100000000 if mstart & 0x80000000 else mstart
            mcount = (struct.unpack_from("<H", mm, tbase + ti * 70 + 0x34)[0]
                      + 0x5F93) & 0xFFFF
            for mi in range(mstart, mstart + mcount):
                h32 = scalar_method_hash32(mi)
                raw_name = struct.unpack_from("<I", mm, mbase + mi * 26)[0]
                name_key = (h32 ^ raw_name ^ FIELD_NAME_CONST) & M32
                name, _ = resolve_identifier(name_key, region)
                if name.decode("utf-8", "replace") == METHOD_NAME:
                    target_ti = ti
                    target_mi = mi
                    break
            break
        if target_mi is None:
            raise SystemExit(f"type/method not found: {TYPE_NAME}.{METHOD_NAME}")

        fstart = (struct.unpack_from("<I", mm, tbase + target_ti * 70 + 0x20)[0]
                  + 0x8B7AC79C) & M32
        fcount = (struct.unpack_from("<H", mm, tbase + target_ti * 70 + 0x32)[0]
                  + 0x444D) & 0xFFFF
        raw_fstart = struct.unpack_from("<I", mm, tbase + target_ti * 70 + 0x20)[0]
        roll0 = (0xAD416BB9 - (raw_fstart * 0x2C5DCB00 & M32)) & M32
        fields = []
        for fi in range(fstart, fstart + fcount):
            local = fi - fstart
            roll = (roll0 + local * 0xD3A23500) & M32
            raw_name, raw_type = struct.unpack_from("<II", mm, fbase + fi * 8)
            name_key = (raw_name + roll + 0x2AAFC785) & M32
            name, _ = resolve_identifier(name_key, region)
            fields.append({
                "field_index": fi,
                "ordinal": local,
                "name": name.decode("utf-8", "replace"),
                "type_reference": (raw_type + roll) & M32,
            })
        q = struct.unpack("<Q", pe.read_rva(args.code_table_rva + target_mi * 8, 8))[0]
        method_rva = q - pe.image_base
        mm.close()

    raw = pe.read_rva(method_rva, MAX_FUNCTION)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    insns = list(md.disasm(raw, pe.image_base + method_rva))

    allowed = ("rbx", "ebx", "bx", "bl", "r14", "r14d", "r14w", "r14b")
    by_addr = {ins.address: ins for ins in insns}
    reg_constants = {}
    raw_checks = {}
    for ins in insns:
        if ins.address - pe.image_base > method_rva + 0x3800:
            break
        if ins.mnemonic in ("movabs", "mov") and len(ins.operands) == 2:
            dst, src = ins.operands
            if (dst.type == x86.X86_OP_REG and src.type == x86.X86_OP_IMM):
                reg_constants[reg_name(ins, dst.reg)] = int(src.imm)
        if ins.mnemonic not in ("test", "bt") or len(ins.operands) < 2:
            continue
        dst, src = ins.operands
        if dst.type != x86.X86_OP_REG:
            continue
        reg = reg_name(ins, dst.reg)
        if reg not in allowed:
            continue
        if src.type == x86.X86_OP_IMM:
            imm = int(src.imm)
        elif src.type == x86.X86_OP_REG:
            imm = reg_constants.get(reg_name(ins, src.reg))
            # `test rbx,rbx` followed by js tests the sign bit (bit 63).
            if imm is None and ins.mnemonic == "test" and reg in ("rbx", "ebx") \
                    and reg_name(ins, src.reg) in ("rbx", "ebx"):
                imm = 1 << 63
        else:
            imm = None
        if imm is None:
            continue
        if ins.mnemonic == "bt":
            bit = imm
        else:
            if imm <= 0 or (imm & (imm - 1)) != 0:
                continue
            bit = imm.bit_length() - 1
        # Find the generated conditional branch right after the check. With
        # `jcc next_check` (first bitfield) the branch target is the next
        # check; with `jcc field_block` (second bitfield / sign bit) the next
        # check is the fall-through instruction.
        nxt = None
        fallthrough = None
        for later in insns:
            if later.address <= ins.address:
                continue
            if later.address - ins.address > 24:
                break
            if later.mnemonic.startswith("j"):
                op = later.operands[0]
                if op.type == x86.X86_OP_IMM:
                    nxt = int(op.imm) - pe.image_base
                fallthrough = later.address + later.size - pe.image_base
                break
        raw_checks[ins.address - pe.image_base] = {
            "bit": bit,
            "register": reg,
            "check_rva": ins.address - pe.image_base,
            "next_check_rva": nxt,
            "fallthrough_rva": fallthrough,
        }

    # Follow the conditional-branch chain: this yields the true 77 checks in
    # serialized field order even though some blocks are laid out-of-line.
    def chain_from(head: int) -> list[dict]:
        out = []
        visited = set()
        cur = head
        while cur is not None and cur in raw_checks and cur not in visited:
            visited.add(cur)
            out.append(raw_checks[cur])
            nxt = raw_checks[cur]["next_check_rva"]
            if nxt not in raw_checks:
                nxt = raw_checks[cur]["fallthrough_rva"]
            cur = nxt
        return out

    checks = []
    for head in sorted(raw_checks):
        candidate = chain_from(head)
        if len(candidate) > len(checks):
            checks = candidate

    rows = []
    for i, check in enumerate(checks):
        next_rva = check["next_check_rva"]
        if next_rva in raw_checks:
            # First-bitfield shape: absent-bit branch -> next check; the
            # present-bit field block is the fall-through range.
            start = check["fallthrough_rva"]
            end = next_rva
            branch_out = False
        else:
            # Second-bitfield / sign-bit shape: present-bit branch -> field
            # block; absent bit falls through to the next check.
            start = next_rva
            end = check["fallthrough_rva"]
            branch_out = True
        offset = None
        store_target = None
        calls = []
        for ins in insns:
            rva = ins.address - pe.image_base
            if start is None or rva <= start:
                continue
            if not branch_out and end is not None and rva >= end:
                break
            if branch_out and (ins.mnemonic in ("ret", "jmp") or ins.address - pe.image_base > start + 0x400):
                if ins.mnemonic == "jmp":
                    op = ins.operands[0]
                    if op.type == x86.X86_OP_IMM:
                        calls.append(int(op.imm) - pe.image_base)
                break
            if offset is None and ins.mnemonic in ("add", "lea"):
                for op in ins.operands:
                    if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RDI:
                        offset = op.mem.disp
                        break
            if store_target is None and ins.mnemonic.startswith("mov"):
                for op in ins.operands:
                    if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RDI:
                        store_target = op.mem.disp
                        break
            if ins.mnemonic in ("call", "jmp"):
                op = ins.operands[0]
                if op.type == x86.X86_OP_IMM:
                    calls.append(int(op.imm) - pe.image_base)
            if ins.mnemonic == "ret":
                break
        row = {
            "ordinal": i,
            "bit": check["bit"],
            "bitfield_register": check["register"],
            "check_rva": f"0x{check['check_rva']:X}",
            "field_offset_candidate": hex(offset) if offset is not None else None,
            "field_store_offset_candidate": (hex(store_target)
                                              if store_target is not None else None),
            "parser_calls": [f"0x{r:X}" for r in calls[:6]],
        }
        if i < len(fields):
            row.update({
                "field_index": fields[i]["field_index"],
                "field_name": fields[i]["name"],
                "type_reference": fields[i]["type_reference"],
            })
        else:
            row.update({"field_index": None, "field_name": None,
                        "type_reference": None})
        rows.append(row)

    result = {
        "schema": "skillconfig_field_map/1",
        "game_version": args.version,
        "type": TYPE_NAME,
        "method": METHOD_NAME,
        "method_index": target_mi,
        "method_rva": f"0x{method_rva:X}",
        "field_start": fstart,
        "field_count": fcount,
        "bit_check_count": len(checks),
        "field_map": rows,
        "semantic_status": "branch order = metadata field declaration order "
                           "(validated against known offsets Name=+0x10, "
                           "UsableConditions=+0x158, VisibleCondition=+0x160, "
                           "ChildSkillList=+0x168)",
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out} checks={len(checks)} fields={fcount}")
    for r in rows:
        if r.get("field_name") in ("Name", "UsableConditions", "VisibleCondition",
                                    "ChildSkillList", "InsertCondition"):
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
