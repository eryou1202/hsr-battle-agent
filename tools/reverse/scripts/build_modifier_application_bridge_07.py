#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Modifier Application Bridge 07 semantic artifact (4.4.54).

Recovered runtime shape (the session label "Modifier application" maps to the
game's real layer):

    serialized AddModifier TaskConfig (RPG.GameCore.AddModifier)
      -> generated task executor JAJPDPAHFOA
          (.ctor stores TaskContext/config and initializes child task lists)
      -> OnTaskBegin (0x161801C0)
      -> TaskContext.EvaluateTarget (Batch 05 target layer)
      -> per-target TurnBasedAbilityComponent.TryAddModifierInstance
          (0xE729500, string name + ModifierConfig + ability + param + bool)
      -> TurnBasedModifierInstance allocation
      -> AbilityComponent.AddModifierInstance (0xE431890)
      -> _ModifierList append at component [+0x38]
      -> TurnBasedModifierInstance state fields (Name/Count/State/
         StackingFlag/Layer/CurrentLife/SourceEntity/CasterEntity)

The batch does not recover modifier effects, damage, DOT or the event system.
The full TryAddModifierInstance lifecycle/stack dispatcher and the post-append
virtual calls are recorded as dependencies, never silently modelled.
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
    disasm_window,
    iter_records,
    load_manifest,
    load_parameter_refs,
    load_pe,
    line_for,
)

GAME_VERSION = "4.4.54"
BATCH_ID = "MODIFIER_APPLICATION_BRIDGE_07"
SCHEMA = "battle_semantics_batch/1"
E4 = "E4_STATIC_MACHINE_CODE"
OUT_PATH = REPO / "data" / "semantics" / "4.4.54" / "modifier_application_bridge_07.json"
BRIDGE_PATH = REPO / "data" / "raw" / "4.4.54" / "action_config_runtime_bridge_06.json"
DISCOVERY_PATH = (
    REPO / "data" / "raw" / "4.4.54" / "modifier_application_discovery_07.json"
)

ADD_MODIFIER_CONFIG_TYPE_INDEX = 22786
ADD_MODIFIER_CONFIG_TYPE_REFERENCE = 283020
ADD_MODIFIER_EXECUTOR_TYPE_INDEX = 54975

