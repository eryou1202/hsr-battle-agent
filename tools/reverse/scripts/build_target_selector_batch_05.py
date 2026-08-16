#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Target Selector Batch 05 semantic artifact (4.4.54).

Recovered runtime shape (see docs/battle_semantics/target_selector_batch_05.md):

    TargetFetch*/TargetMap*/TargetFilter*/TargetSort* serialized config
      -> generated TargetEvaluatorImpl`1 concrete class (type-ref bridge)
      -> Evaluate / Transform
      -> TaskContext / AbilityStatic helper
      -> ordered entity target list (list object: +0x10 items array,
         +0x18 count, +0x1c version, items at [array + idx*8 + 0x20])

This script only assembles evidence already discovered in this session.  It
reuses semantic_batch_evidence / semantic_method_xrefs and the companion
build_target_config_runtime_bridge.py output; it does not re-recover metadata.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    NORMALIZED_BASE,
    build_native_evidence,
    disasm_window,
    iter_records,
    load_manifest,
    load_parameter_refs,
    load_pe,
    line_for,
)
from semantic_method_xrefs import load_method_rva_index  # noqa: E402

REPO = HERE.parents[2]
BRIDGE_PATH = REPO / "data" / "raw" / "4.4.54" / "target_config_runtime_bridge_05.json"
OUT_PATH = (
    REPO / "data" / "semantics" / "4.4.54" / "target_selector_batch_05.json"
)

GAME_VERSION = "4.4.54"
BATCH_ID = "TARGET_SELECTOR_BATCH_05"
SCHEMA = "battle_semantics_batch/1"
E4 = "E4_STATIC_MACHINE_CODE"


# method_index -> metadata used by every accepted primitive
PRIMITIVE_PLANS = [
    {
        "primitive_id": "battle.ir.target.context_task_action_target",
        "semantic_name": "TaskContextTaskActionTarget",
        "description": (
            "TaskContext.get_TaskActionTarget: return the current task-action "
            "target entity pointer stored at TaskContext [+0x48]; no validation "
            "and no fallback, a null field returns null."
        ),
        "inputs": [],
        "context_reads": ["task_action_target"],
        "result": "EntityRef",
        "source_runtime_type": "RPG.GameCore.TaskContext",
        "source_method": "get_TaskActionTarget",
        "method_index": 505847,
        "pseudocode": [
            "EntityRef | null TaskContextTaskActionTarget(TaskContext this):",
            "    return this[+0x48]          # raw entity pointer; null preserved",
        ],
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing context -> native null-instance throw; null stored field -> returns null",
        "ordering_behavior": "single result; no ordering",
        "duplicate_behavior": "single result; no duplication",
        "multiplicity": "single",
        "entity_identity_level": "entity pointer (runtime type_reference 202024)",
    },
    {
        "primitive_id": "battle.ir.target.context_owner_entity",
        "semantic_name": "TaskContextOwnerEntity",
        "description": (
            "TaskContext.get_OwnerEntity: return the owner entity pointer stored "
            "at TaskContext [+0x70]; no validation and no fallback, a null field "
            "returns null."
        ),
        "inputs": [],
        "context_reads": ["owner_entity"],
        "result": "EntityRef",
        "source_runtime_type": "RPG.GameCore.TaskContext",
        "source_method": "get_OwnerEntity",
        "method_index": 505843,
        "pseudocode": [
            "EntityRef | null TaskContextOwnerEntity(TaskContext this):",
            "    return this[+0x70]          # raw entity pointer; null preserved",
        ],
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing context -> native null-instance throw; null stored field -> returns null",
        "ordering_behavior": "single result; no ordering",
        "duplicate_behavior": "single result; no duplication",
        "multiplicity": "single",
        "entity_identity_level": "entity pointer (runtime type_reference 202024)",
    },
    {
        "primitive_id": "battle.ir.target.select_task_action_target",
        "semantic_name": "TargetFetchTaskActionTargetEvaluate",
        "description": (
            "Generated evaluator for RPG.GameCore.TargetFetchTaskActionTarget: "
            "reset the target list, read TaskContext [+0x48] (task-action target "
            "entity), and append it to the list only when the field is non-null. "
            "Order is append order; null field produces an empty list."
        ),
        "inputs": [],
        "context_reads": ["task_action_target"],
        "result": "TargetSet",
        "source_runtime_type": "NDIJLODKLJB",
        "source_method": "Evaluate",
        "method_index": 538090,
        "pseudocode": [
            "void TargetFetchTaskActionTargetEvaluate(this, TaskContext ctx, TargetList list):",
            "    list.Clear()                       # [list+0x18]=0, [list+0x1c]++",
            "    entity = ctx[+0x48]",
            "    if entity != null:",
            "        list.append(entity)             # [items + count*8 + 0x20] = entity; count++",
        ],
        "branch_conditions": [
            "ctx == null -> throw (IL2CPP null check)",
            "list == null -> throw (IL2CPP null check)",
            "TaskContext [+0x48] == null -> no append (result is empty list)",
        ],
        "required_callees": [
            "0x19BB0D610 (list clear helper; UNKNOWN_HELPER_NOT_NEEDED)",
            "0x197DFBE60 (list grow-and-append helper; UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "null task-action-target field -> empty list (CONFIRMED); null ctx/list -> throw",
        "ordering_behavior": "append order; single append at tail",
        "duplicate_behavior": "no deduplication; a second evaluation on a cleared list appends again",
        "multiplicity": "single (0 or 1 element list)",
        "entity_identity_level": "entity pointer appended to target list (runtime type_reference 202024)",
    },
    {
        "primitive_id": "battle.ir.target.select_caster",
        "semantic_name": "TargetFetchCasterEvaluate",
        "description": (
            "Generated evaluator for RPG.GameCore.TargetFetchCaster: reset the "
            "target list, resolve the current caster entity with the duplicated "
            "TaskContext.get_CasterEntity helper at 0x18B429790, then append the "
            "result unconditionally. A null caster result is appended as a null "
            "list element (count still increments)."
        ),
        "inputs": [],
        "context_reads": ["caster_entity"],
        "result": "TargetSet",
        "source_runtime_type": "KCFPGFDHIEO",
        "source_method": "Evaluate",
        "method_index": 538052,
        "pseudocode": [
            "void TargetFetchCasterEvaluate(this, TaskContext ctx, TargetList list):",
            "    list.Clear()",
            "    entity = TaskContext.get_CasterEntity(ctx)   # duplicate entry 0x18B429790",
            "    list.append(entity)                          # appended even when null",
        ],
        "branch_conditions": [
            "ctx == null -> throw",
            "list == null -> throw",
            "caster helper: owner-ability-instance null -> fallback vtable slot +0x120 path",
            "caster helper: nested entity reads null -> throw",
        ],
        "required_callees": [
            "0x18B429790 (duplicate of TaskContext.get_CasterEntity; SEMANTIC_DEPENDENCY_CASTED_CANONICAL)",
            "0x19BB0D610 (list clear helper; UNKNOWN_HELPER_NOT_NEEDED)",
            "0x197DFBE60 (list grow-and-append helper; UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "null caster result -> appended as null list element (CONFIRMED, count++ with null); null ctx/list -> throw",
        "ordering_behavior": "append order; single append at tail",
        "duplicate_behavior": "no deduplication",
        "multiplicity": "single (always 1 element, possibly null)",
        "entity_identity_level": "entity pointer appended to target list",
    },
    {
        "primitive_id": "battle.ir.target.select_none",
        "semantic_name": "TargetFetchNoneEvaluate",
        "description": (
            "Generated evaluator for RPG.GameCore.TargetFetchNone: reset the "
            "target list and append nothing. Result is always an empty ordered "
            "target list; no TaskContext field is read."
        ),
        "inputs": [],
        "context_reads": [],
        "result": "TargetSet",
        "source_runtime_type": "NAOFIGCCGPF",
        "source_method": "Evaluate",
        "method_index": 538056,
        "pseudocode": [
            "void TargetFetchNoneEvaluate(this, TaskContext ctx, TargetList list):",
            "    list.Clear()                       # no reads of ctx fields",
        ],
        "branch_conditions": [
            "list == null -> throw",
            "list count > 0 -> list clear helper (0x19BB0D610); otherwise direct return",
        ],
        "required_callees": [
            "0x19BB0D610 (list clear helper, only when previous count > 0; UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "null list -> throw; otherwise empty list",
        "ordering_behavior": "empty result; trivially ordered",
        "duplicate_behavior": "empty result",
        "multiplicity": "empty set",
        "entity_identity_level": "no entity produced",
    },
    {
        "primitive_id": "battle.ir.target.collapse_single_or_null",
        "semantic_name": "GetTaskSingleTarget",
        "description": (
            "AbilityStatic.GetTaskSingleTarget(TaskContext, target config, mask): "
            "allocate a target list, run TaskContext.EvaluateTarget into it, then "
            "return the first list element; empty list returns null.  This is the "
            "named single-target collapse used by the runtime (>=1 -> first)."
        ),
        "inputs": [{"name": "targets", "type": "TargetSet"}],
        "context_reads": ["targets"],
        "result": "EntityRef",
        "source_runtime_type": "RPG.GameCore.AbilityStatic",
        "source_method": "GetTaskSingleTarget",
        "method_index": 504364,
        "pseudocode": [
            "EntityRef | null GetTaskSingleTarget(TaskContext ctx, TargetConfig cfg, mask):",
            "    list = new TargetList()",
            "    TaskContext.EvaluateTarget(ctx, cfg, list, mask)",
            "    if list.count == 0:",
            "        release(list); return null",
            "    entity = list.items[0]",
            "    release(list); return entity",
        ],
        "branch_conditions": [
            "ctx == null -> throw",
            "list allocation failed -> throw",
            "list.count == 0 -> return null",
            "items array null/empty while count > 0 -> throw (inconsistent list state)",
        ],
        "required_callees": [
            "0x18E6F1530 TaskContext.EvaluateTarget (SEMANTIC_DEPENDENCY_REQUIRED)",
            "0x18B42A0C0 target-list allocator (UNKNOWN_HELPER_NOT_NEEDED)",
            "0x18B429F50 target-list release (UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "empty target list -> null; null ctx/list -> throw",
        "ordering_behavior": "returns first element; list order preserved by EvaluateTarget",
        "duplicate_behavior": "duplicates are ignored by first-element projection (not deduplicated upstream)",
        "multiplicity": "single collapse from ordered list",
        "entity_identity_level": "entity pointer returned (runtime type_reference 202024)",
    },
    {
        "primitive_id": "battle.ir.target.collapse_required_single_or_null",
        "semantic_name": "TaskContextEvaluateSingleTarget",
        "description": (
            "TaskContext.EvaluateSingleTarget(TaskContext, target config, mask): "
            "run EvaluateTarget into a fresh list and return the only element. "
            "0 or >=2 elements log an error and return null after releasing the "
            "list.  This is the strict single-target collapse entrypoint."
        ),
        "inputs": [{"name": "targets", "type": "TargetSet"}],
        "context_reads": ["targets"],
        "result": "EntityRef",
        "source_runtime_type": "RPG.GameCore.TaskContext",
        "source_method": "EvaluateSingleTarget",
        "method_index": 505875,
        "pseudocode": [
            "EntityRef | null TaskContextEvaluateSingleTarget(TaskContext ctx, TargetConfig cfg, mask):",
            "    list = new TargetList()",
            "    TaskContext.EvaluateTarget(ctx, cfg, list, mask)",
            "    if list.count == 0: log_error; release(list); return null",
            "    if list.count >= 2: log_error; release(list); return null",
            "    entity = list.items[0]",
            "    release(list); return entity",
        ],
        "branch_conditions": [
            "cfg == null -> log error path and return null (via error logger)",
            "list allocation failed -> throw",
            "list.count == 0 -> log error -> null",
            "list.count >= 2 -> log error -> null",
            "items array null/empty while count == 1 -> throw (inconsistent list state)",
        ],
        "required_callees": [
            "0x18E6F1530 TaskContext.EvaluateTarget (SEMANTIC_DEPENDENCY_REQUIRED)",
            "0x18B42A0C0 target-list allocator (UNKNOWN_HELPER_NOT_NEEDED)",
            "0x18B42A1C0 target-list release (UNKNOWN_HELPER_NOT_NEEDED)",
            "0x19D701700 error logger (error paths only; UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "0 or >=2 results -> null (with error log); null config -> error log and null",
        "ordering_behavior": "requires exactly one element; order irrelevant by count guard",
        "duplicate_behavior": "duplicates make count >= 2 and are rejected",
        "multiplicity": "strict single collapse from ordered list",
        "entity_identity_level": "entity pointer returned",
    },
    {
        "primitive_id": "battle.ir.entity.game_entity_runtime_id",
        "semantic_name": "GameEntityRuntimeID",
        "description": (
            "GameEntity.get_RuntimeID: signed int32 read at GameEntity [+0xD0]. "
            "This is the stable logical identity used by EntityRef in canonical "
            "IR; equality and hashing are by this id only."
        ),
        "inputs": [{"name": "entity", "type": "EntityRef"}],
        "context_reads": ["entity"],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.GameEntity",
        "source_method": "get_RuntimeID",
        "method_index": 499138,
        "pseudocode": [
            "int32 GameEntityRuntimeID(GameEntity this):",
            "    return this[+0xD0]             # signed 32-bit runtime id",
        ],
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing entity -> native null-instance throw",
        "ordering_behavior": "single scalar result",
        "duplicate_behavior": "single scalar result",
        "multiplicity": "single scalar",
        "entity_identity_level": "stable logical id (runtime id)",
    },
]


def _load_method_records() -> dict[int, dict]:
    wanted = {plan["method_index"] for plan in PRIMITIVE_PLANS}
    records: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        if rec["method_index"] in wanted:
            records[rec["method_index"]] = rec
    return records


def _normal_path_first_ret(pe, rva: int, gap: int):
    """Slice the bounded normal-path body ending at the first ``ret``.

    The accepted generated evaluators put the IL2CPP instrumentation /
    class-init trampoline *after* the first normal-path ret.  The returned
    window is the exact semantic body executed by ordinary runtime calls; the
    full gap disassembly is kept separately in the artifact.
    """
    raw, decoded = disasm_window(pe, rva, gap)
    first_ret = next((ins for ins in decoded if ins["mnemonic"] == "ret"), None)
    if first_ret is None:
        raise RuntimeError(f"no ret in window at 0x{rva:X}")
    end = first_ret["rva"] + first_ret["size"] - rva
    return raw[:end]


def _load_bridge_rows() -> list[dict]:
    if not BRIDGE_PATH.is_file():
        raise RuntimeError(
            f"missing bridge output {BRIDGE_PATH}; run "
            "tools/reverse/scripts/build_target_config_runtime_bridge.py first"
        )
    data = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))
    return data["matched_rows"]


def _load_config_identity(cfg_name: str) -> dict:
    """Named serializer config -> {type_index, serializer method, type_ref}."""
    config_type_index: int | None = None
    for rec in iter_records(NORMALIZED_BASE / "types.json"):
        if rec["full_name"] == cfg_name:
            config_type_index = rec["type_index"]
            break
    if config_type_index is None:
        raise RuntimeError(f"config type not found: {cfg_name}")
    mg_method: dict | None = None
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        if rec["declaring_type_index"] == config_type_index and rec["name"] == "MGMEGEDLMAK":
            mg_method = rec
            break
    if mg_method is None:
        raise RuntimeError(f"config serializer not found: {cfg_name}.MGMEGEDLMAK")
    refs = load_parameter_refs({mg_method["method_index"]}).get(mg_method["method_index"], [])
    if len(refs) != 2:
        raise RuntimeError(f"unexpected serializer params for {cfg_name}: {refs}")
    return {
        "runtime_type": cfg_name,
        "type_index": config_type_index,
        "serializer_method_index": mg_method["method_index"],
        "serializer_native_rva": mg_method.get("native_rva"),
        "runtime_type_reference": refs[1]["type_reference"],
    }


def _build_selector_chains(bridge_rows: list[dict]) -> list[dict]:
    plans = [
        ("task_action_target_selector_chain", "RPG.GameCore.TargetFetchTaskActionTarget",
         "battle.ir.target.select_task_action_target",
         "TaskContext field read [ctx+0x48] -> entity pointer -> list append"),
        ("caster_selector_chain", "RPG.GameCore.TargetFetchCaster",
         "battle.ir.target.select_caster",
         "caster entity -> list append (null caster appended as null element)"),
        ("none_selector_chain", "RPG.GameCore.TargetFetchNone",
         "battle.ir.target.select_none",
         "empty ordered target list"),
    ]
    by_config: dict[str, list[dict]] = {}
    for row in bridge_rows:
        for cfg in row["config_candidates"]:
            by_config.setdefault(cfg, []).append(row)
    chains = []
    for chain_id, cfg_name, primitive_id, role in plans:
        identity = _load_config_identity(cfg_name)
        matches = by_config.get(cfg_name, [])
        if len(matches) != 1:
            raise RuntimeError(f"expected one evaluator for {cfg_name}, got {len(matches)}")
        row = matches[0]
        exec_methods = {m["name"]: m for m in row["execution_methods"]}
        method = exec_methods["Evaluate"] if "Evaluate" in exec_methods else exec_methods["Transform"]
        chains.append({
            "chain_id": chain_id,
            "selector_config": {
                "runtime_type": identity["runtime_type"],
                "type_index": identity["type_index"],
                "serializer_method_index": identity["serializer_method_index"],
                "serializer_native_rva": (
                    f"0x{identity['serializer_native_rva']:X}"
                    if isinstance(identity["serializer_native_rva"], int)
                    else None
                ),
                "runtime_type_reference": identity["runtime_type_reference"],
            },
            "runtime_bridge": {
                "kind": "TYPE_REFERENCE_MATCH",
                "evidence": (
                    f"generated evaluator .ctor parameter type_reference == "
                    f"{identity['runtime_type']}.MGMEGEDLMAK second parameter "
                    f"type_reference ({identity['runtime_type_reference']})"
                ),
                "evaluator_runtime_type": row["evaluator_type"],
                "evaluator_execution_method": method["name"],
                "evaluator_method_index": method["method_index"],
                "evaluator_native_rva": (
                    f"0x{method['native_rva']:X}" if isinstance(method["native_rva"], int) else None
                ),
            },
            "steps": [
                {
                    "step": 1,
                    "primitive_id": primitive_id,
                    "role": role,
                }
            ],
        })
    return chains


def main() -> int:
    manifest = load_manifest()
    pe = load_pe()
    rvas_sorted, methods = load_method_rva_index()
    method_records = _load_method_records()
    param_refs = load_parameter_refs(set(plan["method_index"] for plan in PRIMITIVE_PLANS))
    bridge_rows = _load_bridge_rows()

    bridge_map: dict[str, list[dict]] = {}
    for row in bridge_rows:
        for cfg in row["config_candidates"]:
            bridge_map.setdefault(cfg, []).append(row)

    gameassembly = manifest["GameAssembly"]
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    primitives = []
    for plan in PRIMITIVE_PLANS:
        mi = plan["method_index"]
        method = method_records[mi]
        rva = method["native_rva"]
        if not isinstance(rva, int):
            raise RuntimeError(f"method {mi} has no direct RVA")
        i = rvas_sorted.index(rva) if rva in rvas_sorted else None
        if i is None:
            raise RuntimeError(f"method {mi} RVA not in index")
        next_rva = rvas_sorted[i + 1] if i + 1 < len(rvas_sorted) else rva + 4096
        gap = next_rva - rva
        raw_window, full_decoded = disasm_window(pe, rva, gap)
        body = _normal_path_first_ret(pe, rva, gap)
        # Re-disassemble the exact normal-path window for metrics.
        _, body_decoded = disasm_window(pe, rva, len(body))
        if not body_decoded or body_decoded[-1]["mnemonic"] != "ret":
            raise RuntimeError(f"normal path for {mi} does not end in ret")
        body_sha = hashlib.sha256(body).hexdigest()
        branch_count = sum(
            1
            for ins in body_decoded
            if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
        )
        call_count = sum(1 for ins in body_decoded if ins["mnemonic"] == "call")
        slot_va = pe.image_base + rva
        identity = {
            "method_index": mi,
            "declaring_type_index": method["declaring_type_index"],
            "method_name": method["name"],
            "parameter_count": method["parameter_count"],
            "return_type_reference": method["return_type_reference"],
            "parameter_relations": param_refs.get(mi, []),
            "mapping_kind": method["mapping_kind"],
        }
        native_evidence = {
            "body_rva": f"0x{rva:X}",
            "body_window_kind": "NORMAL_PATH_FIRST_RET_PROJECTION",
            "body_length_bytes": len(body),
            "body_sha256": body_sha,
            "code_table_slot_va": f"0x{slot_va:X}",
            "code_table_slot_index": mi,
            "image_base": f"0x{pe.image_base:X}",
            "mapping_kind": method["mapping_kind"],
            "full_gap_to_next_method": gap,
            "instruction_count": len(body_decoded),
            "conditional_branch_count": branch_count,
            "direct_call_count": call_count,
            "disassembly": [line_for(ins) for ins in body_decoded],
            "full_gap_disassembly": [line_for(ins) for ins in full_decoded],
        }
        primitive = {
            "primitive_id": plan["primitive_id"],
            "semantic_name": plan["semantic_name"],
            "description": plan["description"],
            "inputs": plan["inputs"],
            "context_reads": plan["context_reads"],
            "context_writes": [],
            "result": plan["result"],
            "determinism": "DETERMINISTIC",
            "evidence_level": E4,
            "source_runtime_type": plan["source_runtime_type"],
            "source_method": plan["source_method"],
            "source_method_index": mi,
            "source_native_rva": f"0x{rva:X}",
            "native_body_hash": body_sha,
            "source_identity": identity,
            "native_evidence": native_evidence,
            "branch_conditions": plan["branch_conditions"],
            "required_callees": plan["required_callees"],
            "pseudocode": plan["pseudocode"],
            "null_behavior": plan["null_behavior"],
            "ordering_behavior": plan["ordering_behavior"],
            "duplicate_behavior": plan["duplicate_behavior"],
            "multiplicity": plan["multiplicity"],
            "entity_identity_level": plan["entity_identity_level"],
        }
        primitives.append(primitive)

    selector_chains = _build_selector_chains(bridge_rows)

    context_requirements = [
        {
            "field": "task_action_target",
            "native_read": "TaskContext [+0x48] (get_TaskActionTarget / TargetFetchTaskActionTarget evaluator)",
            "evidence_level": "E4_STATIC_MACHINE_CODE",
            "note": "transient per-execution context field; not BattleState",
        },
        {
            "field": "owner_entity",
            "native_read": "TaskContext [+0x70] (get_OwnerEntity)",
            "evidence_level": "E4_STATIC_MACHINE_CODE",
            "note": "transient per-execution context field; not BattleState",
        },
        {
            "field": "caster_entity",
            "native_read": (
                "computed by TaskContext.get_CasterEntity duplicate entry "
                "0x18B429790 (vtable slot +0x130 -> [+0x38] -> [+0x10])"
            ),
            "evidence_level": "E4_STATIC_MACHINE_CODE",
            "note": "computed transient context entity; canonical materialization only",
        },
    ]

    state_requirements = []

    deferred_candidates = [
        {
            "runtime_type": "RPG.GameCore.TaskContext",
            "method": "EvaluateTarget",
            "method_index": 505873,
            "native_rva": "0xE6F1530",
            "classification": "SKIP_CONTEXT_HEAVY",
            "reason": "registry dispatcher with 41 callees; per-selector leaves recovered instead",
        },
        {
            "runtime_type": "RPG.GameCore.AbilityStatic",
            "method": "RemoveUnselectableEntities",
            "method_index": 504377,
            "native_rva": "0xE4406C0",
            "classification": "SEMANTIC_DEPENDENCY_REQUIRED",
            "reason": "ordered list filter proven at E4 shape; predicate internals not in batch",
        },
        {
            "runtime_type": "RPG.GameCore.AbilityStatic",
            "method": "RemoveForceUnselectableEntities",
            "method_index": 504378,
            "native_rva": "0xE440860",
            "classification": "SEMANTIC_DEPENDENCY_REQUIRED",
            "reason": "ordered list filter proven at E4 shape; predicate internals not in batch",
        },
        {
            "runtime_type": "ACFAOPKCPBD (TargetRemoveUnselectable evaluator)",
            "method": "Transform",
            "method_index": 537874,
            "native_rva": "0xB436990",
            "classification": "DEFERRED_FILTER",
            "reason": "complete leaf shape, but requires RemoveUnselectableEntities predicate semantics",
        },
        {
            "runtime_type": "KJJDGEEIPBE (TargetMapAllTeamMember evaluator)",
            "method": "Transform",
            "method_index": 538115,
            "native_rva": "0xB5D9770",
            "classification": "DEFERRED_MULTI_TARGET",
            "reason": "requires battle entity roster / team formation state",
        },
        {
            "runtime_type": "TargetQuery generated evaluator",
            "method": "Evaluate",
            "method_index": 0,
            "native_rva": "0x0",
            "classification": "DEFERRED_MULTI_TARGET",
            "reason": "requires EntityManager registry query semantics (see candidate_table bridge row)",
        },
        {
            "runtime_type": "RPG.GameCore.EntityManagerExtension",
            "method": "FillTargetEntitiesWithFilter",
            "method_index": 530517,
            "native_rva": "0xE595D00",
            "classification": "SKIP_CONTEXT_HEAVY",
            "reason": "battle roster/filter fan-in; exceeds single-batch budget",
        },
        {
            "runtime_type": "RPG.GameCore.TargetFetch* / TargetMap* / TargetSort* configs",
            "method": "serializer family (OJNNBEJLDIJ/MGMEGEDLMAK/LJACLBNEEEB/EOJLPDGNHEK)",
            "method_index": 0,
            "native_rva": "0x0",
            "classification": "SKIP_SERIALIZATION",
            "reason": "config identity recovered via bridge; execution lives in generated evaluators",
        },
    ]

    semantic_dependencies = [
        {
            "primitive_id": "TaskContext.EvaluateTarget (0xE6F1530)",
            "status": "SEMANTIC_DEPENDENCY_REQUIRED",
            "note": "config -> evaluator dispatch proven; registry construction not recovered",
        },
        {
            "primitive_id": "TaskContext.get_CasterEntity (duplicate entry 0x18B429790)",
            "status": "SEMANTIC_DEPENDENCY_CASTED_CANONICAL",
            "note": "computed context entity; canonical ExecutionContext.caster_entity materializes it",
        },
        {
            "primitive_id": "AbilityStatic.RemoveUnselectableEntities / RemoveForceUnselectableEntities",
            "status": "SEMANTIC_DEPENDENCY_REQUIRED",
            "note": "ordered filter shape proven; unselectable predicate internals deferred",
        },
    ]

    unknowns = [
        "runtime type name behind type_reference 202024 (entity pointer); anchored as GameEntity-compatible by get_RuntimeID and TaskContext/EntityManager consumers",
        "IL2CPP instrumentation / class-init tail paths after the first normal-path ret are excluded from body windows and documented as infrastructure",
        "list allocator/release/grow helper internals (0x18B42A0C0 / 0x18B429F50 / 0x18B42A1C0 / 0x197DFBE60 / 0x19BB0D610)",
        "TaskContext.get_CasterEntity duplicate-entry provenance (same byte pattern as 0xE6EEDF0; no formal identity link)",
        "registry construction for ctx[+0x88] evaluator table",
        "no E5 client-side runtime observation",
        "config->evaluator bridge is E3 metadata type-reference identity plus E4 native bodies",
        "target list capacity growth order is helper-internal; append order is proven",
    ]

    candidate_table = [
        {"method_index": p["source_method_index"], "candidate": f"{p['source_runtime_type']}.{p['source_method']}",
         "native_rva": p["source_native_rva"], "classification": "ACCEPT", "reason": p["description"]}
        for p in primitives
    ]
    candidate_table += [
        {"method_index": 537874, "candidate": "ACFAOPKCPBD.Transform (TargetRemoveUnselectable)", "native_rva": "0xB436990", "classification": "DEFERRED_FILTER", "reason": "needs unselectable predicate semantics"},
        {"method_index": 538115, "candidate": "KJJDGEEIPBE.Transform (TargetMapAllTeamMember)", "native_rva": "0xB5D9770", "classification": "DEFERRED_MULTI_TARGET", "reason": "needs roster/formation state"},
        {"method_index": 505873, "candidate": "TaskContext.EvaluateTarget", "native_rva": "0xE6F1530", "classification": "SKIP_CONTEXT_HEAVY", "reason": "registry dispatcher, 41 callees"},
        {"method_index": 530517, "candidate": "EntityManagerExtension.FillTargetEntitiesWithFilter", "native_rva": "0xE595D00", "classification": "SKIP_CONTEXT_HEAVY", "reason": "roster filter fan-in"},
        {"method_index": 505846, "candidate": "TaskContext.get_CasterEntity", "native_rva": "0xE6EEDF0", "classification": "SKIP_CONTEXT_HEAVY", "reason": "computed getter; duplicate entry used by caster evaluator"},
    ]
    for chain in selector_chains:
        sc = chain["selector_config"]
        rb = chain["runtime_bridge"]
        candidate_table.append({
            "method_index": sc["serializer_method_index"],
            "candidate": f"{sc['runtime_type']} serializer family",
            "native_rva": sc["serializer_native_rva"],
            "classification": "SKIP_SERIALIZATION",
            "reason": f"serializer only; bridge points to {rb['evaluator_runtime_type']}.{rb['evaluator_execution_method']}",
        })
        candidate_table.append({
            "method_index": rb["evaluator_method_index"],
            "candidate": f"{rb['evaluator_runtime_type']}.{rb['evaluator_execution_method']} ({sc['runtime_type']})",
            "native_rva": rb["evaluator_native_rva"],
            "classification": "ACCEPT_SINGLE_TARGET",
            "reason": chain["steps"][0]["role"],
        })
    for row in bridge_rows:
        if "TargetQuery" in row["config_candidates"]:
            method = next((m for m in row["execution_methods"] if m["name"] == "Evaluate"), None)
            if method is not None:
                candidate_table.append({
                    "method_index": method["method_index"],
                    "candidate": f"{row['evaluator_type']}.Evaluate (TargetQuery)",
                    "native_rva": f"0x{method['native_rva']:X}" if isinstance(method["native_rva"], int) else None,
                    "classification": "DEFERRED_MULTI_TARGET",
                    "reason": "needs EntityManager registry query semantics",
                })
            break

    artifact = {
        "schema": SCHEMA,
        "game_version": GAME_VERSION,
        "batch_id": BATCH_ID,
        "generated_at": generated_at,
        "evidence_level": E4,
        "final_status": "BATTLE_SEMANTIC = TARGET_SELECTOR_BATCH_05_PROOF",
        "gameassembly": {
            "path": gameassembly["path"],
            "sha256": gameassembly["sha256"],
        },
        "primitives": primitives,
        "selector_chains": selector_chains,
        "context_requirements": context_requirements,
        "state_requirements": state_requirements,
        "deferred_candidates": deferred_candidates,
        "semantic_dependencies": semantic_dependencies,
        "unknowns": unknowns,
        "candidate_table": candidate_table,
        "entity_identity": {
            "runtime_entity_level": "entity object pointer (type_reference 202024)",
            "stable_logical_id_method": {
                "runtime_type": "RPG.GameCore.GameEntity",
                "method": "get_RuntimeID",
                "method_index": 499138,
                "native_rva": "0xE61B860",
                "field_offset": "+0xD0",
                "width": 4,
                "signedness": "signed int32",
            },
            "canonical_mapping": "EntityRef(runtime_id=int32) -> equality/hash by runtime_id only",
        },
        "target_list_model": {
            "native_layout": {
                "list_count": "+0x18 (int32)",
                "list_version": "+0x1c (int32)",
                "list_items_array": "+0x10 (pointer)",
                "items": "[array + index*8 + 0x20] (entity pointer, may be null)",
            },
            "ordering": "ORDERED_APPEND",
            "duplicates": "PRESERVED_NO_DEDUPLICATION",
            "null_elements": "ALLOWED_PER_SELECTOR (caster appends null; task-action target skips null)",
            "empty": "ALLOWED",
            "canonical_representation": "TargetSet(tuple[EntityRef | None, ...])",
            "canonical_name_note": "kept the requested TargetSet name; it is a tuple-backed ordered list, never Python set()",
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    sha = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    print(f"wrote {OUT_PATH}")
    print(f"sha256={sha}")
    print(f"primitives={len(primitives)} selector_chains={len(selector_chains)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
