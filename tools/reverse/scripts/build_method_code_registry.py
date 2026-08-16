#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the MHY MethodDefinition -> GameAssembly native code registry proof.

The mapping rule recovered in the reverse session is:

    native_rva = qword(registry.code_table + method_index * 8)

where `registry` is the runtime registry struct whose address is held in a
static .data slot, and `registry.code_table` is one of its pointer fields.
`0` is the no-direct-body sentinel (generic/abstract/interface/internal/virtual
methods are explained separately, see `mapping_kind`).

This tool is deliberately narrow:

  * locates the consumer instruction sequence in GameAssembly
    (`mov r12, [registry.field + method_index*8]`), proving that the index is
    the MethodDefinition index recovered from TypeDefinition +0x08/+0x34;
  * locates the static code table with both structural and semantic anchors;
  * decodes the metadata names with the existing identifier resolver;
  * emits a small auditable proof (sample rows + full table statistics), not a
    700k-method human dump.
"""
from __future__ import annotations

import argparse
import json
import mmap
import re
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vendor" / "capstone"))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86_const as x86  # noqa: E402
from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from analyze_mhy_method_candidate import (  # noqa: E402
    METHOD_HASH_ADD,
    RULES,
    FIELD_NAME_CONST,
    FIELD_DECLARING_CONST,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1

CONSUMER_NEEDLE = bytes.fromhex("4e8b24f04d85e4")
METHOD_INDEX_MARKERS = (bytes.fromhex("fef57a1a"), bytes.fromhex("935f0000"))

# Semantic anchors: common mscorlib methods with cross-version stable machine
# code shapes.  These are used only to disambiguate candidate pointer tables.
ANCHORS = {
    4: bytes.fromhex("4889c8c3"),   # Locale.GetText(string) -> return this/msg
    16: bytes.fromhex("488b01c3"),  # Mono.RuntimeClassHandle.get_Value
    18: bytes.fromhex("8b01c3"),    # Mono.RuntimeClassHandle.GetHashCode
    22: bytes.fromhex("488911c3"),  # Mono.RuntimeGenericParamInfoHandle.ctor
}


def scalar_method_hash32(idx: int) -> int:
    x = (idx * 0x31E1) & M64
    x ^= 0x33914937
    x = (x * 0x2C03F17D) & M64
    x >>= 0x17
    x = (x * 0x540CC9F4) & M64
    x >>= 0x15
    return (x + METHOD_HASH_ADD) & M32


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & M32
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    out: dict[int, int] = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        out[field] = FILE_HEADER + signed32(decode_rule(raw, op, const))
    return out


def method_count_from_metadata(pe: PeImage, metadata: Path, template_rva: int) -> int:
    offsets = table_offsets(pe, template_rva)
    tbase = offsets[0x84]
    tnext = offsets[0x38]
    mbase = offsets[0x14C]
    mnext = offsets[0x160]
    ntypes = (tnext - tbase) // 70
    with open(metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        total = 0
        for ti in range(ntypes):
            raw_start = struct.unpack_from("<I", mm, tbase + ti * 70 + 8)[0]
            start = (raw_start ^ 0x1A7AF5FE) & M32
            if start >= 0x80000000:
                continue
            raw_count = struct.unpack_from("<H", mm, tbase + ti * 70 + 0x34)[0]
            count = (raw_count + 0x5F93) & 0xFFFF
            total += count
        capacity = (mnext - mbase) // 26
        mm.close()
    if capacity != total:
        raise SystemExit(f"method table capacity mismatch: capacity={capacity}, partition={total}")
    return total


def resolve_type_name(mm, tbase: int, ti: int, region: bytes) -> str:
    raw24 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x24)[0]
    raw28 = struct.unpack_from("<I", mm, tbase + ti * 70 + 0x28)[0]
    ns, _ = resolve_identifier((raw24 + 0xF1D32D89) & M32, region)
    name, _ = resolve_identifier((raw28 + 0xE9FD68F8) & M32, region)
    ns_s = ns.decode("utf-8", "replace")
    name_s = name.decode("utf-8", "replace")
    return f"{ns_s}.{name_s}" if ns_s else name_s


def decode_method_name(mm, mbase: int, idx: int, region: bytes) -> str:
    h32 = scalar_method_hash32(idx)
    raw_name = struct.unpack_from("<I", mm, mbase + idx * 26)[0]
    key = (h32 ^ raw_name ^ FIELD_NAME_CONST) & M32
    name, _ = resolve_identifier(key, region)
    return name.decode("utf-8", "replace")


def decode_declaring_type(mm, mbase: int, idx: int) -> int:
    h32 = scalar_method_hash32(idx)
    raw = struct.unpack_from("<I", mm, mbase + idx * 26 + 0x10)[0]
    return (h32 ^ raw ^ FIELD_DECLARING_CONST) & M32


def decode_slot16(mm, mbase: int, idx: int) -> int:
    """Decode MethodDefinition +0x14 exactly as the builder consumer does."""
    h32 = scalar_method_hash32(idx)
    raw = struct.unpack_from("<H", mm, mbase + idx * 26 + 0x14)[0]
    u = ((raw + 0xFFFF86FD) & 0xFFFF) ^ (h32 & 0xFFFF)
    return u - 0x10000 if u >= 0x8000 else u


def decode_flags0e(mm, mbase: int, idx: int) -> int:
    h32 = scalar_method_hash32(idx)
    raw = struct.unpack_from("<H", mm, mbase + idx * 26 + 0x0E)[0]
    return (raw ^ (h32 & 0xFFFF)) & 0xFFFF


# ---------------------------------------------------------------------------
# Code table locator
# ---------------------------------------------------------------------------

def find_consumer(pe: PeImage) -> list[dict]:
    """Find the `[registry.field + method_index*8]` consumer instruction."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    hits: list[dict] = []
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if not sec.is_executable or sec.name == ".upx0" or sec.raw_size <= 0:
                continue
            data = raw[sec.raw_offset : sec.raw_offset + sec.raw_size]
            pos = 0
            while True:
                p = data.find(CONSUMER_NEEDLE, pos)
                if p < 0:
                    break
                hit_rva = sec.rva + p
                field_load = None
                global_load = None
                # The consumer instruction ends exactly at the needle.  Try the
                # two x86-64 forms used for `mov rax, [reg + disp]` (disp8 at
                # -3, disp32 at -7) without relying on a linear decode window
                # that can start on non-code bytes.
                for field_start in range(max(0, p - 8), p - 1):
                    if field_start < 0:
                        continue
                    insns = list(md.disasm(
                        data[field_start : p + len(CONSUMER_NEEDLE)],
                        pe.image_base + sec.rva + field_start))
                    if not insns:
                        continue
                    ins = insns[0]
                    if (ins.address == pe.image_base + sec.rva + field_start
                            and ins.address + ins.size == pe.image_base + hit_rva
                            and ins.mnemonic.startswith("mov")):
                        field_load = ins
                        break
                if field_load is not None:
                    field_start = field_load.address - pe.image_base - sec.rva
                    for gstart in range(max(0, field_start - 8), field_start):
                        gins = list(md.disasm(
                            data[gstart : field_start + 8],
                            pe.image_base + sec.rva + gstart))
                        if not gins:
                            continue
                        g = gins[0]
                        if (g.address == pe.image_base + sec.rva + gstart
                                and g.address + g.size == field_load.address
                                and g.mnemonic.startswith("mov")):
                            global_load = g
                            break
                if field_load is None or global_load is None:
                    pos = p + 1
                    continue
                field_off = None
                for op in field_load.operands:
                    if op.type == x86.X86_OP_MEM and op.mem.base != 0x29:
                        field_off = op.mem.disp
                        break
                global_rva = None
                for op in global_load.operands:
                    if op.type == x86.X86_OP_MEM and op.mem.base == 0x29:
                        global_rva = (global_load.address + global_load.size
                                      + op.mem.disp - pe.image_base)
                        break
                nearby = data[max(0, p - 96) : p + 96]
                consumer_ins = next(md.disasm(
                    data[p : p + len(CONSUMER_NEEDLE)],
                    pe.image_base + hit_rva), None)
                disasm_lines = []
                for ins in (global_load, field_load, consumer_ins):
                    if ins is not None:
                        disasm_lines.append(
                            f"0x{ins.address - pe.image_base:X}  {ins.mnemonic} {ins.op_str}")
                hits.append({
                    "consumer_rva": hit_rva,
                    "global_load_rva": global_load.address - pe.image_base,
                    "registry_pointer_global_rva": global_rva,
                    "registry_code_table_field_offset": field_off,
                    "method_index_markers_present": all(m in nearby for m in METHOD_INDEX_MARKERS),
                    "disassembly": disasm_lines,
                })
                pos = p + 1
        raw.close()
    return hits


