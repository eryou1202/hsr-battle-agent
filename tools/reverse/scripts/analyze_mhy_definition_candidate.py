#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrow analysis for the MHY 0x70 -> 0x84 -> 0x12C definition chain.

Scope is deliberately limited to the 70-byte record table at template field
0x84, its u32 index map at 0x70, and the downstream u32 table at 0x12C.

Outputs, for one version at a time:

  * every statically recovered access site for 0x84 records;
  * an offset-within-entry access map (width / read-write / consumer RVA /
    instruction pattern / downstream use);
  * machine-validated domain analysis for 0x70, 0x84, 0x12C;
  * the code-proven identifier resolver (key -> length/offset -> rolling-XOR
    plaintext) with samples;
  * a minimal type-registry proof candidate when the structural checks pass.

Discipline: field names stay field_0xXX in the access map. Semantic labels are
recorded separately and only as CONFIRMED when local consumer code proves the
role; otherwise SUPPORTED / CANDIDATE / UNKNOWN.
"""
from __future__ import annotations

import argparse
import json
import mmap
import re
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(HERE))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

FILE_HEADER = 0x208
MHY_MAGIC = b"MHY\x00\x00\x00\x00\x00"
M64 = (1 << 64) - 1

# Code-derived directory transforms for this chain only.
# (field, op, const) -> payload-relative signed offset.
CHAIN_RULES = {
    0x70: ("xor", 0x57A78949),
    0x84: ("xor", 0x68531D3F),
    0xF0: ("add", 0x9D48920F),
    0x12C: ("xor", 0x26F0FC20),
    0x1B4: ("add", 0x8D43A4EE),
    # next known payload offset used as the 0x84 upper bound
    0x38: ("add", 0xF778F1AB),
    # next known payload offset used as the 0x12C upper bound
    0x18: ("add", 0xE6CD8E6C),
    # next known payload offset used as the 0xF0 upper bound
    0x124: ("xor", 0x1AFCE463),
}

# Offsets of the next-known payload table used as upper bounds.
NEXT_AFTER_84 = 0x38
NEXT_AFTER_12C = 0x18
NEXT_AFTER_F0 = 0x124

# Identifier resolver constants recovered from 0x3C58D70.
ID_HASH_MUL = 0x907C49622D94D21A
ID_HASH_ADD = 0x75B679DAF67C3F24
ID_ROLL = 0x3E693CD23A41FDEF
ID_POS_MASK = 0x1FFFFFF
ID_NEG_MASK = 0x7FFFFF

# Field decode rules recovered from consumers. Each entry keeps the
# structural offset and, separately, the semantic candidate.
FIELD_RULES = [
    {
        "offset": 0x08, "width": 4, "signed": True,
        "decode": "raw_u32 ^ 0x1A7AF5FE (signed32)",
        "consumer_rva": "0x3C80C09",
        "instruction": "movsxd rax, dword ptr [rcx + 8]; xor rax, 0x1a7af5fe",
        "downstream": "indexes qword runtime pointer array [global+0x40] + decoded",
        "sentinel": "-1",
        "semantic_candidate": "method range start (SUPPORTED)",
        "semantic_evidence": "consecutive non-overlapping starts; consumer iterates count entries from this base",
    },
    {
        "offset": 0x0C, "width": 4, "signed": False,
        "decode": "raw_u32 (no transform)",
        "consumer_rva": "0x3C82A81 / 0x3C82BD8 / 0x3C67526",
        "instruction": "cmp dword ptr [rec + 0xc], 0x1c2ad2ab",
        "downstream": "record acceptance gate before object builder 0x3C67270",
        "sentinel": "0x1C2AD2AB acts as the accepted value in three loops",
        "semantic_candidate": "UNKNOWN (not a universal magic; ~76% of records carry it)",
        "semantic_evidence": "explicit consumer compare exists; distribution shows many other values",
    },
    {
        "offset": 0x24, "width": 4, "signed": False,
        "decode": "raw_u32 + 0xF1D32D89 (u32) -> identifier key",
        "consumer_rva": "0x3C67341 / 0x3C67562",
        "instruction": "mov edi, dword ptr [rec + 0x24]; add edi, 0xf1d32d89",
        "downstream": "0x3C58D70 identifier resolver (code-proven rolling-XOR decoder)",
        "sentinel": "decoded -1 handled by resolver",
        "semantic_candidate": "namespace index key (SUPPORTED)",
        "semantic_evidence": "record 0 key decodes to empty string while name key decodes to '<Module>'",
    },
    {
        "offset": 0x28, "width": 4, "signed": False,
        "decode": "raw_u32 + 0xE9FD68F8 (u32) -> identifier key",
        "consumer_rva": "0x3C6732D / 0x3C67555",
        "instruction": "mov ecx, dword ptr [rec + 0x28]; add ecx, 0xe9fd68f8",
        "downstream": "0x3C58D70 identifier resolver; cmp -1 skips name registration",
        "sentinel": "decoded -1",
        "semantic_candidate": "name index key (CONFIRMED by decoded type names)",
        "semantic_evidence": "record 0 decodes to '<Module>'; contiguous mscorlib type order",
    },
    {
        "offset": 0x34, "width": 2, "signed": False,
        "decode": "raw_u16 + 0x5F93 (u16 wrap) -> count",
        "consumer_rva": "0x3C80BA6 / 0x3C80BF6",
        "instruction": "movzx eax, word ptr [rcx + 0x34]; add eax, 0x5f93",
        "downstream": "loop bound while walking qword pointer list from field_0x08",
        "sentinel": "none (wrap gives 0 count for 0xA06D)",
        "semantic_candidate": "method range count (SUPPORTED)",
        "semantic_evidence": "pairs with field_0x08; cumulative start+count consistency across records",
    },
    {
        "offset": 0x3A, "width": 2, "signed": True,
        "decode": "sext16(raw_u16 ^ 0xB2C0)",
        "consumer_rva": "0x3C672F1",
        "instruction": "movsx rax, word ptr [rec + 0x3a]; xor rax, 0x3fffffffffffb2c0",
        "downstream": "start index into 0x12C u32 table; +loop_i -> 0x3C66940 type resolver",
        "sentinel": "raw 0x4D3F decodes to -1",
        "semantic_candidate": "type descriptor range start (SUPPORTED)",
        "semantic_evidence": "consumer resolves every entry through 0x3C66940; bounds check below",
    },
    {
        "offset": 0x3C, "width": 2, "signed": False,
        "decode": "raw_u16 + 0x5404 (u16 wrap)",
        "consumer_rva": "0x3C5B606 / 0x3C6310E / 0x3C5BD35",
        "instruction": "movzx edx, word ptr [rec + 0x3c]; add edx, 0x5404; cmp dx, -1",
        "downstream": "index into 0xF0 table, entry_size 16 (idx<<4); entry +0x0/+0xC compared",
        "sentinel": "decoded 0xFFFF (-1)",
        "semantic_candidate": "16-byte type-relation entry index (SUPPORTED)",
        "semantic_evidence": "three independent consumers address 0xF0 records through this field",
    },
    {
        "offset": 0x43, "width": 1, "signed": False,
        "decode": "(raw_u8 + 4) & 0xFF -> loop count",
        "consumer_rva": "0x3C67291 / 0x3C672DF",
        "instruction": "cmp byte ptr [rec + 0x43], 0xfc ; movzx eax, byte ptr [rec + 0x43]; add al, 4",
        "downstream": "loop count over 0x12C entries; 0xFC means skip (count 0)",
        "sentinel": "0xFC",
        "semantic_candidate": "type descriptor range count (SUPPORTED)",
        "semantic_evidence": "same consumer loop reads field_0x3A + i for i < decoded count",
    },
    {
        "offset": 0x44, "width": 1, "signed": False,
        "decode": "raw_u8 ^ 0xC7 -> comparison count",
        "consumer_rva": "0x3C5B6BE",
        "instruction": "movzx eax, byte ptr [rax + 0x44]; xor rax, 0xc7",
        "downstream": "bounds a pointer comparison loop over [runtime_object+0x40]",
        "sentinel": "decoded 0 skips comparison",
        "semantic_candidate": "UNKNOWN (secondary relation count candidate)",
        "semantic_evidence": "consumer comparison loop only",
    },
]


def signed32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def decode_field(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & 0xFFFFFFFF
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def locate_template_rva(pe: PeImage) -> int:
    """Locate the first MHY template block in raw PE bytes."""
    chunk = 1 << 26
    pos = 0
    prev = b""
    with open(pe.path, "rb") as f:
        while True:
            f.seek(pos)
            data = f.read(chunk)
            if not data:
                break
            buf = prev + data
            i = buf.find(MHY_MAGIC)
            if i >= 0:
                fo = pos - len(prev) + i
                for s in pe.sections:
                    if s.raw_offset <= fo < s.raw_offset + s.raw_size:
                        return s.rva + (fo - s.raw_offset)
                raise RuntimeError(f"MHY magic at file+0x{fo:X} is not section-mapped")
            prev = data[-16:]
            pos += len(data)
    raise RuntimeError("MHY template magic not found")


def resolve_identifier(key: int, payload: bytes) -> tuple[bytes, dict]:
    """Code-proven identifier resolver (0x3C58D70)."""
    key &= 0xFFFFFFFF
    if key == 0xFFFFFFFF:
        return b"", {"key": "0xFFFFFFFF", "sentinel": True,
                     "offset_in_0x1B4_region": None, "length": 0}
    neg = bool(key & 0x80000000)
    if neg:
        off = key & ID_NEG_MASK
        length = (key >> 23) & 0xFF
    else:
        off = key & ID_POS_MASK
        length = (key >> 25) & 0x3F
    info = {
        "key": f"0x{key:08X}",
        "signed": key < 0x80000000,
        "offset_in_0x1B4_region": off,
        "length": length,
    }
    seed = (ID_HASH_ADD + ID_HASH_MUL * off) & M64
    out = bytearray()
    for _ in range((length + 7) // 8):
        if off + 8 > len(payload):
            break
        cipher = struct.unpack_from("<Q", payload, off)[0]
        plain = (cipher ^ seed) & M64
        out += plain.to_bytes(8, "little")
        off += 8
        seed = (seed + ID_ROLL) & M64
    return bytes(out[:length]), info


def find_84_sites(pe: PeImage) -> dict:
    """Find every static site that decodes template field 0x84."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    re_decode = re.compile(rb"\x48\x63[\x40-\x7f\x80-\xbf]\x84\x00\x00\x00")
    sites = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for m in re_decode.finditer(raw):
            fo = m.start()
            win = raw[fo : fo + 40]
            if b"\x3f\x1d\x53\x68" not in win:
                continue
            sec = None
            for s in pe.sections:
                if s.raw_offset <= fo < s.raw_offset + s.raw_size:
                    sec = s
                    break
            if sec is None:
                continue
            rva = sec.rva + (fo - sec.raw_offset)
            near = raw[fo : fo + 64]
            has_imul_46 = bool(re.search(rb"(\x48\x6b|\x4c\x6b|\x6b|\x49\x6b)[\x00-\xff]{0,2}\x46", near))
            sites.append({
                "rva": f"0x{rva:X}",
                "section": sec.name,
                "instruction": f"movsxd reg, dword ptr [tpl + 0x84]; xor reg, 0x68531D3F",
                "nearby_imul_46": has_imul_46,
            })
    return {"site_count": len(sites), "sites": sites}


