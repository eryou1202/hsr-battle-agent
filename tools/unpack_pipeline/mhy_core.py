# -*- coding: utf-8 -*-
"""Core MHY metadata decode primitives used by the pipeline.

This module is the thin engineering adapter around the CONFIRMED reverse
results.  It contains no new discovery logic:

  * directory transform rules      - docs/reverse/mhy_metadata_registry_4.4.54.md
  * identifier resolver            - docs/reverse/mhy_type_registry_proof_4.4.54.md
  * Type/Method/Field definitions  - docs/reverse/mhy_member_registry_proof_4.4.54.md

All algorithms are reused verbatim from
`tools/reverse/scripts/analyze_mhy_definition_candidate.py`,
`analyze_mhy_method_candidate.py` and `analyze_mhy_field_candidate.py`, minus
the optional Capstone consumer-scan that is not required for normalized output.
"""
from __future__ import annotations

import mmap
import struct
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .common import PeImage

FILE_HEADER = 0x208
MHY_MAGIC = b"MHY\x00\x00\x00\x00\x00"
M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1

# (field, op, const, role)
RULES: dict[int, tuple[str, int, str]] = {
    0x18: ("add", 0xE6CD8E6C, "next known table after 0x12C"),
    0x20: ("add", 0xB2FCE189, "FieldDefinition table"),
    0x30: ("add", 0xDCF5FDBE, "ParameterDefinition table"),
    0x38: ("add", 0xF778F1AB, "next known table after TypeDefinition"),
    0x70: ("xor", 0x57A78949, "TypeDefinition index map"),
    0x84: ("xor", 0x68531D3F, "TypeDefinition table"),
    0xF0: ("add", 0x9D48920F, "16-byte type-relation table"),
    0x124: ("xor", 0x1AFCE463, "next known table after 0xF0"),
    0x12C: ("xor", 0x26F0FC20, "type descriptor index table"),
    0x14C: ("add", 0xF3A04294, "MethodDefinition table"),
    0x160: ("add", 0xC769CD52, "usage table (next after MethodDefinition)"),
    0x1B4: ("add", 0x8D43A4EE, "identifier ciphertext heap"),
    0x1C8: ("xor", 0x042F9275, "next known table after ParameterDefinition"),
}

# Identifier resolver constants (code-proven at 0x3C58D70 for 4.4.54).
ID_HASH_MUL = 0x907C49622D94D21A
ID_HASH_ADD = 0x75B679DAF67C3F24
ID_ROLL = 0x3E693CD23A41FDEF
ID_POS_MASK = 0x1FFFFFF
ID_NEG_MASK = 0x7FFFFF

# TypeDefinition field decode constants.
TYPE_METHOD_START_XOR = 0x1A7AF5FE
TYPE_METHOD_COUNT_ADD = 0x5F93
TYPE_FIELD_START_ADD = 0x8B7AC79C
TYPE_FIELD_COUNT_ADD = 0x444D
TYPE_NAMESPACE_ADD = 0xF1D32D89
TYPE_NAME_ADD = 0xE9FD68F8
TYPE_DESC_START_XOR = 0xB2C0
TYPE_DESC_COUNT_ADD = 4
TYPE_DESC_SENTINEL = 0xFC
TYPE_RELATION_ADD = 0x5404
TYPE_RELATION_SENTINEL = 0xFFFF
TYPE_MAGIC_GATE = 0x1C2AD2AB

# MethodDefinition per-index rolling hash.
METHOD_HASH_MUL1 = 0x31E1
METHOD_HASH_XOR = 0x33914937
METHOD_HASH_MUL2 = 0x2C03F17D
METHOD_HASH_SHR2 = 0x17
METHOD_HASH_MUL3 = 0x540CC9F4
METHOD_HASH_SHR3 = 0x15
METHOD_HASH_ADD = 0x71BC7861

FIELD_NAME_CONST = 0x0E714BC1
FIELD_PARAM_START_CONST = 0x009889B8
FIELD_RETURN_ADD_CONST = 0x9AC1F4E3
FIELD_FLAGS0C_CONST = 0x09F73733
FIELD_DECLARING_CONST = 0x2A5FABE8
FIELD_SLOT14_ADD_CONST = 0xFFFF86FD
FIELD_GENERIC16_ADD_CONST = 0xFFFFE395
FIELD_PARAM_COUNT_CONST = 0xA8

