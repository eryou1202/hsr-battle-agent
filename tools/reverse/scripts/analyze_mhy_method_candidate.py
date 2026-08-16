#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrow consumer-driven analyzer for the MHY MethodDefinition candidate.

Proves and records that template field 0x14C is the MethodDefinition table:

  * directory rule       : 0x14C, add 0xF3A04294, payload-relative offset
  * entry size           : 26 bytes (consumer `lea idx*26`)
  * capacity             : (next table 0x160 - 0x14C) // 26, and it equals the
                           TypeDefinition +0x08/+0x34 method partition total
  * per-record transform : 64-bit rolling index hash fed into every field decode
  * field +0x00          : name key -> existing identifier resolver 0x3C58D70
  * field +0x04          : parameter start (sentinel 0xFFFFFFFF) into the 0x30
                           parameter table
  * field +0x08          : return type reference consumed through the 16-byte
                           type-entry array at [runtime + 0x80]
  * field +0x10          : declaring type index; validated against the owner of
                           every TypeDefinition method range
  * field +0x18          : parameter count; validated against the exact
                           parameter-table partition

Outputs `mhy_method_definition_access_map_<version>.json` and, optionally, a
standalone `method_registry_proof_<version>.json`.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    ID_HASH_ADD,
    ID_HASH_MUL,
    ID_NEG_MASK,
    ID_POS_MASK,
    ID_ROLL,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

M64 = (1 << 64) - 1
M32 = 0xFFFFFFFF

# Code-derived directory transforms needed by this analysis.
RULES = {
    0x14C: ("add", 0xF3A04294),  # MethodDefinition table
    0x160: ("add", 0xC769CD52),  # next known table (usage table)
    0x84: ("xor", 0x68531D3F),   # TypeDefinition table
    0x38: ("add", 0xF778F1AB),   # next known table after 0x84
    0x30: ("add", 0xDCF5FDBE),   # ParameterDefinition table
    0x1C8: ("xor", 0x042F9275),  # next known table after 0x30
    0x1B4: ("add", 0x8D43A4EE),  # identifier ciphertext heap
}

# MethodDefinition per-index hash recovered from several independent consumers
# (0x3C66F80, 0x3C71362, 0x3C71C7F, 0x3C72038, 0x3C72314, 0x3C7D45C).
METHOD_HASH_MUL1 = 0x31E1
METHOD_HASH_XOR = 0x33914937
METHOD_HASH_MUL2 = 0x2C03F17D
METHOD_HASH_SHR2 = 0x17
METHOD_HASH_MUL3 = 0x540CC9F4
METHOD_HASH_SHR3 = 0x15
METHOD_HASH_ADD = 0x71BC7861

# Field decode constants (all proven by consumers).
FIELD_NAME_CONST = 0x0E714BC1
FIELD_PARAM_START_CONST = 0x009889B8
FIELD_RETURN_ADD_CONST = 0x9AC1F4E3
FIELD_DECLARING_CONST = 0x2A5FABE8
FIELD_FLAGS0C_CONST = 0x09F73733
FIELD_SLOT14_ADD_CONST = 0xFFFF86FD  # raw_u16 + this, then xor low16(hash)
FIELD_GENERIC16_ADD_CONST = 0xFFFFE395
FIELD_PARAM_COUNT_CONST = 0xA8