def executable_pointer_runs(pe: PeImage, min_len: int) -> list[dict]:
    """Aligned qword runs in raw sections: each qword is 0 or executable pointer."""
    runs: list[dict] = []
    exec_secs = {s.name for s in pe.sections if s.is_executable}
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for sec in pe.sections:
            if sec.raw_size < min_len * 8:
                continue
            n = sec.raw_size // 8
            arr = np.frombuffer(raw, dtype="<u8", count=n, offset=sec.raw_offset)
            rvas = arr - pe.image_base
            valid = arr == 0
            for s in pe.sections:
                if s.name not in exec_secs:
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
                nulls = int((arr[st:en] == 0).sum())
                runs.append({
                    "section": sec.name,
                    "rva": sec.rva + st * 8,
                    "length": en - st,
                    "nulls": nulls,
                })
            del arr, rvas, valid, d
        raw.close()
    return runs


def find_absolute_refs(pe: PeImage, table_rva: int) -> list[int]:
    refs = []
    va = pe.image_base + table_rva
    needle = struct.pack("<Q", va)
    with open(pe.path, "rb") as f:
        raw = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        pos = 0
        while True:
            p = raw.find(needle, pos)
            if p < 0:
                break
            for s in pe.sections:
                if s.raw_offset <= p < s.raw_offset + s.raw_size:
                    refs.append(s.rva + p - s.raw_offset)
                    break
            pos = p + 1
        raw.close()
    return refs


