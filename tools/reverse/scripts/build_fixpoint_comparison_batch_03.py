#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Battle Semantic FixPoint Comparison Batch 03 evidence artifacts.

Inputs (read-only):
  - data/normalized/4.4.54/{manifest,types,methods,fields,parameters}.json
  - data/parsed/4.4.54/method_code_table.bin
  - GameAssembly.dll from the manifest (native body bytes + bounded capstone)

Outputs:
  - data/semantics/4.4.54/fixpoint_comparison_batch_03.json
  - docs/battle_semantics/fixpoint_comparison_batch_03.md

Every ACCEPT is re-verified against the normalized method definition and the
method code-table slot before any evidence is written.  Names and prompt RVAs
are never trusted.  Shared evidence mechanics live in
``semantic_batch_evidence.py``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    NORMALIZED_BASE,
    build_native_evidence,
    disasm_window,
    load_manifest,
    load_parameter_refs,
    load_pe,
    load_registry_facts,
    validate_code_slot,
)

OUT_JSON = REPO / "data" / "semantics" / "4.4.54" / "fixpoint_comparison_batch_03.json"
OUT_MD = REPO / "docs" / "battle_semantics" / "fixpoint_comparison_batch_03.md"

GAME_VERSION = "4.4.54"
FIXPOINT_TYPE_INDEX = 9881
FIXPOINT_TYPE_NAME = "RPG.GameCore.FixPoint"
BOOL_TYPE_REFERENCE = 424
FIXPOINT_TYPE_REFERENCE = 20642
INT32_TYPE_REFERENCE = 71

COMPARE_PSEUDOCODE_COMMON = [
    "int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee",
    "    le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED",
    "    if le == 1 and re == 0:",
    "        c = sign64((lhs & ~1) - sar64(rhs, 7))",
    "        if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0",
    "        return c",
    "    if le == 0 and re == 1:",
    "        c = sign64(sar64(lhs, 7) - (rhs & ~1))",
    "        if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0",
    "        return c",
    "    if le == 0 and re == 0: return sign64(lhs - rhs)",
    "    return sign64((lhs & ~1) - (rhs & ~1))",
]