# Curated access map. `structure_status` and `semantic_status` are recorded
# separately on purpose.
FIELD_ACCESS_MAP = [
    {
        "offset": 0x00, "width": 4,
        "decode": f"name_key = (hash32c ^ raw_u32 ^ 0x{FIELD_NAME_CONST:08X})",
        "consumer_rvas": ["0x3C71C73", "0x3C5E3C6", "0x3C5E4B1"],
        "instruction": "xor ecx, dword ptr [rec + 0x0]; xor ecx, 0x0e714bc1; jmp 0x3C58D70",
        "downstream": "existing identifier resolver 0x3C58D70",
        "sentinel": "resolver key 0xFFFFFFFF -> empty string",
        "semantic_candidate": "name key",
        "semantic_evidence": "decodes to .ctor/Equals/GetHashCode/ToString/... in mscorlib order",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
    {
        "offset": 0x04, "width": 4,
        "decode": f"parameter_start = (hash32c ^ raw_u32 ^ 0x{FIELD_PARAM_START_CONST:08X}) as s32",
        "consumer_rvas": ["0x3C724C1", "0x3C713A2", "0x3C7D4A5"],
        "instruction": "xor ecx, dword ptr [rec + 0x4]; xor ecx, 0x9889b8",
        "downstream": "start index into 0x30 parameter table; loop adds parameter ordinal",
        "sentinel": "0xFFFFFFFF (-1)",
        "semantic_candidate": "parameter start",
        "semantic_evidence": "start+count ranges cover the 0x30 table exactly once",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
    {
        "offset": 0x08, "width": 4,
        "decode": f"return_ref = hash32c ^ ((raw_u32 + 0x{FIELD_RETURN_ADD_CONST:08X}) & 0xFFFFFFFF)",
        "consumer_rvas": ["0x3C72078"],
        "instruction": "add eax, dword ptr [rec + 0x8]; add eax, 0x9ac1f4e3; xor ecx, eax; cmp -1",
        "downstream": "non-sentinel -> [runtime + 0x80] 16-byte type entries",
        "sentinel": "0xFFFFFFFF",
        "semantic_candidate": "return type reference",
        "semantic_evidence": "void methods share one reference; string/int/bool methods share stable references",
        "structure_status": "CONFIRMED",
        "semantic_status": "SUPPORTED",
    },
    {
        "offset": 0x0C, "width": 4,
        "decode": f"flags0c = raw_u32 ^ hash32c ^ 0x{FIELD_FLAGS0C_CONST:08X}",
        "consumer_rvas": ["0x3C5E189"],
        "instruction": "movd xmm1, [rec + 0xc]; pxor xmm1, broadcast(hash32c); pxor xmm1, xmm0",
        "downstream": "stored to runtime method flags region",
        "sentinel": "none",
        "semantic_candidate": "method flags candidate",
        "semantic_evidence": "consumer decodes the whole u32 into runtime method metadata",
        "structure_status": "CONFIRMED",
        "semantic_status": "UNKNOWN",
    },
    {
        "offset": 0x0E, "width": 2,
        "decode": "flags0e = raw_u16 ^ low16(hash32c)",
        "consumer_rvas": ["0x3C5E1D6", "0x3C5E3B5"],
        "instruction": "movzx ecx, word ptr [rec + 0xe]; xor cx, r13w; test bits",
        "downstream": "bit 0x10 gates name-key lookup; bit 0x1000 gates another branch",
        "sentinel": "none",
        "semantic_candidate": "method flags (specific bits)",
        "semantic_evidence": "two consumers test different bits after the same decode",
        "structure_status": "CONFIRMED",
        "semantic_status": "SUPPORTED",
    },
    {
        "offset": 0x10, "width": 4,
        "decode": f"declaring_type = hash32c ^ raw_u32 ^ 0x{FIELD_DECLARING_CONST:08X}",
        "consumer_rvas": ["0x3C67001"],
        "instruction": "xor ecx, dword ptr [rec + 0x10]; xor ecx, 0x2a5fabe8; call 0x3C66940",
        "downstream": "resolver 0x3C66940; value is a TypeDefinition record index",
        "sentinel": "none observed",
        "semantic_candidate": "declaring type index",
        "semantic_evidence": "all 732328 decoded values equal the TypeDefinition range owner",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
    {
        "offset": 0x14, "width": 2,
        "decode": f"slot14 = sext16((raw_u16 + 0x{FIELD_SLOT14_ADD_CONST:04X}) ^ low16(hash32c))",
        "consumer_rvas": ["0x3C5E123"],
        "instruction": "movzx ecx, [rec + 0x14]; add ecx, 0xffff86fd; xor eax, ecx; movsx",
        "downstream": "stored to runtime method record +0x10",
        "sentinel": "none",
        "semantic_candidate": "signed method slot/index candidate",
        "semantic_evidence": "consumer only",
        "structure_status": "CONFIRMED",
        "semantic_status": "UNKNOWN",
    },
    {
        "offset": 0x16, "width": 2,
        "decode": f"generic16 = ((raw_u16 + 0x{FIELD_GENERIC16_ADD_CONST:04X}) ^ low16(hash32c))",
        "consumer_rvas": ["0x3C5E176"],
        "instruction": "movzx ecx, [rec + 0x16]; add ecx, 0xffffe395; xor ecx, r13d",
        "downstream": "stored to runtime method record +0x28",
        "sentinel": "none",
        "semantic_candidate": "UNKNOWN",
        "semantic_evidence": "consumer only",
        "structure_status": "CONFIRMED",
        "semantic_status": "UNKNOWN",
    },
    {
        "offset": 0x18, "width": 1,
        "decode": f"parameter_count = raw_u8 ^ low8(hash + 0x{METHOD_HASH_ADD:X}) ^ 0x{FIELD_PARAM_COUNT_CONST:02X}",
        "consumer_rvas": ["0x3C72361", "0x3C5E1AC"],
        "instruction": "movzx r14d, byte ptr [rec + 0x18]; xor r14b, al; xor r14b, 0xa8",
        "downstream": "loop bound over parameter records",
        "sentinel": "none",
        "semantic_candidate": "parameter count",
        "semantic_evidence": "parameter ranges cover the 0x30 table exactly once",
        "structure_status": "CONFIRMED",
        "semantic_status": "CONFIRMED",
    },
    {
        "offset": 0x19, "width": 1,
        "decode": "flags19 = raw_u8 ^ low8(hash + 0x71BC7861)",
        "consumer_rvas": ["0x3C5E1EC"],
        "instruction": "xor r13b, byte ptr [rec + 0x19]; add r13b, r13b; and 6; ...",
        "downstream": "runtime method flags combination",
        "sentinel": "none",
        "semantic_candidate": "method flags candidate",
        "semantic_evidence": "consumer only",
        "structure_status": "CONFIRMED",
        "semantic_status": "UNKNOWN",
    },
]


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & 0xFFFFFFFF
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def method_hash(idx: np.ndarray) -> np.ndarray:
    """The 64-bit per-method rolling hash used before every field decode."""
    x = (idx.astype(np.uint64) * METHOD_HASH_MUL1) & M64
    x ^= METHOD_HASH_XOR
    x = (x * METHOD_HASH_MUL2) & M64
    x >>= METHOD_HASH_SHR2
    x = (x * METHOD_HASH_MUL3) & M64
    x >>= METHOD_HASH_SHR3
    return x


def type_identifier(mm, tbase: int, rec_index: int, region: bytes) -> tuple[str, str]:
    raw24 = struct.unpack_from("<I", mm, tbase + rec_index * 70 + 0x24)[0]
    raw28 = struct.unpack_from("<I", mm, tbase + rec_index * 70 + 0x28)[0]
    ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & 0xFFFFFFFF, region)
    name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & 0xFFFFFFFF, region)
    return ns.decode("utf-8", "replace"), name.decode("utf-8", "replace")


def analyze(game: Path, metadata: Path, template_rva: int | None,
            identifier_sample_count: int) -> dict:
    pe = PeImage(game)
    tpl_rva = template_rva if template_rva is not None else locate_template_rva(pe)
    block = pe.read_rva(tpl_rva, 0x208)
    offsets: dict[int, int] = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        offsets[field] = FILE_HEADER + signed32(decode_rule(raw, op, const))

    mbase = offsets[0x14C]
    mnext = offsets[0x160]
    tbase = offsets[0x84]
    tnext = offsets[0x38]
    pbase = offsets[0x30]
    pnext = offsets[0x1C8]
    region_base = offsets[0x1B4]

    with open(metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        size = metadata.stat().st_size
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        # --- TypeDefinition method ranges ---------------------------------
        ntypes = (tnext - tbase) // 70
        starts8 = np.ndarray(shape=(ntypes,), dtype="<u4", buffer=mm,
                             offset=tbase + 0x08, strides=(70,))
        words34 = np.ndarray(shape=(ntypes,), dtype="<u2", buffer=mm,
                             offset=tbase + 0x34, strides=(70,))
        t_starts = (starts8.astype(np.uint32) ^ np.uint32(0x1A7AF5FE)).astype(np.int32)
        t_starts = t_starts.astype(np.int64)
        t_counts = ((words34.astype(np.uint32) + 0x5F93) & 0xFFFF).astype(np.int64)
        valid = t_starts >= 0
        t_starts_valid = t_starts[valid]
        t_counts_valid = t_counts[valid]
        method_total = int(t_counts_valid.sum())
        method_max_end = int((t_starts_valid + t_counts_valid).max())
        recidx = np.arange(ntypes, dtype=np.int64)[valid]
        owner = np.repeat(recidx, t_counts_valid)

        # Method partition sanity: exact once coverage.
        method_cov = np.zeros(method_total, dtype=np.uint8)
        for st, ct in zip(t_starts_valid.tolist(), t_counts_valid.tolist()):
            method_cov[st : st + ct] += 1
        method_partition = {
            "rows_with_methods": int(valid.sum()),
            "rows_without_methods": int((~valid).sum()),
            "covered_span": method_total,
            "max_end": method_max_end,
            "covered_exactly_once": bool(method_cov.sum() == method_total
                                         and bool(np.all(method_cov == 1))),
            "cumulative_record_order_ok": True,
        }
        # Cumulative check in record order (mirrors the consumer loop).
        expected = 0
        for i in range(ntypes):
            if t_counts[i] == 0:
                continue
            if t_starts[i] != expected:
                method_partition["cumulative_record_order_ok"] = False
                break
            expected += int(t_counts[i])

        # --- 0x14C MethodDefinition table ----------------------------------
        capacity = (mnext - mbase) // 26
        n = min(capacity, method_total) if method_total else capacity
        if capacity != method_total:
            raise SystemExit(
                f"method capacity mismatch: table capacity={capacity}, "
                f"type partition total={method_total}")
        idx = np.arange(n, dtype=np.uint64)
        hv = method_hash(idx)
        h32c = ((hv + METHOD_HASH_ADD) & 0xFFFFFFFF).astype(np.uint32)
        h16 = (hv & 0xFFFF).astype(np.uint16)
        low8 = ((hv + METHOD_HASH_ADD) & 0xFF).astype(np.uint8)

        f0 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm,
                        offset=mbase + 0x00, strides=(26,))
        f4 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm,
                        offset=mbase + 0x04, strides=(26,))
        f8 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm,
                        offset=mbase + 0x08, strides=(26,))
        f0c = np.ndarray(shape=(n,), dtype="<u4", buffer=mm,
                         offset=mbase + 0x0C, strides=(26,))
        f0e = np.ndarray(shape=(n,), dtype="<u2", buffer=mm,
                         offset=mbase + 0x0E, strides=(26,))
        f10 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm,
                         offset=mbase + 0x10, strides=(26,))
        f18 = np.ndarray(shape=(n,), dtype="u1", buffer=mm,
                         offset=mbase + 0x18, strides=(26,))

        name_key = h32c ^ f0.astype(np.uint32) ^ np.uint32(FIELD_NAME_CONST)
        ps = (h32c ^ f4.astype(np.uint32) ^ np.uint32(FIELD_PARAM_START_CONST)).astype(np.int64)
        ps = np.where(ps >= 0x80000000, ps - 0x100000000, ps)
        return_ref = (h32c ^ ((f8.astype(np.uint32) + np.uint32(FIELD_RETURN_ADD_CONST))
                              & np.uint32(0xFFFFFFFF))).astype(np.int64)
        return_ref = np.where(return_ref >= 0x80000000, return_ref - 0x100000000, return_ref)
        flags0c = h32c ^ f0c.astype(np.uint32) ^ np.uint32(FIELD_FLAGS0C_CONST)
        flags0e = h16 ^ f0e.astype(np.uint16)
        declaring = (h32c ^ f10.astype(np.uint32) ^ np.uint32(FIELD_DECLARING_CONST)).astype(np.int64)
        pc = (f18.astype(np.uint16) ^ low8.astype(np.uint16) ^ 0xA8).astype(np.int64)

        declaring_match = {
            "checked_methods": n,
            "mismatch_count": int((declaring != owner).sum()),
            "all_match": bool(np.all(declaring == owner)),
            "min": int(declaring.min()),
            "max": int(declaring.max()),
        }

        # --- parameter partition ------------------------------------------
        pcapacity_known = (pnext - pbase) // 8
        ptotal = int(pc.sum())
        ps_valid_rows = int((ps >= 0).sum())
        max_pend = int((ps + pc).max())
        pcov = np.zeros(ptotal, dtype=np.uint8)
        for st, ct in zip(ps.tolist(), pc.tolist()):
            if ct:
                pcov[st : st + ct] += 1
        parameter_partition = {
            "table_field": "0x30",
            "entry_size": 8,
            "capacity_from_next_known_offset": pcapacity_known,
            "rows_with_parameters": ps_valid_rows,
            "parameter_total": ptotal,
            "max_end": max_pend,
            "all_ranges_in_bounds": bool(max_pend <= ptotal and ps_valid_rows and pcapacity_known == ptotal),
            "covered_exactly_once": bool(pcov.sum() == ptotal and bool(np.all(pcov == 1))),
        }

        # --- identifier samples --------------------------------------------
        sample_idx_list = list(range(min(identifier_sample_count, n)))
        if n > 64:
            sample_idx_list += list(range(64, n, n // 64))[:64]
        sample_idx_list = sorted(set(sample_idx_list))
        id_rows = []
        printable_checked = 0
        printable_ok = 0
        for i in sample_idx_list:
            key = int(name_key[i])
            text, info = resolve_identifier(key, region)
            ns, tname = type_identifier(mm, tbase, int(declaring[i]), region)
            printable = all(32 <= c < 127 or c in (0,) for c in text)
            printable_checked += 1
            printable_ok += int(printable)
            id_rows.append({
                "method_index": i,
                "name": text.decode("utf-8", "replace"),
                "name_key": f"0x{key:08X}",
                "declaring_type_index": int(declaring[i]),
                "declaring_type": f"{ns}.{tname}" if ns else tname,
                "parameter_count": int(pc[i]),
                "parameter_start": int(ps[i]) if int(ps[i]) >= 0 else -1,
                "return_type_reference": int(return_ref[i]),
                "flags_0x0E": f"0x{int(flags0e[i]):04X}",
            })
        identifier_stats = {
            "rows_checked": printable_checked,
            "printable_rows": printable_ok,
            "all_checked_printable": printable_checked == printable_ok,
        }

        # --- proof block ------------------------------------------------------
        checks = {
            "table_capacity_equals_type_partition": capacity == method_total,
            "type_method_ranges_exact_once": method_partition["covered_exactly_once"],
            "declaring_type_matches_owner": declaring_match["all_match"],
            "parameter_ranges_exact_once": parameter_partition["covered_exactly_once"],
            "identifier_names_printable": identifier_stats["all_checked_printable"],
        }
        proof = {
            "schema": "mhy_method_registry_proof/1",
            "status": ("MHY_METADATA = METHOD_REGISTRY_PROOF"
                       if all(checks.values()) else "MHY_METADATA = METHOD_SCHEMA_UNRESOLVED"),
            "method_table": "0x14C (entry_size 26, consumer lea idx*26)",
            "record_count": n,
            "samples": id_rows[:24],
            "checks": checks,
            "not_claimed": [
                "MethodDefinition -> GameAssembly RVA mapping",
                "return type semantic name",
                "parameter name recovery (all observed keys are 0xFFFFFFFF)",
            ],
        }

    out = {
        "schema": "mhy_method_definition_access_map/1",
        "game": str(game.resolve()),
        "metadata": str(metadata.resolve()),
        "template_rva": f"0x{tpl_rva:X}",
        "file_header_size": FILE_HEADER,
        "table_offsets": {f"0x{k:X}": f"0x{v:X}" for k, v in offsets.items()},
        "method_table": {
            "field": "0x14C",
            "transform": "add 0xF3A04294",
            "entry_size": 26,
            "file_offset": f"0x{mbase:X}",
            "next_table_field": "0x160",
            "capacity_to_next_table": capacity,
            "record_count": n,
            "record_index_stride": "lea idx*26 (consumer 0x3C66FF0 / 0x3C71CB3 / 0x3C7234E)",
            "per_record_hash": {
                "expression": "h = (((idx*0x31E1 ^ 0x33914937)*0x2C03F17D >> 0x17)*0x540CC9F4 >> 0x15); hash32c = (h + 0x71BC7861) & 0xFFFFFFFF",
                "consumer_rvas": ["0x3C66FCC", "0x3C7136D", "0x3C71C8F",
                                  "0x3C72048", "0x3C72324", "0x3C7D470"],
            },
        },
        "type_range_source": {
            "field": "0x84",
            "method_start": "+0x08 raw_u32 ^ 0x1A7AF5FE",
            "method_count": "+0x34 raw_u16 + 0x5F93",
            "rows_with_methods": method_partition["rows_with_methods"],
        },
        "field_access_map": FIELD_ACCESS_MAP,
        "validations": {
            "method_partition": method_partition,
            "declaring_type_match": declaring_match,
            "parameter_partition": parameter_partition,
            "identifier_samples": identifier_stats,
        },
        "identifier_resolver": {
            "function_rva": "0x3C58D70",
            "constants": {
                "hash_mul": f"0x{ID_HASH_MUL:016X}",
                "hash_add": f"0x{ID_HASH_ADD:016X}",
                "roll": f"0x{ID_ROLL:016X}",
                "positive_key_mask": f"0x{ID_POS_MASK:X}",
                "negative_key_mask": f"0x{ID_NEG_MASK:X}",
            },
        },
        "method_registry_proof": proof,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", help="GameAssembly.dll")
    ap.add_argument("--metadata", required=True, help="global-metadata.dat")
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--identifier-sample-count", type=int, default=32)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--proof-output", default=None)
    args = ap.parse_args()
    result = analyze(Path(args.game), Path(args.metadata), args.template_rva,
                     args.identifier_sample_count)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    if args.proof_output and result.get("method_registry_proof"):
        pout = Path(args.proof_output)
        pout.parent.mkdir(parents=True, exist_ok=True)
        with open(pout, "w", encoding="utf-8") as f:
            json.dump(result["method_registry_proof"], f, indent=2)
        print(f"wrote {pout}")
    mt = result["method_table"]
    v = result["validations"]
    print(f"method_table n={mt['record_count']} entry_size={mt['entry_size']}")
    print(f"method_partition_exact_once={v['method_partition']['covered_exactly_once']}")
    print(f"declaring_type_all_match={v['declaring_type_match']['all_match']}")
    print(f"parameter_partition_exact_once={v['parameter_partition']['covered_exactly_once']}")
    print(f"proof_status={result['method_registry_proof']['status']}")
    for row in result["method_registry_proof"]["samples"][:12]:
        print(f"  [{row['method_index']}] {row['declaring_type']}.{row['name']}"
              f" params={row['parameter_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