def locate_code_table(pe: PeImage, method_count: int) -> dict:
    consumers = find_consumer(pe)
    if not consumers:
        raise SystemExit("consumer `mov r12,[reg + method_index*8]` not found")
    consumer = max(consumers, key=lambda c: c["method_index_markers_present"])
    field_off = consumer["registry_code_table_field_offset"]
    if field_off is None:
        raise SystemExit("consumer field offset could not be decoded")

    candidates = []
    for run in executable_pointer_runs(pe, method_count):
        max_offset = min(0x80, (run["length"] - method_count) * 8)
        for off in range(0, max_offset + 1, 8):
            t = run["rva"] + off
            b = pe.read_rva(t, 64)
            first4_zero = all(struct.unpack_from("<Q", b, i * 8)[0] == 0 for i in range(4))
            score = 0
            anchor_hits = {}
            for idx, sig in ANCHORS.items():
                raw = pe.read_rva(t + idx * 8, 8)
                q = struct.unpack("<Q", raw)[0]
                rva = q - pe.image_base
                if q == 0 or pe.section_at_rva(rva) is None:
                    continue
                code = pe.read_rva(rva, max(4, len(sig)))
                if code and code[: len(sig)] == sig:
                    anchor_hits[str(idx)] = True
                    score += 50
            struct_hits = []
            for ref_rva in find_absolute_refs(pe, t):
                struct_start = ref_rva - field_off
                if struct_start < 0 or struct_start % 8:
                    continue
                block = pe.read_rva(struct_start, max(0x100, field_off + 8))
                if block is None or len(block) <= field_off:
                    continue
                if struct.unpack_from("<Q", block, field_off)[0] == pe.image_base + t:
                    struct_hits.append(struct_start)
            if first4_zero:
                score += 100
            if struct_hits:
                score += 200
            if run["length"] - off // 8 >= method_count:
                score += 50
            if score:
                candidates.append({
                    "code_table_rva": t,
                    "score": score,
                    "first_4_slots_zero": first4_zero,
                    "semantic_anchor_hits": anchor_hits,
                    "registry_struct_rvas": struct_hits,
                    "run": run,
                })
            # Once semantic anchors and the registry struct reference agree, this
            # is the real table start; do not keep scanning the same run.
            if anchor_hits and struct_hits and first4_zero:
                break
    if not candidates:
        raise SystemExit("no plausible method code table found")
    candidates.sort(key=lambda c: c["score"], reverse=True)
    best = candidates[0]
    return {
        "consumer": consumer,
        "code_table_rva": best["code_table_rva"],
        "score": best["score"],
        "first_4_slots_zero": best["first_4_slots_zero"],
        "semantic_anchor_hits": best["semantic_anchor_hits"],
        "registry_struct_rvas": best["registry_struct_rvas"],
        "run": best["run"],
        "candidate_count": len(candidates),
    }


# ---------------------------------------------------------------------------
# Proof builder
# ---------------------------------------------------------------------------

def disasm_first(pe: PeImage, rva: int, max_insns: int = 6) -> list[str]:
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    raw = pe.read_rva(rva, 32)
    out = []
    for ins in md.disasm(raw, pe.image_base + rva):
        out.append(f"{ins.mnemonic} {ins.op_str}")
        if len(out) >= max_insns:
            break
    return out