# ParameterDefinition rolling transform.
PARAM_HASH_MUL = 0x72E1D74B12B
PARAM_HASH_ADD = 0x1911D05AFF5
PARAM_HASH_SHR = 0xB
PARAM_ROLL_MUL = 0x58B870A2
PARAM_ROLL_ADD = 0x83CF7B44
PARAM_NAME_XOR = 0x7103092E
PARAM_TYPE_XOR = 0x67E90DC5

# FieldDefinition per-type rolling transform.
FIELD_ROLL_BASE = 0xAD416BB9
FIELD_ROLL_MUL = 0x2C5DCB00
FIELD_ROLL_STEP = 0xD3A23500
FIELD_NAME_ADD = 0x2AAFC785


def signed32(value: int) -> int:
    value &= M32
    return value - 0x100000000 if value & 0x80000000 else value


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & M32
    if op == "xor":
        return raw ^ const
    raise ValueError(f"unsupported transform op: {op}")


def locate_template_rva(pe: PeImage) -> int:
    """Locate the first per-build MHY template block (pure byte search)."""
    chunk = 1 << 26
    pos = 0
    prev = b""
    with open(pe.path, "rb") as fh:
        while True:
            fh.seek(pos)
            data = fh.read(chunk)
            if not data:
                break
            buf = prev + data
            index = buf.find(MHY_MAGIC)
            if index >= 0:
                file_offset = pos - len(prev) + index
                for section in pe.sections:
                    if section.raw_offset <= file_offset < section.raw_offset + section.raw_size:
                        return section.rva + (file_offset - section.raw_offset)
                raise RuntimeError(f"MHY magic at file+0x{file_offset:X} is not section-mapped")
            prev = data[-16:]
            pos += len(data)
    raise RuntimeError("MHY template magic not found in GameAssembly")


