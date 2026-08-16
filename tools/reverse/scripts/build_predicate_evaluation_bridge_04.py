#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Battle Semantic Predicate/Evaluator Bridge Batch 04.

PHASE A output:
  - data/semantics/4.4.54/predicate_evaluation_bridge_04.json
  - docs/battle_semantics/predicate_evaluation_bridge_04.md

Recovery strategy implemented here (not a full call graph):

  1. one-pass rel32/lea/mov/qword xref scan from the already-proven
     FixPoint comparator RVAs and DynamicValue conversion RVAs
     (``semantic_method_xrefs.py``);
  2. candidate filtering by caller type / body size / callee fan-out;
  3. bounded E4 native evidence for the ValueEvaluatorConfig operator leaves
     that inline Batch 02 / Batch 03 primitives.

Every ACCEPT is re-verified against normalized method identity, parameter
relations and the method code-table slot.  Shared evidence mechanics live in
``semantic_batch_evidence.py``; xref mechanics live in
``semantic_method_xrefs.py``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    NORMALIZED_BASE,
    bounded_body_metrics,
    disasm_window,
    load_manifest,
    load_parameter_refs,
    load_pe,
    load_registry_facts,
    validate_code_slot,
)

OUT_JSON = REPO / "data" / "semantics" / "4.4.54" / "predicate_evaluation_bridge_04.json"
OUT_MD = REPO / "docs" / "battle_semantics" / "predicate_evaluation_bridge_04.md"
XREF_GRAPH = REPO / "data" / "raw" / "4.4.54" / "predicate_caller_graph_04.json"
XREF_ANCHORS = REPO / "data" / "raw" / "4.4.54" / "predicate_anchor_caller_graph_04.json"

GAME_VERSION = "4.4.54"
BATCH_ID = "PREDICATE_EVALUATION_BRIDGE_04"
TYPE_INDEX = 23733
TYPE_NAME = "RPG.GameCore.ValueEvaluatorConfig"