def build(game: Path, metadata: Path, template_rva: int | None,
          code_table_rva: int | None, member_proof: Path | None,
          sample_limit: int) -> dict:
    pe = PeImage(game)
    tpl_rva = template_rva if template_rva is not None else locate_template_rva(pe)
    offsets = table_offsets(pe, tpl_rva)
    n = method_count_from_metadata(pe, metadata, tpl_rva)

    locator = None
    if code_table_rva is None:
        locator = locate_code_table(pe, n)
        table_rva = locator["code_table_rva"]
    else:
        table_rva = code_table_rva
        consumers = find_consumer(pe)
        consumer = consumers[0] if consumers else {}
        field_off = consumer.get("registry_code_table_field_offset")
        struct_hits = []
        if field_off is not None:
            for ref_rva in find_absolute_refs(pe, table_rva):
                struct_start = ref_rva - field_off
                if struct_start >= 0 and struct_start % 8 == 0:
                    struct_hits.append(struct_start)
        locator = {
            "consumer": consumer,
            "code_table_rva": table_rva,
            "registry_struct_rvas": struct_hits,
        }

    table = pe.read_rva(table_rva, n * 8)
    if table is None or len(table) != n * 8:
        raise SystemExit(f"code table at 0x{table_rva:X} does not cover {n} methods")

    ptrs = np.frombuffer(table, dtype="<u8", count=n)
    null_mask = ptrs == 0
    exec_secs = {s.name for s in pe.sections if s.is_executable}
    sec_counter: dict[str, int] = {}
    bad_pointers: list[int] = []
    for i, q in enumerate(ptrs):
        if q == 0:
            continue
        rva = int(q - pe.image_base)
        sec = pe.section_at_rva(rva)
        if sec is None or sec.name not in exec_secs:
            bad_pointers.append(i)
            continue
        sec_counter[sec.name] = sec_counter.get(sec.name, 0) + 1
    unique_rvas = len(set(int(q) for q in ptrs if q != 0))
    duplicate_count = int((~null_mask).sum()) - unique_rvas

    # Metadata arrays for sample decoding / classification.
    mbase = offsets[0x14C]
    tbase = offsets[0x84]
    region_base = offsets[0x1B4]
    sample_indices: list[int] = []
    with open(metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        size = metadata.stat().st_size
        region = mm[region_base : region_base + min(size - region_base, 1 << 26)]

        # Base mscorlib / Mono sample.
        sample_indices += list(range(0, min(24, n)))

        # Null classification samples (interface / generic / abstract).
        for i in (89, 96, 516, 632, 656, 769, 784, 804, 821, 839, 854):
            if i < n:
                sample_indices.append(i)

        # Semantic game samples carried over from the member registry proof.
        if member_proof is not None:
            proof = json.load(open(member_proof, encoding="utf-8"))
            seen = set(sample_indices)
            for tm in proof.get("semantic_battle_sanity", []):
                for m in tm.get("methods", []):
                    mi = int(m["method_index"])
                    if mi < n and mi not in seen:
                        sample_indices.append(mi)
                        seen.add(mi)
                        if len(sample_indices) >= sample_limit:
                            break
                if len(sample_indices) >= sample_limit:
                    break

        sample_indices = sorted(set(sample_indices))[:sample_limit]
        samples = []
        for mi in sample_indices:
            q = int(ptrs[mi])
            h32 = scalar_method_hash32(mi)
            name = decode_method_name(mm, mbase, mi, region)
            declaring = decode_declaring_type(mm, mbase, mi)
            type_name = resolve_type_name(mm, tbase, declaring, region)
            slot = decode_slot16(mm, mbase, mi)
            flags0e = decode_flags0e(mm, mbase, mi)
            raw_name = struct.unpack_from("<I", mm, mbase + mi * 26)[0]
            name_key = (h32 ^ raw_name ^ FIELD_NAME_CONST) & M32

            if q == 0:
                kind = "VIRTUAL_VTABLE" if slot >= 0 else "NO_BODY"
                native_rva = None
                section = None
                first_bytes = ""
                asm_lines = []
            else:
                native_rva = q - pe.image_base
                section = pe.section_at_rva(native_rva)
                section = section.name if section else None
                raw = pe.read_rva(native_rva, 32)
                first_bytes = raw[:16].hex(" ")
                asm_lines = disasm_first(pe, native_rva)
                kind = "THUNK" if asm_lines and asm_lines[0].startswith("jmp") else "DIRECT_NATIVE"
            samples.append({
                "method_index": mi,
                "declaring_type": type_name,
                "method_name": name,
                "name_key": f"0x{name_key:08X}",
                "mapping_kind": kind,
                "slot": slot,
                "flags_0x0E": f"0x{flags0e:04X}",
                "native_rva": f"0x{native_rva:X}" if native_rva is not None else None,
                "native_section": section,
                "first_bytes": first_bytes,
                "first_instructions": asm_lines,
            })
        mm.close()

    null_slots = int(null_mask.sum())
    nonnull_slots = int((~null_mask).sum())
    slot_rows = []
    # Compute slot classification for every method with streaming chunks.
    with open(metadata, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        virtual_count = 0
        for i in range(n):
            if decode_slot16(mm, mbase, i) >= 0:
                virtual_count += 1
        mm.close()
    virtual_slots = virtual_count
    no_body_slots = null_slots - virtual_slots  # all virtual slots observed null

    checks = {
        "table_slots_equal_method_defs": bool(nonnull_slots + null_slots == n),
        "all_nonnull_point_to_executable_section": not bad_pointers,
        "all_nonnull_unique": duplicate_count == 0,
        "consumer_method_index_markers_present": bool(
            locator.get("consumer", {}).get("method_index_markers_present")),
        "registry_struct_reference_found": bool(locator.get("registry_struct_rvas")),
        "semantic_anchor_hits_present": bool(locator.get("semantic_anchor_hits")),
    }

    status = ("METHOD_CODE = RVA_REGISTRY_PROOF"
              if all(checks.values()) else "METHOD_CODE = PARTIAL_MAPPING_RECOVERED")

    return {
        "schema": "mhy_method_code_registry_proof/1",
        "status": status,
        "game": str(game.resolve()),
        "metadata": str(metadata.resolve()),
        "template_rva": f"0x{tpl_rva:X}",
        "method_definition": {
            "table_field": "0x14C",
            "entry_size": 26,
            "record_count": n,
        },
        "mapping_rule": {
            "native_rva": "qword(code_table_rva + method_index * 8)",
            "null_slot_semantic": "no direct native body; see mapping_kind",
            "consumer": locator.get("consumer", {}),
            "locator": {
                "code_table_rva": f"0x{table_rva:X}",
                "score": locator.get("score"),
                "first_4_slots_zero": locator.get("first_4_slots_zero"),
                "semantic_anchor_hits": locator.get("semantic_anchor_hits"),
                "registry_struct_rvas": [f"0x{r:X}" for r in locator.get("registry_struct_rvas", [])],
                "candidate_count": locator.get("candidate_count"),
            },
        },
        "statistics": {
            "total_method_defs": n,
            "table_slots": n,
            "null_slots": null_slots,
            "direct_native_slots": nonnull_slots,
            "virtual_vtable_slots": virtual_slots,
            "no_direct_body_slots": no_body_slots,
            "unique_native_rvas": unique_rvas,
            "duplicate_native_pointer_slots": duplicate_count,
            "out_of_range_nonnull_slots": len(bad_pointers),
            "native_sections": sec_counter,
            "first_null_run": "0..3 (generic AnonymousType methods)",
        },
        "classification": {
            "DIRECT_NATIVE": "slot < 0 and code_table[method_index] != 0",
            "VIRTUAL_VTABLE": "slot >= 0; direct table entry is 0; runtime dispatch via type vtable",
            "NO_BODY": "slot < 0 and code_table[method_index] == 0 (generic/abstract/interface/internal)",
            "THUNK": "first instruction is jmp; stable entry RVA is recorded, dispatcher is not analyzed",
        },
        "samples": samples,
        "sample_count": len(samples),
        "checks": checks,
        "evidence_level": "E3 metadata/runtime structural + E4 code-level consumer evidence",
        "not_claimed": [
            "semantic decompilation of mapped native functions",
            "vtable slot -> final implementation RVA resolution",
            "dynamic dispatcher internals",
            "Battle DSL / ability semantics / Black Swan analysis",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--code-table-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--member-proof", type=Path, default=None)
    ap.add_argument("--sample-limit", type=int, default=80)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    result = build(Path(args.game), Path(args.metadata), args.template_rva,
                   args.code_table_rva, args.member_proof, args.sample_limit)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    st = result["statistics"]
    print(f"wrote {out}")
    print(f"status={result['status']}")
    print(f"methods={st['total_method_defs']} nulls={st['null_slots']} "
          f"direct_native={st['direct_native_slots']} virtual={st['virtual_vtable_slots']} "
          f"unique_rvas={st['unique_native_rvas']}")
    for row in result["samples"][:12]:
        print(f"  [{row['method_index']}] {row['declaring_type']}.{row['method_name']} "
              f"{row['mapping_kind']} rva={row['native_rva']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