# Accepted Batch 03 primitives.  `body_bytes` is the exact native window ending
# in the method's final `ret`; it was derived from bounded disassembly, not from
# trusting same-type RVA gaps (FixPoint methods are interleaved with other
# runtime types).
CANDIDATES = [
    {
        "method_index": 68214,
        "method_name": "op_Equality",
        "native_rva": 0x1D661340,
        "body_bytes": 0x90,
        "semantic_name": "FixPointEqual",
        "primitive_id": "battle.ir.compare.fixpoint_equal",
        "result": "boolean",
        "inputs": [("lhs", "FixPointRaw"), ("rhs", "FixPointRaw")],
        "description": "Mode-aware equality of two RPG.GameCore.FixPoint raw encodings",
        "abi": "x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al",
        "op_semantics": "return FixPointCompareRaw(lhs, rhs) == 0",
        "branch_conditions": [
            "lhs mode flag bit0 == 0 and rhs mode flag bit0 == 0 -> compare raw qwords directly",
            "lhs mode flag bit0 == 0 and rhs mode flag bit0 == 1 -> compare sar(lhs,7) with rhs & ~1; tie broken by lhs low 7 bits",
            "lhs mode flag bit0 == 1 and rhs mode flag bit0 == 0 -> compare lhs & ~1 with sar(rhs,7); tie broken by rhs low 7 bits",
            "both mode flag bit0 == 1 -> compare (lhs & ~1) with (rhs & ~1)",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": ["mode mask 1", "mixed-mode shift 7", "fraction mask 0x7F"],
        "required_callees": [],
        "pseudocode": COMPARE_PSEUDOCODE_COMMON
        + [
            "bool FixPointEqual(lhs, rhs):",
            "    return FixPointCompareRaw(lhs, rhs) == 0   # native: sete",
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction beyond the raw-encoding order is not recovered in this batch",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68215,
        "method_name": "op_Inequality",
        "native_rva": 0x1D664520,
        "body_bytes": 0x90,
        "semantic_name": "FixPointNotEqual",
        "primitive_id": "battle.ir.compare.fixpoint_not_equal",
        "result": "boolean",
        "inputs": [("lhs", "FixPointRaw"), ("rhs", "FixPointRaw")],
        "description": "Mode-aware inequality of two RPG.GameCore.FixPoint raw encodings",
        "abi": "x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al",
        "op_semantics": "return FixPointCompareRaw(lhs, rhs) != 0",
        "branch_conditions": [
            "same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization",
            "mixed-mode equality tie is broken by the standard-mode low 7 fraction bits",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": ["mode mask 1", "mixed-mode shift 7", "fraction mask 0x7F"],
        "required_callees": [],
        "pseudocode": COMPARE_PSEUDOCODE_COMMON
        + [
            "bool FixPointNotEqual(lhs, rhs):",
            "    return FixPointCompareRaw(lhs, rhs) != 0   # native: setne",
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction beyond the raw-encoding order is not recovered in this batch",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68216,
        "method_name": "op_GreaterThan",
        "native_rva": 0x1D6645B0,
        "body_bytes": 0x90,
        "semantic_name": "FixPointGreaterThan",
        "primitive_id": "battle.ir.compare.fixpoint_greater",
        "result": "boolean",
        "inputs": [("lhs", "FixPointRaw"), ("rhs", "FixPointRaw")],
        "description": "Mode-aware greater-than over two RPG.GameCore.FixPoint raw encodings",
        "abi": "x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al",
        "op_semantics": "return FixPointCompareRaw(lhs, rhs) > 0",
        "branch_conditions": [
            "same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization",
            "mixed-mode equality tie is broken by the standard-mode low 7 fraction bits",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": ["mode mask 1", "mixed-mode shift 7", "fraction mask 0x7F"],
        "required_callees": [],
        "pseudocode": COMPARE_PSEUDOCODE_COMMON
        + [
            "bool FixPointGreaterThan(lhs, rhs):",
            "    return FixPointCompareRaw(lhs, rhs) > 0    # native: setg",
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction beyond the raw-encoding order is not recovered in this batch",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68217,
        "method_name": "op_LessThan",
        "native_rva": 0x1D6646D0,
        "body_bytes": 0x8A,
        "semantic_name": "FixPointLessThan",
        "primitive_id": "battle.ir.compare.fixpoint_less",
        "result": "boolean",
        "inputs": [("lhs", "FixPointRaw"), ("rhs", "FixPointRaw")],
        "description": "Mode-aware less-than over two RPG.GameCore.FixPoint raw encodings",
        "abi": "x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al",
        "op_semantics": "return FixPointCompareRaw(lhs, rhs) < 0",
        "branch_conditions": [
            "same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization",
            "mixed-mode equality tie is broken by the standard-mode low 7 fraction bits",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": ["mode mask 1", "mixed-mode shift 7", "fraction mask 0x7F"],
        "required_callees": [],
        "pseudocode": COMPARE_PSEUDOCODE_COMMON
        + [
            "bool FixPointLessThan(lhs, rhs):",
            "    return FixPointCompareRaw(lhs, rhs) < 0     # native: setl",
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction beyond the raw-encoding order is not recovered in this batch",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68218,
        "method_name": "op_GreaterThanOrEqual",
        "native_rva": 0x1D660C50,
        "body_bytes": 0x90,
        "semantic_name": "FixPointGreaterEqual",
        "primitive_id": "battle.ir.compare.fixpoint_greater_equal",
        "result": "boolean",
        "inputs": [("lhs", "FixPointRaw"), ("rhs", "FixPointRaw")],
        "description": "Mode-aware greater-than-or-equal over two RPG.GameCore.FixPoint raw encodings",
        "abi": "x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al",
        "op_semantics": "return FixPointCompareRaw(lhs, rhs) >= 0",
        "branch_conditions": [
            "same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization",
            "mixed-mode equality tie is broken by the standard-mode low 7 fraction bits",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": ["mode mask 1", "mixed-mode shift 7", "fraction mask 0x7F"],
        "required_callees": [],
        "pseudocode": COMPARE_PSEUDOCODE_COMMON
        + [
            "bool FixPointGreaterEqual(lhs, rhs):",
            "    return FixPointCompareRaw(lhs, rhs) >= 0   # native: setns",
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction beyond the raw-encoding order is not recovered in this batch",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68219,
        "method_name": "op_LessThanOrEqual",
        "native_rva": 0x1D664760,
        "body_bytes": 0x90,
        "semantic_name": "FixPointLessEqual",
        "primitive_id": "battle.ir.compare.fixpoint_less_equal",
        "result": "boolean",
        "inputs": [("lhs", "FixPointRaw"), ("rhs", "FixPointRaw")],
        "description": "Mode-aware less-than-or-equal over two RPG.GameCore.FixPoint raw encodings",
        "abi": "x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al",
        "op_semantics": "return FixPointCompareRaw(lhs, rhs) <= 0",
        "branch_conditions": [
            "same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization",
            "mixed-mode equality tie is broken by the standard-mode low 7 fraction bits",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": ["mode mask 1", "mixed-mode shift 7", "fraction mask 0x7F"],
        "required_callees": [],
        "pseudocode": COMPARE_PSEUDOCODE_COMMON
        + [
            "bool FixPointLessEqual(lhs, rhs):",
            "    return FixPointCompareRaw(lhs, rhs) <= 0    # native: setle",
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction beyond the raw-encoding order is not recovered in this batch",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68256,
        "method_name": "op_Implicit",
        "native_rva": 0x1D664F30,
        "body_bytes": 0x28,
        "semantic_name": "FixPointFromInt32",
        "primitive_id": "battle.ir.value.fixpoint_from_int32",
        "result": "fixpoint_raw",
        "inputs": [("value", "int32")],
        "description": "Signed int32 -> RPG.GameCore.FixPoint raw encoding (standard or extended mode)",
        "abi": "x64: value=ecx (int32), raw qword return=rax",
        "op_semantics": (
            "n = sign_extend_32(value); "
            "if abs(n) >= 0x40000000: return ((n << 0x1A) | 1) & MASK64; "
            "return (n << 0x21) & MASK64"
        ),
        "branch_conditions": [
            "abs(sign_extend_32(value)) < 0x40000000 -> STANDARD raw = n << 0x21",
            "abs(sign_extend_32(value)) >= 0x40000000 -> EXTENDED raw = (n << 0x1A) | 1",
        ],
        "field_reads": [],
        "field_writes": [],
        "constants": [
            "standard shift 0x21 (33)",
            "extended shift 0x1A (26)",
            "mode flag 1",
            "standard/extended threshold abs(n) == 0x40000000",
        ],
        "required_callees": [],
        "pseudocode": [
            "fixpoint_raw FixPointFromInt32(int32 value):",
            "    n = sign_extend_32(value)",
            "    if abs(n) >= 0x40000000:",
            "        return ((n << 26) | 1) & 0xFFFFFFFFFFFFFFFF   # EXTENDED",
            "    return (n << 33) & 0xFFFFFFFFFFFFFFFF            # STANDARD",
        ],
        "unknowns": [
            "type_reference 71 identity is anchored as System.Int32 by registry consumers; no formal type-reference resolver exists yet",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68173,
        "method_name": "get_IsZero",
        "native_rva": 0x1D663050,
        "body_bytes": 0x08,
        "semantic_name": "FixPointIsZero",
        "primitive_id": "battle.ir.predicate.fixpoint_is_zero",
        "result": "boolean",
        "inputs": [("value", "FixPointRaw")],
        "description": "True iff a FixPoint raw encoding is STANDARD zero (0) or EXTENDED zero (1)",
        "abi": "x64: this=rcx (boxed FixPoint), raw qword read from [this+0x00], bool return=al",
        "op_semantics": "return raw < 2 (unsigned qword compare)",
        "branch_conditions": ["raw qword < 2 -> true; otherwise false"],
        "field_reads": ["FixPoint.m_rawValue qword (field_index 40768) at boxed offset +0x00"],
        "field_writes": [],
        "constants": ["zero encodings 0 and 1", "threshold 2"],
        "required_callees": [],
        "pseudocode": [
            "bool FixPointIsZero(fixpoint_raw raw):",
            "    return (raw & 0xFFFFFFFFFFFFFFFF) < 2   # native: cmp [this], 2; setb al",
        ],
        "unknowns": [
            "Canonical IR takes raw qword directly; IL2CPP boxed-object pointer is provenance only",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68174,
        "method_name": "get_IsNegative",
        "native_rva": 0x1D663060,
        "body_bytes": 0x08,
        "semantic_name": "FixPointIsNegative",
        "primitive_id": "battle.ir.predicate.fixpoint_is_negative",
        "result": "boolean",
        "inputs": [("value", "FixPointRaw")],
        "description": "True iff the sign bit (bit 63) of a FixPoint raw encoding is set",
        "abi": "x64: this=rcx (boxed FixPoint), raw qword read from [this+0x00], bool return=al",
        "op_semantics": "return (raw >> 63) == 1 (logical shift of qword)",
        "branch_conditions": ["raw bit 63 == 0 -> false", "raw bit 63 == 1 -> true"],
        "field_reads": ["FixPoint.m_rawValue qword (field_index 40768) at boxed offset +0x00"],
        "field_writes": [],
        "constants": ["sign bit mask 0x8000000000000000"],
        "required_callees": [],
        "pseudocode": [
            "bool FixPointIsNegative(fixpoint_raw raw):",
            "    return ((raw & 0xFFFFFFFFFFFFFFFF) >> 63) == 1   # native: shr rax, 0x3F",
        ],
        "unknowns": [
            "Canonical IR takes raw qword directly; IL2CPP boxed-object pointer is provenance only",
            "No E5 client-side runtime observation",
        ],
    },
    {
        "method_index": 68175,
        "method_name": "get_IsPositive",
        "native_rva": 0x1D663070,
        "body_bytes": 0x0B,
        "semantic_name": "FixPointIsPositive",
        "primitive_id": "battle.ir.predicate.fixpoint_is_positive",
        "result": "boolean",
        "inputs": [("value", "FixPointRaw")],
        "description": "True iff (raw & ~1) is a positive signed qword (both zero encodings are false)",
        "abi": "x64: this=rcx (boxed FixPoint), raw qword read from [this+0x00], bool return=al",
        "op_semantics": "return signed64(raw & ~1) > 0",
        "branch_conditions": [
            "signed(raw & ~1) > 0 -> true",
            "signed(raw & ~1) <= 0 -> false (covers 0, 1, and negative encodings)",
        ],
        "field_reads": ["FixPoint.m_rawValue qword (field_index 40768) at boxed offset +0x00"],
        "field_writes": [],
        "constants": ["mode flag clear mask ~1", "signed qword sign semantics"],
        "required_callees": [],
        "pseudocode": [
            "bool FixPointIsPositive(fixpoint_raw raw):",
            "    masked = (raw & 0xFFFFFFFFFFFFFFFF) & ~1",
            "    return signed64(masked) > 0            # native: test [this], -2; setg al",
        ],
        "unknowns": [
            "Canonical IR takes raw qword directly; IL2CPP boxed-object pointer is provenance only",
            "No E5 client-side runtime observation",
        ],
    },
]

# Candidate classification for the first-round table.  ACCEPT rows carry exact
# bounded evidence; skipped rows carry a quick complexity scan estimate and a
# classification reason.
SKIP_CANDIDATES = [
    {
        "runtime_type": "RPG.GameCore.ByCompareDynamicValue",
        "method": ".ctor",
        "method_index": 133350,
        "native_rva": 0x1CE2F1C0,
        "classification": "SKIP_SERIALIZATION",
        "reason": "all five declared methods are ctor/serializer wrapper shapes; no Check/Evaluate/Compare/Execute/IsSatisfied runtime method exists on this runtime type",
    },
    {
        "runtime_type": "RPG.GameCore.ByCompareDynamicValue",
        "method": "OJNNBEJLDIJ",
        "method_index": 133351,
        "native_rva": 0x1CE2F160,
        "classification": "SKIP_SERIALIZATION",
        "reason": "wrapper/impl serializer pair (historical 4.4.54 evidence)",
    },
    {
        "runtime_type": "RPG.GameCore.ByCompareDynamicValue",
        "method": "MGMEGEDLMAK",
        "method_index": 133352,
        "native_rva": 0x1CE2F200,
        "classification": "SKIP_SERIALIZATION",
        "reason": "wrapper/impl serializer pair (historical 4.4.54 evidence)",
    },
    {
        "runtime_type": "RPG.GameCore.ByCompareDynamicValue",
        "method": "LJACLBNEEEB",
        "method_index": 133353,
        "native_rva": 0x1CE2F500,
        "classification": "SKIP_SERIALIZATION",
        "reason": "wrapper/impl serializer pair (historical 4.4.54 evidence)",
    },
    {
        "runtime_type": "RPG.GameCore.ByCompareDynamicValue",
        "method": "EOJLPDGNHEK",
        "method_index": 133354,
        "native_rva": 0x1CE2F560,
        "classification": "SKIP_SERIALIZATION",
        "reason": "wrapper/impl serializer pair (historical 4.4.54 evidence)",
    },
    {
        "runtime_type": "RPG.GameCore.ByCompareValue",
        "method": ".ctor",
        "method_index": 133355,
        "native_rva": 0x1CE7C770,
        "classification": "SKIP_SERIALIZATION",
        "reason": "runtime class contains only ctor/wrapper/impl serialization methods; comparison semantics live in the FixPoint compare core recovered by this batch",
    },
    {
        "runtime_type": "RPG.GameCore.ByDynamicValueDefined",
        "method": ".ctor",
        "method_index": 125477,
        "native_rva": 0x1CE899F0,
        "classification": "SKIP_SERIALIZATION",
        "reason": "same serializer/wrapper family; no non-serialization runtime predicate method on the type",
    },
    {
        "runtime_type": "RPG.GameCore.PredicateConfig",
        "method": ".ctor",
        "method_index": 132841,
        "native_rva": 0x1D2CA150,
        "classification": "SKIP_SERIALIZATION",
        "reason": "config runtime type with only ctor/wrapper/impl serializer methods",
    },
    {
        "runtime_type": "RPG.GameCore.CondCompareConfig",
        "method": ".ctor",
        "method_index": 106308,
        "native_rva": 0x1CF67770,
        "classification": "SKIP_SERIALIZATION",
        "reason": "config runtime type with only ctor/wrapper/impl serializer methods",
    },
    {
        "runtime_type": "RPG.GameCore.TaskContext",
        "method": "Evaluate",
        "method_index": 505866,
        "native_rva": 0xE6F0A60,
        "classification": "SKIP_CONTEXT_HEAVY",
        "reason": "bool predicate dispatcher: reads TaskContext evaluator dictionary, hashes a string key, calls dictionary/index helpers and a tail dispatcher; call graph exceeds the batch budget",
    },
    {
        "runtime_type": "RPG.GameCore.TaskContext",
        "method": "EvaluateOrDefault",
        "method_index": 505884,
        "native_rva": 0xE6F24D0,
        "classification": "SKIP_WRAPPER",
        "reason": "null -> false, otherwise tailcall TaskContext.Evaluate(bool); no independent semantic beyond the skipped heavy dispatcher",
    },
    {
        "runtime_type": "RPG.GameCore.ValueEvaluatorConfig",
        "method": "FEIIDFFOICL",
        "method_index": 135383,
        "native_rva": 0x1D606570,
        "classification": "SKIP_WRAPPER",
        "reason": "compares a wrapped object field [rcx+0x20] to a FixPoint raw; current Kernel has no wrapper-object representation and the compare core is already recovered as FixPointEqual",
    },
    {
        "runtime_type": "RPG.GameCore.ValueEvaluatorConfig",
        "method": "DLDBLNNPHKE",
        "method_index": 135384,
        "native_rva": 0x1D606640,
        "classification": "SKIP_WRAPPER",
        "reason": "same wrapped-field compare pattern as 135383; no additional semantic operation",
    },
    {
        "runtime_type": "RPG.GameCore.FixPoint",
        "method": "op_Implicit",
        "method_index": 68257,
        "native_rva": 0x1D668000,
        "classification": "SKIP_WRAPPER",
        "reason": "same standard/extended encoding core as accepted 68256; native ABI shows an unsigned 32-bit entry (cmovb threshold) and is deferred to respect the batch value budget",
    },
    {
        "runtime_type": "RPG.GameCore.FixPoint",
        "method": "ToBoolean",
        "method_index": 68147,
        "native_rva": 0x1D6628B0,
        "classification": "SKIP_COMPLEX",
        "reason": "one-time IL2CPP class-init wrapper + interface conversion path; not a leaf predicate",
    },
    {
        "runtime_type": "RPG.GameCore.FixPoint",
        "method": "Approximately",
        "method_index": 68258,
        "native_rva": 0x1D668020,
        "classification": "SKIP_COMPLEX",
        "reason": "epsilon/global-constant-dependent approximate comparison; larger body and more branches than the exact six-operator core",
    },
    {
        "runtime_type": "RPG.GameCore.FixPoint",
        "method": "IsAlmostZero",
        "method_index": 68259,
        "native_rva": 0x1D668170,
        "classification": "SKIP_COMPLEX",
        "reason": "epsilon-dependent helper; outside this batch's exact-comparison core",
    },
    {
        "runtime_type": "RPG.GameCore.FixPoint",
        "method": "BothStandardMode",
        "method_index": 68185,
        "native_rva": 0x1D663220,
        "classification": "SKIP_COMPLEX",
        "reason": "mode helper, not a predicate/compare primitive; recovered compare code already handles mixed modes directly",
    },
    {
        "runtime_type": "RPG.GameCore.DialogueConditionRow",
        "method": "CompareItemState",
        "method_index": 88610,
        "native_rva": 0x1CF94880,
        "classification": "SKIP_NON_BATTLE",
        "reason": "dialogue content condition comparison, not battle gameplay semantic",
    },
    {
        "runtime_type": "RPG.Client.ConditionCheckerUtil",
        "method": "DoCheckConditions",
        "method_index": 546444,
        "native_rva": 0xCC3A300,
        "classification": "SKIP_CONTEXT_HEAVY",
        "reason": "client condition list dispatcher; call graph and client state dependencies exceed the batch budget",
    },
    {
        "runtime_type": "RPG.GameCore.CheckPredicateAxis",
        "method": ".ctor",
        "method_index": 102771,
        "native_rva": 0x1CF125B0,
        "classification": "SKIP_SERIALIZATION",
        "reason": "serializer-shaped runtime type; no leaf predicate body",
    },
]


def quick_method_stats(pe, facts, skip_candidates):
    """Quick bounded scan for skipped candidate rows (estimate only).

    Skipped rows are not E4 primitives; their windows are approximations from
    the next same-type RVA and may include trailing padding.  The scan ends at
    the last non-``nop`` decoded instruction, which is good enough for
    first-round classification and is marked ``scan_estimate``.
    """
    methods_by_index = {m["method_index"]: m for m in facts["all_methods"]}
    rvas_by_type: dict[int, list[int]] = {}
    for rec in facts["all_methods"]:
        if isinstance(rec.get("native_rva"), int):
            rvas_by_type.setdefault(rec["declaring_type_index"], []).append(rec["native_rva"])
    out = {}
    for cand in skip_candidates:
        method = methods_by_index.get(cand["method_index"])
        if method is None:
            out[cand["method_index"]] = None
            continue
        rva = int(method["native_rva"])
        size = None
        for other in sorted(rvas_by_type.get(method["declaring_type_index"], [])):
            if other > rva:
                size = other - rva
                break
        if size is None or size > 0x400:
            size = 0x200
        size = min(size, 0x400)
        raw, decoded = disasm_window(pe, rva, size)
        if not decoded:
            out[cand["method_index"]] = None
            continue
        end = size
        for ins in reversed(decoded):
            if ins["mnemonic"] == "nop":
                continue
            end = ins["rva"] + ins["size"] - rva
            break
        body = [i for i in decoded if i["rva"] + i["size"] - rva <= end]
        out[cand["method_index"]] = {
            "native_size_estimate_bytes": end,
            "instruction_count": len(body),
            "branch_count": sum(
                1
                for i in body
                if i["mnemonic"].startswith("j") and i["mnemonic"] != "jmp"
            ),
            "callee_count": sum(1 for i in body if i["mnemonic"] == "call"),
        }
    return out


def build_json(facts, pe):
    manifest = load_manifest()
    methods_by_index = {m["method_index"]: m for m in facts["all_methods"]}
    params_by_method = load_parameter_refs(
        {c["method_index"] for c in CANDIDATES}
    )
    skip_stats = quick_method_stats(pe, facts, SKIP_CANDIDATES)

    primitives = []
    accepted_rows = []
    for cand in CANDIDATES:
        method = methods_by_index[cand["method_index"]]
        assert method["declaring_type_index"] == FIXPOINT_TYPE_INDEX, method
        assert method["name"] == cand["method_name"], (method, cand["method_name"])
        assert int(method["native_rva"]) == cand["native_rva"], (
            method["native_rva"],
            cand["native_rva"],
        )
        if cand["method_index"] == 68256:
            assert method["return_type_reference"] == FIXPOINT_TYPE_REFERENCE, method
        else:
            assert method["return_type_reference"] == BOOL_TYPE_REFERENCE, method
        ne = build_native_evidence(pe, cand, method)
        params = params_by_method.get(cand["method_index"], [])
        primitive = {
            "primitive_id": cand["primitive_id"],
            "semantic_name": cand["semantic_name"],
            "description": cand["description"],
            "source_runtime_type": FIXPOINT_TYPE_NAME,
            "source_method": cand["method_name"],
            "source_method_index": cand["method_index"],
            "source_native_rva": f"0x{cand['native_rva']:X}",
            "native_body_hash": ne["body_sha256"],
            "inputs": [
                {"name": name, "type": typ} for name, typ in cand["inputs"]
            ],
            "result": cand["result"],
            "context_reads": [name for name, _ in cand["inputs"]],
            "context_writes": [],
            "determinism": "DETERMINISTIC",
            "op_semantics": cand["op_semantics"],
            "field_reads": cand["field_reads"],
            "field_writes": cand["field_writes"],
            "constants": cand["constants"],
            "branch_conditions": cand["branch_conditions"],
            "required_callees": cand["required_callees"],
            "pseudocode": cand["pseudocode"],
            "unknowns": cand["unknowns"],
            "native_evidence": ne,
            "parameter_relation": [
                {
                    "parameter_index": p["parameter_index"],
                    "name_key": p.get("name_key"),
                    "type_reference": p["type_reference"],
                    "structure_status": p.get("structure_status"),
                }
                for p in params
            ],
            "return_type_reference": method["return_type_reference"],
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
        primitives.append(primitive)
        accepted_rows.append(
            {
                "runtime_type": FIXPOINT_TYPE_NAME,
                "method": cand["method_name"],
                "method_index": cand["method_index"],
                "native_rva": f"0x{cand['native_rva']:X}",
                "size_bytes": ne["body_length_bytes"],
                "instruction_count": ne["instruction_count"],
                "branch_count": ne["conditional_branch_count"],
                "callee_count": ne["direct_call_count"],
                "classification": "ACCEPT",
                "reason": "exact bounded native body; no normal-path callees; no context reads beyond operands",
            }
        )

    skipped_rows = []
    for cand in SKIP_CANDIDATES:
        stats = skip_stats.get(cand["method_index"]) or {}
        skipped_rows.append(
            {
                "runtime_type": cand["runtime_type"],
                "method": cand["method"],
                "method_index": cand["method_index"],
                "native_rva": f"0x{cand['native_rva']:X}",
                "size_bytes": stats.get("native_size_estimate_bytes"),
                "instruction_count": stats.get("instruction_count"),
                "branch_count": stats.get("branch_count"),
                "callee_count": stats.get("callee_count"),
                "classification": cand["classification"],
                "reason": cand["reason"],
                "scan_estimate": True,
            }
        )

    return {
        "schema": "battle_semantics_batch/1",
        "session": "Battle Semantic FixPoint Comparison Batch 03",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "final_status": "BATTLE_SEMANTIC = FIXPOINT_COMPARISON_BATCH_03_PROOF",
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
            "base": str(NORMALIZED_BASE),
            "primary_type_index": FIXPOINT_TYPE_INDEX,
            "primary_type": FIXPOINT_TYPE_NAME,
            "method_count": facts["primary_type"]["method_count"],
            "field_count": facts["primary_type"]["field_count"],
            "semantic_status": "METADATA_IDENTITY_CONFIRMED",
        },
        "candidate_selection": {
            "search_summary": {
                "name_matched_types_all_namespaces": 876,
                "rpg_gamecore_priority_types": 581,
                "priority_by_keyword": {
                    "predicate": 75,
                    "condition": 195,
                    "compare": 207,
                    "check": 111,
                    "comparison": 0,
                    "boolean": 0,
                },
                "rpg_gamecore_bool_direct_native_methods": 2674,
                "method_name_pattern_candidates_scanned": 289,
                "accepted_primitives": len(CANDIDATES),
                "skipped_candidates": len(SKIP_CANDIDATES),
            },
            "candidates": accepted_rows + skipped_rows,
            "primary_choice_rationale": (
                "The game does not expose a single CompareValue(lhs,rhs,op) "
                "dispatcher in small native code.  Its real comparison core is "
                "the six FixPoint op_Equality/op_Inequality/op_LessThan/"
                "op_LessThanOrEqual/op_GreaterThan/op_GreaterThanOrEqual "
                "bodies: 0 normal-path callees, exact bounded windows, "
                "mode-aware raw-encoding comparison.  FixPointFromInt32 is the "
                "smallest proven bridge from an existing DynamicValue scalar "
                "coercion into that core, and the three boxed sign/zero "
                "getters are the simplest true predicate leaves.  "
                "ByCompareDynamicValue and its neighbours are serializer/"
                "wrapper shapes and remain excluded."
            ),
        },
        "fixpoint_encoding": {
            "type_index": FIXPOINT_TYPE_INDEX,
            "instance_field": {
                "field_index": 40768,
                "name": "m_rawValue",
                "type_reference": 432361,
                "role": "single qword raw encoding; boxed-object offset +0x00",
                "evidence": "get_IsZero/get_IsNegative/get_IsPositive read [this+0x00]",
            },
            "mode_flag": "bit0: 0 = STANDARD, 1 = EXTENDED",
            "standard_mode": "canonical standard raw = signed int64 << 0x21 (low 7 bits zero)",
            "extended_mode": "canonical extended raw = (signed int64 << 0x1A) | 1",
            "mixed_mode_compare": "standard raw >> 7 (arithmetic) is compared with extended raw & ~1; a non-zero standard low 7-bit fraction breaks equality as greater-than",
            "evidence": "derived from op_Implicit(Int32) shift constants and the six compare bodies",
            "evidence_level": "CONFIRMED",
        },
        "comparison_semantics": {
            "internal_representation": "one qword raw value; bit0 selects STANDARD (0) or EXTENDED (1)",
            "branch_semantics": [
                "both STANDARD: signed qword compare of the raw values",
                "both EXTENDED: signed qword compare of (raw & ~1) on both sides",
                "STANDARD lhs, EXTENDED rhs: sign(sar(lhs,7) - (rhs & ~1)); on equality, a non-zero low-7-bit fraction in lhs makes lhs greater",
                "EXTENDED lhs, STANDARD rhs: sign((lhs & ~1) - sar(rhs,7)); on equality, a non-zero low-7-bit fraction in rhs makes rhs greater",
            ],
            "signedness": "all same-mode and normalized mixed-mode comparisons are signed 64-bit; get_IsNegative reads the raw sign bit; get_IsPositive tests signed(raw & ~1) > 0",
            "special_mode_or_sentinel": "NONE_OBSERVED — no NaN, infinity, saturation, or sentinel branch exists in any accepted body; every raw qword participates in the same total order",
            "proven_comparison_coverage": "all six operators over the full 64-bit raw qword domain, including non-canonical mixed-mode and low-7-bit-fraction raw values",
            "sandbox_constructible_domain": "canonical FixPoint raw values produced by FixPointFromInt32(int32) only; comparison primitives accept full qword inputs for differential testing but the IR constructor set is intentionally minimal",
            "evidence_level": "CONFIRMED",
        },
        "primitives": primitives,
        "skipped_candidates": skipped_rows,
        "semantic_dependencies": [
            {
                "dependency": "DynamicValueToInt32 (battle.ir.value.dynamic_value_to_int)",
                "role": "existing Batch 02 primitive; canonical composition bridge into FixPointFromInt32 for INT DynamicValue cells",
                "status": "SATISFIED",
            },
            {
                "dependency": "DynamicValueEquals (battle.ir.value.dynamic_value_equals)",
                "role": "existing Vertical Slice 01 primitive; reference equality for comparison-heavy predicate composition tests",
                "status": "SATISFIED",
            },
            {
                "dependency": "TaskContext.Evaluate(bool) predicate dispatcher",
                "role": "full ByCompareDynamicValue predicate graph evaluation",
                "status": "SEMANTIC_DEPENDENCY_REQUIRED",
                "note": "PHASE B does not implement this dispatcher; see skipped_candidates",
            },
        ],
        "unknowns": [
            "Numeric FixPoint reconstruction outside the recovered raw-encoding order/conversion predicates is not part of this batch",
            "type_reference identities (71/424/20642) are anchored by consumers; no formal type-reference resolver exists in the normalized pipeline yet",
            "IL2CPP boxed-object ABI for get_IsZero/get_IsNegative/get_IsPositive is provenance only; canonical IR models the raw qword",
            "No E5 client-side runtime observation for any Batch 03 primitive",
        ],
    }


def build_markdown(doc: dict) -> str:
    rows = []
    for row in doc["candidate_selection"]["candidates"]:
        size = row.get("size_bytes")
        insn = row.get("instruction_count")
        branch = row.get("branch_count")
        callee = row.get("callee_count")
        rows.append(
            f"| {row['method_index']} | {row['runtime_type']}.{row['method']} "
            f"| {row['native_rva']} | {size if size is not None else '-'} "
            f"| {insn if insn is not None else '-'} "
            f"| {branch if branch is not None else '-'} "
            f"| {callee if callee is not None else '-'} "
            f"| {row['classification']} | {row['reason']} |"
        )
    table = "\n".join(rows)

    sections = []
    for p in doc["primitives"]:
        ne = p["native_evidence"]
        disasm = "\n".join(f"    {line}" for line in ne["disassembly"])
        pseudocode = "\n".join(f"    {line}" for line in p["pseudocode"])
        callees = "\n".join(
            f"- {c['rva']} ({c['role']}, {c['evidence_level']})"
            for c in p["required_callees"]
        ) or "- none"
        fields = "\n".join(f"- {f}" for f in p["field_reads"]) or "- none"
        branches = "\n".join(f"- {b}" for b in p["branch_conditions"]) or "- none"
        sections.append(
            f"""### {p['semantic_name']} (`{p['source_method']}`, method_index {p['source_method_index']})

- Primitive: `{p['primitive_id']}`; result `{p['result']}`
- RVA `{p['source_native_rva']}`; body {ne['body_length_bytes']} bytes /
  {ne['instruction_count']} instructions / {ne['conditional_branch_count']}
  conditional branches / {ne['direct_call_count']} calls
- Body sha256 `{ne['body_sha256']}`
- ABI: `{ne['abi']}`
- Operation: `{p['op_semantics']}`
- Field reads:
{fields}
- Branch conditions:
{branches}
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

    sections = "\n".join(sections)

    skipped = "\n".join(
        f"- {row['method_index']} {row['runtime_type']}.{row['method']} "
        f"({row['classification']}): {row['reason']}"
        for row in doc["skipped_candidates"]
    )
    deps = "\n".join(
        f"- {d['dependency']}: {d['status']}" + (f" — {d['note']}" if d.get("note") else "")
        for d in doc["semantic_dependencies"]
    )
    unknowns = "\n".join(f"- {u}" for u in doc["unknowns"])
    return f"""# Battle Semantic FixPoint Comparison Batch 03

> Final status: **`{doc['final_status']}`**
> Game version: `{doc['game_version']}` ({doc['build_string']})
> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)
> Artifact schema: `{doc['schema']}`

## 1. Scope

This batch recovers the game's real comparison core: six mode-aware
`RPG.GameCore.FixPoint` comparison operators, one signed int32 -> FixPoint
raw-encoding bridge, and three boxed sign/zero predicate leaves.  It does
**not** recover the `TaskContext.Evaluate(bool)` predicate graph dispatcher,
FixPoint arithmetic, serializer wrappers, or any `ByCompareDynamicValue`
content pipeline.

Composition shape proven by this batch plus existing artifacts:

```text
DynamicValue (INT)
  -> DynamicValueToInt32        (Batch 02, reused)
  -> FixPointFromInt32          (Batch 03)
  -> FixPoint{{Less,LessEqual,Equal,NotEqual,Greater,GreaterEqual}}
  -> boolean
```

## 2. Candidate table

| method_index | candidate | native_rva | size(B) | insn | branch | callee | classification | reason |
|---:|---|---|---:|---:|---:|---:|---|---|
{table}

## 3. FixPoint raw encoding and comparison semantics (recovered in this batch)

- `type_index 9881`, single instance field `m_rawValue` (field_index 40768).
- bit0 is the mode flag: `0 = STANDARD`, `1 = EXTENDED`.
- canonical STANDARD raw = `signed64 << 0x21`.
- canonical EXTENDED raw = `(signed64 << 0x1A) | 1`.
- mixed-mode comparison normalizes with a 7-bit arithmetic shift and keeps a
  low-7-bit fraction tie-break exactly as the native bodies do.
- **Signedness:** every same-mode comparison and every mixed-mode normalized
  comparison is a signed 64-bit comparison.  `get_IsNegative` reads bit 63;
  `get_IsPositive` tests `signed(raw & ~1) > 0`.
- **Special mode / sentinel:** `NONE_OBSERVED`.  The accepted bodies contain no
  NaN / infinity / saturation / sentinel branch; every raw qword participates
  in the same total order.
- **Proven comparison coverage:** all six operators over the full qword raw
  domain, including non-canonical mixed-mode and low-7-bit-fraction inputs.
- **Sandbox-constructible domain:** canonical raw values produced by
  `FixPointFromInt32(int32)` only.  Comparison primitives accept full qword
  raw inputs for differential verification, but the IR constructor set stays
  minimal and does not grow into a full FixPoint framework.

## 4. Accepted primitives

{sections}

## 5. Skipped candidates

{skipped}

## 6. Semantic dependencies

{deps}

## 7. Known unknowns

{unknowns}

Machine-readable companion:
`data/semantics/4.4.54/fixpoint_comparison_batch_03.json`.
"""


def main() -> int:
    type_indexes = {FIXPOINT_TYPE_INDEX}
    type_indexes.update(
        {
            23498,  # ByCompareDynamicValue
            23499,  # ByCompareValue
            22622,  # ByDynamicValueDefined
            23438,  # PredicateConfig
            16867,  # CondCompareConfig
            54933,  # TaskContext
            23733,  # ValueEvaluatorConfig
            13029,  # DialogueConditionRow
            15329,  # CheckPredicateAxis
            59977,  # RPG.Client.ConditionCheckerUtil
        }
    )

    types, methods, _fields = load_registry_facts(type_indexes)
    assert types[FIXPOINT_TYPE_INDEX]["full_name"] == FIXPOINT_TYPE_NAME
    methods_by_index = {m["method_index"]: m for m in methods}
    facts = {
        "primary_type": types[FIXPOINT_TYPE_INDEX],
        "all_methods": methods,
    }

    pe = load_pe()
    # Verify every referenced method exists before quick-scanning it.
    for cand in CANDIDATES + [
        {**c, "method_name": c["method"]} for c in SKIP_CANDIDATES
    ]:
        method = methods_by_index.get(cand["method_index"])
        if method is None:
            raise SystemExit(f"missing method identity for {cand}")
        if int(method.get("native_rva") or 0) != cand["native_rva"]:
            raise SystemExit(
                f"method {cand['method_index']} RVA mismatch: "
                f"{method.get('native_rva')} != {cand['native_rva']}"
            )
        if method.get("mapping_kind") != "DIRECT_NATIVE":
            raise SystemExit(
                f"method {cand['method_index']} is not DIRECT_NATIVE: "
                f"{method.get('mapping_kind')}"
            )
        validate_code_slot(pe, cand["method_index"], cand["native_rva"])

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
