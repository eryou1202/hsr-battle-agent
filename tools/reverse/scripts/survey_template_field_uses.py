#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Survey every template-field arithmetic use near payload/template xrefs."""
import json, re, sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor" / "capstone"))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone import x86
sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_il2cpp_get_api_table import PeImage

FILE_HEADER = 0x208
RE_LOAD = re.compile(r"^mov (\w+), (?:qword|dword) ptr \[rip \+ 0x[0-9a-f]+\]$")
RE_LEA = re.compile(r"^lea (\w+), \[rip \+ 0x[0-9a-f]+\]$")
RE_MOV_IMM = re.compile(r"^mov (\w\w\w), 0x([0-9a-f]+)$")
RE_ADD_FIELD = re.compile(r"^add (\w\w\w), dword ptr \[(\w+) \+ 0x([0-9a-f]+)\]$")
RE_MOVSXD = re.compile(r"^movsxd (\w+), (\w\w\w)$")
RE_ADD64 = re.compile(r"^add (\w+), (\w+)$")
RE_READ4 = re.compile(r"^mov \w+, dword ptr \[(\w+) \+ (\w+)\*(\d+)\]$")
RE_READ8 = re.compile(r"^mov \w+, qword ptr \[(\w+) \+ (\w+)\*(\d+)\]$")


def canon(reg):
    if reg in ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"):
        return "r" + reg[1:]
    if reg.endswith("d") and reg[:-1] in ("r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"):
        return reg[:-1]
    return reg


def target_rva(insn, image_base):
    for op in insn.operands:
        if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
            return insn.address + insn.size + op.mem.disp - image_base
    return None


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("xref_json")
    ap.add_argument("game")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    xrefs = json.load(open(args.xref_json, encoding="utf-8"))
    pe = PeImage(Path(args.game))
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    globals_ = {name: v["rva"] for name, v in xrefs["anchors"].items()}
    interesting = list(globals_.keys())
    sites = {}
    for name in interesting:
        for h in xrefs["rip_relative_hits"].get(name, []):
            if h.get("rva"):
                sites.setdefault(h["rva"], set()).add(name)
    seen = set()
    rows = []
    for rva, names in sorted(sites.items()):
        off = pe.rva_to_file_offset(rva)
        raw = pe._read(off, 0x80)
        insns = list(md.disasm(raw, pe.image_base + rva))
        # register -> global kind
        reg_global = {}
        for insn in insns:
            m = RE_LOAD.match(f"{insn.mnemonic} {insn.op_str}") or RE_LEA.match(f"{insn.mnemonic} {insn.op_str}")
            if m:
                reg = canon(m.group(1))
                tgt = target_rva(insn, pe.image_base)
                if tgt in globals_.values():
                    gname = next(n for n, v in globals_.items() if v == tgt)
                    reg_global[reg] = gname
        if not reg_global:
            continue
        tpl = next((r for r, g in reg_global.items() if "template" in g), None)
        pay = next((r for r, g in reg_global.items() if "payload" in g), None)
        last_imm = {}
        for i, insn in enumerate(insns):
            t = f"{insn.mnemonic} {insn.op_str}"
            m = RE_MOV_IMM.match(t)
            if m:
                last_imm[canon(m.group(1))] = int(m.group(2), 16)
                continue
            m = RE_ADD_FIELD.match(t)
            if not m or m.group(2) not in reg_global:
                continue
            base_name = reg_global[m.group(2)]
            r32 = canon(m.group(1)); field = int(m.group(3), 16)
            imm = last_imm.get(r32)
            if imm is None:
                continue
            # follow chain; payload register may be absent in this window
            r64 = None
            for j in range(i + 1, min(i + 8, len(insns))):
                m2 = RE_MOVSXD.match(f"{insns[j].mnemonic} {insns[j].op_str}")
                if m2 and canon(m2.group(2)) == r32:
                    r64 = m2.group(1); break
            base_ok = False
            if r64 is not None and pay is not None:
                for j in range(i + 1, min(i + 10, len(insns))):
                    m2 = RE_ADD64.match(f"{insns[j].mnemonic} {insns[j].op_str}")
                    if m2 and m2.group(1) == r64 and m2.group(2) == pay:
                        base_ok = True; break
            entry = None
            if base_ok:
                for j in range(i + 1, min(i + 14, len(insns))):
                    tj = f"{insns[j].mnemonic} {insns[j].op_str}"
                    m2 = RE_READ4.match(tj) or RE_READ8.match(tj)
                    if m2 and m2.group(1) == r64:
                        entry = int(m2.group(3)); break
            key = (base_name, field, imm)
            if key in seen:
                continue
            seen.add(key)
            rawval = struct.unpack_from("<I", pe.read_rva(0x47BA958, 0x208), field)[0]
            dec = (rawval + imm) & 0xFFFFFFFF
            signed = dec - 0x100000000 if dec & 0x80000000 else dec
            rows.append({
                "global_name": base_name,
                "template_field": f"0x{field:X}", "add_const": f"0x{imm:X}",
                "template_raw": f"0x{rawval:X}", "decoded": f"0x{dec:X}",
                "file_offset": f"0x{FILE_HEADER + signed:X}", "entry_size": entry,
                "first_site_rva": f"0x{rva:X}",
            })
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"schema": "mhy_template_field_survey/1", "rows": rows}, f, indent=2)
    print(f"wrote {args.output}; rows={len(rows)}")
    for r in sorted(rows, key=lambda x: int(x["template_field"], 16)):
        print(r)


if __name__ == "__main__":
    main()
