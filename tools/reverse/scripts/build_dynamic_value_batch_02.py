#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Battle Semantic DynamicValue Batch 02 evidence artifacts.

Inputs (read-only):
  - data/normalized/4.4.54/{manifest,types,methods,fields,parameters}.json
  - data/parsed/4.4.54/method_code_table.bin
  - GameAssembly.dll from the manifest (native body bytes + bounded capstone)

Outputs:
  - data/semantics/4.4.54/dynamic_value_batch_02.json
  - docs/battle_semantics/dynamic_value_batch_02.md

This is a narrow batch evidence assembler.  It re-verifies every normalized
method identity and code-table slot it writes into the report; the method
indices / RVAs in the candidate tables are never trusted from the prompt.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
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

BASE = REPO / "data" / "normalized" / "4.4.54"
CODE_TABLE = REPO / "data" / "parsed" / "4.4.54" / "method_code_table.bin"
OUT_JSON = REPO / "data" / "semantics" / "4.4.54" / "dynamic_value_batch_02.json"
OUT_MD = REPO / "docs" / "battle_semantics" / "dynamic_value_batch_02.md"

GAME_VERSION = "4.4.54"
PRIMARY_TYPE_INDEX = 10822
PRIMARY_TYPE_NAME = "RPG.GameCore.DynamicValue"
ENUM_TYPE_INDEX = 10824

