#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recover and validate the MHY metadata top-level table registry.

Consumer-driven registry for the custom MHY global-metadata format.

For each template field with code evidence, the registry stores:
  template_field
  transform_type
  transform_constant
  decoded_value
  base_kind        (payload | startup | count_only)
  file_offset      (when base_kind is payload)
  consumer_rvas
  entry_size
  entry_field_accesses
  candidate_semantic
  semantic_evidence
  structure_status
  semantic_status

Structure confidence and semantic confidence are deliberately separated.
Only `usage table` and the 0xC-branch triple table carry CONFIRMED semantic
roles from code; every other semantic name is a CANDIDATE or SUPPORTED
working hypothesis backed by the recorded code path, never by shape alone.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402

FILE_HEADER = 0x208
MHY_MAGIC = b"MHY\x00\x00\x00\x00\x00"


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


# ---------------------------------------------------------------------------
# Registry rules recovered from GameAssembly code.
# base_kind:
#   payload  -> file_offset = 0x208 + signed32(decoded), relative to
#               global-metadata.dat payload base (0x9D387B0)
#   startup  -> offset relative to startup-metadata.dat buffer (0x9D387B8)
#   count    -> decoded value is a count/size, not a table pointer
# ---------------------------------------------------------------------------

RULES: list[dict] = [
    # --- usage / type resolution chain (strongest code evidence) ---
    {"field": 0x160, "op": "add", "const": 0xC769CD52, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x5720", "0x1EB31", "0x263D9", "0x3C2DF23"],
     "entry_accesses": ["mov ecx,[base+idx*4]", "and low 0x1FFFFFFF", "and tag 0xE0000000"],
     "semantic": "metadata usage table (tagged index)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x5720: tag mask + cmp 0xC0000000 branch; many generated accessors"},
    {"field": 0x38, "op": "add", "const": 0xF778F1AB, "base": "payload",
     "entry_size": 12, "consumer_rvas": ["0x5778", "0x1EBB9", "0x3C2DF68"],
     "entry_accesses": ["record[0]", "record[1] (-1 sentinel)", "record[2] (-1 sentinel)"],
     "semantic": "12-byte triple table consumed by 0xC0000000 usage branch",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x5720 branch reads triples, resolves two pointer fields, caches result"},
    {"field": 0x1FC, "op": "xor", "const": 0x6238CDB0, "base": "payload",
     "entry_size": 12, "consumer_rvas": ["0x3C11478", "0x3C66719"],
     "entry_accesses": ["record[+0x0] -> 16-byte type entry index", "record[+0x4] -> data offset", "record[+0x8] = match key"],
     "semantic": "type-index lookup map (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C113C0 linear scan; +0 -> gptr+0x80 + idx*16; +4 -> table 0x3C byte offset"},
    {"field": 0x3C, "op": "add", "const": 0x978BE7A5, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C11520", "0x3C65CC7", "0x3C66765"],
     "entry_accesses": ["[base + field1_of_0x1FC_record]", "switch on first u32"],
     "semantic": "type-encoding data stream (candidate)",
     "structure": "SUPPORTED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C1151B adds 0x1FC record field1 to this base and interprets tokens"},
    # --- 70-byte definition table + index chain ---
    {"field": 0x84, "op": "xor", "const": 0x68531D3F, "base": "payload",
     "entry_size": 70, "consumer_rvas": ["0x3C82BAC", "0x3C67502", "0x3C5B5F1", "0x3C63107"],
     "entry_accesses": ["+0x0C magic == 0x1C2AD2AB", "+0x24 + 0xF1D32D89", "+0x28 + 0xE9FD68F8",
                        "+0x3A xor const", "+0x3C u16 + 0x5404", "+0x43 byte count"],
     "semantic": "definition records (method/type candidate)",
     "structure": "CONFIRMED", "semantic_status": "CANDIDATE",
     "semantic_evidence": "imul idx,0x46 addressing; magic validation; decoded fields feed metadata object builder"},
    {"field": 0x70, "op": "xor", "const": 0x57A78949, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C82BAC", "0x3C5F70E", "0x3C67762"],
     "entry_accesses": ["mov ecx,[base+idx*4]", "result indexes 0x84 records"],
     "semantic": "definition index map (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C82BAC: value -> imul 0x46 -> 0x84 record"},
    {"field": 0x12C, "op": "xor", "const": 0x26F0FC20, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C6730A", "0x3C5AE52"],
     "entry_accesses": ["mov ecx,[base+idx*4]", "value -> 0x3C66940"],
     "semantic": "type index table used by 0x84 record consumer (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C672F1-0x3C67325 loads word from 0x84 record, indexes this table, resolves type"},
    # --- range / lookup tables ---
    {"field": 0x18, "op": "add", "const": 0xE6CD8E6C, "base": "payload",
     "entry_size": 8, "consumer_rvas": ["0x3BFB767", "0x3C6F7E9", "0x3C7D98A"],
     "entry_accesses": ["binary search element size 8", "u32[0] = count<<24|start", "u32[4] = count<<24|start"],
     "semantic": "packed two-range table (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C6F9F4 splits count/start and iterates 0x1EC table"},
    {"field": 0x1EC, "op": "add", "const": 0xA75A2A51, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C6FA41"],
     "entry_accesses": ["movsxd [base+idx*4]", "-1 sentinel", "value indexes allocA pointer cache"],
     "semantic": "range target index table (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C6FA40-0x3C6FB1D"},
    {"field": 0x198, "op": "add", "const": 0xB10C86E7, "base": "payload",
     "entry_size": 8, "consumer_rvas": ["0x3C5D833"],
     "entry_accesses": ["decoded value sar 3 -> count", "binary search element size 8"],
     "semantic": "8-byte sorted lookup table (candidate)",
     "structure": "SUPPORTED", "semantic_status": "CANDIDATE",
     "semantic_evidence": "0x3C5D832: add const, sar 3, lower_bound at 0x184005310"},
    {"field": 0x1C4, "op": "xor", "const": 0x11531BF7, "base": "payload",
     "entry_size": 12, "consumer_rvas": ["0x3C5D7B7", "0x3C81254"],
     "entry_accesses": ["u16 [+0x8]", "u16 [+0xA]", "index -> 0x2C table"],
     "semantic": "12-byte definition/type record (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C5D7B3-0x3C5D7EB chains 0x34 -> 0x1C4 -> 0x2C"},
    {"field": 0x2C, "op": "xor", "const": 0x767BDACA, "base": "payload",
     "entry_size": 8, "consumer_rvas": ["0x3C5D467", "0x3C5D7D5"],
     "entry_accesses": ["lea [base + idx*8]", "feeds 0x183C03BA0"],
     "semantic": "8-byte value pair table (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C5D7E3-0x3C5D7EB"},
    {"field": 0x30, "op": "add", "const": 0xDCF5FDBE, "base": "payload",
     "entry_size": 8, "consumer_rvas": ["0x3C724D7"],
     "entry_accesses": ["[base + idx*8] type reference (-1 sentinel)",
                        "[base + idx*8 + 4] name key -> 0x3C58D70"],
     "semantic": "ParameterDefinition records", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED",
     "semantic_evidence": "MethodDefinition +0x04/+0x18 ranges cover this table exactly once; "
                         "type reference consumer 0x3C7250D-0x3C7254E; all observed name keys are 0xFFFFFFFF"},
    {"field": 0x34, "op": "xor", "const": 0x7FBFB3F8, "base": "payload",
     "entry_size": 2, "consumer_rvas": ["0x3C5D7A3"],
     "entry_accesses": ["movzx [base+idx*2]", "value indexes 0x1C4 records"],
     "semantic": "u16 index table (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C5D7A3-0x3C5D7CC"},
    {"field": 0x94, "op": "xor", "const": 0x3D160A8B, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C5D8A1", "0x3C3138A"],
     "entry_accesses": ["[base + idx*4] -> {count<<24|start}", "iterates count"],
     "semantic": "packed range table (candidate)",
     "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C5D89A-0x3C5D8B2"},
    # --- consumer-validated directory fields (structure only) ---
    {"field": 0x10, "op": "xor", "const": 0x22E64E71, "base": "payload",
     "entry_size": 2, "consumer_rvas": ["0x3C8123F"], "entry_accesses": ["movzx [base+idx*2]"],
     "semantic": "u16 table (UNKNOWN)", "structure": "CONFIRMED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x20, "op": "add", "const": 0xB2FCE189, "base": "payload",
     "entry_size": 8, "consumer_rvas": ["0x3C5C5CA", "0x3C5C5FC"],
     "entry_accesses": ["[base + idx*8] name key -> 0x3C58D70",
                        "[base + idx*8 + 4] field type reference (-1 sentinel)"],
     "semantic": "FieldDefinition records", "structure": "CONFIRMED",
     "semantic_status": "CONFIRMED",
     "semantic_evidence": "TypeDefinition +0x20/+0x32 ranges cover this table exactly once; "
                         "field names decode; +4 indexes the 16-byte type-entry array"},
    {"field": 0x4C, "op": "add", "const": 0xE82C6008, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C713B5"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x54, "op": "add", "const": 0xD43F4844, "base": "count",
     "entry_size": None, "consumer_rvas": ["0x3C81136", "0x3C81214"],
     "entry_accesses": ["decoded >> 2 = entry count"],
     "semantic": "size/4 count field (not a table offset)", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED", "semantic_evidence": "0x3C81136 shr 2; 0x3C81214 sar 2"},
    {"field": 0x78, "op": "xor", "const": 0x67325228, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C811FA", "0x3C81362"],
     "entry_accesses": ["movsxd [base+idx*4]"],
     "semantic": "index table (candidate)", "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C81345-0x3C81362"},
    {"field": 0x90, "op": "xor", "const": 0x697A7664, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C3130C"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x9C, "op": "add", "const": 0xBC7EC9D7, "base": "payload",
     "entry_size": 12, "consumer_rvas": ["0x3C5C4FC", "0x3C81225"],
     "entry_accesses": ["lea idx*3", "[base+idx*12]", "u16 fields"],
     "semantic": "12-byte record table (candidate)", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED", "semantic_evidence": "0x3C5C4FC-0x3C5C548, 0x3C81392"},
    {"field": 0xA8, "op": "xor", "const": 0x2CE30270, "base": "payload",
     "entry_size": 1, "consumer_rvas": ["0x3C5D53F", "0x3C5E076"],
     "entry_accesses": ["[base+idx*1+0x4]"],
     "semantic": "byte table (UNKNOWN)", "structure": "CONFIRMED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "0x3C5E0E0"},
    {"field": 0xB0, "op": "add", "const": 0x8B605DE7, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C6EEE1"], "entry_accesses": ["decodes to 0"],
     "semantic": "payload-start alias", "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "decoded == 0"},
    {"field": 0xC4, "op": "xor", "const": 0x38BDB304, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C5D826"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0xD0, "op": "add", "const": 0xDFCFC6B0, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C7F528"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0xEC, "op": "xor", "const": 0x67F701BA, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C80DD3"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0xF0, "op": "add", "const": 0x9D48920F, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C11716", "0x3C8F396"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x114, "op": "xor", "const": 0x3EABB25A, "base": "payload",
     "entry_size": 2, "consumer_rvas": ["0x3C5C937", "0x3C5D411"],
     "entry_accesses": ["movzx [base+idx*2+0x4]"],
     "semantic": "u16 table (UNKNOWN)", "structure": "CONFIRMED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "0x3C5C949"},
    {"field": 0x118, "op": "add", "const": 0xF6D615EF, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C811E0", "0x3C81345"],
     "entry_accesses": ["movsxd [base+idx*4]"],
     "semantic": "index table (candidate)", "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "0x3C81345"},
    {"field": 0x124, "op": "xor", "const": 0x1AFCE463, "base": "payload",
     "entry_size": 1, "consumer_rvas": ["0x3C8FF18"], "entry_accesses": ["[base+idx*1]"],
     "semantic": "byte table (UNKNOWN)", "structure": "CONFIRMED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "0x3C8FFA8"},
    {"field": 0x13C, "op": "xor", "const": 0x46C8010F, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C5E141"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x140, "op": "add", "const": 0xDAAC7309, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C21B22"], "entry_accesses": ["decodes to 0"],
     "semantic": "payload-start alias", "structure": "CONFIRMED", "semantic_status": "SUPPORTED",
     "semantic_evidence": "decoded == 0"},
    {"field": 0x144, "op": "xor", "const": 0x4CDE6970, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C6EF09"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x148, "op": "xor", "const": 0x329E1172, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C5C340", "0x3C5C643"],
     "entry_accesses": ["mov ebp,[base+idx*4]", "test 0x1000000", "low24 index"],
     "semantic": "usage-like u32 table (candidate)", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED", "semantic_evidence": "0x3C5C34E-0x3C5C383"},
    {"field": 0x14C, "op": "add", "const": 0xF3A04294, "base": "payload",
     "entry_size": 26, "consumer_rvas": ["0x3C66FBA", "0x3C71362", "0x3C71C7F",
                                           "0x3C72038", "0x3C72314", "0x3C7D45C"],
     "entry_accesses": ["idx*26", "[+0x00] name key -> 0x3C58D70", "[+0x04] parameter start",
                        "[+0x08] return type reference", "[+0x10] declaring type index",
                        "[+0x18] parameter count"],
     "semantic": "MethodDefinition records", "structure": "CONFIRMED",
     "semantic_status": "CONFIRMED",
     "semantic_evidence": "capacity == TypeDefinition method partition; names decode; "
                         "declaring type matches every range owner; parameter ranges cover 0x30 exactly once"},
    {"field": 0x180, "op": "add", "const": 0xE4DBE763, "base": "payload",
     "entry_size": 4, "consumer_rvas": ["0x3C5C514"],
     "entry_accesses": ["movsxd [base+idx*4]", "idx*12 -> 0x9C table"],
     "semantic": "index table into 0x9C records (candidate)", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED", "semantic_evidence": "0x3C5C540-0x3C5C548"},
    {"field": 0x184, "op": "add", "const": 0x8709B6A3, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C74C90"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x1AC, "op": "xor", "const": 0x37080D6E, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C5E924"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x1B4, "op": "add", "const": 0x8D43A4EE, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C59C5B"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x1C8, "op": "xor", "const": 0x042F9275, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C5F179"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x1D0, "op": "add", "const": 0xC9A664A5, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C6D109"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x1DC, "op": "xor", "const": 0x3E0C72F0, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C11434", "0x3C666DC"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    {"field": 0x1E4, "op": "xor", "const": 0x720FEF70, "base": "payload",
     "entry_size": None, "consumer_rvas": ["0x3C80DE8", "0x3C8316F"], "entry_accesses": ["base only"],
     "semantic": "UNKNOWN", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "none"},
    # --- startup-metadata relative fields (loader uses 0x9D387B8 base) ---
    {"field": 0x150, "op": "add", "const": 0xD882615E, "base": "startup",
     "entry_size": 40, "consumer_rvas": ["0x3C7F193"],
     "entry_accesses": ["idx*40", "[+0x0C] xor per-index", "writes runtime 0x58-byte records"],
     "semantic": "startup metadata 40-byte table", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED", "semantic_evidence": "0x3C7F120-0x3C7F503"},
    {"field": 0x158, "op": "add", "const": 0xE03EEAC1, "base": "startup",
     "entry_size": None, "consumer_rvas": ["0x3C7F510"], "entry_accesses": ["base only"],
     "semantic": "startup metadata table", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "0x3C7F50B"},
    {"field": 0x164, "op": "xor", "const": 0x7F5C5934, "base": "startup",
     "entry_size": 8, "consumer_rvas": ["0x3C7E938"],
     "entry_accesses": ["[base+idx*8+0]", "[base+idx*8+4] (-1 sentinel)"],
     "semantic": "startup metadata 8-byte table", "structure": "CONFIRMED",
     "semantic_status": "SUPPORTED", "semantic_evidence": "0x3C7E931-0x3C7EA24"},
    {"field": 0x170, "op": "xor", "const": 0x61645FE8, "base": "startup",
     "entry_size": None, "consumer_rvas": ["0x3C7FACB"], "entry_accesses": ["base only"],
     "semantic": "startup metadata table", "structure": "SUPPORTED", "semantic_status": "UNKNOWN",
     "semantic_evidence": "0x3C7FAC4"},
]

# count/size fields decoded by loader (not table offsets)
COUNT_FIELDS = [
    {"field": 0xBC, "transform": "sar 3; xor 0x079FC2EC", "consumer_rva": "0x3C7E8D8",
     "note": "startup 0x164 table entry count (0x642D5 = 410325)"},
    {"field": 0x74, "transform": "xor 0x080EF250; mul 0xAAAAAAAB; hi>>?; and ~7", "consumer_rva": "0x3C7E59E",
     "note": "allocation size field"},
    {"field": 0x134, "transform": "xor 0x10210728; mul 0xCCCCCCCD; hi>>5", "consumer_rva": "0x3C7E64D",
     "note": "count 142 used by startup 40-byte table loop"},
    {"field": 0x178, "transform": "sar 4; xor 0x05CC1AE1", "consumer_rva": "0x3C7E78F",
     "note": "count 142; 0x58-byte runtime records"},
    {"field": 0x1A8, "transform": "xor 0x729B1A9E; mul 0xEA0EA0EA0EA0EA0F; hi>>3; and ~7",
     "consumer_rva": "0x3C7E43D", "note": "allocation size field"},
    {"field": 0x1F8, "transform": "xor 0x1608C2C8; mul 0x4EC4EC4EC4EC4EC5; hi; and ~7",
     "consumer_rva": "0x3C7E4EE", "note": "allocation size field"},
]


def signed32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def decode_rule(raw: int, op: str, const: int) -> int:
    if op == "add":
        return (raw + const) & 0xFFFFFFFF
    if op == "xor":
        return raw ^ const
    raise ValueError(op)


def build_registry(pe: PeImage, metadata_path: Path | None, template_rva: int) -> dict:
    block = pe.read_rva(template_rva, 0x208)
    rows = []
    for rule in RULES:
        field = rule["field"]
        raw = struct.unpack_from("<I", block, field)[0]
        dec = decode_rule(raw, rule["op"], rule["const"])
        signed = signed32(dec)
        row = {
            "template_field": f"0x{field:X}",
            "template_raw_u32": f"0x{raw:08X}",
            "transform_type": rule["op"],
            "transform_constant": f"0x{rule['const']:08X}",
            "decoded_u32": f"0x{dec:08X}",
            "signed32": signed,
            "base_kind": rule["base"],
            "file_offset": None,
            "in_metadata": None,
            "consumer_rvas": rule["consumer_rvas"],
            "entry_size": rule["entry_size"],
            "entry_field_accesses": rule["entry_accesses"],
            "candidate_semantic": rule["semantic"],
            "semantic_evidence": rule["semantic_evidence"],
            "structure_status": rule["structure"],
            "semantic_status": rule["semantic_status"],
        }
        if rule["base"] == "payload":
            fo = FILE_HEADER + signed
            row["file_offset"] = f"0x{fo:X}" if fo >= 0 else f"-0x{-fo:X}"
            if metadata_path is not None:
                row["in_metadata"] = 0 <= fo < metadata_path.stat().st_size
        elif rule["base"] == "count":
            row["file_offset"] = None
        rows.append(row)

    counts = []
    for cf in COUNT_FIELDS:
        field = cf["field"]
        raw = struct.unpack_from("<I", block, field)[0]
        counts.append({
            "template_field": f"0x{field:X}",
            "template_raw_u32": f"0x{raw:08X}",
            "transform": cf["transform"],
            "consumer_rva": cf["consumer_rva"],
            "note": cf["note"],
        })

    return {
        "schema": "mhy_table_registry/1",
        "game": str(pe.path),
        "template_rva": template_rva,
        "template_size": 0x208,
        "file_header_size": FILE_HEADER,
        "structure_vs_semantic_discipline": {
            "structure_status_values": ["CONFIRMED", "SUPPORTED", "HYPOTHESIS"],
            "semantic_status_values": ["CONFIRMED", "SUPPORTED", "CANDIDATE", "UNKNOWN"],
            "rule": "structure confidence and semantic confidence are recorded separately",
        },
        "tables": rows,
        "count_fields": counts,
        "cross_table_links": [
            {"from_field": "0x160", "to_field": "0x38",
             "link": "usage tag 0xC0000000 branch reads 0x38 triples"},
            {"from_field": "0x84", "to_field": "0x70",
             "link": "0x70 u32 value indexes 0x84 70-byte records"},
            {"from_field": "0x84", "to_field": "0x14C",
             "link": "0x84 +0x08/+0x34 method ranges cover the 0x14C MethodDefinition table exactly once"},
            {"from_field": "0x14C", "to_field": "0x30",
             "link": "0x14C +0x04/+0x18 parameter ranges cover the 0x30 ParameterDefinition table exactly once"},
            {"from_field": "0x84", "to_field": "0x20",
             "link": "0x84 +0x20/+0x32 field ranges cover the 0x20 FieldDefinition table exactly once"},
            {"from_field": "0x84", "to_field": "0x12C",
             "link": "0x84 +0x3A word indexes 0x12C type indices"},
            {"from_field": "0x34", "to_field": "0x1C4",
             "link": "0x34 u16 value indexes 0x1C4 12-byte records"},
            {"from_field": "0x1C4", "to_field": "0x2C",
             "link": "0x1C4 +0xA value indexes 0x2C 8-byte records"},
            {"from_field": "0x1FC", "to_field": "0x3C",
             "link": "0x1FC +0x4 byte offset points into 0x3C type data"},
            {"from_field": "0x18", "to_field": "0x1EC",
             "link": "0x18 packed range start/count scans 0x1EC u32 table"},
            {"from_field": "0x180", "to_field": "0x9C",
             "link": "0x180 u32 index addresses 0x9C 12-byte records"},
        ],
        "final_status": "MHY_METADATA = MEMBER_REGISTRY_PROOF",
        "not_claimed": [
            "MethodDefinition -> GameAssembly RVA mapping",
            "return type / field type semantic names",
            "parameter names (observed sentinel-only)",
            "Image / Assembly semantic decoding",
            "payload transform algorithm",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--template-rva", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--metadata", default=None, help="global-metadata.dat for in-file validation")
    args = ap.parse_args()
    pe = PeImage(Path(args.game))
    template_rva = args.template_rva if args.template_rva is not None else locate_template_rva(pe)
    metadata_path = Path(args.metadata) if args.metadata and os.path.isfile(args.metadata) else None
    result = build_registry(pe, metadata_path, template_rva)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    n_struct = sum(1 for r in result["tables"] if r["structure_status"] in ("CONFIRMED", "SUPPORTED"))
    n_sem = sum(1 for r in result["tables"] if r["semantic_status"] in ("CONFIRMED", "SUPPORTED"))
    print(f"wrote {out}")
    print(f"template_rva=0x{template_rva:X}; tables={len(result['tables'])} "
          f"structure_confirmed={n_struct} semantic_supported={n_sem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