# Accepted primitives.  `body_bytes` is the exact native window ending in the
# method's final `ret` (multiple conditional returns exist in three bodies; the
# bounded window is validated by `bounded_body_metrics`).
ACCEPTED = [
    {
        "method_index": 135379,
        "method_name": "BBNJCKPKPDN",
        "native_rva": 0x1D5AA260,
        "body_bytes": 0x49,
        "semantic_name": "EvaluatorSpecFromInt32",
        "primitive_id": "battle.ir.predicate.evaluator_spec_from_int32",
        "result": "evaluator_spec",
        "inputs": [("value", "int32")],
        "description": (
            "ValueEvaluatorConfig static operator: allocate the evaluator-spec "
            "operand class (runtime type_reference 23221, class-pointer global "
            "0x95E2B08) and store FixPointFromInt32(value) at object field "
            "[obj+0x20]"
        ),
        "abi": "x64 static: value=ecx (int32), object pointer return=rax",
        "field_reads": ["runtime operand class [obj+0x20] <- written"],
        "field_writes": ["runtime operand class +0x20 qword = fixpoint raw"],
        "branch_conditions": [
            "il2cpp object allocation returned null -> return null (allocation failure path)",
            "abs(sign_extend_32(value)) >= 0x40000000 -> EXTENDED FixPoint raw",
        ],
        "required_callees": [
            "0x3C736B0 il2cpp_object_new (runtime allocation infrastructure, UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "pseudocode": [
            "EvaluatorSpec EvaluatorSpecFromInt32(int32 value):",
            "    obj = il2cpp_object_new(class_global_0x95E2B08)",
            "    if obj == null: return null",
            "    raw = FixPointFromInt32(value)      # reuses battle.ir.value.fixpoint_from_int32",
            "    obj[+0x20] = raw                    # CONFIRMED single qword write",
            "    return obj",
        ],
        "default_path": "object allocation null -> return null; sandbox representation never allocates",
        "unknowns": [
            "runtime type name behind type_reference 23221 / class global 0x95E2B08",
            "object layout beyond the single proven +0x20 qword",
        ],
    },
    {
        "method_index": 135380,
        "method_name": "BBNJCKPKPDN",
        "native_rva": 0x1D5AA2B0,
        "body_bytes": 0x23,
        "semantic_name": "EvaluatorSpecFromFixPointRaw",
        "primitive_id": "battle.ir.predicate.evaluator_spec_from_fixpoint_raw",
        "result": "evaluator_spec",
        "inputs": [("value", "fixpoint_raw")],
        "description": (
            "ValueEvaluatorConfig static operator: allocate the same evaluator-spec "
            "operand class and store a raw FixPoint qword at [obj+0x20]"
        ),
        "abi": "x64 static: value=rcx (raw qword), object pointer return=rax",
        "field_reads": [],
        "field_writes": ["runtime operand class +0x20 qword = fixpoint raw"],
        "branch_conditions": [
            "il2cpp object allocation returned null -> return null (allocation failure path)",
        ],
        "required_callees": [
            "0x3C736B0 il2cpp_object_new (runtime allocation infrastructure, UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "pseudocode": [
            "EvaluatorSpec EvaluatorSpecFromFixPointRaw(fixpoint_raw value):",
            "    obj = il2cpp_object_new(class_global_0x95E2B08)",
            "    if obj == null: return null",
            "    obj[+0x20] = value                 # CONFIRMED single qword write",
            "    return obj",
        ],
        "default_path": "object allocation null -> return null; sandbox representation never allocates",
        "unknowns": [
            "runtime type name behind type_reference 23221 / class global 0x95E2B08",
            "object layout beyond the single proven +0x20 qword",
        ],
    },
    {
        "method_index": 135381,
        "method_name": "FEIIDFFOICL",
        "native_rva": 0x1D5AA2E0,
        "body_bytes": 0xE8,
        "semantic_name": "EvaluatorSpecFixPointEqualInt32",
        "primitive_id": "battle.ir.predicate.evaluator_spec_fixpoint_equal_int32",
        "result": "boolean",
        "inputs": [("evaluator_spec", "EvaluatorSpec"), ("rhs", "int32")],
        "description": (
            "ValueEvaluatorConfig static equality operator: read the evaluator-spec "
            "FixPoint raw at [obj+0x20], convert the int32 RHS with "
            "FixPointFromInt32 and return FixPointEqual of the two raw qwords"
        ),
        "abi": "x64 static: obj=rcx (type_reference 23221), rhs=edx (int32), bool return=al",
        "field_reads": ["runtime operand class +0x20 qword = FixPoint raw (CONFIRMED)"],
        "field_writes": [],
        "branch_conditions": [
            "obj == null -> return false (CONFIRMED default path)",
            "obj class is not class_global_0x95E2B08 nor subclass -> return false (CONFIRMED default path)",
            "FixPoint compare: same-mode standard -> raw signed comparison",
            "FixPoint compare: lhs EXTENDED, rhs canonical STANDARD/EXTENDED from int32 -> Batch 03 mixed-mode normalization",
            "FixPoint compare: lhs STANDARD, rhs canonical from int32 -> Batch 03 mixed-mode normalization",
        ],
        "required_callees": [],
        "pseudocode": [
            "bool EvaluatorSpecFixPointEqualInt32(EvaluatorSpec obj, int32 rhs):",
            "    if obj == null: return false",
            "    if not is_instance_of(obj, class_global_0x95E2B08): return false",
            "    lhs = obj[+0x20]",
            "    rhs_raw = FixPointFromInt32(rhs)",
            "    return FixPointEqual(lhs, rhs_raw)",
            "# lhs -> battle.ir.value.fixpoint_from_int32 -> battle.ir.compare.fixpoint_equal -> bool",
        ],
        "default_path": "null / wrong runtime type -> false",
        "unknowns": [
            "runtime type name behind type_reference 23221 / class global 0x95E2B08",
            "IL2CPP type-hierarchy walk internals (only the true/false outcome is used)",
        ],
    },
    {
        "method_index": 135383,
        "method_name": "FEIIDFFOICL",
        "native_rva": 0x1D606570,
        "body_bytes": 0xC5,
        "semantic_name": "EvaluatorSpecFixPointEqualRaw",
        "primitive_id": "battle.ir.predicate.evaluator_spec_fixpoint_equal_raw",
        "result": "boolean",
        "inputs": [("evaluator_spec", "EvaluatorSpec"), ("rhs", "fixpoint_raw")],
        "description": (
            "ValueEvaluatorConfig static equality operator: read the evaluator-spec "
            "FixPoint raw at [obj+0x20] and return FixPointEqual(obj raw, rhs raw)"
        ),
        "abi": "x64 static: obj=rcx (type_reference 23221), rhs=rdx (raw qword), bool return=al",
        "field_reads": ["runtime operand class +0x20 qword = FixPoint raw (CONFIRMED)"],
        "field_writes": [],
        "branch_conditions": [
            "obj == null -> return false (CONFIRMED default path)",
            "obj class is not class_global_0x95E2B08 nor subclass -> return false (CONFIRMED default path)",
            "then exactly the six-way Batch 03 FixPointEqual branch structure",
        ],
        "required_callees": [],
        "pseudocode": [
            "bool EvaluatorSpecFixPointEqualRaw(EvaluatorSpec obj, fixpoint_raw rhs):",
            "    if obj == null: return false",
            "    if not is_instance_of(obj, class_global_0x95E2B08): return false",
            "    lhs = obj[+0x20]",
            "    return FixPointEqual(lhs, rhs)",
            "# reuses battle.ir.compare.fixpoint_equal",
        ],
        "default_path": "null / wrong runtime type -> false",
        "unknowns": [
            "runtime type name behind type_reference 23221 / class global 0x95E2B08",
            "IL2CPP type-hierarchy walk internals (only the true/false outcome is used)",
        ],
    },
    {
        "method_index": 135384,
        "method_name": "DLDBLNNPHKE",
        "native_rva": 0x1D606640,
        "body_bytes": 0xC5,
        "semantic_name": "EvaluatorSpecFixPointNotEqualRaw",
        "primitive_id": "battle.ir.predicate.evaluator_spec_fixpoint_not_equal_raw",
        "result": "boolean",
        "inputs": [("evaluator_spec", "EvaluatorSpec"), ("rhs", "fixpoint_raw")],
        "description": (
            "ValueEvaluatorConfig static inequality operator: read the evaluator-spec "
            "FixPoint raw at [obj+0x20] and return FixPointNotEqual(obj raw, rhs raw); "
            "null / wrong runtime type returns true"
        ),
        "abi": "x64 static: obj=rcx (type_reference 23221), rhs=rdx (raw qword), bool return=al",
        "field_reads": ["runtime operand class +0x20 qword = FixPoint raw (CONFIRMED)"],
        "field_writes": [],
        "branch_conditions": [
            "obj == null -> return true (CONFIRMED default path)",
            "obj class is not class_global_0x95E2B08 nor subclass -> return true (CONFIRMED default path)",
            "then exactly the six-way Batch 03 FixPointNotEqual branch structure",
        ],
        "required_callees": [],
        "pseudocode": [
            "bool EvaluatorSpecFixPointNotEqualRaw(EvaluatorSpec obj, fixpoint_raw rhs):",
            "    if obj == null: return true",
            "    if not is_instance_of(obj, class_global_0x95E2B08): return true",
            "    lhs = obj[+0x20]",
            "    return FixPointNotEqual(lhs, rhs)",
            "# reuses battle.ir.compare.fixpoint_not_equal",
        ],
        "default_path": "null / wrong runtime type -> true (operator semantics, not an error)",
        "unknowns": [
            "runtime type name behind type_reference 23221 / class global 0x95E2B08",
            "IL2CPP type-hierarchy walk internals (only the true/false outcome is used)",
        ],
    },
]