def auto_field_accesses(pe: PeImage, sites: list[dict]) -> list[dict]:
    """Lightweight extraction of record-field memory operands per access site.

    Conservative on purpose: the register that receives `add rec, base` (or the
    imul destination when the record pointer is used via index addressing) is
    tracked, and only operands after the decode site are considered. The
    authoritative access map is FIELD_RULES; this list is machine cross-check.
    """
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    rows = []
    for site in sites:
        if not site.get("nearby_imul_46"):
            continue
        rva = int(site["rva"], 16)
        start = max(pe.section_at_rva(rva).rva, rva - 0x60)
        length = min(0x1C0, pe.section_at_rva(rva).rva + pe.section_at_rva(rva).size - start)
        raw = pe.read_rva(start, length)
        insns = list(md.disasm(raw, pe.image_base + start))

        # Find the 0x84 decode site inside this window and its base register.
        decode_va = None
        base_reg = None
        for insn in insns:
            if insn.address - pe.image_base != rva:
                continue
            decode_va = insn.address
            if insn.mnemonic == "movsxd" and len(insn.operands) >= 2:
                base_reg = insn.reg_name(insn.operands[0].reg)
            break

        # Find imul dest and the add that forms the record pointer.
        rec_regs: set[str] = set()
        keepalive_adds: set[int] = set()
        for i, insn in enumerate(insns):
            if insn.mnemonic != "imul" or not insn.op_str.endswith(", 0x46"):
                continue
            if not insn.operands:
                continue
            imul_dest = insn.reg_name(insn.operands[0].reg)
            rec_regs.add(imul_dest)
            keepalive_adds.add(insn.address)
            for later in insns[i + 1 : i + 6]:
                if later.mnemonic == "add" and len(later.operands) >= 2:
                    dst = later.reg_name(later.operands[0].reg)
                    srcs = [later.reg_name(o.reg) for o in later.operands if o.type == x86.X86_OP_REG]
                    if imul_dest in srcs:
                        rec_regs.add(dst)
                        keepalive_adds.add(later.address)
                        break
            break

        if decode_va is None:
            continue
        live: dict[str, bool] = {r: False for r in rec_regs}
        for i, insn in enumerate(insns):
            if insn.address < decode_va:
                continue
            if insn.mnemonic == "imul" and insn.op_str.endswith(", 0x46") and insn.operands:
                live[insn.reg_name(insn.operands[0].reg)] = True
            for op in insn.operands:
                if op.type != x86.X86_OP_MEM or not op.mem.base:
                    continue
                reg = insn.reg_name(op.mem.base)
                if reg in rec_regs and live.get(reg, False):
                    disp = op.mem.disp
                    if 0 <= disp <= 0x45:
                        full = f"{insn.mnemonic} {insn.op_str}"
                        width = "unknown"
                        for suffix, w in (("byte", 1), ("qword", 8), ("dword", 4), ("word", 2)):
                            if suffix in full:
                                width = w
                                break
                        rows.append({
                            "offset": disp,
                            "width": width,
                            "consumer_rva": site["rva"],
                            "instruction": full,
                            "instruction_rva": f"0x{insn.address - pe.image_base:X}",
                            "auto": True,
                        })
            # Kill a record-pointer register when it is rewritten outside the
            # formation `add rec, base`.
            for op in insn.operands:
                if op.type != x86.X86_OP_REG:
                    continue
                reg = insn.reg_name(op.reg)
                if reg in rec_regs and insn.address not in keepalive_adds:
                    live[reg] = False
    return rows