PRIMITIVE_PLANS = [
    {
        "primitive_id": "battle.ir.action.add_modifier_executor_init",
        "semantic_name": "AddModifierExecutorInit",
        "description": (
            "Generated AddModifier task executor ctor (JAJPDPAHFOA..ctor): "
            "stores arg0 TaskContext at [+0x18], arg1 AddModifier config at "
            "[+0x20], sets TaskState [+0x10] = Ready (0x7777), then builds the "
            "SuccessTaskList / FailTaskList / ResistedTaskList child executors "
            "from config [+0xc8]/[+0xd0]/[+0xd8] into executor [+0x48]/[+0x30]/"
            "[+0x28]. The child-list construction is recorded as deferred "
            "task-graph initialization; the canonical primitive materializes "
            "the config reference and Ready state only."
        ),
        "inputs": [{"name": "config", "type": "action_config_ref"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [
            "task_context_slot",
            "task_config_slot",
            "task_state",
            "child_task_executor_slots",
        ],
        "result": "task_execution",
        "source_runtime_type": "JAJPDPAHFOA",
        "source_method": ".ctor",
        "method_index": 506046,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "null this/config -> IL2CPP throw",
            "config child-task-list field null -> skip that child executor",
            "IL2CPP class-init instrumentation excluded from the normal path",
        ],
        "required_callees": [
            "0x183C736B0 il2cpp_object_new (runtime allocation, not needed)",
            "0x1962E5C00 generated child task-list factory (deferred task graph)",
        ],
        "null_behavior": "native null-instance throw paths; canonical input validation",
        "ordering_behavior": "single initialization; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.add_modifier_task_begin_apply",
        "semantic_name": "AddModifierTaskBeginApplyBoundary",
        "description": (
            "Normal-path projection of JAJPDPAHFOA.OnTaskBegin "
            "(RPG.GameCore.AddModifier): read TaskContext/config slots, "
            "evaluate the target list with TaskContext.EvaluateTarget "
            "(config TargetType at [+0x18], alive mask from config [+0x20]), "
            "iterate the ordered target list ([list+0x10]/[+0x18]), call "
            "TurnBasedAbilityComponent.TryAddModifierInstance per target, and "
            "write TaskState [+0x10] = Success (0x9999) on the observed normal "
            "path. The 6592-byte native body is a boundary, not a fully cloned "
            "leaf: dynamic-value/string parameter evaluation, stack/lifetime "
            "dispatch and event branches are deferred."
        ),
        "inputs": [
            {"name": "execution", "type": "task_execution"},
            {"name": "targets", "type": "TargetSet"},
            {"name": "modifier", "type": "modifier_state"},
        ],
        "context_reads": ["targets"],
        "context_writes": [],
        "state_reads": [],
        "state_writes": ["modifier_state_by_entity"],
        "action_reads": [],
        "action_writes": ["task_state"],
        "result": "modifier_task_application",
        "source_runtime_type": "JAJPDPAHFOA",
        "source_method": "OnTaskBegin",
        "method_index": 506048,
        "projection": "FULL_GAP",
        "branch_conditions": [
            "source-entity invalid/disallowed -> early Success store (0x16180263)",
            "config/context null -> IL2CPP throw paths",
            "target list empty -> normal path returns Success after no application",
            "per-target TryAddModifierInstance null result -> skip post-processing path",
            "dynamic-value/string evaluator branches are outside this boundary projection",
        ],
        "required_callees": [
            "0xE6EEFE0 TaskContext.get_SourceEntity",
            "0xE6F1530 TaskContext.EvaluateTarget",
            "0xE6EFAE0 TaskContext.Evaluate",
            "0x16181B80 JAJPDPAHFOA.GAKKBJAPCKI (target transform helper)",
            "0xE61F7A0 GameEntityExtensions.IsAllowAddModifier",
            "0xE729500 TurnBasedAbilityComponent.TryAddModifierInstance",
        ],
        "null_behavior": (
            "null TaskContext/config slots and null target-list backing array "
            "follow native throw paths; canonical primitive rejects them. Null "
            "individual target elements are rejected in the canonical path."
        ),
        "ordering_behavior": (
            "ORDERED_APPEND: native iterates target list index 0..count-1 and "
            "calls TryAddModifierInstance in that order"
        ),
    },
    {
        "primitive_id": "battle.ir.modifier.apply_modifier_instance",
        "semantic_name": "AbilityComponentAddModifierInstance",
        "description": (
            "RPG.GameCore.AbilityComponent.AddModifierInstance normal path: "
            "list = this[+0x38] (_ModifierList); list[+0x1c]++ (version); if "
            "count < capacity write [items + count*8 + 0x20] = modifier and "
            "count++; else call the List<T> growth helper. After the append the "
            "native body performs two virtual interface dispatches on the "
            "modifier (post-apply lifecycle) with a bool guard; those calls are "
            "recorded as POST_APPLY_LIFECYCLE_DEPENDENCY_REQUIRED and are not "
            "part of the canonical append. Duplicates are never checked here: "
            "this leaf always appends."
        ),
        "inputs": [
            {"name": "target", "type": "EntityRef"},
            {"name": "modifier", "type": "modifier_state"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": ["modifier_state_by_entity"],
        "state_writes": ["modifier_state_by_entity"],
        "action_reads": [],
        "action_writes": [],
        "result": "modifier_container",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "AddModifierInstance",
        "method_index": 520236,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "list null / items array null -> IL2CPP throw",
            "count < array capacity -> inline append",
            "count == capacity -> List<T> growth helper (0x197DFBE60)",
            "post-append virtual dispatch branch -> deferred lifecycle",
        ],
        "required_callees": [
            "0x197DFBE60 List<T>.AddWithResize (container growth helper)",
            "two interface method dispatches on the modifier instance -> "
            "POST_APPLY_LIFECYCLE_DEPENDENCY_REQUIRED",
        ],
        "null_behavior": "null list/items -> native throw; canonical rejects null container",
        "ordering_behavior": "ORDERED_APPEND at tail; duplicates preserved; no search before append",
    },
    {
        "primitive_id": "battle.ir.modifier.container_get_by_index",
        "semantic_name": "AbilityComponentGetModifierByIndex",
        "description": (
            "Read AbilityComponent [+0x38] _ModifierList and return "
            "[items + index*8 + 0x20]; index >= list count or index >= array "
            "count returns null/throws exactly as the native bounds checks; "
            "normal in-range path returns the modifier instance."
        ),
        "inputs": [
            {"name": "container", "type": "modifier_container"},
            {"name": "index", "type": "int32"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "modifier_state_or_null",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "GetModifierByIndex",
        "method_index": 520239,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "index >= list count -> return null",
            "index >= backing array capacity -> throw",
            "backing array null -> throw",
        ],
        "required_callees": ["none in the accepted normal path"],
        "null_behavior": "index >= count -> null; null list/array -> native throw",
        "ordering_behavior": "index-address read; no iteration",
    },
    {
        "primitive_id": "battle.ir.modifier.container_index_of",
        "semantic_name": "AbilityComponentGetIndexByModifier",
        "description": (
            "Linear scan of AbilityComponent [+0x38] _ModifierList; returns the "
            "first index whose element reference equals the queried modifier, "
            "or -1. Proven ordered index semantics for instance ordinal."
        ),
        "inputs": [
            {"name": "container", "type": "modifier_container"},
            {"name": "modifier", "type": "modifier_state"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "GetIndexByModifier",
        "method_index": 520240,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "list null -> return -1",
            "count <= 0 -> return -1",
            "reference equal -> return current index",
        ],
        "required_callees": ["none in the accepted normal path"],
        "null_behavior": "null list -> -1; null queried modifier never matches",
        "ordering_behavior": "forward linear scan from index 0",
    },
    {
        "primitive_id": "battle.ir.modifier.container_has_modifier_by_name",
        "semantic_name": "AbilityComponentHasModifier",
        "description": (
            "Linear scan of AbilityComponent [+0x38] _ModifierList; only "
            "instances with State [+0x80] == 1 are considered; returns true when "
            "BaseModifierInstance.Name [+0x60] string equals the query. Null "
            "query has its own native path (any active modifier with null name "
            "is a match only through the equality helper behavior observed in "
            "the body). Canonical normal path keeps the active-state guard and "
            "ordinal string equality."
        ),
        "inputs": [
            {"name": "container", "type": "modifier_container"},
            {"name": "name", "type": "string_or_null"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "boolean",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "HasModifier",
        "method_index": 520246,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "list null -> native throw",
            "state [+0x80] != 1 -> skip instance",
            "name length differs -> skip",
            "ordinal string equal -> true",
        ],
        "required_callees": [
            "0x1BB65990 System.String.EqualsHelper (ordinal string equality)",
        ],
        "null_behavior": "null list -> throw; null name follows native two-branch equality path",
        "ordering_behavior": "forward linear scan from index 0; first match wins",
    },
    {
        "primitive_id": "battle.ir.modifier.container_count",
        "semantic_name": "AbilityComponentModifierCount",
        "description": (
            "Return AbilityComponent [+0x38] _ModifierList count field "
            "[list +0x18] as int32; null list -> native throw."
        ),
        "inputs": [{"name": "container", "type": "modifier_container"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "get_ModifierCount",
        "method_index": 520257,
        "projection": "FIRST_RET",
        "branch_conditions": ["list null -> native throw"],
        "required_callees": ["none in the accepted normal path"],
        "null_behavior": "null list -> native throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_name",
        "semantic_name": "BaseModifierInstanceName",
        "description": "BaseModifierInstance.Name getter: return string slot [+0x60].",
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "string_or_null",
        "source_runtime_type": "RPG.GameCore.BaseModifierInstance",
        "source_method": "get_Name",
        "method_index": 504746,
        "projection": "FIRST_RET",
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "returns the stored string pointer, including null",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_count",
        "semantic_name": "BaseModifierInstanceCount",
        "description": "BaseModifierInstance.Count getter: int32 slot [+0x7c].",
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.BaseModifierInstance",
        "source_method": "get_Count",
        "method_index": 504765,
        "projection": "FIRST_RET",
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing instance -> native null-instance throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_state_raw",
        "semantic_name": "BaseModifierInstanceStateRaw",
        "description": (
            "BaseModifierInstance.State getter: raw int32 slot [+0x80]. The enum "
            "member names/ordinals are UNKNOWN; the accepted read is raw."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.BaseModifierInstance",
        "source_method": "get_State",
        "method_index": 504749,
        "projection": "FIRST_RET",
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing instance -> native null-instance throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_stacking_flag_raw",
        "semantic_name": "BaseModifierInstanceStackingFlagRaw",
        "description": (
            "BaseModifierInstance.StackingFlag getter: raw int32 slot [+0x88]. "
            "Enum member names/ordinals are UNKNOWN; the accepted read is raw."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.BaseModifierInstance",
        "source_method": "get_StackingFlag",
        "method_index": 504751,
        "projection": "FIRST_RET",
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing instance -> native null-instance throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_caster_entity",
        "semantic_name": "BaseModifierInstanceCasterEntity",
        "description": (
            "BaseModifierInstance.CasterEntity getter: cached entity slot [+0x58]; "
            "when null it lazily resolves from [+0x48] via the unregistered local "
            "helper 0xB429790 and writes the cache slot [+0x58]. Canonical "
            "ModifierState materializes the resolved value immutably."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "EntityRef",
        "source_runtime_type": "RPG.GameCore.BaseModifierInstance",
        "source_method": "get_CasterEntity",
        "method_index": 504757,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "cached [+0x58] non-null -> return cache",
            "cached null + resolver object [+0x48] null -> throw",
            "cached null -> call local helper 0xB429790 and write cache [+0x58]",
        ],
        "required_callees": [
            "0xB429790 unregistered local resolver helper (UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "cache miss with null resolver -> native throw; resolved value may be null",
        "ordering_behavior": "lazy cache fill; canonical value is immutable",
    },
    {
        "primitive_id": "battle.ir.modifier.state_layer",
        "semantic_name": "TurnBasedModifierInstanceLayer",
        "description": "TurnBasedModifierInstance.Layer getter: int32 slot [+0x288].",
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "get_Layer",
        "method_index": 506325,
        "projection": "FIRST_RET",
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing instance -> native null-instance throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_max_layer",
        "semantic_name": "TurnBasedModifierInstanceMaxLayer",
        "description": (
            "TurnBasedModifierInstance.MaxLayer getter: max(1, int32 [+0x2e0] + "
            "int32 [+0x270]). The two slot names are UNKNOWN; the arithmetic is "
            "proven."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "get_MaxLayer",
        "method_index": 506327,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "[+0x2e0] + [+0x270] < 2 -> result 1",
            "otherwise -> result = sum",
        ],
        "required_callees": ["none in the accepted normal path"],
        "null_behavior": "missing instance -> native null-instance throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_current_life",
        "semantic_name": "TurnBasedModifierInstanceCurrentLife",
        "description": (
            "TurnBasedModifierInstance.CurrentLife getter: int32 slot [+0x2c4]. "
            "Expiration trigger semantics are UNKNOWN."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "int32",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "get_CurrentLife",
        "method_index": 506329,
        "projection": "FIRST_RET",
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing instance -> native null-instance throw",
        "ordering_behavior": "scalar read; no ordering",
    },
    {
        "primitive_id": "battle.ir.modifier.state_source_entity",
        "semantic_name": "TurnBasedModifierInstanceSourceEntity",
        "description": (
            "TurnBasedModifierInstance.SourceEntity getter: cached entity slot "
            "[+0x100]; when null it lazily resolves from [+0x48] via the "
            "unregistered local helper 0xB429790. Canonical ModifierState "
            "materializes the resolved value immutably."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": [],
        "result": "EntityRef",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "get_SourceEntity",
        "method_index": 506280,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "cached [+0x100] non-null -> return cache",
            "cached null + resolver object [+0x48] null -> throw",
            "cached null -> local helper 0xB429790 (does not write the [+0x100] slot in this getter)",
        ],
        "required_callees": [
            "0xB429790 unregistered local resolver helper (UNKNOWN_HELPER_NOT_NEEDED)",
        ],
        "null_behavior": "cache miss with null resolver -> native throw; resolved value may be null",
        "ordering_behavior": "lazy fallback; canonical value is immutable",
    },
]


def _load_method_records(wanted: set[int]) -> tuple[dict[int, dict], list[int], dict[int, dict]]:
    records: dict[int, dict] = {}
    rvas: list[int] = []
    methods_by_rva: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        rva = rec.get("native_rva")
        if isinstance(rva, int) and rec.get("mapping_kind") == "DIRECT_NATIVE":
            rvas.append(rva)
            methods_by_rva[rva] = rec
        if rec["method_index"] in wanted:
            records[rec["method_index"]] = rec
    rvas.sort()
    if len(records) != len(wanted):
        missing = wanted - set(records)
        raise RuntimeError(f"missing method records: {sorted(missing)}")
    return records, rvas, methods_by_rva


def _load_type_map() -> dict[int, dict]:
    return {
        rec["type_index"]: rec
        for rec in iter_records(NORMALIZED_BASE / "types.json")
    }


def _load_fields(type_indexes: set[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for rec in iter_records(NORMALIZED_BASE / "fields.json"):
        if rec["declaring_type_index"] in type_indexes:
            out.setdefault(rec["declaring_type_index"], []).append(rec)
    return out


def _project_body(pe, rva: int, gap: int, projection: str) -> tuple[bytes, str]:
    raw, decoded = disasm_window(pe, rva, gap)
    if projection == "EXACT":
        if not decoded or decoded[-1]["mnemonic"] != "ret":
            raise RuntimeError(f"EXACT body does not end in ret at 0x{rva:X}")
        end = decoded[-1]["rva"] + decoded[-1]["size"] - rva
        return raw[:end], "EXACT_FULL_BODY"
    if projection == "FIRST_RET":
        first_ret = next((ins for ins in decoded if ins["mnemonic"] == "ret"), None)
        if first_ret is None:
            raise RuntimeError(f"no ret in window at 0x{rva:X}")
        end = first_ret["rva"] + first_ret["size"] - rva
        return raw[:end], "NORMAL_PATH_FIRST_RET_PROJECTION"
    if projection == "FULL_GAP":
        return raw, "FULL_GAP_CHAIN_BOUNDARY"
    raise RuntimeError(f"unknown projection {projection}")


def _evidence_for(
    pe,
    method: dict,
    rvas: list[int],
    methods_by_rva: dict[int, dict],
    projection: str,
) -> tuple[dict, dict]:
    rva = method["native_rva"]
    if not isinstance(rva, int):
        raise RuntimeError(f"method {method['method_index']} has no DIRECT_NATIVE RVA")
    idx = next(i for i, v in enumerate(rvas) if v == rva)
    next_rva = rvas[idx + 1] if idx + 1 < len(rvas) else rva + 4096
    gap = next_rva - rva
    raw, decoded = disasm_window(pe, rva, gap)
    body, window_kind = _project_body(pe, rva, gap, projection)
    _, body_decoded = disasm_window(pe, rva, len(body))
    body_sha = hashlib.sha256(body).hexdigest()
    branch_count = sum(
        1
        for ins in body_decoded
        if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
    )
    call_count = sum(1 for ins in body_decoded if ins["mnemonic"] == "call")
    jmp_count = sum(1 for ins in body_decoded if ins["mnemonic"] == "jmp")
    identity = {
        "method_index": method["method_index"],
        "declaring_type_index": method["declaring_type_index"],
        "method_name": method["name"],
        "parameter_count": method["parameter_count"],
        "return_type_reference": method["return_type_reference"],
        "mapping_kind": method["mapping_kind"],
    }
    evidence = {
        "body_rva": f"0x{rva:X}",
        "body_window_kind": window_kind,
        "body_length_bytes": len(body),
        "body_sha256": body_sha,
        "code_table_slot_va": f"0x{pe.image_base + rva:X}",
        "code_table_slot_index": method["method_index"],
        "image_base": f"0x{pe.image_base:X}",
        "mapping_kind": method["mapping_kind"],
        "full_gap_to_next_method": gap,
        "instruction_count": len(body_decoded),
        "conditional_branch_count": branch_count,
        "direct_call_count": call_count,
        "direct_jump_count": jmp_count,
        "disassembly": [line_for(ins) for ins in body_decoded],
        "full_gap_disassembly": [line_for(ins) for ins in decoded],
    }
    return evidence, identity


def _chain_evidence() -> list[dict]:
    """The AddModifier application chain, assembled from E4 boundaries."""
    return [
        {
            "chain_id": "add_modifier_action_application_chain",
            "status": "E4_CHAIN_CLOSED_BOUNDARY_PROJECTION",
            "config": {
                "runtime_type": "RPG.GameCore.AddModifier",
                "type_index": ADD_MODIFIER_CONFIG_TYPE_INDEX,
                "serializer_method_index": 126119,
                "serializer_native_rva": "0x1CD26280",
                "runtime_type_reference": ADD_MODIFIER_CONFIG_TYPE_REFERENCE,
                "fields_used": [
                    "TargetType (config [+0x18] -> EvaluateTarget)",
                    "AliveOnly (config [+0x20] -> target mask 0xF / 1)",
                    "ModifierName (E3 field identity; runtime name slot [+0x60])",
                    "SuccessTaskList / FailTaskList / ResistedTaskList "
                    "(config [+0xc8]/[+0xd0]/[+0xd8] -> ctor child executors)",
                ],
            },
            "runtime_bridge": {
                "kind": "TYPE_REFERENCE_MATCH",
                "evidence": (
                    "generated executor .ctor(parameter 2 type_reference) == "
                    "config MGMEGEDLMAK(parameter 2 type_reference) "
                    f"({ADD_MODIFIER_CONFIG_TYPE_REFERENCE})"
                ),
                "executor_runtime_type": "JAJPDPAHFOA",
                "executor_type_index": ADD_MODIFIER_EXECUTOR_TYPE_INDEX,
            },
            "steps": [
                {
                    "step": 1,
                    "role": "config -> generated executor",
                    "method": ".ctor",
                    "method_index": 506046,
                    "native_rva": "0x1617FE60",
                    "evidence": (
                        "[+0x20]=config, [+0x18]=TaskContext, [+0x10]=Ready; "
                        "child task executors from config [+0xc8]/[+0xd0]/[+0xd8]"
                    ),
                },
                {
                    "step": 2,
                    "role": "source entity context read",
                    "method": "get_SourceEntity",
                    "method_index": 505849,
                    "native_rva": "0xE6EEFE0",
                    "evidence": "TaskContext [+0x68] -> source/caster entity chain",
                },
                {
                    "step": 3,
                    "role": "target selection (Batch 05 layer reuse)",
                    "method": "EvaluateTarget",
                    "method_index": 505873,
                    "native_rva": "0xE6F1530",
                    "evidence": (
                        "call site 0x16180353: EvaluateTarget(ctx=[executor+0x18], "
                        "targetType=config[+0x18], list, mask); result target list "
                        "iterated at 0x16180517..0x1618059A using [+0x10]/[+0x18]"
                    ),
                },
                {
                    "step": 4,
                    "role": "per-target application helper",
                    "method": "TryAddModifierInstance",
                    "method_index": 506463,
                    "native_rva": "0xE729500",
                    "evidence": (
                        "OnTaskBegin call site 0x16181043; signature "
                        "(this=TurnBasedAbilityComponent, string, ModifierConfig "
                        "typeref 104288, ability typeref 286703, param typeref "
                        "608873, bool typeref 433618)"
                    ),
                },
                {
                    "step": 5,
                    "role": "modifier instance construction",
                    "method": ".ctor",
                    "method_index": 506132,
                    "native_rva": "0xE77EB00",
                    "evidence": (
                        "TryAddModifierInstance allocates TurnBasedModifierInstance "
                        "class global 0x95CAFF8 at 0xE729890 and calls its ctor "
                        "0xE77EB00 at 0xE7298AE; config/name copied into instance slots"
                    ),
                },
                {
                    "step": 6,
                    "role": "persistent container mutation",
                    "method": "AddModifierInstance",
                    "method_index": 520236,
                    "native_rva": "0xE431890",
                    "evidence": (
                        "TryAddModifierInstance call site 0xE729C2E; leaf writes "
                        "_ModifierList at AbilityComponent [+0x38]: version "
                        "[list+0x1c]++, items [array + count*8 + 0x20], count "
                        "[list+0x18]++"
                    ),
                },
                {
                    "step": 7,
                    "role": "task state result",
                    "method": "OnTaskBegin",
                    "method_index": 506048,
                    "native_rva": "0x161801C0",
                    "evidence": (
                        "normal path writes TaskState [+0x10] = Success (0x9999); "
                        "early-path success store at 0x16180263, normal tail store "
                        "at 0x16181708"
                    ),
                },
            ],
        },
        {
            "chain_id": "modifier_owner_container_chain",
            "status": "E4_CHAIN_CLOSED",
            "steps": [
                {
                    "step": 1,
                    "role": "entity owns component",
                    "method": "_OnInitOwnerRef",
                    "method_index": 506418,
                    "native_rva": "0xE723BB0",
                    "evidence": (
                        "TurnBasedAbilityComponent [+0x10] is the owner entity; "
                        "body reads [component+0x10] and stores it into new owner "
                        "structures at [+0x1e8] and [+0x160]+0x18"
                    ),
                },
                {
                    "step": 2,
                    "role": "component owns modifier list",
                    "method": "get_ModifierList / AddModifierInstance",
                    "method_index": 520258,
                    "native_rva": "0xE433E20",
                    "evidence": (
                        "get_ModifierList returns AbilityComponent [+0x38]; "
                        "AddModifierInstance mutates that same slot's list"
                    ),
                },
                {
                    "step": 3,
                    "role": "instance remembers owner component",
                    "method": "GetOwnerAbilityComponent",
                    "method_index": 506159,
                    "native_rva": "0xE740660",
                    "evidence": "TurnBasedModifierInstance [+0x198] returns owner component",
                },
            ],
        },
    ]


def _candidate_table() -> list[dict]:
    return [
        {
            "method_index": 506048,
            "candidate": "JAJPDPAHFOA.OnTaskBegin (RPG.GameCore.AddModifier)",
            "native_rva": "0x161801C0",
            "classification": "ACCEPT_APPLICATION_BOUNDARY",
            "reason": "6592-byte generated task body; target loop -> TryAddModifierInstance -> Success store accepted as boundary; dynamic value/lifetime branches deferred",
        },
        {
            "method_index": 506046,
            "candidate": "JAJPDPAHFOA..ctor (RPG.GameCore.AddModifier)",
            "native_rva": "0x1617FE60",
            "classification": "ACCEPT_APPLICATION",
            "reason": "config/context slots + Ready + child task executor initialization",
        },
        {
            "method_index": 506463,
            "candidate": "RPG.GameCore.TurnBasedAbilityComponent.TryAddModifierInstance",
            "native_rva": "0xE729500",
            "classification": "SKIP_LIFECYCLE_HEAVY",
            "reason": "application helper boundary used; 3424-byte stack/lifetime/event dispatcher internals deferred",
        },
        {
            "method_index": 520236,
            "candidate": "RPG.GameCore.AbilityComponent.AddModifierInstance",
            "native_rva": "0xE431890",
            "classification": "ACCEPT_APPLICATION",
            "reason": "proven ordered append into _ModifierList [+0x38]; post-append lifecycle calls deferred",
        },
        {
            "method_index": 520239,
            "candidate": "RPG.GameCore.AbilityComponent.GetModifierByIndex",
            "native_rva": "0xE4321E0",
            "classification": "ACCEPT_QUERY",
            "reason": "ordered index read",
        },
        {
            "method_index": 520240,
            "candidate": "RPG.GameCore.AbilityComponent.GetIndexByModifier",
            "native_rva": "0xE432270",
            "classification": "ACCEPT_QUERY",
            "reason": "linear ordinal lookup",
        },
        {
            "method_index": 520246,
            "candidate": "RPG.GameCore.AbilityComponent.HasModifier",
            "native_rva": "0xE4331F0",
            "classification": "ACCEPT_QUERY",
            "reason": "existence query by name + state raw == 1",
        },
        {
            "method_index": 520257,
            "candidate": "RPG.GameCore.AbilityComponent.get_ModifierCount",
            "native_rva": "0xE433DD0",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "list count read",
        },
        {
            "method_index": 504746,
            "candidate": "RPG.GameCore.BaseModifierInstance.get_Name",
            "native_rva": "0xE4EEF10",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "identity field [+0x60]",
        },
        {
            "method_index": 504765,
            "candidate": "RPG.GameCore.BaseModifierInstance.get_Count",
            "native_rva": "0xE4EF0E0",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "proven int32 state slot",
        },
        {
            "method_index": 504749,
            "candidate": "RPG.GameCore.BaseModifierInstance.get_State",
            "native_rva": "0xE4EEF40",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "raw active-state slot; enum semantics UNKNOWN",
        },
        {
            "method_index": 504751,
            "candidate": "RPG.GameCore.BaseModifierInstance.get_StackingFlag",
            "native_rva": "0xE4EEF60",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "raw stacking enum slot; semantics UNKNOWN",
        },
        {
            "method_index": 504757,
            "candidate": "RPG.GameCore.BaseModifierInstance.get_CasterEntity",
            "native_rva": "0xE4EEFC0",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "cached entity read with lazy fallback",
        },
        {
            "method_index": 506325,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.get_Layer",
            "native_rva": "0xE78E480",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "proven layer int32",
        },
        {
            "method_index": 506327,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.get_MaxLayer",
            "native_rva": "0xE78E500",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "max(1, slot sum) arithmetic proven; slot names unknown",
        },
        {
            "method_index": 506329,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.get_CurrentLife",
            "native_rva": "0xE78E5C0",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "proven current-life int32; expiration UNKNOWN",
        },
        {
            "method_index": 506280,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.get_SourceEntity",
            "native_rva": "0xE78A810",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "cached entity read with lazy fallback",
        },
        {
            "method_index": 506238,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.GetModifierConfig",
            "native_rva": "0xE7456B0",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "ModifierConfig ref slot [+0xa0]; canonical identity uses the proven Name slot instead of object identity",
        },
        {
            "method_index": 506159,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.GetOwnerAbilityComponent",
            "native_rva": "0xE740660",
            "classification": "ACCEPT_STATE_LEAF",
            "reason": "owner component slot [+0x198]; closes owner/container relationship",
        },
        {
            "method_index": 506132,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance..ctor",
            "native_rva": "0xE77EB00",
            "classification": "SKIP_LIFECYCLE_HEAVY",
            "reason": "instance field-copy ctor; chain identity uses the proven state getters",
        },
        {
            "method_index": 506250,
            "candidate": "RPG.GameCore.TurnBasedModifierInstance.Destroy",
            "native_rva": "0xE7384B0",
            "classification": "SKIP_LIFECYCLE_HEAVY",
            "reason": "destruction/event cleanup path observed from TryAddModifierInstance; removal semantics not in this round",
        },
        {
            "method_index": 504365,
            "candidate": "RPG.GameCore.AbilityStatic.GlobalFindModifierInstance",
            "native_rva": "0xE43E2B0",
            "classification": "SKIP_LIFECYCLE_HEAVY",
            "reason": "global duplicate-search dispatcher; stack policy condition unresolved",
        },
        {
            "method_index": 506476,
            "candidate": "RPG.GameCore.TurnBasedAbilityComponent.FindModifierInstance",
            "native_rva": "0xE72B410",
            "classification": "SKIP_DUPLICATE",
            "reason": "delegates to AbilityComponent.FindModifierInstance; duplicate search observed but exact stack policy unresolved",
        },
        {
            "method_index": 506672,
            "candidate": "RPG.GameCore.TurnBasedAbilityComponent._PostProcessAfterModifierAdd",
            "native_rva": "0xE74E070",
            "classification": "SKIP_LIFECYCLE_HEAVY",
            "reason": "post-apply property/event processing; effect semantics deferred",
        },
        {
            "method_index": 506464,
            "candidate": "RPG.GameCore.TurnBasedAbilityComponent._ProcessModifierRedd",
            "native_rva": "0xE72A3C0",
            "classification": "SKIP_LIFECYCLE_HEAVY",
            "reason": "stack/refresh internals; stack policy UNKNOWN",
        },
        {
            "method_index": 126119,
            "candidate": "RPG.GameCore.AddModifier.MGMEGEDLMAK serializer",
            "native_rva": "0x1CD26280",
            "classification": "SKIP_SERIALIZATION",
            "reason": "config identity via bridge; execution recovered in generated executor",
        },
    ]


def main() -> int:
    wanted = {plan["method_index"] for plan in PRIMITIVE_PLANS}
    wanted |= {126119, 505849, 505873, 506463, 506132, 520258, 506159, 506418}
    method_records, rvas, methods_by_rva = _load_method_records(wanted)
    type_map = _load_type_map()
    fields = _load_fields(
        {
            ADD_MODIFIER_CONFIG_TYPE_INDEX,
            ADD_MODIFIER_EXECUTOR_TYPE_INDEX,
            55009,
            56973,
            55002,
            54598,
        }
    )
    param_refs = load_parameter_refs(
        {plan["method_index"] for plan in PRIMITIVE_PLANS} | {506463, 506046}
    )
    pe = load_pe()
    manifest = load_manifest()
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))
    bridge_rows = bridge["matched_rows"]
    addmodifier_bridge_row = next(
        r for r in bridge_rows if r["config_type_ref"] == ADD_MODIFIER_CONFIG_TYPE_REFERENCE
    )
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    primitives = []
    for plan in PRIMITIVE_PLANS:
        mi = plan["method_index"]
        method = method_records[mi]
        evidence, identity = _evidence_for(
            pe, method, rvas, methods_by_rva, plan["projection"]
        )
        identity["parameter_relations"] = param_refs.get(mi, [])
        primitive = {
            "primitive_id": plan["primitive_id"],
            "semantic_name": plan["semantic_name"],
            "description": plan["description"],
            "inputs": plan["inputs"],
            "context_reads": plan["context_reads"],
            "context_writes": plan["context_writes"],
            "state_reads": plan["state_reads"],
            "state_writes": plan["state_writes"],
            "action_reads": plan["action_reads"],
            "action_writes": plan["action_writes"],
            "result": plan["result"],
            "determinism": "DETERMINISTIC",
            "evidence_level": E4,
            "source_runtime_type": plan["source_runtime_type"],
            "source_method": plan["source_method"],
            "source_method_index": mi,
            "source_native_rva": f"0x{method['native_rva']:X}",
            "native_body_hash": evidence["body_sha256"],
            "source_identity": identity,
            "native_evidence": evidence,
            "branch_conditions": plan["branch_conditions"],
            "required_callees": plan["required_callees"],
            "null_behavior": plan["null_behavior"],
            "ordering_behavior": plan["ordering_behavior"],
            "determinism_note": (
                "constant writes and ordered list iteration; no PRNG/clock/"
                "context dependency in the accepted canonical projections"
            ),
        }
        primitives.append(primitive)

    artifact = {
        "schema": SCHEMA,
        "game_version": GAME_VERSION,
        "batch_id": BATCH_ID,
        "generated_at": generated_at,
        "evidence_level": E4,
        "final_status": "BATTLE_SEMANTIC = MODIFIER_APPLICATION_BRIDGE_07_PROOF",
        "runtime_layer_name": "TURNBASED_MODIFIER_APPLICATION_RUNTIME",
        "runtime_layer_shape": {
            "serialized_config_layer": (
                "TaskConfig DSL (RPG.GameCore.AddModifier type 22786, runtime "
                "type_reference 283020); ModifierName/TargetType/AliveOnly/"
                "LifeTime/Count/MaxLayer/LayerAddWhenStack/etc fields (E3)"
            ),
            "generated_runtime_layer": (
                "generated task executor JAJPDPAHFOA (type 54975): ctor slots + "
                "child task executors; OnTaskBegin target loop + application "
                "boundary; TaskState [+0x10] Ready/Success"
            ),
            "application_runtime_layer": (
                "TurnBasedAbilityComponent.TryAddModifierInstance -> "
                "TurnBasedModifierInstance -> AbilityComponent.AddModifierInstance "
                "-> _ModifierList ordered append"
            ),
            "modifier_instance_runtime": (
                "BaseModifierInstance (type 54598) / TurnBasedModifierInstance "
                "(type 55002) / AdventureModifierInstance (type 54579) / "
                "ModifierSequenceComposite (type 55003)"
            ),
        },
        "gameassembly": {
            "path": manifest["GameAssembly"]["path"],
            "sha256": manifest["GameAssembly"]["sha256"],
        },
        "primitives": primitives,
        "application_chains": _chain_evidence(),
        "persistent_reads": [
            "TurnBasedAbilityComponent [+0x10] owner entity (_OnInitOwnerRef)",
            "AbilityComponent [+0x38] _ModifierList",
            "List<T> [+0x10] items, [+0x18] count, [+0x1c] version",
            "BaseModifierInstance [+0x60] Name, [+0x7c] Count, [+0x80] State, [+0x88] StackingFlag, [+0x58] caster cache, [+0x48] lazy resolver",
            "TurnBasedModifierInstance [+0x100] source cache, [+0x288] Layer, [+0x2c4] CurrentLife, [+0x2e0]/[+0x270] MaxLayer slots, [+0xa0] ConfigRef, [+0x198] owner component",
        ],
        "persistent_writes": [
            "AbilityComponent [+0x38] list version [+0x1c] increment",
            "AbilityComponent [+0x38] list items [array + count*8 + 0x20] = modifier instance",
            "AbilityComponent [+0x38] list count [+0x18] increment",
            "BattleState canonical write: modifier_state_by_entity[owner runtime_id] ordered collection",
        ],
        "modifier_identity": [
            {
                "kind": "config_name_string",
                "native_source": "BaseModifierInstance.get_Name [+0x60] (M504746, 0xE4EEF10)",
                "config_metadata": "RPG.GameCore.AddModifier.ModifierName field (typeref 483870, E3)",
                "status": "PROVEN",
            },
            {
                "kind": "owner_entity",
                "native_source": "component [+0x10] owner entity -> list owner (_OnInitOwnerRef 0xE723BB0)",
                "logical_id": "GameEntity.RuntimeID (Batch 05 EntityRef)",
                "status": "PROVEN",
            },
            {
                "kind": "instance_ordinal",
                "native_source": "ordered append tail + GetIndexByModifier linear index (M520240)",
                "status": "PROVEN_ORDERED_APPEND_ORDINAL",
            },
            {
                "kind": "runtime_instance_id",
                "native_source": "not recovered in this round (object pointer only)",
                "status": "UNKNOWN",
            },
        ],
        "stack_policy": [
            {
                "scope": "AbilityComponent.AddModifierInstance",
                "policy": "PRESERVED_NO_DEDUPLICATION",
                "status": "PROVEN",
                "evidence": "no contains/search before append; version/count/items writes only",
            },
            {
                "scope": "TurnBasedAbilityComponent.TryAddModifierInstance",
                "policy": "DESTROY_AND_READD_PATH_OBSERVED_CONDITION_UNRESOLVED",
                "status": "UNKNOWN",
                "evidence": "GlobalFindModifierInstance (0xE43E2B0), FindModifierInstance (0xE72B410), Destroy (0xE7384B0) and fresh allocation path observed; exact duplicate condition not recovered",
            },
            {
                "scope": "canonical sandbox duplicate behavior",
                "policy": "UNKNOWN",
                "status": "STACK_POLICY_UNKNOWN",
            },
        ],
        "lifetime_semantics": [
            {
                "field": "TurnBasedModifierInstance.CurrentLife [+0x2c4]",
                "evidence": "getter E4 (M506329)",
                "policy": "FIELDS_PROVEN_EXPIRATION_TRIGGER_UNKNOWN",
            },
            {
                "field": "TurnBasedModifierInstance.Layer [+0x288] / MaxLayer",
                "evidence": "getters E4 (M506325/M506327)",
                "policy": "FIELDS_PROVEN_STACK_POLICY_UNKNOWN",
            },
            {
                "scope": "duration/round/turn expiration",
                "policy": "UNKNOWN",
            },
        ],
        "deferred_effects": [
            {
                "effect_id": "post_apply_instance_lifecycle_calls",
                "entry": "AbilityComponent.AddModifierInstance after append",
                "native_rva": "0xE431890",
                "classification": "POST_APPLY_LIFECYCLE_DEPENDENCY_REQUIRED",
                "observed": "two virtual interface dispatches on the appended instance guarded by bool arg",
            },
            {
                "effect_id": "try_add_modifier_instance_lifecycle",
                "entry": "TurnBasedAbilityComponent.TryAddModifierInstance",
                "native_rva": "0xE729500",
                "classification": "SKIP_LIFECYCLE_HEAVY",
                "observed": "duplicate find/destroy, property min/max arithmetic, _PostProcessAfterModifierAdd, _ProcessModifierRedd",
            },
            {
                "effect_id": "addmodifier_dynamic_parameter_evaluation",
                "entry": "JAJPDPAHFOA.OnTaskBegin dynamic values/strings",
                "native_rva": "0x161801C0",
                "classification": "SKIP_CONTEXT_HEAVY",
                "observed": "TaskContext.Evaluate and generated helper evaluators inside the 6592-byte body",
            },
            {
                "effect_id": "modifier_effect_semantics",
                "entry": "TurnBasedModifierInstance events/property stacks/DOT",
                "classification": "SEMANTIC_DEPENDENCY_REQUIRED",
                "observed": "event processor and property stack APIs exist on TurnBasedAbilityComponent; not entered",
            },
        ],
        "event_dependencies": [
            {
                "dependency": "AbilityAddModifier / AbilityPreAddModifier / LevelAfterAddModifier event rows",
                "status": "POST_APPLY_EVENT_DEPENDENCY_REQUIRED",
                "note": "application mutation itself is proven; notify/listener side effects are deferred",
            },
        ],
        "semantic_dependencies": [
            {
                "primitive_id": "battle.ir.target.select_task_action_target",
                "status": "SATISFIED_BATCH_05",
                "artifact": "target_selector_batch_05.json",
            },
            {
                "primitive_id": "battle.ir.target.collapse_single_or_null",
                "status": "SATISFIED_BATCH_05",
                "artifact": "target_selector_batch_05.json",
            },
            {
                "primitive_id": "battle.ir.entity.game_entity_runtime_id",
                "status": "SATISFIED_BATCH_05",
                "artifact": "target_selector_batch_05.json",
            },
            {
                "primitive_id": "battle.ir.action.task_state_read",
                "status": "SATISFIED_BATCH_06",
                "artifact": "action_execution_bridge_06.json",
            },
            {
                "primitive_id": "RPG.GameCore.TaskContext.EvaluateTarget dispatcher internals",
                "status": "SEMANTIC_DEPENDENCY_REQUIRED",
                "note": "chain uses the proven Batch 05 target leaves and the OnTaskBegin call-site evidence; dispatcher itself remains deferred",
            },
        ],
        "unknowns": [
            "TryAddModifierInstance param typeref 608873 name",
            "TryAddModifierInstance return typeref 231567 and AbilityComponent list element typeref 232380 canonical names (anchored by consumers, not resolved)",
            "BaseModifierInstance.State enum member ordinals (raw read only)",
            "BaseModifierInstance.StackingFlag enum member ordinals (raw read only)",
            "TurnBasedModifierInstance MaxLayer slot names [+0x2e0]/[+0x270]",
            "unregistered local helper 0xB429790 exact method identity (lazy entity resolver)",
            "OnTaskBegin 6592-byte full control flow beyond the accepted boundary projection",
            "exact duplicate modifier stack/refresh/replace policy",
            "duration expiration trigger semantics",
            "no E5 client-side runtime observation",
            "ModifierConfig numeric/config-id stable identity not recovered; canonical identity is name + owner + ordinal",
        ],
        "candidate_table": _candidate_table(),
        "first_round_report": {
            "commits_confirmed": [
                "b62910f sandbox: add action execution runtime",
                "1ec6983 reverse: recover action execution bridge",
                "74c5a59 sandbox: add target selector runtime batch",
                "7ae767f reverse: recover target selector semantic batch",
            ],
            "tracked_state": "clean; pre-existing untracked files (hsr_design_data_hashes.csv, hsr_design_data_inventory.csv, tools/reference/, tools/reverse/vendor/) left untouched",
            "add_modifier_task_config_identity": {
                "runtime_type": "RPG.GameCore.AddModifier",
                "type_index": ADD_MODIFIER_CONFIG_TYPE_INDEX,
                "serializer_method_index": 126119,
                "serializer_native_rva": "0x1CD26280",
                "runtime_type_reference": ADD_MODIFIER_CONFIG_TYPE_REFERENCE,
            },
            "add_modifier_executor_identity": {
                "runtime_type": "JAJPDPAHFOA",
                "type_index": ADD_MODIFIER_EXECUTOR_TYPE_INDEX,
                "ctor_method_index": 506046,
                "ctor_native_rva": "0x1617FE60",
                "on_task_begin_method_index": 506048,
                "on_task_begin_native_rva": "0x161801C0",
                "on_task_begin_gap_bytes": 6592,
            },
            "application_helper_chain": [
                "JAJPDPAHFOA.OnTaskBegin 0x161801C0 -> TaskContext.EvaluateTarget 0xE6F1530",
                "target loop -> TryAddModifierInstance 0xE729500 (call site 0x16181043)",
                "TryAddModifierInstance -> TurnBasedModifierInstance ctor 0xE77EB00 (call site 0xE7298AE)",
                "TryAddModifierInstance -> AbilityComponent.AddModifierInstance 0xE431890 (call site 0xE729C2E)",
                "AddModifierInstance -> _ModifierList append at component [+0x38]",
            ],
            "modifier_runtime_family_scale": {
                "modifier_config_factory_variants": 4,
                "base_modifier_instance": "type 54598, 51 methods, 24 fields",
                "turn_based_modifier_instance": "type 55002, 243 methods, 109 fields",
                "adventure_modifier_instance": "type 54579, 45 methods, 24 fields",
                "modifier_sequence_composite": "type 55003, 17 methods, 14 fields",
                "ability_component_container": "type 56973, 50 methods, 15 fields",
                "turn_based_ability_component": "type 55009, 380 methods, 123 fields",
            },
            "persistent_owner_container_candidates": [
                "RPG.GameCore.AbilityComponent._ModifierList (field E3; native slot [+0x38] E4)",
                "RPG.GameCore.TurnBasedAbilityComponent [+0x10] owner entity (_OnInitOwnerRef E4)",
                "RPG.GameCore.TurnBasedModifierInstance [+0x198] owner component (E4)",
            ],
            "plausible_method_count": 28 + 1 + 1 + 6 + 22 + 10 + 5,
            "shortlist_count": len(_candidate_table()),
            "primary_chain": "add_modifier_action_application_chain",
            "heavy_dependency_skip_list": [
                "TryAddModifierInstance lifecycle/stack dispatcher (3424B)",
                "TurnBasedModifierInstance ctor / Destroy lifecycle",
                "AbilityStatic.GlobalFindModifierInstance global search",
                "_PostProcessAfterModifierAdd / _ProcessModifierRedd",
                "AddModifier dynamic value/string evaluator helpers",
                "modifier event processors and property stacks",
            ],
            "real_runtime_layer_name": (
                "TURNBASED_MODIFIER_APPLICATION_RUNTIME: the requested "
                "'Modifier application' layer is TurnBasedAbilityComponent."
                "TryAddModifierInstance -> TurnBasedModifierInstance -> "
                "AbilityComponent._ModifierList. There is no standalone "
                "ModifierManager class in the recovered path."
            ),
        },
        "modifier_runtime_bridge": {
            "path": "data/raw/4.4.54/modifier_runtime_bridge_07.json",
            "status": "NO_GENERATED_CONFIG_TO_INSTANCE_BRIDGE",
            "evidence": (
                "Unlike Target/Action, there is no generated modifier class per "
                "config type_reference. TryAddModifierInstance receives "
                "(string, ModifierConfig typeref 104288, ability, param, bool) "
                "and creates a runtime TurnBasedModifierInstance; config identity "
                "flows through the Name slot, not a config-type-ref class match."
            ),
        },
        "config_runtime_bridge": {
            "path": "data/raw/4.4.54/action_config_runtime_bridge_06.json",
            "matched_add_modifier_row": addmodifier_bridge_row,
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    sha = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    print(f"wrote {OUT_PATH}")
    print(f"sha256={sha}")
    print(f"primitives={len(primitives)} chains={len(artifact['application_chains'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