CANDIDATE_TABLE = [
    {"method_index": 135379, "candidate": "RPG.GameCore.ValueEvaluatorConfig.BBNJCKPKPDN(int32)", "native_rva": "0x1D5AA260", "size": 73, "insn": 21, "branch": 1, "callee": 1, "classification": "ACCEPT_BRIDGE", "reason": "static int32 -> evaluator-spec object factory; inline FixPointFromInt32; single proven field write at +0x20"},
    {"method_index": 135380, "candidate": "RPG.GameCore.ValueEvaluatorConfig.BBNJCKPKPDN(FixPoint)", "native_rva": "0x1D5AA2B0", "size": 35, "insn": 11, "branch": 1, "callee": 1, "classification": "ACCEPT_BRIDGE", "reason": "static raw FixPoint -> evaluator-spec object factory; single proven field write at +0x20"},
    {"method_index": 135381, "candidate": "RPG.GameCore.ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, int32)", "native_rva": "0x1D5AA2E0", "size": 232, "insn": 71, "branch": 7, "callee": 0, "classification": "ACCEPT_PREDICATE", "reason": "complete leaf chain: object field read -> FixPointFromInt32 -> FixPointEqual -> bool; bounded native body"},
    {"method_index": 135383, "candidate": "RPG.GameCore.ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, FixPoint)", "native_rva": "0x1D606570", "size": 197, "insn": 63, "branch": 7, "callee": 0, "classification": "ACCEPT_PREDICATE", "reason": "object field read -> FixPointEqual(raw, raw) -> bool; exact Batch 03 compare core"},
    {"method_index": 135384, "candidate": "RPG.GameCore.ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, FixPoint)", "native_rva": "0x1D606640", "size": 197, "insn": 63, "branch": 7, "callee": 0, "classification": "ACCEPT_PREDICATE", "reason": "object field read -> FixPointNotEqual(raw, raw) -> bool; proven true default path for null/wrong type"},
    {"method_index": 135382, "candidate": "RPG.GameCore.ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, int32)", "native_rva": "0x1D606560", "size": 16, "insn": 5, "branch": 0, "callee": 1, "classification": "SKIP_WRAPPER", "reason": "calls 135381 then XORs the bool; no independent comparison semantic"},
    {"method_index": 505866, "candidate": "RPG.GameCore.TaskContext.Evaluate(bool)", "native_rva": "0xE6F0A60", "size": 347, "insn": 108, "branch": 14, "callee": 11, "classification": "SKIP_CONTEXT_HEAVY", "reason": "string-keyed evaluator dictionary dispatch; call graph exceeds bounded budget"},
    {"method_index": 505884, "candidate": "RPG.GameCore.TaskContext.EvaluateOrDefault(bool)", "native_rva": "0xE6F24D0", "size": 93, "insn": 33, "branch": 3, "callee": 2, "classification": "SKIP_WRAPPER", "reason": "null -> false, otherwise tailcall heavy Evaluate(bool)"},
    {"method_index": 507741, "candidate": "INEOLMDOFMB.Evaluate", "native_rva": "0x16117690", "size": "~2180 observed window", "insn": "~400 observed window", "branch": "~90 observed window", "callee": "~25 observed window", "classification": "SKIP_CONTEXT_HEAVY", "reason": "direct FixPointGreaterThan caller but body walks battle-world/ability/entity object graph"},
    {"method_index": 531579, "candidate": "LKJEOBHCOID.Evaluate", "native_rva": "0xB8AE270", "size": "~2200 observed window", "insn": "~300 observed window", "branch": "~60 observed window", "callee": "~20 observed window", "classification": "SKIP_CONTEXT_HEAVY", "reason": "direct FixPointGreaterThan caller but allocates closure context and walks ability/game-world graph"},
    {"method_index": 500558, "candidate": "KPCACPAEMGK.ILOHHJDPDBE", "native_rva": "0xB6D6E00", "size": "~2000 observed window", "insn": "~300 observed window", "branch": "~40 observed window", "callee": "~15 observed window", "classification": "SKIP_CONTEXT_HEAVY", "reason": "FixPoint comparison fan-in but multi-callee math body"},
    {"method_index": 500572, "candidate": "DHGEHJGMCLB.ILOHHJDPDBE", "native_rva": "0xE88F360", "size": "~3600 observed window", "insn": "~500 observed window", "branch": "~70 observed window", "callee": "~20 observed window", "classification": "SKIP_CONTEXT_HEAVY", "reason": "same fan-in family; multi-KB body with FixPoint math and context reads"},
    {"method_index": 617796, "candidate": "RPG.Client.SpaceZooUtils.IsMatch", "native_rva": "0xE0884E0", "size": "~800 observed window", "insn": "~150 observed window", "branch": "~20 observed window", "callee": "~8 observed window", "classification": "SKIP_NON_BATTLE", "reason": "only direct caller of DynamicValueToInt32; client Space Zoo matching, not battle"},
    {"method_index": 133350, "candidate": "RPG.GameCore.ByCompareDynamicValue..ctor", "native_rva": "0x1CE2F1C0", "size": 57, "insn": 15, "branch": 1, "callee": 2, "classification": "SKIP_SERIALIZATION", "reason": "serializer family confirmed in Batch 03; no runtime predicate method on the type"},
    {"method_index": 133355, "candidate": "RPG.GameCore.ByCompareValue..ctor", "native_rva": "0x1CE7C770", "size": 9, "insn": 3, "branch": 0, "callee": 0, "classification": "SKIP_SERIALIZATION", "reason": "serializer family confirmed in Batch 03"},
    {"method_index": 125477, "candidate": "RPG.GameCore.ByDynamicValueDefined..ctor", "native_rva": "0x1CE899F0", "size": 5, "insn": 2, "branch": 0, "callee": 0, "classification": "SKIP_SERIALIZATION", "reason": "serializer family confirmed in Batch 03"},
    {"method_index": 132841, "candidate": "RPG.GameCore.PredicateConfig..ctor", "native_rva": "0x1D2CA150", "size": 510, "insn": 124, "branch": 20, "callee": 9, "classification": "SKIP_SERIALIZATION", "reason": "config runtime type with only ctor/wrapper/impl serializer methods"},
    {"method_index": 106308, "candidate": "RPG.GameCore.CondCompareConfig..ctor", "native_rva": "0x1CF67770", "size": 8, "insn": 2, "branch": 0, "callee": 0, "classification": "SKIP_SERIALIZATION", "reason": "config runtime type with only ctor/wrapper/impl serializer methods"},
    {"method_index": 102771, "candidate": "RPG.GameCore.CheckPredicateAxis..ctor", "native_rva": "0x1CF125B0", "size": 1, "insn": 1, "branch": 0, "callee": 0, "classification": "SKIP_SERIALIZATION", "reason": "serializer-shaped runtime type; no leaf predicate body"},
]