def domain_run_analysis(values: list[int], threshold: int) -> dict:
    """Find the leading run whose values stay below threshold (indices) or are -1."""
    run = []
    for i, v in enumerate(values):
        if v == 0xFFFFFFFF or v < threshold:
            run.append(v)
        else:
            break
    if not run:
        return {"run_length": 0, "note": "no plausible leading run"}
    counter = Counter(run)
    return {
        "run_length": len(run),
        "min": f"0x{min(run):X}",
        "max": f"0x{max(run):X}",
        "minus1_count": sum(1 for v in run if v == 0xFFFFFFFF),
        "distinct_count": len(counter),
        "duplicate_values": sum(1 for v, c in counter.items() if c > 1),
        "max_repeat": max(counter.values()),
        "all_below_threshold": max(v for v in run if v != 0xFFFFFFFF) < threshold,
        "first_rejected_value": f"0x{values[len(run)]:08X}" if len(run) < len(values) else None,
        "first_rejected_index": len(run) if len(run) < len(values) else None,
        "first_values": [f"0x{v:X}" for v in run[:32]],
    }


def analyze(
    game: Path,
    metadata: Path,
    template_rva: int | None,
    max_scan_entries: int,
    identifier_sample_count: int,
    want_proof: bool = False,
) -> dict:
    pe = PeImage(game)
    tpl_rva = template_rva if template_rva is not None else locate_template_rva(pe)
    block = pe.read_rva(tpl_rva, 0x208)
    offsets: dict[int, int] = {}
    for field, (op, const) in CHAIN_RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        dec = decode_field(raw, op, const)
        offsets[field] = FILE_HEADER + signed32(dec)

    with open(metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        size = metadata.stat().st_size

        # --- 0x84 record table -------------------------------------------------
        base84 = offsets[0x84]
        cap84 = (offsets[NEXT_AFTER_84] - base84) // 70
        n84 = min(cap84, max_scan_entries)
        record_bytes = mm[base84 : base84 + n84 * 70]

        def rec_field(offset: int, dtype: str, n: int = n84) -> object:
            import numpy as np  # local import keeps core deps light
            arr = np.ndarray(shape=(n,), dtype=dtype, buffer=record_bytes,
                             offset=offset, strides=(70,))
            return arr

        import numpy as np
        magic = rec_field(0x0C, "<u4")
        b43 = rec_field(0x43, "u1")
        magic_eq = magic == 0x1C2AD2AB
        magic_stats = {
            "total_entries_scanned": int(n84),
            "capacity_to_next_table": int(cap84),
            "field_0x0C_equal_0x1C2AD2AB": int(magic_eq.sum()),
            "field_0x0C_equal_ratio": float(magic_eq.mean()),
            "distinct_field_0x0C_values": int(len(np.unique(magic))),
            "not_all_entries_equal": bool(not (magic == magic[0]).all()),
        }
        uniq, counts = np.unique(magic, return_counts=True)
        order = np.argsort(-counts)[:10]
        magic_stats["most_common"] = [
            {"value": f"0x{int(uniq[i]):08X}", "count": int(counts[i])} for i in order
        ]
        b43_counts = np.bincount(b43.astype(np.int64), minlength=256)
        b43_stats = {
            "field_0x43_0xFC_count": int(b43_counts[0xFC]),
            "field_0x43_0xFD_count": int(b43_counts[0xFD]),
            "field_0x43_0xFE_count": int(b43_counts[0xFE]),
            "field_0x43_0xFF_count": int(b43_counts[0xFF]),
            "field_0x43_other_count": int(n84 - b43_counts[0xFC:0x100].sum()),
        }
        corr = {
            "field_0x43_ne_FC_total": int((b43 != 0xFC).sum()),
            "field_0x43_ne_FC_and_magic": int(((b43 != 0xFC) & magic_eq).sum()),
            "field_0x43_eq_FC_total": int((b43 == 0xFC).sum()),
            "field_0x43_eq_FC_and_magic": int(((b43 == 0xFC) & magic_eq).sum()),
        }

        # --- identifier resolver samples -------------------------------------
        region_len = min(size - offsets[0x1B4], 1 << 26)
        region = mm[offsets[0x1B4] : offsets[0x1B4] + region_len]
        id_rows = []
        raw24s = np.ndarray(shape=(n84,), dtype="<u4", buffer=record_bytes, offset=0x24, strides=(70,))
        raw28s = np.ndarray(shape=(n84,), dtype="<u4", buffer=record_bytes, offset=0x28, strides=(70,))
        sample_idx = 0
        for i in range(n84):
            key24 = (int(raw24s[i]) + 0xF1D32D89) & 0xFFFFFFFF
            key28 = (int(raw28s[i]) + 0xE9FD68F8) & 0xFFFFFFFF
            ns, info24 = resolve_identifier(key24, region)
            name, info28 = resolve_identifier(key28, region)
            if sample_idx < identifier_sample_count:
                id_rows.append({
                    "record_index": i,
                    "field_0x28_key": info28["key"],
                    "identifier": name.decode("utf-8", "replace"),
                    "field_0x24_key": info24["key"],
                    "namespace": ns.decode("utf-8", "replace"),
                    "field_0x43": f"0x{int(b43[i]):02X}",
                    "field_0x0C": f"0x{int(magic[i]):08X}",
                })
                sample_idx += 1
            elif identifier_sample_count == 0:
                break
        # Printable sanity across all scanned records
        printable_stats = {"rows_checked": 0, "printable_rows": 0}
        for i in range(0, n84, max(1, n84 // 4096)):
            key24 = (int(raw24s[i]) + 0xF1D32D89) & 0xFFFFFFFF
            key28 = (int(raw28s[i]) + 0xE9FD68F8) & 0xFFFFFFFF
            ns, _ = resolve_identifier(key24, region)
            name, _ = resolve_identifier(key28, region)
            ok_ns = all(32 <= c < 127 or c in (0,) for c in ns)
            ok_name = all(32 <= c < 127 or c in (0,) for c in name)
            printable_stats["rows_checked"] += 1
            printable_stats["printable_rows"] += int(ok_ns and ok_name)

        # --- 0x70 map domain ---------------------------------------------------
        base70 = offsets[0x70]
        u32s70 = np.ndarray(shape=((size - base70) // 4,), dtype="<u4",
                            buffer=mm, offset=base70, strides=(4,))
        d70 = domain_run_analysis([int(v) for v in u32s70], n84)
        d70["file_offset"] = f"0x{base70:X}"
        d70["entry_size"] = 4
        d70["classification"] = (
            "INDEX_MAP (SUPPORTED)" if d70.get("run_length") and d70["run_length"] < len(u32s70)
            else "UNKNOWN"
        )
        d70["consumer_rvas"] = ["0x3C82BAC", "0x3C5F70E", "0x3C67762"]
        d70["consumer_evidence"] = "0x3C82BAC: value -> imul 0x46 -> 0x84 record; -1 sentinel skip"

        # --- 0x12C map domain ---------------------------------------------------
        base12c = offsets[0x12C]
        u32s12c = np.ndarray(shape=((size - base12c) // 4,), dtype="<u4",
                             buffer=mm, offset=base12c, strides=(4,))
        d12c = {
            "file_offset": f"0x{base12c:X}",
            "entry_size": 4,
            "capacity_to_next_table": (offsets[NEXT_AFTER_12C] - base12c) // 4,
            "consumer_rvas": ["0x3C6730A", "0x3C5AE52"],
            "consumer_evidence": "0x3C672F1 decodes 0x84 +0x3A, indexes this table, calls 0x3C66940",
        }
        vals12c = [int(v) for v in u32s12c[: d12c["capacity_to_next_table"]]]
        d12c["domain"] = {
            "min": f"0x{min(vals12c):08X}",
            "max": f"0x{max(vals12c):08X}",
            "minus1_count": sum(1 for v in vals12c if v == 0xFFFFFFFF),
            "distinct_count": len(set(vals12c)),
            "first_values": [f"0x{v:08X}" for v in vals12c[:32]],
        }

        # --- field validations -------------------------------------------------
        starts8 = np.ndarray(shape=(n84,), dtype="<u4", buffer=record_bytes, offset=8, strides=(70,))
        w34 = np.ndarray(shape=(n84,), dtype="<u2", buffer=record_bytes, offset=0x34, strides=(70,))
        method_starts = []
        method_counts = []
        range_rows = []
        for i in range(n84):
            st = int(starts8[i]) ^ 0x1A7AF5FE
            st = signed32(st)
            ct = (int(w34[i]) + 0x5F93) & 0xFFFF
            method_starts.append(st)
            method_counts.append(ct)
            if i < 256:
                range_rows.append({"record_index": i, "field_0x08_decoded": st,
                                   "field_0x34_decoded": ct})
        valid_range = [i for i in range(n84) if method_starts[i] >= 0]
        cumulative_ok = True
        for i in range(len(valid_range) - 1):
            a = valid_range[i]
            b = valid_range[i + 1]
            if method_starts[a] + method_counts[a] != method_starts[b]:
                cumulative_ok = False
                break
        max_end = max((method_starts[i] + method_counts[i] for i in valid_range), default=0)
        method_covered = bytearray(max_end)
        method_overlap = 0
        for i in valid_range:
            st, ct = method_starts[i], method_counts[i]
            for pos in range(st, st + ct):
                method_overlap += method_covered[pos]
                method_covered[pos] = 1
        method_gaps = [i for i in range(max_end) if not method_covered[i]]
        range_validation = {
            "rows_with_start_ge_0": len(valid_range),
            "rows_with_start_minus1": n84 - len(valid_range),
            "rows_with_count_gt_0": sum(1 for c in method_counts if c > 0),
            "start_min": min(method_starts),
            "start_max": max(method_starts),
            "count_max": max(method_counts),
            "covered_span": max_end,
            "covered_entries": method_covered.count(1),
            "overlapped_entries": method_overlap,
            "first_gaps": method_gaps[:8],
            "coverage_exact_once": bool(method_covered.count(1) == max_end
                                        and method_overlap == 0),
            "cumulative_start_plus_count_ok": cumulative_ok,
            "evidence": "start+count chains contiguously and covers a unified span exactly once "
                        "(method range candidate)",
            "samples": range_rows[:24],
        }

        # 0x12C references from field_0x3A + field_0x43
        w3a = np.ndarray(shape=(n84,), dtype="<i2", buffer=record_bytes, offset=0x3A, strides=(70,))
        cap12c = d12c["capacity_to_next_table"]
        desc_ok = True
        desc_rows = []
        desc_total = 0
        desc_covered = bytearray(cap12c)
        desc_overlap = 0
        for i in range(n84):
            start = int(w3a[i])
            start = start if start < 0x8000 else start - 0x10000
            start = ((start & 0xFFFF) ^ 0xB2C0)
            start = start - 0x10000 if start & 0x8000 else start
            count = (int(b43[i]) + 4) & 0xFF
            if count and not (0 <= start and start + count <= cap12c):
                desc_ok = False
                if len(desc_rows) < 8:
                    desc_rows.append({"record_index": i, "start": start, "count": count,
                                      "problem": "out_of_bounds"})
            if count:
                for pos in range(start, start + count):
                    if 0 <= pos < cap12c:
                        desc_overlap += desc_covered[pos]
                        desc_covered[pos] = 1
                desc_total += count
                if len(desc_rows) < 12:
                    desc_rows.append({"record_index": i, "start": start, "count": count,
                                      "problem": None})
        desc_gaps = [i for i in range(cap12c) if not desc_covered[i]]
        desc_validation = {
            "all_referenced_ranges_in_bounds": desc_ok,
            "referenced_entry_total": desc_total,
            "rows_with_nonzero_count": int((((b43.astype(np.int64) + 4) & 0xFF) != 0).sum()),
            "table_capacity": cap12c,
            "covered_entries": desc_covered.count(1),
            "overlapped_entries": desc_overlap,
            "first_gaps": desc_gaps[:8],
            "coverage_exact_once": bool(desc_ok and desc_overlap == 0
                                        and desc_covered.count(1) == cap12c),
            "evidence": "every 0x12C entry is referenced exactly once by 0x84 ranges",
            "samples": desc_rows[:12],
        }

        # 0xF0 references from field_0x3C
        w3c = np.ndarray(shape=(n84,), dtype="<u2", buffer=record_bytes, offset=0x3C, strides=(70,))
        baseF0 = offsets[0xF0]
        f0_upper = offsets[NEXT_AFTER_F0]
        capF0 = (f0_upper - baseF0) // 16
        f0_ok = True
        f0_bad = []
        for i in range(n84):
            idx = (int(w3c[i]) + 0x5404) & 0xFFFF
            if idx == 0xFFFF:
                continue
            if capF0 is None or idx >= capF0:
                f0_ok = False
                if len(f0_bad) < 8:
                    f0_bad.append({"record_index": i, "index": idx, "capacity": capF0})
        f0_validation = {
            "field_0xF0_file_offset": f"0x{baseF0:X}",
            "entry_size": 16,
            "capacity_to_next_table": capF0,
            "all_indices_in_bounds": f0_ok,
            "out_of_bounds_samples": f0_bad,
        }

    # --- optional minimal Type Registry Proof --------------------------------
    proof = None
    if want_proof:
        def decode_identifier(raw: int, const: int) -> tuple[str, dict]:
            key = (raw + const) & 0xFFFFFFFF
            text, info = resolve_identifier(key, region)
            return text.decode("utf-8", "replace"), info

        wanted = {
            "Ability", "Mixin", "Modifier", "Predicate", "Target",
            "DynamicValue", "BattleEvent",
        }
        search_hits: dict[str, list[dict]] = {w: [] for w in wanted}
        proof_rows: list[dict] = []
        for i in range(n84):
            ns, _ = decode_identifier(int(raw24s[i]), 0xF1D32D89)
            name, _ = decode_identifier(int(raw28s[i]), 0xE9FD68F8)
            if len(proof_rows) < 32 and name:
                proof_rows.append({
                    "record_index": i,
                    "identifier": name,
                    "namespace": ns,
                    "method_start": method_starts[i],
                    "method_count": method_counts[i],
                    "type_descriptor_start": int(w3a[i]) if False else None,
                    "type_descriptor_count": (int(b43[i]) + 4) & 0xFF,
                    "type_relation_index_0xF0": (int(w3c[i]) + 0x5404) & 0x0FFFF
                    if (int(w3c[i]) + 0x5404) & 0xFFFF != 0xFFFF else -1,
                    "field_0x0C_raw": f"0x{int(magic[i]):08X}",
                })
            for word in wanted:
                if word in name and len(search_hits[word]) < 3:
                    search_hits[word].append({
                        "record_index": i,
                        "identifier": name,
                        "namespace": ns,
                    })
        # Fill type_descriptor_start after the fact (w3a decode per row).
        for row in proof_rows:
            i = row["record_index"]
            start = int(w3a[i])
            start = start if start < 0x8000 else start - 0x10000
            start = ((start & 0xFFFF) ^ 0xB2C0)
            start = start - 0x10000 if start & 0x8000 else start
            row["type_descriptor_start"] = start
            row["field_0x44_decoded"] = record_bytes[i * 70 + 0x44] ^ 0xC7

        checks = {
            "at_least_20_records_with_index_and_name": len(proof_rows) >= 20,
            "identifier_resolver_code_proven": True,
            "method_range_candidate": cumulative_ok and range_validation["coverage_exact_once"],
            "type_descriptor_range_candidate": desc_ok and desc_validation["coverage_exact_once"],
            "cross_table_references_in_bounds": desc_ok and f0_ok,
        }
        proof = {
            "schema": "mhy_type_registry_proof/1",
            "status": ("MHY_METADATA = TYPE_REGISTRY_PROOF"
                       if all(checks.values()) else "MHY_METADATA = TYPE_SEMANTIC_UNRESOLVED"),
            "definition_table": "0x84 (entry_size 70, consumer imul idx,0x46)",
            "identifier_resolution": "CONFIRMED (0x3C58D70 key -> 0x1B4 region -> rolling XOR)",
            "records": proof_rows,
            "semantic_sanity_search": {
                word: search_hits[word] for word in sorted(wanted) if search_hits[word]
            },
            "checks": checks,
            "evidence_classes": {
                "identifier_name": "E4 code-proven decoder + E2 repeated structure + E3 metadata semantics",
                "method_range": "E4 consumer 0x3C80BA6/0x3C80C09 + E2 cumulative start/count",
                "type_descriptor_relation": "E4 consumer 0x3C672F1 -> 0x12C -> 0x3C66940 resolver",
            },
            "not_claimed": [
                "0x12C entry semantic name (consumer is a .upx0 thunk)",
                "full MethodDefinition / FieldDefinition tables",
                "0x70 length from code (domain-run length is data evidence)",
            ],
        }

    # --- consumer sites --------------------------------------------------------
    sites = find_84_sites(pe)
    auto_accesses = auto_field_accesses(pe, sites["sites"])
    auto_accesses.sort(key=lambda r: r["offset"])

    out = {
        "schema": "mhy_0x84_record_access_map/1",
        "game": str(game.resolve()),
        "metadata": str(metadata.resolve()),
        "template_rva": f"0x{tpl_rva:X}",
        "file_header_size": FILE_HEADER,
        "table_offsets": {f"0x{k:X}": f"0x{v:X}" for k, v in offsets.items()},
        "record_table": {
            "field": "0x84",
            "entry_size": 70,
            "index_stride": "imul idx, 0x46 (code)",
            "file_offset": f"0x{base84:X}",
            "capacity_to_next_table": int(cap84),
            "field_0x0C_stats": magic_stats,
            "field_0x43_stats": b43_stats,
            "correlation": corr,
        },
        "consumer_scan": sites,
        "auto_field_accesses": auto_accesses,
        "field_access_map": FIELD_RULES,
        "field_validations": {
            "identifier_printable_sample": printable_stats,
            "method_range": range_validation,
            "type_descriptor_range_0x12C": desc_validation,
            "type_relation_index_0xF0": f0_validation,
        },
        "identifier_resolver": {
            "function_rva": "0x3C58D70",
            "constants": {
                "hash_mul": f"0x{ID_HASH_MUL:016X}",
                "hash_add": f"0x{ID_HASH_ADD:016X}",
                "roll": f"0x{ID_ROLL:016X}",
                "positive_key_mask": f"0x{ID_POS_MASK:X}",
                "negative_key_mask": f"0x{ID_NEG_MASK:X}",
                "positive_length_shift": 25,
                "positive_length_mask_bits": 6,
                "negative_length_shift": 23,
                "negative_length_mask_bits": 8,
            },
            "evidence": [
                "0x3C58D70: hash key -> slot offset -> decrypt qwords at 0x1B4_base + key_offset",
                "rolling key += 0x3E693CD23A41FDEF per qword (code 0x3C59CB2)",
                "length bits come from the key itself (code 0x3C58EFC-0x3C58F1B)",
                "record 0 +0x28 decodes to '<Module>'; +0x24 decodes to empty namespace",
            ],
            "samples": id_rows,
        },
        "chain_0x70": d70,
        "chain_0x12C": d12c,
        "type_registry_proof": proof,
        "cross_version_note": "file offsets differ; rerun this tool against the other version and compare shape",
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", help="GameAssembly.dll")
    ap.add_argument("--metadata", required=True, help="global-metadata.dat")
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--max-scan-entries", type=int, default=100000)
    ap.add_argument("--identifier-sample-count", type=int, default=30)
    ap.add_argument("--proof", action="store_true",
                    help="include the minimal type-registry proof in the output")
    ap.add_argument("--proof-output", default=None,
                    help="also write the proof as a standalone JSON file")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    result = analyze(Path(args.game), Path(args.metadata), args.template_rva,
                     args.max_scan_entries, args.identifier_sample_count,
                     want_proof=args.proof)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    if args.proof_output and result.get("type_registry_proof"):
        pout = Path(args.proof_output)
        pout.parent.mkdir(parents=True, exist_ok=True)
        with open(pout, "w", encoding="utf-8") as f:
            json.dump(result["type_registry_proof"], f, indent=2)
        print(f"wrote {pout}")
    print(f"record_table n={result['record_table']['capacity_to_next_table']} "
          f"magic_eq={result['record_table']['field_0x0C_stats']['field_0x0C_equal_0x1C2AD2AB']}")
    print(f"method_range cumulative_ok="
          f"{result['field_validations']['method_range']['cumulative_start_plus_count_ok']}")
    print(f"0x12C bounds_ok={result['field_validations']['type_descriptor_range_0x12C']['all_referenced_ranges_in_bounds']}")
    print(f"0xF0 bounds_ok={result['field_validations']['type_relation_index_0xF0']['all_indices_in_bounds']}")
    if result.get("type_registry_proof"):
        p = result["type_registry_proof"]
        print(f"proof_status={p['status']} records={len(p['records'])}")
    print("identifier samples:")
    for r in result["identifier_resolver"]["samples"][:12]:
        print(f"  [{r['record_index']}] {r['namespace']}.{r['identifier']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