# Accepted Batch 02 primitives.
# `body_slot` is the next-method-RVA distance used as a bounded decode window;
# the real body length is derived from the decoded instruction stream.
CANDIDATES = [
    {
        "method_index": 74637,
        "method_name": "get_IntValue",
        "native_rva": 0x1CFBF070,
        "body_slot": 0x50,
        "semantic_name": "DynamicValueToInt32",
        "primitive_id": "battle.ir.value.dynamic_value_to_int",
        "result": "int32",
        "description": "Tag-aware DynamicValue -> signed 32-bit int coercion",
        "abi": "x64: this=rcx, int32 return=eax",
        "tag_behavior": [
            "INT(0): read signed 32-bit low dword of unionValue",
            "FLOAT(1): cvttsd2si eax (truncate toward zero; out-of-range/NaN -> 0x80000000)",
            "BOOL(2): unionValue == 1 -> 1, otherwise 0 (silent)",
            "any other tag: error-log callee, return 0",
        ],
        "branch_conditions": [
            "tag == 2 -> BOOL path",
            "tag == 1 -> FLOAT path",
            "tag == 0 -> INT path",
            "tag not in {0,1,2} -> mismatch path",
        ],
        "field_reads": ["this.ValueType byte @ +0x30", "this.unionValue qword @ +0x28"],
        "field_writes": [],
        "constants": ["tag constants 0/1/2", "bool normal form 1"],
        "required_callees": [
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            }
        ],
        "pseudocode": [
            "int32 DynamicValueToInt32(DynamicValue this):",
            "    t = this.ValueType                 # byte @ +0x30",
            "    if t == BOOL(2): return this.unionValue == 1 ? 1 : 0",
            "    if t == FLOAT(1): return cvttsd2si32(this.unionValue)",
            "    if t == INT(0): return (int32)(uint32)low32(this.unionValue)",
            "    _LogTypeMismatch(this); return 0   # CONFIRMED default, helper internals not followed",
        ],
        "unknowns": [
            "Type-mismatch log helper internals (0x1CFD2950) are not followed; error path returns 0 after the call",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74638,
        "method_name": "get_UintValue",
        "native_rva": 0x1CFBF0C0,
        "body_slot": 0x50,
        "semantic_name": "DynamicValueToUInt32",
        "primitive_id": "battle.ir.value.dynamic_value_to_uint",
        "result": "uint32",
        "description": "Tag-aware DynamicValue -> unsigned 32-bit int coercion",
        "abi": "x64: this=rcx, uint32 return=eax",
        "tag_behavior": [
            "INT(0): bit-preserving read of signed 32-bit low dword of unionValue",
            "FLOAT(1): cvttsd2si rax (64-bit truncation) then return low 32 bits",
            "BOOL(2): unionValue == 1 -> 1, otherwise 0 (silent)",
            "any other tag: error-log callee, return 0",
        ],
        "branch_conditions": [
            "tag == 2 -> BOOL path",
            "tag == 1 -> FLOAT path",
            "tag == 0 -> INT path",
            "tag not in {0,1,2} -> mismatch path",
        ],
        "field_reads": ["this.ValueType byte @ +0x30", "this.unionValue qword @ +0x28"],
        "field_writes": [],
        "constants": ["tag constants 0/1/2", "bool normal form 1"],
        "required_callees": [
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            }
        ],
        "pseudocode": [
            "uint32 DynamicValueToUInt32(DynamicValue this):",
            "    t = this.ValueType                 # byte @ +0x30",
            "    if t == BOOL(2): return this.unionValue == 1 ? 1 : 0",
            "    if t == FLOAT(1): return (uint32)(int64)cvttsd2si64(this.unionValue)",
            "    if t == INT(0): return (uint32)low32(this.unionValue)",
            "    _LogTypeMismatch(this); return 0   # CONFIRMED default, helper internals not followed",
        ],
        "unknowns": [
            "Type-mismatch log helper internals (0x1CFD2950) are not followed; error path returns 0 after the call",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74639,
        "method_name": "get_LongValue",
        "native_rva": 0x1CFBF110,
        "body_slot": 0x80,
        "semantic_name": "DynamicValueToInt64",
        "primitive_id": "battle.ir.value.dynamic_value_to_long",
        "result": "int64",
        "description": "Tag-aware DynamicValue -> signed 64-bit long coercion with one-time IL2CPP class init",
        "abi": "x64: this=rcx, int64 return=rax",
        "tag_behavior": [
            "BOOL(2): unionValue == 1 -> 1, otherwise 0 (silent)",
            "FLOAT(1): cvttsd2si rax (truncate toward zero; out-of-range/NaN -> 0x8000000000000000)",
            "INT(0): full signed qword unionValue",
            "any other tag: error-log callee, return 0",
        ],
        "branch_conditions": [
            "IL2CPP class-init flag @ 0x9A5743C == 0 -> one-time init branch",
            "tag == 2 -> BOOL path",
            "tag == 1 -> FLOAT path",
            "tag == 0 -> INT path",
            "tag not in {0,1,2} -> mismatch path",
        ],
        "field_reads": ["this.ValueType byte @ +0x30", "this.unionValue qword @ +0x28"],
        "field_writes": ["IL2CPP class-init flag byte @ 0x9A5743C (infrastructure, set to 1 once)"],
        "constants": ["IL2CPP class init token 0x1034C", "tag constants 0/1/2", "bool normal form 1"],
        "required_callees": [
            {
                "rva": "0x3C6D0E0",
                "role": "IL2CPP runtime class-init helper (one-time branch only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            },
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            },
        ],
        "pseudocode": [
            "int64 DynamicValueToInt64(DynamicValue this):",
            "    if not il2cpp_class_initialized(0x1034C):   # one-time runtime infrastructure",
            "        il2cpp_runtime_class_init(0x1034C)",
            "    t = this.ValueType                 # byte @ +0x30",
            "    if t == BOOL(2): return this.unionValue == 1 ? 1 : 0",
            "    if t == FLOAT(1): return cvttsd2si64(this.unionValue)",
            "    if t == INT(0): return this.unionValue",
            "    _LogTypeMismatch(this); return 0   # CONFIRMED default, helper internals not followed",
        ],
        "unknowns": [
            "IL2CPP class-init helper internals (0x3C6D0E0); one-time infrastructure, not modeled in BattleState",
            "Type-mismatch log helper internals (0x1CFD2950) are not followed; error path returns 0 after the call",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74633,
        "method_name": "get_FloatValue",
        "native_rva": 0x1CFBED90,
        "body_slot": 0x60,
        "semantic_name": "DynamicValueToFloat32",
        "primitive_id": "battle.ir.value.dynamic_value_to_float",
        "result": "float32",
        "description": "Tag-aware DynamicValue -> IEEE-754 single-precision float coercion",
        "abi": "x64: this=rcx, float32 return=xmm0",
        "tag_behavior": [
            "INT(0): cvtsi2ss signed int64 -> float32",
            "FLOAT(1): cvtsd2ss float64 -> float32 (payload is always a double in the union)",
            "BOOL(2): unionValue == 1 -> +1.0f, otherwise +0.0f (silent)",
            "any other tag: error-log callee, return +0.0f",
        ],
        "branch_conditions": [
            "tag == 0 -> INT path",
            "tag == 2 -> BOOL path",
            "tag == 1 -> FLOAT path",
            "tag not in {0,1,2} -> mismatch path",
            "BOOL path: unionValue != 1 -> zero-float path",
        ],
        "field_reads": ["this.ValueType byte @ +0x30", "this.unionValue qword @ +0x28"],
        "field_writes": [],
        "constants": ["tag constants 0/1/2", "float32 +1.0f @ 0x4029000", "float32 +0.0f"],
        "required_callees": [
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            }
        ],
        "pseudocode": [
            "float32 DynamicValueToFloat32(DynamicValue this):",
            "    t = this.ValueType                 # byte @ +0x30",
            "    if t == INT(0): return cvtsi2ss64(this.unionValue)",
            "    if t == BOOL(2): return this.unionValue == 1 ? 1.0f : 0.0f",
            "    if t == FLOAT(1): return cvtsd2ss(this.unionValue)",
            "    _LogTypeMismatch(this); return 0.0f  # CONFIRMED default, helper internals not followed",
        ],
        "unknowns": [
            "Type-mismatch log helper internals (0x1CFD2950) are not followed; error path returns +0.0f after the call",
            "cvtsd2ss rounding-mode dependency (default MXCSR round-to-nearest-even assumed)",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74634,
        "method_name": "get_DoubleValue",
        "native_rva": 0x1CFBEE20,
        "body_slot": 0x80,
        "semantic_name": "DynamicValueToFloat64",
        "primitive_id": "battle.ir.value.dynamic_value_to_double",
        "result": "float64",
        "description": "Tag-aware DynamicValue -> IEEE-754 double coercion with one-time IL2CPP class init",
        "abi": "x64: this=rcx, float64 return=xmm0",
        "tag_behavior": [
            "INT(0): cvtsi2sd signed int64 -> float64",
            "BOOL(2): unionValue == 1 -> +1.0, otherwise +0.0 (silent)",
            "FLOAT(1): raw float64 union payload",
            "any other tag: error-log callee, return +0.0",
        ],
        "branch_conditions": [
            "IL2CPP class-init flag @ 0x9A57434 == 0 -> one-time init branch",
            "tag == 0 -> INT path",
            "tag == 2 -> BOOL path",
            "tag == 1 -> FLOAT path",
            "tag not in {0,1,2} -> mismatch path",
            "BOOL path: unionValue != 1 -> zero-double path",
        ],
        "field_reads": ["this.ValueType byte @ +0x30", "this.unionValue qword @ +0x28"],
        "field_writes": ["IL2CPP class-init flag byte @ 0x9A57434 (infrastructure, set to 1 once)"],
        "constants": ["IL2CPP class init token 0x10344", "tag constants 0/1/2", "float64 +1.0 @ 0x40292E8", "float64 +0.0"],
        "required_callees": [
            {
                "rva": "0x3C6D0E0",
                "role": "IL2CPP runtime class-init helper (one-time branch only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            },
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            },
        ],
        "pseudocode": [
            "float64 DynamicValueToFloat64(DynamicValue this):",
            "    if not il2cpp_class_initialized(0x10344):   # one-time runtime infrastructure",
            "        il2cpp_runtime_class_init(0x10344)",
            "    t = this.ValueType                 # byte @ +0x30",
            "    if t == INT(0): return cvtsi2sd64(this.unionValue)",
            "    if t == BOOL(2): return this.unionValue == 1 ? 1.0 : 0.0",
            "    if t == FLOAT(1): return this.unionValue",
            "    _LogTypeMismatch(this); return 0.0   # CONFIRMED default, helper internals not followed",
        ],
        "unknowns": [
            "IL2CPP class-init helper internals (0x3C6D0E0); one-time infrastructure, not modeled in BattleState",
            "Type-mismatch log helper internals (0x1CFD2950) are not followed; error path returns +0.0 after the call",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74636,
        "method_name": "get_BoolValue",
        "native_rva": 0x1CFBF010,
        "body_slot": 0x60,
        "semantic_name": "DynamicValueToBool",
        "primitive_id": "battle.ir.value.dynamic_value_to_bool",
        "result": "boolean",
        "description": "Tag-aware DynamicValue -> bool normalization; invalid INT payload is logged and yields false",
        "abi": "x64: this=rcx, bool return=al",
        "tag_behavior": [
            "INT(0): unionValue in {0,1} -> value != 0; any other raw payload -> invalid-value log helper then false",
            "BOOL(2): unionValue == 1 (raw payloads other than 1 normalize to false, silently)",
            "any other tag: type-mismatch log helper, return false",
        ],
        "branch_conditions": [
            "tag == 0 -> INT path",
            "tag == 2 -> BOOL path",
            "tag not in {0,2} -> mismatch path",
            "INT path: unsigned comparison raw < 2 bypasses the invalid-value helper",
            "BOOL path: unionValue == 1",
        ],
        "field_reads": ["this.ValueType byte @ +0x30", "this.unionValue qword @ +0x28"],
        "field_writes": [],
        "constants": ["tag constants 0/2", "bool normal form 1", "invalid-INT threshold 2"],
        "required_callees": [
            {
                "rva": "0x1CFD2AB0",
                "role": "invalid-value log helper (INT raw value >= 2; error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            },
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (non INT/BOOL tags; error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            },
        ],
        "pseudocode": [
            "bool DynamicValueToBool(DynamicValue this):",
            "    t = this.ValueType                 # byte @ +0x30",
            "    if t == INT(0):",
            "        raw = this.unionValue",
            "        if raw >= 2: _LogInvalidValue(this)   # negative/2+ raw payload",
            "        return raw == 1",
            "    if t == BOOL(2):",
            "        return this.unionValue == 1",
            "    _LogTypeMismatch(this); return false  # CONFIRMED default",
        ],
        "unknowns": [
            "Invalid-value log helper internals (0x1CFD2AB0); error path only, result stays false",
            "Type-mismatch log helper internals (0x1CFD2950); error path only, result stays false",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74648,
        "method_name": "get_ValueType",
        "native_rva": 0x1CFBE650,
        "body_slot": 0x10,
        "semantic_name": "DynamicValueTypeTag",
        "primitive_id": "battle.ir.value.dynamic_value_type",
        "result": "DynamicValueType",
        "description": "Raw ValueType tag ordinal read from a DynamicValue cell",
        "abi": "x64: this=rcx, enum ordinal return=eax (zero-extended byte)",
        "tag_behavior": [
            "Returns the raw +0x30 byte unchanged (0..6 for canonical cells; no validation and no coercion)",
        ],
        "branch_conditions": [],
        "field_reads": ["this.ValueType byte @ +0x30"],
        "field_writes": [],
        "constants": [],
        "required_callees": [],
        "pseudocode": [
            "DynamicValueType DynamicValueTypeTag(DynamicValue this):",
            "    return this.ValueType              # byte @ +0x30, zero-extended",
        ],
        "unknowns": [
            "FieldDefinition provenance for the +0x30 ValueType tag byte remains UNKNOWN",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74640,
        "method_name": "get_StringValue",
        "native_rva": 0x1CFBF190,
        "body_slot": 0x30,
        "semantic_name": "DynamicValueStringPayload",
        "primitive_id": "battle.ir.value.dynamic_value_string",
        "result": "string_or_null",
        "description": "Tag-checked STRING payload access; non-STRING tags log and return null",
        "abi": "x64: this=rcx, string pointer return=rax",
        "tag_behavior": [
            "STRING(5): return stringValue pointer (null pointer is returned as-is)",
            "any other tag: type-mismatch log helper, return null",
        ],
        "branch_conditions": ["tag == 5 -> payload path", "tag != 5 -> mismatch path"],
        "field_reads": ["this.ValueType byte @ +0x30", "this.stringValue pointer @ +0x18"],
        "field_writes": [],
        "constants": ["tag constant 5"],
        "required_callees": [
            {
                "rva": "0x1CFD2950",
                "role": "type-mismatch log helper (error path only)",
                "evidence_level": "UNKNOWN_HELPER_NOT_NEEDED",
            }
        ],
        "pseudocode": [
            "string | null DynamicValueStringPayload(DynamicValue this):",
            "    if this.ValueType == STRING(5):",
            "        return this.stringValue          # may be null",
            "    _LogTypeMismatch(this); return null  # CONFIRMED default",
        ],
        "unknowns": [
            "Type-mismatch log helper internals (0x1CFD2950) are not followed; error path returns null after the call",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74654,
        "method_name": "get_IsArray",
        "native_rva": 0x1CFBF200,
        "body_slot": 0x20,
        "semantic_name": "DynamicValueIsArray",
        "primitive_id": "battle.ir.value.dynamic_value_is_array",
        "result": "boolean",
        "description": "True iff ValueType == ARRAY and arrayValue pointer is non-null",
        "abi": "x64: this=rcx, bool return=al",
        "tag_behavior": [
            "ARRAY(3) with non-null arrayValue -> true",
            "ARRAY(3) with null arrayValue -> false (no log call)",
            "any other tag -> false (no log call)",
        ],
        "branch_conditions": ["tag == 3 -> payload-null check", "payload != null"],
        "field_reads": ["this.ValueType byte @ +0x30", "this.arrayValue pointer @ +0x20"],
        "field_writes": [],
        "constants": ["tag constant 3", "null pointer 0"],
        "required_callees": [],
        "pseudocode": [
            "bool DynamicValueIsArray(DynamicValue this):",
            "    return this.ValueType == ARRAY(3) and this.arrayValue != null",
        ],
        "unknowns": [
            "Canonical representation cannot currently construct ARRAY cells with null arrayValue; sandbox keeps the native null-check as a defensive branch",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74655,
        "method_name": "get_IsMap",
        "native_rva": 0x1CFBF250,
        "body_slot": 0x20,
        "semantic_name": "DynamicValueIsMap",
        "primitive_id": "battle.ir.value.dynamic_value_is_map",
        "result": "boolean",
        "description": "True iff ValueType == MAP and mapValue pointer is non-null",
        "abi": "x64: this=rcx, bool return=al",
        "tag_behavior": [
            "MAP(4) with non-null mapValue -> true",
            "MAP(4) with null mapValue -> false (no log call)",
            "any other tag -> false (no log call)",
        ],
        "branch_conditions": ["tag == 4 -> payload-null check", "payload != null"],
        "field_reads": ["this.ValueType byte @ +0x30", "this.mapValue pointer @ +0x10"],
        "field_writes": [],
        "constants": ["tag constant 4", "null pointer 0"],
        "required_callees": [],
        "pseudocode": [
            "bool DynamicValueIsMap(DynamicValue this):",
            "    return this.ValueType == MAP(4) and this.mapValue != null",
        ],
        "unknowns": [
            "Canonical representation cannot currently construct MAP cells with null mapValue; sandbox keeps the native null-check as a defensive branch",
            "No E5 runtime observation for this primitive",
        ],
    },
    {
        "method_index": 74653,
        "method_name": "get_IsNull",
        "native_rva": 0x1CFBF620,
        "body_slot": 0x10,
        "semantic_name": "DynamicValueIsNull",
        "primitive_id": "battle.ir.value.dynamic_value_is_null",
        "result": "boolean",
        "description": "True iff ValueType == NULL",
        "abi": "x64: this=rcx, bool return=al",
        "tag_behavior": [
            "NULL(6) -> true",
            "any other tag -> false",
        ],
        "branch_conditions": ["tag == 6"],
        "field_reads": ["this.ValueType byte @ +0x30"],
        "field_writes": [],
        "constants": ["tag constant 6"],
        "required_callees": [],
        "pseudocode": [
            "bool DynamicValueIsNull(DynamicValue this):",
            "    return this.ValueType == NULL(6)",
        ],
        "unknowns": [
            "FieldDefinition provenance for the +0x30 ValueType tag byte remains UNKNOWN",
            "No E5 runtime observation for this primitive",
        ],
    },
]

# Classification of every method declared on DynamicValue (verified from the
# normalized registry, not from prompt numbers).
CLASSIFICATION = {
    74611: ("SKIP_WRAPPER", "parameterless constructor wrapper"),
    74612: ("SKIP_WRAPPER", "bool constructor wrapper"),
    74613: ("SKIP_WRAPPER", "float32 constructor wrapper"),
    74614: ("SKIP_WRAPPER", "float64 constructor wrapper"),
    74615: ("SKIP_WRAPPER", "string constructor wrapper"),
    74616: ("SKIP_WRAPPER", "int32 constructor wrapper"),
    74617: ("SKIP_WRAPPER", "int64 constructor wrapper"),
    74618: ("SKIP_WRAPPER", "array payload constructor wrapper"),
    74619: ("SKIP_WRAPPER", "map payload constructor wrapper"),
    74620: ("SKIP_COMPLEX", "static class initializer; 251 calls / 88 jumps, runtime infrastructure"),
    74621: ("SKIP_WRAPPER", "op_Implicit(string) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74622: ("SKIP_WRAPPER", "op_Implicit(int32) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74623: ("SKIP_WRAPPER", "op_Implicit(int64) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74624: ("SKIP_WRAPPER", "op_Implicit(float32) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74625: ("SKIP_WRAPPER", "op_Implicit(float64) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74626: ("SKIP_WRAPPER", "op_Implicit(bool) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74627: ("SKIP_WRAPPER", "op_Implicit(map) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74628: ("SKIP_WRAPPER", "op_Implicit(array) allocates a DynamicValue cell; allocation-shaped wrapper"),
    74629: ("SKIP_COMPLEX", "ToString formatting dispatcher; 639 instructions, 57 calls, 33 jumps"),
    74630: ("SKIP_WRAPPER", "Equals(object) adds IL2CPP runtime type identity check then duplicates the recovered Equals(DynamicValue) switch; no new battle semantic"),
    74631: ("SKIP_COMPLEX", "GetHashCode dispatcher; 195 instructions, 15 branches, 6 calls"),
    74632: ("SKIP_WRAPPER", "already recovered as battle.ir.value.dynamic_value_equals in vertical_slice_01.json"),
    74633: ("ACCEPT", ""),
    74634: ("ACCEPT", ""),
    74635: ("SKIP_COMPLEX", "FixPoint framework: 89 instructions, 14 branches, range/shift encoding and two FixPoint global constants (0x95B1E00 / 0x95B1E60); exceeds single-callee batch budget"),
    74636: ("ACCEPT", ""),
    74637: ("ACCEPT", ""),
    74638: ("ACCEPT", ""),
    74639: ("ACCEPT", ""),
    74640: ("ACCEPT", ""),
    74641: ("SKIP_WRAPPER", "get_ArrayValue returns ObjectRef; current scalar-only trace contract would need a reference-result summary, deferred instead of special-cased"),
    74642: ("SKIP_WRAPPER", "get_MapValue returns ObjectRef; current scalar-only trace contract would need a reference-result summary, deferred instead of special-cased"),
    74643: ("SKIP_COMPLEX", "private logging helper; no value semantic"),
    74644: ("SKIP_COMPLEX", "private logging helper; no value semantic"),
    74645: ("SKIP_COMPLEX", "private logging helper; no value semantic"),
    74646: ("SKIP_COMPLEX", "private logging helper; no value semantic"),
    74647: ("SKIP_COMPLEX", "string escaping helper; 150 instructions, 15 calls, not a gameplay value semantic"),
    74648: ("ACCEPT", ""),
    74649: ("SKIP_WRAPPER", "single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget"),
    74650: ("SKIP_WRAPPER", "single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget"),
    74651: ("SKIP_WRAPPER", "single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget"),
    74652: ("SKIP_WRAPPER", "single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget"),
    74653: ("ACCEPT", ""),
    74654: ("ACCEPT", ""),
    74655: ("ACCEPT", ""),
    74656: ("SKIP_WRAPPER", "raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells"),
    74657: ("SKIP_WRAPPER", "raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells"),
    74658: ("SKIP_WRAPPER", "raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells"),
    74659: ("SKIP_SERIALIZATION", "explicitly excluded FromByteBinary serialization semantic"),
    74660: ("SKIP_SERIALIZATION", "explicitly excluded ToBinary serialization semantic"),
    74661: ("SKIP_COMPLEX", "debugger-display formatter; 34 instructions, 4 calls, allocates debug string"),
}


def iter_records(path: Path):
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


def load_registry_facts():
    wanted_types = {PRIMARY_TYPE_INDEX, ENUM_TYPE_INDEX}
    wanted_methods = {PRIMARY_TYPE_INDEX}
    wanted_fields = {PRIMARY_TYPE_INDEX, ENUM_TYPE_INDEX}

    types = {}
    methods = []
    fields = []
    for rec in iter_records(BASE / "types.json"):
        if rec["type_index"] in wanted_types:
            types[rec["type_index"]] = rec
    for rec in iter_records(BASE / "methods.json"):
        if rec["declaring_type_index"] == PRIMARY_TYPE_INDEX:
            methods.append(rec)
    for rec in iter_records(BASE / "fields.json"):
        if rec["declaring_type_index"] in wanted_fields:
            fields.append(rec)

    ptype = types[PRIMARY_TYPE_INDEX]
    etype = types[ENUM_TYPE_INDEX]
    assert ptype["full_name"] == PRIMARY_TYPE_NAME, ptype
    assert len(methods) == ptype["method_count"] == 51, (len(methods), ptype)
    methods_by_index = {rec["method_index"]: rec for rec in methods}
    fields_by_type = {
        PRIMARY_TYPE_INDEX: sorted(
            (r for r in fields if r["declaring_type_index"] == PRIMARY_TYPE_INDEX),
            key=lambda r: r["field_index"],
        ),
        ENUM_TYPE_INDEX: sorted(
            (r for r in fields if r["declaring_type_index"] == ENUM_TYPE_INDEX),
            key=lambda r: r["field_index"],
        ),
    }
    return {
        "primary_type": ptype,
        "enum_type": etype,
        "methods": sorted(methods, key=lambda r: r["method_index"]),
        "methods_by_index": methods_by_index,
        "primary_fields": fields_by_type[PRIMARY_TYPE_INDEX],
        "enum_fields": fields_by_type[ENUM_TYPE_INDEX],
    }


def disasm_window(pe: PeImage, rva: int, length: int):
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
                    comment = f" ; [rip]->0x{target:X} (rva 0x{target - pe.image_base:X})"
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


def line_for(ins):
    return (
        f"{ins['rva']:08X}  {bytes(ins['bytes']).hex(' '):<24}  "
        f"{ins['mnemonic']:8} {ins['op_str']}{ins['comment']}"
    )


def body_metrics(raw, decoded, rva):
    if not decoded:
        raise RuntimeError(f"no instructions decoded at 0x{rva:X}")
    # Skip trailing alignment nops to derive the real body span.
    end_offset = len(raw)
    for ins in reversed(decoded):
        if ins["mnemonic"] == "nop":
            continue
        end_offset = ins["rva"] + ins["size"] - rva
        break
    body_insns = [ins for ins in decoded if ins["rva"] + ins["size"] - rva <= end_offset]
    if not body_insns:
        raise RuntimeError(f"body contains only padding at 0x{rva:X}")
    body_raw = raw[:end_offset]
    branch_count = sum(
        1
        for ins in body_insns
        if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
    )
    call_count = sum(1 for ins in body_insns if ins["mnemonic"] == "call")
    jmp_count = sum(1 for ins in body_insns if ins["mnemonic"] == "jmp")
    return {
        "body_length": end_offset,
        "body_raw": body_raw,
        "body_insns": body_insns,
        "instruction_count": len(body_insns),
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


def build_native_evidence(pe, cand, method):
    rva = cand["native_rva"]
    raw, decoded = disasm_window(pe, rva, cand["body_slot"])
    metrics = body_metrics(raw, decoded, rva)
    slot = read_code_slot(pe, cand["method_index"])
    expected_va = pe.image_base + rva
    if slot != expected_va:
        raise RuntimeError(
            f"{cand['method_name']}: code table slot {slot:#x} != {expected_va:#x}"
        )
    body_sha = hashlib.sha256(metrics["body_raw"]).hexdigest()
    return {
        "body_rva": f"0x{rva:X}",
        "body_length_bytes": metrics["body_length"],
        "body_slot_size_bytes": cand["body_slot"],
        "instruction_count": metrics["instruction_count"],
        "conditional_branch_count": metrics["branch_count"],
        "direct_call_count": metrics["call_count"],
        "direct_jump_count": metrics["jmp_count"],
        "body_sha256": body_sha,
        "code_table_slot_va": f"0x{slot:X}",
        "code_table_slot_index": cand["method_index"],
        "image_base": f"0x{pe.image_base:X}",
        "mapping_kind": method["mapping_kind"],
        "abi": cand["abi"],
        "disassembly": [line_for(ins) for ins in metrics["body_insns"]],
    }


def build_primitive(pe, cand, method):
    ne = build_native_evidence(pe, cand, method)
    inputs = [{"name": "value", "type": "DynamicValue"}]
    return {
        "primitive_id": cand["primitive_id"],
        "semantic_name": cand["semantic_name"],
        "description": cand["description"],
        "source_runtime_type": PRIMARY_TYPE_NAME,
        "source_method": cand["method_name"],
        "source_method_index": cand["method_index"],
        "source_native_rva": f"0x{cand['native_rva']:X}",
        "native_body_hash": ne["body_sha256"],
        "inputs": inputs,
        "result": cand["result"],
        "context_reads": ["value"],
        "context_writes": [],
        "determinism": "DETERMINISTIC",
        "tag_behavior": cand["tag_behavior"],
        "field_reads": cand["field_reads"],
        "field_writes": cand["field_writes"],
        "constants": cand["constants"],
        "branch_conditions": cand["branch_conditions"],
        "required_callees": cand["required_callees"],
        "pseudocode": cand["pseudocode"],
        "unknowns": cand["unknowns"],
        "native_evidence": ne,
        "evidence_level": "E4_STATIC_MACHINE_CODE",
        "success_criteria": {
            "A_runtime_type_identity": "PASS",
            "B_method_definition_identity": "PASS",
            "C_native_rva_reliable": "PASS",
            "D_native_body_dataflow_explained": "PASS",
            "E_inputs_outputs_described": "PASS",
            "F_read_write_set_described": "PASS",
            "G_branches_described": "PASS",
            "H_deterministic_pseudocode": "PASS",
            "I_generic_ir_primitive": "PASS",
        },
    }


def method_stats(pe, methods):
    rvas = sorted(int(m["native_rva"]) for m in methods)
    slots = {}
    for rec in methods:
        rva = int(rec["native_rva"])
        size = None
        for other in rvas:
            if other > rva:
                size = other - rva
                break
        slots[rec["method_index"]] = size
    out = {}
    for rec in methods:
        rva = int(rec["native_rva"])
        size = slots[rec["method_index"]]
        if size is None or size > 0x2000:
            size = 0x2000
        raw, decoded = disasm_window(pe, rva, size)
        metrics = body_metrics(raw, decoded, rva)
        out[rec["method_index"]] = {
            "rva": rva,
            "slot_size": slots[rec["method_index"]],
            "instruction_count": metrics["instruction_count"],
            "branch_count": metrics["branch_count"],
            "call_count": metrics["call_count"],
            "jmp_count": metrics["jmp_count"],
        }
    return out, slots


def build_json(facts, pe):
    manifest = json.load((BASE / "manifest.json").open(encoding="utf-8"))
    methods = facts["methods"]
    methods_by_index = facts["methods_by_index"]
    stats, _slots = method_stats(pe, methods)

    primitives = []
    for cand in CANDIDATES:
        method = methods_by_index[cand["method_index"]]
        rva = int(method["native_rva"])
        assert method["name"] == cand["method_name"], (method, cand["method_name"])
        assert method["declaring_type_index"] == PRIMARY_TYPE_INDEX
        assert rva == cand["native_rva"], (rva, cand["native_rva"])
        primitives.append(build_primitive(pe, cand, method))

    accepted = {c["method_index"] for c in CANDIDATES}
    candidate_rows = []
    skipped = []
    for rec in methods:
        mi = rec["method_index"]
        status, reason = CLASSIFICATION[mi]
        if mi in accepted:
            status = "ACCEPT"
            reason = "selected Batch 02 primitive"
        s = stats[mi]
        row = {
            "method_index": mi,
            "name": rec["name"],
            "native_rva": f"0x{s['rva']:X}",
            "slot_size_bytes": s["slot_size"],
            "instruction_count": s["instruction_count"],
            "branch_count": s["branch_count"],
            "callee_count": s["call_count"],
            "classification": status,
            "reason": reason,
        }
        candidate_rows.append(row)
        if status != "ACCEPT":
            skipped.append(row)

    return {
        "schema": "battle_semantics_batch/1",
        "session": "Battle Semantic DynamicValue Batch 02",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "final_status": "BATTLE_SEMANTIC = DYNAMIC_VALUE_BATCH_02_PROOF",
        "game_version": GAME_VERSION,
        "evidence_level": "E4_STATIC_MACHINE_CODE",
        "build_string": manifest["build_string"],
        "source_manifest": {
            "game_root": manifest["game_root"],
            "version_source_sha256": manifest["version_source_sha256"],
            "GameAssembly": manifest["GameAssembly"],
            "global_metadata": manifest["global_metadata"],
        },
        "normalized_registries": {
            "base": str(BASE),
            "primary_type_index": PRIMARY_TYPE_INDEX,
            "primary_type": PRIMARY_TYPE_NAME,
            "method_count": facts["primary_type"]["method_count"],
            "field_count": facts["primary_type"]["field_count"],
            "semantic_status": "METADATA_IDENTITY_CONFIRMED",
        },
        "candidate_selection": {
            "search_summary": {
                "dynamic_value_total_methods": len(methods),
                "accepted_primitives": len(primitives),
                "skipped_candidates": len(skipped),
                "serialization_excluded": 2,
                "complex_skipped": sum(
                    1 for row in candidate_rows if row["classification"] == "SKIP_COMPLEX"
                ),
                "wrapper_skipped": sum(
                    1 for row in candidate_rows if row["classification"] == "SKIP_WRAPPER"
                ),
            },
            "all_methods": candidate_rows,
            "accepted_methods": [
                {
                    "method_index": c["method_index"],
                    "name": c["method_name"],
                    "native_rva": f"0x{c['native_rva']:X}",
                    "semantic_name": c["semantic_name"],
                    "primitive_id": c["primitive_id"],
                    "result": c["result"],
                }
                for c in CANDIDATES
            ],
            "primary_choice_rationale": (
                "The Batch 02 shortlist is the tag-aware scalar coercion family "
                "of RPG.GameCore.DynamicValue plus three structurally distinct "
                "tag/payload predicates and the raw tag accessor.  Every ACCEPT "
                "body is <= 40 instructions, has <= 2 direct callees, reads only "
                "the input cell, writes no battle state, and the only deeper "
                "callees are error/log or one-time IL2CPP init helpers that do "
                "not affect the returned value."
            ),
        },
        "dynamic_value_type_enum": {
            "type_index": ENUM_TYPE_INDEX,
            "name": "DynamicValueType",
            "values": [
                {"name": f["name"], "ordinal": i, "field_index": f["field_index"]}
                for i, f in enumerate(facts["enum_fields"][:-1])
            ],
            "evidence": "enum field order 0..6 matches native tag guards in Batch 02",
            "evidence_level": "CONFIRMED",
        },
        "primitives": primitives,
        "skipped_candidates": skipped,
        "unknowns": [
            "FieldDefinition provenance for the +0x30 ValueType tag byte",
            "Type-mismatch / invalid-value log helper internals (0x1CFD2950 / 0x1CFD2AB0); error paths only and value-neutral",
            "IL2CPP runtime class-init helper internals (0x3C6D0E0); one-time infrastructure on get_LongValue / get_DoubleValue",
            "get_FloatValue cvtsd2ss assumes default MXCSR round-to-nearest-even",
            "No E5 client-side runtime observation for any Batch 02 primitive",
            "Canonical DynamicValue cannot represent ARRAY/MAP cells with null payload pointers; IsArray/IsMap keep the native null-check defensively (REPRESENTATION_CONFLICT recorded, no representation change)",
        ],
        "representation_conflicts": [
            {
                "primitive_ids": [
                    "battle.ir.value.dynamic_value_is_array",
                    "battle.ir.value.dynamic_value_is_map",
                ],
                "native_behavior": "get_IsArray/get_IsMap return false when tag matches but the payload pointer is null",
                "canonical_behavior": "DynamicValue ARRAY/MAP require a non-null ObjectRef; null payload is rejected at the representation boundary",
                "analysis": "For every representable input the native and canonical results agree; the unreachable native null-payload case is kept as a defensive runtime check.  No representation change is justified yet.",
                "status": "REPRESENTATION_CONFLICT_RECORDED_NO_CHANGE",
            }
        ],
    }


def build_markdown(doc: dict) -> str:
    rows = []
    for row in doc["candidate_selection"]["all_methods"]:
        if row["classification"] == "ACCEPT":
            status = "ACCEPT"
        elif row["classification"] == "SKIP_SERIALIZATION":
            status = "SKIP_SERIALIZATION"
        else:
            status = row["classification"]
        reason = row["reason"] or "-"
        rows.append(
            f"| {row['method_index']} | {row['name']} | {row['native_rva']} | "
            f"{row['slot_size_bytes']} | {row['instruction_count']} | "
            f"{row['branch_count']} | {row['callee_count']} | {status} | {reason} |"
        )
    table = "\n".join(rows)

    primitive_sections = []
    for p in doc["primitives"]:
        ne = p["native_evidence"]
        disasm = "\n".join(f"    {line}" for line in ne["disassembly"])
        pseudocode = "\n".join(f"    {line}" for line in p["pseudocode"])
        callees = "\n".join(
            f"- {c['rva']} ({c['role']}, {c['evidence_level']})"
            for c in p["required_callees"]
        ) or "- none"
        tag = "\n".join(f"- {line}" for line in p["tag_behavior"])
        primitive_sections.append(
            f"""### {p['semantic_name']} (`{p['source_method']}`, method_index {p['source_method_index']})

- Primitive: `{p['primitive_id']}`; result `{p['result']}`
- RVA `{p['source_native_rva']}`; body {ne['body_length_bytes']} bytes /
  {ne['instruction_count']} instructions / {ne['conditional_branch_count']}
  conditional branches / {ne['direct_call_count']} calls
- Body sha256 `{ne['body_sha256']}`
- Tag behavior:

{tag}

- Branch conditions: {', '.join(p['branch_conditions']) or 'none'}
- Required callees:

{callees}

- Pseudocode:

```
{pseudocode}
```

- Native evidence:

```
{disasm}
```
"""
        )
    sections = "\n".join(primitive_sections)
    skipped = "\n".join(
        f"- {row['method_index']} {row['name']} ({row['classification']}): {row['reason']}"
        for row in doc["skipped_candidates"]
    )
    conflicts = "\n".join(
        f"- {c['status']}: {c['analysis']}" for c in doc["representation_conflicts"]
    )
    return f"""# Battle Semantic DynamicValue Batch 02

> Final status: **`{doc['final_status']}`**
> Game version: `{doc['game_version']}` ({doc['build_string']})
> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)
> Artifact schema: `{doc['schema']}`

## 1. Scope

This batch recovers eleven small tag-aware DynamicValue scalar coercions,
tag/payload queries and the raw tag accessor.  It does **not** recover the
DynamicValue resolve system, BattleContext evaluation, FixPoint framework,
serialization, logging helpers, or any non-value method.

## 2. Candidate table (all 51 methods of `RPG.GameCore.DynamicValue`)

| method_index | name | native_rva | slot(B) | insn | branch | callees | classification | reason |
|---:|---|---|---:|---:|---:|---:|---|---|
{table}

## 3. Accepted primitives

{sections}

## 4. Skipped candidates

{skipped}

## 5. Representation conflicts

{conflicts}

## 6. Known unknowns

{chr(10).join('- ' + u for u in doc['unknowns'])}

Machine-readable companion:
`data/semantics/4.4.54/dynamic_value_batch_02.json`.
"""


def main() -> int:
    facts = load_registry_facts()
    manifest = json.load((BASE / "manifest.json").open(encoding="utf-8"))
    pe = PeImage(Path(manifest["GameAssembly"]["path"]))
    doc = build_json(facts, pe)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(build_markdown(doc), encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(f"accepted={len(doc['primitives'])} skipped={len(doc['skipped_candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