def resolve_identifier(key: int, region: bytes) -> bytes:
    """Code-proven identifier resolver (rolling 64-bit XOR)."""
    key &= M32
    if key == M32:
        return b""
    negative = bool(key & 0x80000000)
    if negative:
        offset = key & ID_NEG_MASK
        length = (key >> 23) & 0xFF
    else:
        offset = key & ID_POS_MASK
        length = (key >> 25) & 0x3F
    seed = (ID_HASH_ADD + ID_HASH_MUL * offset) & M64
    out = bytearray()
    cursor = offset
    for _ in range((length + 7) // 8):
        if cursor + 8 > len(region):
            break
        cipher = struct.unpack_from("<Q", region, cursor)[0]
        plain = (cipher ^ seed) & M64
        out += plain.to_bytes(8, "little")
        cursor += 8
        seed = (seed + ID_ROLL) & M64
    return bytes(out[:length])


class MhyModel:
    """One version's decoded MHY metadata registries, ready for normalization."""

    def __init__(self, game_assembly: Path, metadata: Path,
                 template_rva: int | None = None):
        self.game_assembly = game_assembly
        self.metadata = metadata
        self.pe = PeImage(game_assembly)
        self.template_rva = template_rva if template_rva is not None else locate_template_rva(self.pe)
        self.block = self.pe.read_rva(self.template_rva, 0x208)
        if self.block is None or len(self.block) != 0x208:
            raise RuntimeError("failed to read MHY template block")
        self.offsets: dict[int, int] = {}
        for field, (op, const, _role) in RULES.items():
            raw = struct.unpack_from("<I", self.block, field)[0]
            decoded = decode_rule(raw, op, const)
            self.offsets[field] = FILE_HEADER + signed32(decoded)

        self.file = open(self.metadata, "rb")
        self.mm = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        self.size = self.metadata.stat().st_size
        self._validate_offsets()

        self.tbase = self.offsets[0x84]
        self.tnext = self.offsets[0x38]
        self.mbase = self.offsets[0x14C]
        self.mnext = self.offsets[0x160]
        self.fbase = self.offsets[0x20]
        self.pbase = self.offsets[0x30]
        self.pnext = self.offsets[0x1C8]
        self.region_base = self.offsets[0x1B4]
        self.region = self.mm[self.region_base: self.region_base + min(self.size - self.region_base, 1 << 26)]
        self._id_cache: dict[int, str] = {}

        self.ntypes = (self.tnext - self.tbase) // 70
        if self.ntypes <= 0:
            raise ValueError("non-positive TypeDefinition table capacity")
        self._decode_types()
        self._decode_methods()
        self._decode_parameters()
        self._decode_fields()
        self.validations = self._build_validations()

    def close(self) -> None:
        if self.mm is not None:
            self.mm.close()
            self.mm = None
        if self.file is not None:
            self.file.close()
            self.file = None

    def __enter__(self) -> "MhyModel":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    def _validate_offsets(self) -> None:
        problems = []
        for field, offset in self.offsets.items():
            if not (0 <= offset < self.size):
                problems.append(f"field 0x{field:X} -> offset 0x{offset:X} outside metadata")
        if not (self.offsets[0x84] < self.offsets[0x38] < self.offsets[0x14C]
                < self.offsets[0x160]):
            problems.append("core table order 0x84 < 0x38 < 0x14C < 0x160 violated")
        if problems:
            raise RuntimeError("MHY table locator failed: " + "; ".join(problems))

    # ------------------------------------------------------------------
    def identifier(self, key: int) -> str:
        cached = self._id_cache.get(key)
        if cached is None:
            cached = resolve_identifier(key, self.region).decode("utf-8", "replace")
            self._id_cache[key] = cached
        return cached

    def type_name(self, type_index: int) -> str:
        base = self.tbase + type_index * 70
        raw24 = struct.unpack_from("<I", self.mm, base + 0x24)[0]
        raw28 = struct.unpack_from("<I", self.mm, base + 0x28)[0]
        namespace = self.identifier((raw24 + TYPE_NAMESPACE_ADD) & M32)
        name = self.identifier((raw28 + TYPE_NAME_ADD) & M32)
        return f"{namespace}.{name}" if namespace else name

    # ------------------------------------------------------------------
    def _decode_types(self) -> None:
        n = self.ntypes
        mm = self.mm
        base = self.tbase
        self.t_raw08 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=base + 0x08, strides=(70,))
        self.t_raw0c = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=base + 0x0C, strides=(70,))
        self.t_raw20 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=base + 0x20, strides=(70,))
        self.t_raw24 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=base + 0x24, strides=(70,))
        self.t_raw28 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=base + 0x28, strides=(70,))
        self.t_raw32 = np.ndarray(shape=(n,), dtype="<u2", buffer=mm, offset=base + 0x32, strides=(70,))
        self.t_raw34 = np.ndarray(shape=(n,), dtype="<u2", buffer=mm, offset=base + 0x34, strides=(70,))
        self.t_raw3a = np.ndarray(shape=(n,), dtype="<i2", buffer=mm, offset=base + 0x3A, strides=(70,))
        self.t_raw3c = np.ndarray(shape=(n,), dtype="<u2", buffer=mm, offset=base + 0x3C, strides=(70,))
        self.t_raw43 = np.ndarray(shape=(n,), dtype="u1", buffer=mm, offset=base + 0x43, strides=(70,))
        self.t_raw44 = np.ndarray(shape=(n,), dtype="u1", buffer=mm, offset=base + 0x44, strides=(70,))

        starts = (self.t_raw08.astype(np.uint32) ^ np.uint32(TYPE_METHOD_START_XOR)).astype(np.int64)
        starts = np.where(starts >= 0x80000000, starts - 0x100000000, starts)
        counts = ((self.t_raw34.astype(np.uint32) + TYPE_METHOD_COUNT_ADD) & 0xFFFF).astype(np.int64)
        self.t_method_start = starts
        self.t_method_count = counts

        field_starts = ((self.t_raw20.astype(np.uint32) + np.uint32(TYPE_FIELD_START_ADD))
                        & np.uint32(0xFFFFFFFF)).astype(np.int64)
        field_counts = (((self.t_raw32.astype(np.uint32) + TYPE_FIELD_COUNT_ADD)
                         & 0xFFFF)).astype(np.int64)
        self.t_field_start = field_starts
        self.t_field_count = field_counts

        desc_starts = ((self.t_raw3a.astype(np.uint16) ^ np.uint16(TYPE_DESC_START_XOR))
                       .astype(np.int64))
        desc_starts = np.where(desc_starts >= 0x8000, desc_starts - 0x10000, desc_starts)
        self.t_desc_start = desc_starts
        self.t_desc_count = ((self.t_raw43.astype(np.uint16) + TYPE_DESC_COUNT_ADD) & 0xFF).astype(np.int64)
        relation = ((self.t_raw3c.astype(np.uint32) + TYPE_RELATION_ADD) & 0xFFFF).astype(np.int64)
        self.t_relation_index = np.where(relation == TYPE_RELATION_SENTINEL, -1, relation)
        self.t_44_decoded = (self.t_raw44.astype(np.uint16) ^ 0xC7).astype(np.int64)

    def _decode_methods(self) -> None:
        capacity = (self.mnext - self.mbase) // 26
        ntypes = self.ntypes
        valid = self.t_method_start >= 0
        method_total = int(self.t_method_count[valid].sum())
        if capacity != method_total:
            raise RuntimeError(
                f"method partition no longer exact: capacity={capacity} partition_total={method_total}")
        self.nmethods = method_total
        mm = self.mm
        n = method_total
        idx = np.arange(n, dtype=np.uint64)
        x = (idx * METHOD_HASH_MUL1) & M64
        x ^= METHOD_HASH_XOR
        x = (x * METHOD_HASH_MUL2) & M64
        x >>= METHOD_HASH_SHR2
        x = (x * METHOD_HASH_MUL3) & M64
        x >>= METHOD_HASH_SHR3
        h32c = ((x + METHOD_HASH_ADD) & M32).astype(np.uint32)
        low8 = ((x + METHOD_HASH_ADD) & 0xFF).astype(np.uint8)
        low16 = ((x + METHOD_HASH_ADD) & 0xFFFF).astype(np.uint16)

        f0 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=self.mbase + 0x00, strides=(26,))
        f4 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=self.mbase + 0x04, strides=(26,))
        f8 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=self.mbase + 0x08, strides=(26,))
        f0c = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=self.mbase + 0x0C, strides=(26,))
        f0e = np.ndarray(shape=(n,), dtype="<u2", buffer=mm, offset=self.mbase + 0x0E, strides=(26,))
        f10 = np.ndarray(shape=(n,), dtype="<u4", buffer=mm, offset=self.mbase + 0x10, strides=(26,))
        f14 = np.ndarray(shape=(n,), dtype="<u2", buffer=mm, offset=self.mbase + 0x14, strides=(26,))
        f16 = np.ndarray(shape=(n,), dtype="<u2", buffer=mm, offset=self.mbase + 0x16, strides=(26,))
        f18 = np.ndarray(shape=(n,), dtype="u1", buffer=mm, offset=self.mbase + 0x18, strides=(26,))
        f19 = np.ndarray(shape=(n,), dtype="u1", buffer=mm, offset=self.mbase + 0x19, strides=(26,))

        self.m_name_key = (h32c ^ f0.astype(np.uint32) ^ np.uint32(FIELD_NAME_CONST)).astype(np.uint32)
        ps = (h32c ^ f4.astype(np.uint32) ^ np.uint32(FIELD_PARAM_START_CONST)).astype(np.int64)
        self.m_param_start = np.where(ps >= 0x80000000, ps - 0x100000000, ps)
        ret = (h32c ^ ((f8.astype(np.uint32) + np.uint32(FIELD_RETURN_ADD_CONST)) & M32)).astype(np.int64)
        self.m_return_ref = np.where(ret >= 0x80000000, ret - 0x100000000, ret)
        self.m_flags0c = (h32c ^ f0c.astype(np.uint32) ^ np.uint32(FIELD_FLAGS0C_CONST)).astype(np.uint32)
        self.m_flags0e = (low16 ^ f0e.astype(np.uint16)).astype(np.uint16)
        declaring = (h32c ^ f10.astype(np.uint32) ^ np.uint32(FIELD_DECLARING_CONST)).astype(np.int64)
        self.m_declaring_type = np.where(declaring >= 0x80000000, declaring - 0x100000000, declaring)
        slot_u = (((f14.astype(np.uint32) + FIELD_SLOT14_ADD_CONST) & 0xFFFF)
                  ^ low16.astype(np.uint32)).astype(np.int64)
        self.m_slot14 = np.where(slot_u >= 0x8000, slot_u - 0x10000, slot_u)
        self.m_generic16 = (((f16.astype(np.uint32) + FIELD_GENERIC16_ADD_CONST) & 0xFFFF)
                            ^ low16.astype(np.uint32)).astype(np.uint16)
        self.m_param_count = (f18.astype(np.uint16) ^ low8.astype(np.uint16) ^ 0xA8).astype(np.int64)
        self.m_flags19 = (f19.astype(np.uint16) ^ low8.astype(np.uint16)).astype(np.uint8)

        # Owner array (method index -> TypeDefinition index) for validation.
        recidx = np.arange(ntypes, dtype=np.int64)[valid]
        self.m_owner = np.repeat(recidx, self.t_method_count[valid].astype(np.int64))
        self.m_index = idx
        self.m_h32c = h32c

    def _decode_parameters(self) -> None:
        pcapacity = (self.pnext - self.pbase) // 8
        ptotal = int(self.m_param_count.sum())
        if pcapacity != ptotal:
            raise RuntimeError(
                f"parameter partition no longer exact: capacity={pcapacity} partition_total={ptotal}")
        self.nparams = ptotal
        n = ptotal
        if n == 0:
            self.p_method_owner = np.empty(0, dtype=np.int64)
            self.p_name_key = np.empty(0, dtype=np.uint32)
            self.p_type_ref = np.empty(0, dtype=np.int64)
            return
        q = np.arange(n, dtype=np.uint64)
        roll64 = ((q * PARAM_HASH_MUL + PARAM_HASH_ADD) >> PARAM_HASH_SHR)
        roll = ((roll64 * PARAM_ROLL_MUL + PARAM_ROLL_ADD) & M32).astype(np.uint32)
        f0 = np.ndarray(shape=(n,), dtype="<u4", buffer=self.mm, offset=self.pbase, strides=(8,))
        f4 = np.ndarray(shape=(n,), dtype="<u4", buffer=self.mm, offset=self.pbase + 4, strides=(8,))
        name_key = ((f4.astype(np.uint32) ^ np.uint32(PARAM_NAME_XOR)) - roll).astype(np.uint32)
        type_ref = ((f0.astype(np.uint32) ^ np.uint32(PARAM_TYPE_XOR)) - roll).astype(np.int64)
        type_ref = np.where(type_ref >= 0x80000000, type_ref - 0x100000000, type_ref)
        valid = self.m_param_count > 0
        owner = np.repeat(np.arange(self.nmethods, dtype=np.int64)[valid],
                          self.m_param_count[valid].astype(np.int64))
        self.p_method_owner = owner.astype(np.int64)
        self.p_name_key = name_key
        self.p_type_ref = type_ref

    def _decode_fields(self) -> None:
        ntypes = self.ntypes
        valid = self.t_field_count > 0
        field_total = int(self.t_field_count[valid].sum())
        self.nfields = field_total
        n = field_total
        if n == 0:
            self.f_owner = np.empty(0, dtype=np.int64)
            self.f_name_key = np.empty(0, dtype=np.uint32)
            self.f_type_ref = np.empty(0, dtype=np.int64)
            return
        owner = np.repeat(np.arange(ntypes, dtype=np.int64)[valid],
                          self.t_field_count[valid].astype(np.int64))
        local = np.arange(n, dtype=np.int64) - np.repeat(
            self.t_field_start[valid].astype(np.int64),
            self.t_field_count[valid].astype(np.int64))
        raw_starts = self.t_raw20[owner]
        roll0 = (np.uint32(FIELD_ROLL_BASE)
                 - (raw_starts.astype(np.uint64) * FIELD_ROLL_MUL & np.uint64(0xFFFFFFFF))
                   .astype(np.uint32)).astype(np.uint32)
        roll = (roll0.astype(np.uint64)
                + ((local.astype(np.uint64) * FIELD_ROLL_STEP) & np.uint64(0xFFFFFFFF))).astype(np.uint32)
        f0 = np.ndarray(shape=(n,), dtype="<u4", buffer=self.mm, offset=self.fbase, strides=(8,))
        f4 = np.ndarray(shape=(n,), dtype="<u4", buffer=self.mm, offset=self.fbase + 4, strides=(8,))
        self.f_owner = owner
        self.f_name_key = ((f0.astype(np.uint32) + roll + np.uint32(FIELD_NAME_ADD))
                           & np.uint32(0xFFFFFFFF)).astype(np.uint32)
        type_ref = (f4.astype(np.uint32) + roll).astype(np.uint32).astype(np.int64)
        self.f_type_ref = np.where(type_ref >= 0x80000000, type_ref - 0x100000000, type_ref)

    # ------------------------------------------------------------------
    def _partition_check(self, starts: np.ndarray, counts: np.ndarray,
                         total: int, kind: str) -> dict[str, Any]:
        valid = counts > 0
        cumulative_ok = True
        expected = 0
        for start, count in zip(starts.tolist(), counts.tolist()):
            if count == 0:
                continue
            if start != expected:
                cumulative_ok = False
                break
            expected += int(count)
        coverage = np.zeros(total, dtype=np.uint8)
        for start, count in zip(starts[valid].tolist(), counts[valid].tolist()):
            coverage[start: start + count] += 1
        return {
            "kind": kind,
            "total": total,
            "rows_with_records": int(valid.sum()),
            "rows_without_records": int((~valid).sum()),
            "covered_exactly_once": bool(coverage.sum() == total and np.all(coverage == 1)),
            "cumulative_record_order_ok": cumulative_ok,
            "max_end": int((starts[valid] + counts[valid]).max()) if valid.any() else 0,
        }

    def _build_validations(self) -> dict[str, Any]:
        desc_valid = self.t_desc_count > 0
        cap_desc = (self.offsets[0x18] - self.offsets[0x12C]) // 4
        desc_ok = True
        desc_total = int(self.t_desc_count.sum())
        if cap_desc > 0:
            desc_cov = np.zeros(cap_desc, dtype=np.uint8)
            for start, count in zip(self.t_desc_start[desc_valid].tolist(),
                                    self.t_desc_count[desc_valid].tolist()):
                if not (0 <= start and start + count <= cap_desc):
                    desc_ok = False
                    continue
                desc_cov[start: start + count] += 1
        else:
            desc_cov = np.zeros(0, dtype=np.uint8)
        cap_f0 = (self.offsets[0x124] - self.offsets[0xF0]) // 16
        f0_ok = bool(np.all((self.t_relation_index < 0) | (self.t_relation_index < cap_f0)))
        return {
            "type_count": self.ntypes,
            "method_count": self.nmethods,
            "parameter_count": self.nparams,
            "field_count": self.nfields,
            "method_partition": self._partition_check(
                self.t_method_start, self.t_method_count, self.nmethods, "method"),
            "field_partition": self._partition_check(
                self.t_field_start, self.t_field_count, self.nfields, "field"),
            "parameter_partition": self._partition_check(
                self.m_param_start, self.m_param_count, self.nparams, "parameter"),
            "declaring_type_all_match": bool(np.all(self.m_declaring_type == self.m_owner)),
            "declaring_type_mismatch_count": int((self.m_declaring_type != self.m_owner).sum()),
            "type_descriptor_ranges_in_bounds": bool(desc_ok),
            "type_descriptor_coverage_exact_once": bool(
                desc_ok and desc_cov.sum() == cap_desc and np.all(desc_cov == 1)) if cap_desc else None,
            "type_relation_indices_in_bounds": bool(f0_ok),
        }

    # ------------------------------------------------------------------
    def iter_types(self) -> Iterator[dict[str, Any]]:
        for ti in range(self.ntypes):
            raw24 = int(self.t_raw24[ti])
            raw28 = int(self.t_raw28[ti])
            namespace = self.identifier((raw24 + TYPE_NAMESPACE_ADD) & M32)
            name = self.identifier((raw28 + TYPE_NAME_ADD) & M32)
            yield {
                "type_index": ti,
                "namespace": namespace,
                "name": name,
                "full_name": f"{namespace}.{name}" if namespace else name,
                "parent_base": None,
                "method_start": int(self.t_method_start[ti]),
                "method_count": int(self.t_method_count[ti]),
                "field_start": int(self.t_field_start[ti]),
                "field_count": int(self.t_field_count[ti]),
                "type_descriptor_start": int(self.t_desc_start[ti]),
                "type_descriptor_count": int(self.t_desc_count[ti]),
                "type_relation_index_0xF0": int(self.t_relation_index[ti]),
                "field_0x0C_raw": f"0x{int(self.t_raw0c[ti]):08X}",
                "field_0x0C_matches_gate": bool(int(self.t_raw0c[ti]) == TYPE_MAGIC_GATE),
                "field_0x43_raw": f"0x{int(self.t_raw43[ti]):02X}",
                "field_0x44_decoded": int(self.t_44_decoded[ti]),
                "structure_status": "CONFIRMED",
                "semantic_status": "TYPE_IDENTITY_CONFIRMED",
            }

    def iter_methods(self) -> Iterator[dict[str, Any]]:
        for mi in range(self.nmethods):
            yield {
                "method_index": mi,
                "declaring_type_index": int(self.m_declaring_type[mi]),
                "name": self.identifier(int(self.m_name_key[mi])),
                "parameter_start": int(self.m_param_start[mi]),
                "parameter_count": int(self.m_param_count[mi]),
                "return_type_reference": int(self.m_return_ref[mi]),
                "slot_0x14_decoded": int(self.m_slot14[mi]),
                "flags_0x0E_decoded": int(self.m_flags0e[mi]),
                "flags_0x0C_decoded": f"0x{int(self.m_flags0c[mi]):08X}",
                "field_0x16_decoded": int(self.m_generic16[mi]),
                "flags_0x19_decoded": int(self.m_flags19[mi]),
                "structure_status": "CONFIRMED",
                "semantic_status": "METHOD_IDENTITY_CONFIRMED",
            }

    def iter_fields(self) -> Iterator[dict[str, Any]]:
        for fi in range(self.nfields):
            yield {
                "field_index": fi,
                "declaring_type_index": int(self.f_owner[fi]),
                "name": self.identifier(int(self.f_name_key[fi])),
                "type_reference": int(self.f_type_ref[fi]),
                "structure_status": "CONFIRMED",
                "semantic_status": "FIELD_IDENTITY_CONFIRMED",
            }

    def iter_parameters(self) -> Iterator[dict[str, Any]]:
        for pi in range(self.nparams):
            yield {
                "parameter_index": pi,
                "method_index": int(self.p_method_owner[pi]),
                "name_key": f"0x{int(self.p_name_key[pi]):08X}",
                "name": self.identifier(int(self.p_name_key[pi])),
                "type_reference": int(self.p_type_ref[pi]),
                "structure_status": "CONFIRMED",
                "semantic_status": ("PARAMETER_NAME_STRIPPED"
                                    if int(self.p_name_key[pi]) == M32 else "UNKNOWN"),
            }

    def find_method(self, type_full_name: str, method_name: str) -> int | None:
        for mi in range(self.nmethods):
            declaring = int(self.m_declaring_type[mi])
            if self.type_name(declaring) == type_full_name:
                if self.identifier(int(self.m_name_key[mi])) == method_name:
                    return mi
        return None


if __name__ == "__main__":
    import argparse
    import time
    ap = argparse.ArgumentParser()
    ap.add_argument("game", type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    args = ap.parse_args()
    started = time.time()
    with MhyModel(args.game, args.metadata, args.template_rva) as model:
        print(f"template_rva=0x{model.template_rva:X}")
        print(model.validations)
        for row in list(model.iter_types())[:8]:
            print(row["type_index"], row["full_name"], row["method_start"], row["method_count"])
    print(f"elapsed={time.time() - started:.1f}s")