def _load_xref_summary() -> dict:
    summary = {"comparison_targets": {}, "conversion_targets": {}}
    try:
        data = json.loads(XREF_GRAPH.read_text(encoding="utf-8"))
        for target in data["targets"]:
            summary["comparison_targets"][target["native_rva"]] = target["ref_counts"]
            summary["conversion_targets"][target["native_rva"]] = target["ref_counts"]
    except OSError:
        summary["note"] = "xref graph file missing"
    try:
        anchors = json.loads(XREF_ANCHORS.read_text(encoding="utf-8"))
        summary["anchor_targets"] = {
            target["native_rva"]: target["ref_counts"] for target in anchors["targets"]
        }
    except OSError:
        pass
    return summary


def main() -> int:
    pe = load_pe()
    manifest = load_manifest()
    facts = load_registry_facts({TYPE_INDEX})
    methods = {m["method_index"]: m for m in facts[1]}
    params = load_parameter_refs({c["method_index"] for c in ACCEPTED})
    for mi in ACCEPTED:
        method = methods[mi["method_index"]]
        assert method["declaring_type_index"] == TYPE_INDEX, method
        assert method["parameter_count"] == len(params[mi["method_index"]]), method

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primitives = []
    for cand in ACCEPTED:
        method = methods[cand["method_index"]]
        rva = cand["native_rva"]
        raw, decoded = disasm_window(pe, rva, cand["body_bytes"])
        metrics = bounded_body_metrics(raw, decoded, rva, cand["body_bytes"])
        slot = validate_code_slot(pe, cand["method_index"], rva)
        body_sha = hashlib.sha256(raw).hexdigest()
        disasm_lines = []
        for ins in metrics["body_insns"]:
            comment = ins["comment"]
            disasm_lines.append(
                f"{ins['rva']:08X}  {bytes(ins['bytes']).hex(' '):<24}  "
                f"{ins['mnemonic']:8} {ins['op_str']}{comment}"
            )
        primitive = {
            "primitive_id": cand["primitive_id"],
            "semantic_name": cand["semantic_name"],
            "description": cand["description"],
            "inputs": [{"name": n, "type": t} for n, t in cand["inputs"]],
            "context_reads": [name for name, _ in cand["inputs"]],
            "context_writes": [],
            "result": cand["result"],
            "determinism": "DETERMINISTIC",
            "evidence_level": "E4_STATIC_MACHINE_CODE",
            "source_runtime_type": TYPE_NAME,
            "source_method": cand["method_name"],
            "source_method_index": cand["method_index"],
            "source_native_rva": f"0x{rva:X}",
            "native_body_hash": body_sha,
            "source_identity": {
                "method_index": cand["method_index"],
                "declaring_type_index": TYPE_INDEX,
                "method_name": method["name"],
                "parameter_count": method["parameter_count"],
                "return_type_reference": method["return_type_reference"],
                "parameter_relations": params[cand["method_index"]],
                "mapping_kind": method["mapping_kind"],
                "method_flags_0x0E": method["flags_0x0E_decoded"],
                "method_kind_note": (
                    "flags 0x0E == 16293 matches FixPoint static operators "
                    "op_Equality / op_Implicit; ABI is static (no this)"
                ),
            },
            "native_evidence": {
                "body_rva": f"0x{rva:X}",
                "body_length_bytes": metrics["body_length"],
                "body_sha256": body_sha,
                "code_table_slot_va": f"0x{slot:X}",
                "code_table_slot_index": cand["method_index"],
                "image_base": f"0x{pe.image_base:X}",
                "instruction_count": metrics["instruction_count"],
                "conditional_branch_count": metrics["branch_count"],
                "direct_call_count": metrics["call_count"],
                "direct_jump_count": metrics["jmp_count"],
                "abi": cand["abi"],
                "disassembly": disasm_lines,
            },
            "object_fields": {
                "field_reads": cand["field_reads"],
                "field_writes": cand["field_writes"],
                "+0x20": {
                    "width_bytes": 8,
                    "role": "FixPoint raw qword operand",
                    "evidence": (
                        "135379/135380 write this qword; 135381/135383/135384 "
                        "read it and feed it to the FixPoint compare core"
                    ),
                    "evidence_level": "CONFIRMED",
                },
                "runtime_operand_class": {
                    "type_reference": 23221,
                    "class_pointer_global_rva": "0x95E2B08",
                    "identity": "UNKNOWN_NAME",
                    "evidence": (
                        "static ABI from flags + parameter relation; class "
                        "allocation and is-instance check both use global "
                        "0x95E2B08"
                    ),
                    "evidence_level": "SUPPORTED",
                },
            },
            "branch_conditions": cand["branch_conditions"],
            "required_callees": cand["required_callees"],
            "pseudocode": cand["pseudocode"],
            "default_or_error_path": cand["default_path"],
            "unknowns": cand["unknowns"],
        }
        primitives.append(primitive)

    artifact = {
        "schema": "battle_semantics_batch/1",
        "game_version": GAME_VERSION,
        "batch_id": BATCH_ID,
        "generated_at": now,
        "evidence_level": "E4_STATIC_MACHINE_CODE",
        "gameassembly": {
            "path": manifest["GameAssembly"]["path"],
            "sha256": manifest["GameAssembly"].get("sha256"),
        },
        "primitives": primitives,
        "composition_chains": [
            {
                "chain_id": "evaluator_spec_int32_equal_chain",
                "runtime_evidence": "ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, int32)",
                "steps": [
                    {
                        "step": 1,
                        "primitive_id": "battle.ir.predicate.evaluator_spec_from_int32",
                        "role": "runtime object construction (native allocation + [obj+0x20] store)",
                    },
                    {
                        "step": 2,
                        "primitive_id": "battle.ir.predicate.evaluator_spec_fixpoint_equal_int32",
                        "role": "predicate leaf: [obj+0x20] read -> inline FixPointFromInt32 -> inline FixPointEqual -> bool",
                    },
                ],
                "inline_reuse": [
                    "battle.ir.value.fixpoint_from_int32",
                    "battle.ir.compare.fixpoint_equal",
                ],
                "note": (
                    "The leaf body does not call comparator RVAs; it inlines the "
                    "proven Batch 03 encoding/compare dataflow. Sandbox implementation "
                    "calls the shared Batch 03 helpers."
                ),
            },
            {
                "chain_id": "evaluator_spec_raw_equal_chain",
                "runtime_evidence": "ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, FixPoint)",
                "steps": [
                    {
                        "step": 1,
                        "primitive_id": "battle.ir.predicate.evaluator_spec_from_fixpoint_raw",
                        "role": "runtime object construction with a raw FixPoint qword",
                    },
                    {
                        "step": 2,
                        "primitive_id": "battle.ir.predicate.evaluator_spec_fixpoint_equal_raw",
                        "role": "predicate leaf: [obj+0x20] read -> FixPointEqual -> bool",
                    },
                ],
                "inline_reuse": ["battle.ir.compare.fixpoint_equal"],
            },
            {
                "chain_id": "evaluator_spec_raw_not_equal_chain",
                "runtime_evidence": "ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, FixPoint)",
                "steps": [
                    {
                        "step": 1,
                        "primitive_id": "battle.ir.predicate.evaluator_spec_from_fixpoint_raw",
                        "role": "runtime object construction with a raw FixPoint qword",
                    },
                    {
                        "step": 2,
                        "primitive_id": "battle.ir.predicate.evaluator_spec_fixpoint_not_equal_raw",
                        "role": "predicate leaf: [obj+0x20] read -> FixPointNotEqual -> bool",
                    },
                ],
                "inline_reuse": ["battle.ir.compare.fixpoint_not_equal"],
            },
        ],
        "caller_discovery": _load_xref_summary(),
        "candidate_table": CANDIDATE_TABLE,
        "deferred_candidates": [
            {
                "method_index": 505866,
                "runtime_type": "RPG.GameCore.TaskContext",
                "method": "Evaluate(bool)",
                "native_rva": "0xE6F0A60",
                "classification": "SKIP_CONTEXT_HEAVY",
                "reason": "string-keyed evaluator dictionary dispatcher; not a leaf",
            },
            {
                "method_index": 500558,
                "runtime_type": "KPCACPAEMGK",
                "method": "ILOHHJDPDBE",
                "native_rva": "0xB6D6E00",
                "classification": "SKIP_CONTEXT_HEAVY",
            },
            {
                "method_index": 500572,
                "runtime_type": "DHGEHJGMCLB",
                "method": "ILOHHJDPDBE",
                "native_rva": "0xE88F360",
                "classification": "SKIP_CONTEXT_HEAVY",
            },
            {
                "method_index": 507741,
                "runtime_type": "INEOLMDOFMB",
                "method": "Evaluate",
                "native_rva": "0x16117690",
                "classification": "SKIP_CONTEXT_HEAVY",
            },
            {
                "method_index": 531579,
                "runtime_type": "LKJEOBHCOID",
                "method": "Evaluate",
                "native_rva": "0xB8AE270",
                "classification": "SKIP_CONTEXT_HEAVY",
            },
        ],
        "semantic_dependencies": [
            {
                "primitive_id": "battle.ir.value.fixpoint_from_int32",
                "status": "SATISFIED",
                "artifact": "fixpoint_comparison_batch_03.json",
            },
            {
                "primitive_id": "battle.ir.compare.fixpoint_equal",
                "status": "SATISFIED",
                "artifact": "fixpoint_comparison_batch_03.json",
            },
            {
                "primitive_id": "battle.ir.compare.fixpoint_not_equal",
                "status": "SATISFIED",
                "artifact": "fixpoint_comparison_batch_03.json",
            },
            {
                "primitive_id": "TaskContext.Evaluate(bool) predicate dispatcher",
                "status": "SEMANTIC_DEPENDENCY_REQUIRED",
                "note": "dispatcher structure observed, not recovered; leaf predicates below it are recovered in this batch",
            },
        ],
        "unknowns": [
            "runtime type name behind type_reference 23221 / class-pointer global 0x95E2B08",
            "object layout beyond the single proven +0x20 qword",
            "IL2CPP object allocation / type-hierarchy helper internals (error/default paths only)",
            "no E5 client-side runtime observation",
            "raw rel32 xref scan can contain false positives from byte-pattern overlap; only curated callers are reported",
            "DynamicValue conversion methods have no direct RPG.GameCore caller in this scan; conversion reach is virtual/indirect",
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)

    _write_markdown(artifact, primitives)
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print("sha256", hashlib.sha256(OUT_JSON.read_bytes()).hexdigest())
    return 0


def _write_markdown(artifact: dict, primitives: list[dict]) -> None:
    lines = [
        "# Battle Semantic Predicate / Evaluator Bridge Batch 04",
        "",
        f"> Final status: **`BATTLE_SEMANTIC = PREDICATE_EVALUATION_BRIDGE_04_PROOF`**",
        f"> Game version: `{artifact['game_version']}`",
        "> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)",
        "> Artifact schema: `battle_semantics_batch/1`",
        "",
        "## 1. Scope",
        "",
        "This batch closes the predicate/evaluator execution bridge on a bounded",
        "set of real `RPG.GameCore.ValueEvaluatorConfig` native leaves.  It does",
        "**not** recover the full `TaskContext` predicate dispatcher, target",
        "selection, modifiers or damage.",
        "",
        "Recovered composition shape:",
        "",
        "```text",
        "evaluator-spec runtime object (type_reference 23221)",
        "  -> object field [obj+0x20] = FixPoint raw qword        (CONFIRMED)",
        "  -> int32 RHS -> FixPointFromInt32                       (Batch 03 reuse)",
        "  -> FixPointEqual / FixPointNotEqual                     (Batch 03 reuse)",
        "  -> bool",
        "```",
        "",
        "## 2. Candidate discovery (callers, not names)",
        "",
        "Raw single-pass rel32 scan counts for the already-proven cores:",
        "",
        "| Target core | RVAs | rel32 direct-call sites |",
        "|---|---|---:|",
        "| FixPoint == / != / > / < / >= / <= | 0x1D661340 / 0x1D664520 / 0x1D6645B0 / 0x1D6646D0 / 0x1D660C50 / 0x1D664760 | 102 / 29 / 18 / 13 / 16 / 4 |",
        "| DynamicValue to Int32 / UInt32 / Int64 / Float32 / Float64 / Bool / TypeTag / IsNull | Batch 02 RVAs | 2 / 21 / 0 / 1 / 0 / 0 / 0 / 0 |",
        "",
        "The most relevant callers of comparison operators are heavy gameplay",
        "components (TurnBasedAbilityComponent.ModifyProperty, SkillCharacterComponent,",
        "AbilityStatic.TargetDamageHP) or heavy Evaluate bodies; they were",
        "SKIP_CONTEXT_HEAVY after one bounded look.  DynamicValue conversions have",
        "no direct RPG.GameCore caller in this static scan, so the conversion->comparison",
        "bridge is proven inside ValueEvaluatorConfig instead of a conversion caller.",
        "",
        "### First-round report (before PHASE A acceptance)",
        "",
        "1. Commits confirmed: `e1b2668`, `11a6019`, `c66451f`, `a2ea2d1`.",
        "2. Tracked state was clean at session start; only Batch 04 files are added",
        "   by this session, and pre-existing untracked files are left untouched.",
        "3. FixPoint comparator direct rel32 caller counts: 102 / 29 / 18 / 13 / 16 / 4",
        "   for == / != / > / < / >= / <= (raw one-pass scan).",
        "4. DynamicValue conversion direct rel32 caller counts: 2 / 21 / 0 / 1 / 0 / 0 / 0 / 0",
        "   for ToInt32 / ToUInt32 / ToInt64 / ToFloat32 / ToFloat64 / ToBool / TypeTag / IsNull.",
        "5. Intersection with `ValueEvaluatorConfig` / `TaskContext`: ValueEvaluatorConfig",
        "   leaves inline the Batch 03 compare core rather than calling its RVAs;",
        "   `TaskContext.Evaluate(bool)` remains a dictionary dispatcher with no",
        "   recoverable leaf at depth 1.  No `RPG.GameCore` direct caller of the",
        "   DynamicValue conversions was found in this scan.",
        "6. Plausible candidates: the 19 rows in the candidate table below.",
        "7. Shortlist: 5 accepted methods (`135379`, `135380`, `135381`, `135383`, `135384`).",
        "8. Shortlist details: see the accepted-primitive sections; every entry has",
        "   type / method / method_index / RVA / size / branch / callee / caller path.",
        "9. Most likely to close the real predicate chain: `135381`",
        "   (`FEIIDFFOICL(type_ref_23221, int32)`), because one bounded native body",
        "   proves object-field read -> FixPointFromInt32 -> FixPointEqual -> bool.",
        "10. Explicitly skipped as heavy: `TaskContext.Evaluate(bool)`",
        "    (`SKIP_CONTEXT_HEAVY`), `INEOLMDOFMB.Evaluate`, `LKJEOBHCOID.Evaluate`,",
        "    `KPCACPAEMGK.ILOHHJDPDBE`, `DHGEHJGMCLB.ILOHHJDPDBE`, and",
        "    `RPG.Client.SpaceZooUtils.IsMatch` (`SKIP_NON_BATTLE`).",
        "",
        "## 3. Candidate table",
        "",
        "| method_index | candidate | native_rva | size(B) | insn | branch | callee | classification |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for c in artifact["candidate_table"]:
        lines.append(
            f"| {c['method_index']} | {c['candidate']} | {c['native_rva']} | "
            f"{c['size']} | {c['insn']} | {c['branch']} | {c['callee']} | "
            f"{c['classification']} |"
        )
    lines += [
        "",
        "Shortlist (5 accepted): `135379`, `135380`, `135381`, `135383`, `135384`.",
        "`135381` is the most important chain-closing leaf: one bounded native body",
        "proves `object field -> value conversion -> comparison -> bool`.",
        "",
        "## 4. Runtime type / method identity",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Runtime type | `{TYPE_NAME}` (type_index `{TYPE_INDEX}`) |",
        "| Operand type | runtime `type_reference 23221`, name UNKNOWN, class-pointer global RVA `0x95E2B08` |",
        "| Static ABI evidence | method flags 0x0E == `16293`, identical to `FixPoint.op_Equality` / `op_Implicit` static operators |",
        "",
        "Field map proven by native bodies:",
        "",
        "| Offset | Width | Role | Evidence |",
        "|---|---:|---|---|",
        "| +0x20 | 8 | FixPoint raw qword operand | CONFIRMED |",
        "| runtime class identity | - | type_reference 23221 / class global 0x95E2B08 | SUPPORTED |",
        "| other object fields | - | not read by accepted bodies | UNKNOWN |",
        "",
        "## 5. Accepted primitives",
        "",
    ]
    for p in primitives:
        ne = p["native_evidence"]
        lines += [
            f"### {p['semantic_name']} (`{p['source_method']}`, method_index {p['source_method_index']})",
            "",
            f"- Primitive: `{p['primitive_id']}`; result `{p['result']}`",
            f"- RVA `{p['source_native_rva']}`; body {ne['body_length_bytes']} bytes / "
            f"{ne['instruction_count']} instructions / {ne['conditional_branch_count']} "
            f"conditional branches / {ne['direct_call_count']} calls",
            f"- Body sha256 `{ne['body_sha256']}`",
            "- Field reads:",
        ]
        if p["object_fields"]["field_reads"]:
            for fr in p["object_fields"]["field_reads"]:
                lines.append(f"  - {fr}")
        else:
            lines.append("  - none")
        lines += [
            "- Field writes:",
        ]
        for fw in p["object_fields"]["field_writes"]:
            lines.append(f"  - {fw}")
        lines += [
            "- Branch conditions:",
        ]
        for bc in p["branch_conditions"]:
            lines.append(f"  - {bc}")
        lines += [
            "- Default / error path:",
            f"  - {p['default_or_error_path']}",
            "- Required callees:",
        ]
        for callee in p["required_callees"]:
            lines.append(f"  - {callee}")
        lines += [
            "- Pseudocode:",
            "```",
            *p["pseudocode"],
            "```",
            "- Native evidence (first instructions + body hash anchor):",
            "```",
            *ne["disassembly"],
            "```",
            "",
        ]
    lines += [
        "## 6. Composition chains (machine-readable in the artifact)",
        "",
    ]
    for chain in artifact["composition_chains"]:
        lines += [
            f"### {chain['chain_id']}",
            "",
            f"Runtime evidence: `{chain['runtime_evidence']}`",
            "",
            "```text",
        ]
        for step in chain["steps"]:
            lines.append(f"  {step['role']}")
            lines.append(f"    {step['primitive_id']}")
        lines += ["```", ""]
    lines += [
        "## 7. Dependencies / unknowns",
        "",
        "- `battle.ir.value.fixpoint_from_int32`: SATISFIED (Batch 03)",
        "- `battle.ir.compare.fixpoint_equal` / `fixpoint_not_equal`: SATISFIED (Batch 03)",
        "- `TaskContext.Evaluate(bool)` dispatcher: SEMANTIC_DEPENDENCY_REQUIRED",
        "- operand runtime type name (`type_reference 23221`) remains UNKNOWN_NAME",
        "- no E5 runtime observation",
        "",
        "Machine-readable companion:",
        "`data/semantics/4.4.54/predicate_evaluation_bridge_04.json`.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
