#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Action Execution Bridge 06 semantic artifact (4.4.54).

Recovered runtime shape (the prompt-level name "Action Execution" maps to the
game's real generated-task-executor runtime; names below follow evidence):

    serialized TaskConfig DSL family (MGMEGEDLMAK serializer identity)
      -> generated task executor class (.ctor(TaskContext, config))
      -> OnTaskBegin / OnTaskReset / Tick / Dispose
      -> TaskState (+0x10): Ready=0x7777 Executing=0x8888 Success=0x9999 Fail=0xAAAA
      -> target/value dependencies (Batch 04/05 reuse)
      -> TaskContext / BattleState / notify effects (deferred where heavy)

This script only assembles evidence already discovered by
``action_execution_discovery.py`` / ``build_action_config_runtime_bridge.py`` /
``action_execution_shortlist.py``.  It does not re-recover metadata.
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
from semantic_method_xrefs import load_method_rva_index  # noqa: E402

BRIDGE_PATH = REPO / "data" / "raw" / "4.4.54" / "action_config_runtime_bridge_06.json"
SHORTLIST_PATH = REPO / "data" / "raw" / "4.4.54" / "action_execution_shortlist_06.json"
XREFS_PATH = REPO / "data" / "raw" / "4.4.54" / "target_selector_xrefs_05.json"
OUT_PATH = REPO / "data" / "semantics" / "4.4.54" / "action_execution_bridge_06.json"

GAME_VERSION = "4.4.54"
BATCH_ID = "ACTION_EXECUTION_BRIDGE_06"
SCHEMA = "battle_semantics_batch/1"
E4 = "E4_STATIC_MACHINE_CODE"

TASK_CONTEXT_TYPE_REFERENCE = 417116  # anchored by Batch 05 evaluator parameters

# method_index -> canonical plan for every accepted primitive
PRIMITIVE_PLANS = [
    {
        "primitive_id": "battle.ir.action.task_executor_init",
        "semantic_name": "GeneratedTaskExecutorInit",
        "description": (
            "Generated task executor ctor for RPG.GameCore.Obsolete "
            "(HDDPKFNLMEG..ctor): stores arg0 (TaskContext) at executor [+0x20], "
            "arg1 (task config) at executor [+0x18] and sets TaskState [+0x10] = "
            "Ready (0x7777). No config/context field is read. Canonical sandbox "
            "materializes the config reference and TaskState and never stores the "
            "live ExecutionContext (reference-only native slot)."
        ),
        "inputs": [{"name": "config", "type": "action_config_ref"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": ["task_context_slot", "task_config_slot", "task_state"],
        "result": "task_execution",
        "source_runtime_type": "HDDPKFNLMEG",
        "source_method": ".ctor",
        "method_index": 517404,
        "projection": "FIRST_RET",
        "pseudocode": [
            "TaskExecution TaskExecutorInit(this, TaskContext ctx, TaskConfig config):",
            "    this[+0x20] = ctx                # TaskContext slot (arg0)",
            "    this[+0x18] = config             # task config slot (arg1)",
            "    this[+0x10] = TaskState.Ready     # 0x7777",
        ],
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "native stores pointers without validation; null ctx/config stored as-is",
        "ordering_behavior": "single initialization; no ordering",
        "determinism": "DETERMINISTIC",
    },
    {
        "primitive_id": "battle.ir.action.task_begin_immediate_success",
        "semantic_name": "GeneratedTaskBeginImmediateSuccess",
        "description": (
            "Generated task executor OnTaskBegin for RPG.GameCore.Obsolete "
            "(HDDPKFNLMEG.OnTaskBegin): write TaskState [+0x10] = Success "
            "(0x9999) and return. This is the real empty/no-op action DSL leaf: "
            "an Obsolete task config compiles to an executor whose only "
            "observable effect is the deterministic Success transition."
        ),
        "inputs": [{"name": "execution", "type": "task_execution"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": ["task_state"],
        "result": "task_execution",
        "source_runtime_type": "HDDPKFNLMEG",
        "source_method": "OnTaskBegin",
        "method_index": 517406,
        "projection": "FIRST_RET",
        "pseudocode": [
            "TaskExecution TaskBeginImmediateSuccess(TaskExecution execution):",
            "    execution.task_state = TaskState.Success   # native: [+0x10] = 0x9999",
            "    return execution",
        ],
        "branch_conditions": [
            "IL2CPP class-init gate (one-time runtime infrastructure, excluded from semantics)",
        ],
        "required_callees": ["none"],
        "null_behavior": "missing executor object -> native null-instance throw; no config/ctx read",
        "ordering_behavior": "single terminal transition; no ordering",
        "determinism": "DETERMINISTIC",
    },
    {
        "primitive_id": "battle.ir.action.task_reset_ready",
        "semantic_name": "GeneratedTaskResetReady",
        "description": (
            "Generated task executor OnTaskReset for RPG.GameCore.Obsolete "
            "(HDDPKFNLMEG.OnTaskReset): write TaskState [+0x10] = Ready "
            "(0x7777) and return. Only the state field is written; this exact "
            "leaf touches no other executor slot."
        ),
        "inputs": [{"name": "execution", "type": "task_execution"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": ["task_state"],
        "result": "task_execution",
        "source_runtime_type": "HDDPKFNLMEG",
        "source_method": "OnTaskReset",
        "method_index": 517407,
        "projection": "FIRST_RET",
        "pseudocode": [
            "TaskExecution TaskResetReady(TaskExecution execution):",
            "    execution.task_state = TaskState.Ready    # native: [+0x10] = 0x7777",
            "    return execution",
        ],
        "branch_conditions": [
            "IL2CPP class-init gate (one-time runtime infrastructure, excluded from semantics)",
        ],
        "required_callees": ["none"],
        "null_behavior": "missing executor object -> native null-instance throw",
        "ordering_behavior": "single reset transition; no ordering",
        "determinism": "DETERMINISTIC",
    },
    {
        "primitive_id": "battle.ir.action.task_state_read",
        "semantic_name": "GeneratedTaskBaseTaskStateAccessor",
        "description": (
            "Generated task-executor base class accessor "
            "(GELIALJDFBL.MDFBKGOJOJI): return the raw int32 TaskState stored "
            "at executor [+0x10]. The obfuscated method name is anchored by the "
            "TaskState constants (0x7777/0x8888/0x9999/0xAAAA) written by every "
            "recovered lifecycle leaf and by GELIALJDFBL.GetConfig returning "
            "TaskConfig runtime type_reference 22744."
        ),
        "inputs": [{"name": "execution", "type": "task_execution"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": ["task_state"],
        "action_writes": [],
        "result": "task_state",
        "source_runtime_type": "GELIALJDFBL",
        "source_method": "MDFBKGOJOJI",
        "method_index": 505903,
        "projection": "FIRST_RET",
        "pseudocode": [
            "task_state TaskStateRead(TaskExecution execution):",
            "    return execution.task_state         # native: eax = [this + 0x10]",
        ],
        "branch_conditions": [
            "IL2CPP class-init gate (one-time runtime infrastructure, excluded from semantics)",
        ],
        "required_callees": ["none"],
        "null_behavior": "missing executor object -> native null-instance throw",
        "ordering_behavior": "single scalar read; no ordering",
        "determinism": "DETERMINISTIC",
    },
    {
        "primitive_id": "battle.ir.action.task_executor_base_ready_init",
        "semantic_name": "GeneratedTaskBaseReadyInit",
        "description": (
            "Generated task-executor base ctor (GELIALJDFBL..ctor): set "
            "TaskState [+0x10] = Ready (0x7777). This is the shared base-state "
            "initialization every generated executor inherits; config/context "
            "slots are written by the concrete generated ctor."
        ),
        "inputs": [],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": ["task_state"],
        "result": "task_execution",
        "source_runtime_type": "GELIALJDFBL",
        "source_method": ".ctor",
        "method_index": 505902,
        "projection": "FIRST_RET",
        "pseudocode": [
            "TaskExecution TaskBaseReadyInit():",
            "    execution.task_state = TaskState.Ready   # native: [+0x10] = 0x7777",
            "    return execution",
        ],
        "branch_conditions": ["none"],
        "required_callees": ["none"],
        "null_behavior": "missing receiver -> native null-instance throw",
        "ordering_behavior": "single initialization; no ordering",
        "determinism": "DETERMINISTIC",
    },
    {
        "primitive_id": "battle.ir.action.task_begin_select_single_target",
        "semantic_name": "GeneratedTaskBeginSelectSingleTarget",
        "description": (
            "Generated task executor OnTaskBegin for "
            "RPG.GameCore.SwitchHandItemSetBreathingLight "
            "(CPHGMLEAPJL.OnTaskBegin): set TaskState [+0x10] = Executing "
            "(0x8888), evaluate the config target slot through "
            "TaskContext.EvaluateSingleTarget (Batch 05 collapse semantics), "
            "store the resulting single entity at executor [+0x28], then "
            "tailcall Tick with deltaTime=0. Canonical sandbox receives the "
            "already-evaluated ordered TargetSet and applies the proven "
            "Batch 05 collapse; the deferred Tick gameplay leaf is recorded "
            "separately."
        ),
        "inputs": [
            {"name": "execution", "type": "task_execution"},
            {"name": "targets", "type": "TargetSet"},
        ],
        "context_reads": ["targets"],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": ["task_state"],
        "action_writes": ["task_state", "selected_target", "next_phase"],
        "result": "task_execution",
        "source_runtime_type": "CPHGMLEAPJL",
        "source_method": "OnTaskBegin",
        "method_index": 498176,
        "projection": "TAILCALL",
        "pseudocode": [
            "TaskExecution TaskBeginSelectSingleTarget(TaskExecution execution, TargetSet targets):",
            "    execution.task_state = TaskState.Executing   # native: [+0x10] = 0x8888",
            "    entity = EvaluateSingleTarget(ctx, config.TargetType, mask=0xffff)",
            "            # Batch 05: collapse_required_single_or_null(targets)",
            "    execution.selected_target = entity           # native: [+0x28] = rax",
            "    execution.next_phase = 'Tick'                # native: tailcall Tick(this, dt=0)",
            "    return execution",
        ],
        "branch_conditions": [
            "IL2CPP class-init gate (one-time runtime infrastructure)",
            "ctx slot [+0x20] null -> throw",
            "config slot [+0x18] null -> throw",
            "EvaluateSingleTarget: 0 or >=2 targets -> null (Batch 05)",
            "tailcall Tick with dt=0 after storing the selected target",
        ],
        "required_callees": [
            "0x18E6D5830 TaskContext.EvaluateSingleTarget (SEMANTIC_DEPENDENCY_SATISFIED_BATCH_05)",
            "0x18DD772E0 CPHGMLEAPJL.Tick (tailcall, gameplay leaf DEFERRED_ACTION_LEAF)",
        ],
        "null_behavior": "null ctx/config slots -> throw; null/0/2+ target results -> selected_target=null",
        "ordering_behavior": "single-target projection; Batch 05 ordered-list collapse",
        "determinism": "DETERMINISTIC",
    },
    {
        "primitive_id": "battle.ir.action.task_reset_ready_clear_selected_target",
        "semantic_name": "GeneratedTaskResetReadyClearTarget",
        "description": (
            "Generated task executor OnTaskReset for "
            "RPG.GameCore.SwitchHandItemSetBreathingLight "
            "(CPHGMLEAPJL.OnTaskReset): write TaskState [+0x10] = Ready "
            "(0x7777) and clear the selected-target slot [+0x28] = null. "
            "This is the target-aware reset leaf paired with "
            "task_begin_select_single_target."
        ),
        "inputs": [{"name": "execution", "type": "task_execution"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "action_reads": [],
        "action_writes": ["task_state", "selected_target"],
        "result": "task_execution",
        "source_runtime_type": "CPHGMLEAPJL",
        "source_method": "OnTaskReset",
        "method_index": 498177,
        "projection": "FIRST_RET",
        "pseudocode": [
            "TaskExecution TaskResetReadyClearTarget(TaskExecution execution):",
            "    execution.task_state = TaskState.Ready     # native: [+0x10] = 0x7777",
            "    execution.selected_target = null           # native: [+0x28] = 0",
            "    return execution",
        ],
        "branch_conditions": [
            "IL2CPP class-init gate (one-time runtime infrastructure, excluded from semantics)",
        ],
        "required_callees": ["none"],
        "null_behavior": "missing executor object -> native null-instance throw",
        "ordering_behavior": "single reset transition; no ordering",
        "determinism": "DETERMINISTIC",
    },
]


def _load_method_records() -> dict[int, dict]:
    wanted = {plan["method_index"] for plan in PRIMITIVE_PLANS}
    records: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        if rec["method_index"] in wanted:
            records[rec["method_index"]] = rec
    if len(records) != len(wanted):
        missing = wanted - set(records)
        raise RuntimeError(f"missing method records: {sorted(missing)}")
    return records


_TYPE_MAP_CACHE: dict[int, dict] | None = None
_METHODS_BY_TYPE_CACHE: dict[int, list[dict]] | None = None


def _type_map() -> dict[int, dict]:
    global _TYPE_MAP_CACHE
    if _TYPE_MAP_CACHE is None:
        _TYPE_MAP_CACHE = {
            rec["type_index"]: rec
            for rec in iter_records(NORMALIZED_BASE / "types.json")
        }
    return _TYPE_MAP_CACHE


def _methods_by_type() -> dict[int, list[dict]]:
    global _METHODS_BY_TYPE_CACHE
    if _METHODS_BY_TYPE_CACHE is None:
        out: dict[int, list[dict]] = {}
        for rec in iter_records(NORMALIZED_BASE / "methods.json"):
            out.setdefault(rec["declaring_type_index"], []).append(rec)
        _METHODS_BY_TYPE_CACHE = out
    return _METHODS_BY_TYPE_CACHE


def _project_body(pe, rva: int, gap: int, projection: str) -> bytes:
    raw, decoded = disasm_window(pe, rva, gap)
    if projection == "FIRST_RET":
        first_ret = next((ins for ins in decoded if ins["mnemonic"] == "ret"), None)
        if first_ret is None:
            raise RuntimeError(f"no ret in window at 0x{rva:X}")
        end = first_ret["rva"] + first_ret["size"] - rva
        return raw[:end]
    if projection == "TAILCALL":
        # Normal path ends at the first unconditional jmp (tailcall to the next
        # phase).  Instrumentation/class-init tails follow that jmp.
        first_jmp = next((ins for ins in decoded if ins["mnemonic"] == "jmp"), None)
        if first_jmp is None:
            raise RuntimeError(f"no tailcall jmp in window at 0x{rva:X}")
        end = first_jmp["rva"] + first_jmp["size"] - rva
        return raw[:end]
    raise RuntimeError(f"unknown projection {projection}")


def _load_bridge_rows() -> list[dict]:
    data = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))
    return data["matched_rows"]


def _bridge_for_config(bridge_rows: list[dict], cfg_name: str) -> dict:
    matches = [r for r in bridge_rows if cfg_name in r["config_candidates"]]
    if len(matches) != 1:
        raise RuntimeError(f"expected one executor row for {cfg_name}, got {len(matches)}")
    return matches[0]


def _config_identity(cfg_name: str) -> dict:
    type_map = _type_map()
    config_type_index = next(
        (
            ti
            for ti, rec in type_map.items()
            if rec["full_name"] == cfg_name
        ),
        None,
    )
    if config_type_index is None:
        raise RuntimeError(f"config type not found: {cfg_name}")
    mg_method = next(
        (
            rec
            for rec in _methods_by_type().get(config_type_index, [])
            if rec["name"] == "MGMEGEDLMAK"
        ),
        None,
    )
    if mg_method is None:
        raise RuntimeError(f"config serializer not found: {cfg_name}.MGMEGEDLMAK")
    refs = load_parameter_refs({mg_method["method_index"]}).get(
        mg_method["method_index"], []
    )
    if len(refs) != 2:
        raise RuntimeError(f"unexpected serializer params for {cfg_name}: {refs}")
    return {
        "runtime_type": cfg_name,
        "type_index": config_type_index,
        "serializer_method_index": mg_method["method_index"],
        "serializer_native_rva": mg_method.get("native_rva"),
        "runtime_type_reference": refs[1]["type_reference"],
    }


def _execution_chains(bridge_rows: list[dict]) -> list[dict]:
    chains = []

    obsolete = _config_identity("RPG.GameCore.Obsolete")
    obsolete_row = _bridge_for_config(bridge_rows, "RPG.GameCore.Obsolete")
    obsolete_methods = {m["name"]: m for m in obsolete_row["execution_methods"]}
    chains.append(
        {
            "chain_id": "obsolete_empty_action_chain",
            "status": "E4_CHAIN_CLOSED",
            "config": {
                "runtime_type": obsolete["runtime_type"],
                "type_index": obsolete["type_index"],
                "serializer_method_index": obsolete["serializer_method_index"],
                "serializer_native_rva": (
                    f"0x{obsolete['serializer_native_rva']:X}"
                    if isinstance(obsolete["serializer_native_rva"], int)
                    else None
                ),
                "runtime_type_reference": obsolete["runtime_type_reference"],
                "fields": ["Message (string, serializer-only; never read by the leaf)"],
            },
            "runtime_bridge": {
                "kind": "TYPE_REFERENCE_MATCH",
                "evidence": (
                    "generated executor .ctor second parameter type_reference == "
                    "RPG.GameCore.Obsolete.MGMEGEDLMAK second parameter "
                    f"type_reference ({obsolete['runtime_type_reference']})"
                ),
                "executor_runtime_type": obsolete_row["executor_type"],
                "executor_type_index": obsolete_row["executor_type_index"],
            },
            "steps": [
                {
                    "step": 1,
                    "role": "config -> generated executor",
                    "method": ".ctor",
                    "method_index": obsolete_row["ctor"]["method_index"],
                    "native_rva": (
                        f"0x{obsolete_row['ctor']['native_rva']:X}"
                        if isinstance(obsolete_row["ctor"]["native_rva"], int)
                        else None
                    ),
                    "primitive_id": "battle.ir.action.task_executor_init",
                },
                {
                    "step": 2,
                    "role": "execution method",
                    "method": "OnTaskBegin",
                    "method_index": obsolete_methods["OnTaskBegin"]["method_index"],
                    "native_rva": (
                        f"0x{obsolete_methods['OnTaskBegin']['native_rva']:X}"
                        if isinstance(obsolete_methods["OnTaskBegin"]["native_rva"], int)
                        else None
                    ),
                    "primitive_id": "battle.ir.action.task_begin_immediate_success",
                },
                {
                    "step": 3,
                    "role": "observable deterministic effect",
                    "effect": "TaskState [+0x10] = Success (0x9999); no context/state write",
                },
            ],
        }
    )

    reset_chain = dict(chains[0])
    reset_chain["chain_id"] = "obsolete_empty_action_reset_chain"
    reset_chain["steps"] = [
        {
            "step": 1,
            "role": "generated executor lifecycle reset",
            "method": "OnTaskReset",
            "method_index": obsolete_methods["OnTaskReset"]["method_index"],
            "native_rva": (
                f"0x{obsolete_methods['OnTaskReset']['native_rva']:X}"
                if isinstance(obsolete_methods["OnTaskReset"]["native_rva"], int)
                else None
            ),
            "primitive_id": "battle.ir.action.task_reset_ready",
        },
        {
            "step": 2,
            "role": "observable deterministic effect",
            "effect": "TaskState [+0x10] = Ready (0x7777)",
        },
    ]
    chains.append(reset_chain)

    switch_cfg = _config_identity("RPG.GameCore.SwitchHandItemSetBreathingLight")
    switch_row = _bridge_for_config(
        bridge_rows, "RPG.GameCore.SwitchHandItemSetBreathingLight"
    )
    switch_methods = {m["name"]: m for m in switch_row["execution_methods"]}
    chains.append(
        {
            "chain_id": "target_select_executor_chain",
            "status": "E4_CHAIN_TARGET_STORE_CLOSED_TICK_LEAF_DEFERRED",
            "config": {
                "runtime_type": switch_cfg["runtime_type"],
                "type_index": switch_cfg["type_index"],
                "serializer_method_index": switch_cfg["serializer_method_index"],
                "serializer_native_rva": (
                    f"0x{switch_cfg['serializer_native_rva']:X}"
                    if isinstance(switch_cfg["serializer_native_rva"], int)
                    else None
                ),
                "runtime_type_reference": switch_cfg["runtime_type_reference"],
                "fields": ["TargetType (target config slot read at +0x18)", "Enable", "EnableItem"],
            },
            "runtime_bridge": {
                "kind": "TYPE_REFERENCE_MATCH",
                "evidence": (
                    "generated executor .ctor second parameter type_reference == "
                    "config MGMEGEDLMAK second parameter type_reference "
                    f"({switch_cfg['runtime_type_reference']})"
                ),
                "executor_runtime_type": switch_row["executor_type"],
                "executor_type_index": switch_row["executor_type_index"],
            },
            "steps": [
                {
                    "step": 1,
                    "role": "task state -> Executing",
                    "method": "OnTaskBegin",
                    "method_index": switch_methods["OnTaskBegin"]["method_index"],
                    "native_rva": (
                        f"0x{switch_methods['OnTaskBegin']['native_rva']:X}"
                        if isinstance(switch_methods["OnTaskBegin"]["native_rva"], int)
                        else None
                    ),
                    "primitive_id": "battle.ir.action.task_begin_select_single_target",
                },
                {
                    "step": 2,
                    "role": "target input (Batch 05 reuse)",
                    "dependency": "battle.ir.target.collapse_required_single_or_null",
                    "status": "SATISFIED_BATCH_05",
                },
                {
                    "step": 3,
                    "role": "transient write",
                    "effect": "executor [+0x28] = selected target (EntityRef|null)",
                },
                {
                    "step": 4,
                    "role": "next phase",
                    "effect": "tailcall Tick(this, dt=0) -> DEFERRED_ACTION_LEAF (component field write)",
                },
            ],
        }
    )

    turn_cfg = _config_identity("RPG.GameCore.SetCurrentTurnActionEntity")
    turn_row = _bridge_for_config(bridge_rows, "RPG.GameCore.SetCurrentTurnActionEntity")
    turn_methods = {m["name"]: m for m in turn_row["execution_methods"]}
    chains.append(
        {
            "chain_id": "battle_current_turn_action_chain",
            "status": "E4_STRUCTURE_SUPPORTED_PERSISTENT_DEPENDENCY",
            "config": {
                "runtime_type": turn_cfg["runtime_type"],
                "type_index": turn_cfg["type_index"],
                "serializer_method_index": turn_cfg["serializer_method_index"],
                "serializer_native_rva": (
                    f"0x{turn_cfg['serializer_native_rva']:X}"
                    if isinstance(turn_cfg["serializer_native_rva"], int)
                    else None
                ),
                "runtime_type_reference": turn_cfg["runtime_type_reference"],
                "fields": ["TargetType (target config slot read at +0x18)"],
            },
            "runtime_bridge": {
                "kind": "TYPE_REFERENCE_MATCH",
                "evidence": (
                    "generated executor .ctor second parameter type_reference == "
                    "config MGMEGEDLMAK second parameter type_reference "
                    f"({turn_cfg['runtime_type_reference']})"
                ),
                "executor_runtime_type": turn_row["executor_type"],
                "executor_type_index": turn_row["executor_type_index"],
            },
            "steps": [
                {
                    "step": 1,
                    "role": "task state -> Success before gameplay leaf",
                    "method": "OnTaskBegin",
                    "method_index": turn_methods["OnTaskBegin"]["method_index"],
                    "native_rva": (
                        f"0x{int(turn_methods['OnTaskBegin']['native_rva']):X}"
                        if isinstance(turn_methods["OnTaskBegin"]["native_rva"], int)
                        else None
                    ),
                    "effect": "TaskState [+0x10] = Success (0x9999)",
                },
                {
                    "step": 2,
                    "role": "target input (Batch 05 reuse)",
                    "dependency": "battle.ir.target.collapse_single_or_null",
                    "status": "SATISFIED_BATCH_05",
                    "native_call": "0x18E43E160 AbilityStatic.GetTaskSingleTarget",
                },
                {
                    "step": 3,
                    "role": "gameplay leaf",
                    "dependency": "RPG.GameCore.TurnBasedGameMode.SetCurrentTurnActionEntity",
                    "method_index": 499719,
                    "native_rva": "0xE75F700",
                    "status": "PERSISTENT_STATE_DEPENDENCY_REQUIRED",
                    "observed_writes": (
                        "[mode+0x2FA]=0, [mode+0x318]=0 and conditional "
                        "[mode+0x2C9]/[mode+0x2CA]=0 when the new entity differs"
                    ),
                },
            ],
        }
    )
    return chains


def _candidate_table(bridge_rows: list[dict]) -> list[dict]:
    del bridge_rows  # bridge facts live in execution_chains / config_runtime_bridge
    method_records = _load_method_records()
    rows = [
        {
            "method_index": p["method_index"],
            "candidate": f"{p['source_runtime_type']}.{p['source_method']}",
            "native_rva": f"0x{method_records[p['method_index']]['native_rva']:X}",
            "classification": "ACCEPT",
            "reason": p["description"],
        }
        for p in PRIMITIVE_PLANS
    ]

    deferred_rows = [
        {
            "method_index": 505873,
            "candidate": "RPG.GameCore.TaskContext.EvaluateTarget",
            "native_rva": "0xE6F1530",
            "classification": "SKIP_CONTEXT_HEAVY",
            "reason": "target selector registry dispatcher (544 rel32 call sites); Batch 05 leaves reused instead",
        },
        {
            "method_index": 505813,
            "candidate": "SequenceConfig generated executor step helper (JDHDNAFAKCN)",
            "native_rva": "0xB526340",
            "classification": "DISPATCHER_STRUCTURE_SUPPORTED",
            "reason": "ordered child-executor iteration proven at E4 shape (Ready->OnTaskBegin, Success/Fail early stop, Tick advances); 2080-byte helper with vtable/global dispatch deferred",
        },
        {
            "method_index": 535645,
            "candidate": "FNGLHFPADGA.NICNFGOAOHI (TriggerHitTarget leaf)",
            "native_rva": "0x15547AB0",
            "classification": "SKIP_CONTEXT_HEAVY",
            "reason": "enters hit/damage target processing; 656-byte body beyond leaf budget",
        },
        {
            "method_index": 538414,
            "candidate": "RPG.Client.NotifyManager.Notify (ForbidBattleConditionOnStart / SetBattleTargetMultiTargetSwitch leaves)",
            "native_rva": "0xD994450",
            "classification": "SKIP_EVENT_SYSTEM",
            "reason": "task effect is client notify event dispatch; event system excluded this round",
        },
        {
            "method_index": 499719,
            "candidate": "RPG.GameCore.TurnBasedGameMode.SetCurrentTurnActionEntity",
            "native_rva": "0xE75F700",
            "classification": "PERSISTENT_STATE_DEPENDENCY_REQUIRED",
            "reason": "persistent turn-mode field writes proven at E4 shape; field identities +0x100/+0x2FA/+0x318/+0x2C9/+0x2CA not resolved",
        },
        {
            "method_index": 498175,
            "candidate": "CPHGMLEAPJL.Tick (SwitchHandItemSetBreathingLight gameplay leaf)",
            "native_rva": "0xDD772E0",
            "classification": "COMPONENT_STATE_DEPENDENCY_REQUIRED",
            "reason": "writes ctx bytes to component [+0x44] (class global 0x983DA48); component type/field semantic unresolved",
        },
        {
            "method_index": 508633,
            "candidate": "OMBLCOFIDOA.LAPFHJPBOED / NOICODFGEIE (SetDynamicValueByBattleTargetParam)",
            "native_rva": "0xC007800",
            "classification": "SKIP_CONTEXT_HEAVY",
            "reason": "TaskContext string-hash dictionary setter; dispatcher exceeds budget",
        },
        {
            "method_index": 517404,
            "candidate": "RPG.GameCore.Obsolete serializer family",
            "native_rva": None,
            "classification": "SKIP_SERIALIZATION",
            "reason": "config identity via bridge; execution recovered in generated executor",
        },
        {
            "method_index": 517405,
            "candidate": "HDDPKFNLMEG.Dispose (Obsolete)",
            "native_rva": "0x15886B50",
            "classification": "SKIP_WRAPPER",
            "reason": "empty normal path (no slots written); lifecycle no-op",
        },
        {
            "method_index": 517408,
            "candidate": "HDDPKFNLMEG.Tick (Obsolete)",
            "native_rva": "0x15886C30",
            "classification": "SKIP_WRAPPER",
            "reason": "empty normal path after immediate Success; no further action",
        },
        {
            "method_index": 531457,
            "candidate": "RPG.GameCore.BaseLevelTask.OnTaskBegin",
            "native_rva": "0xE4F0B90",
            "classification": "SKIP_CONTEXT_HEAVY",
            "reason": "named level-task base; dispatcher-shaped body not needed for the recovered generated-runtime",
        },
    ]
    # Fill Obsolete serializer rva.
    obsolete_identity = _config_identity("RPG.GameCore.Obsolete")
    for row in deferred_rows:
        if "serializer family" in row["candidate"]:
            row["native_rva"] = (
                f"0x{obsolete_identity['serializer_native_rva']:X}"
            )
            row["method_index"] = obsolete_identity["serializer_method_index"]
    rows.extend(deferred_rows)
    return rows


def main() -> int:
    manifest = load_manifest()
    pe = load_pe()
    rvas_sorted, _methods = load_method_rva_index()
    method_records = _load_method_records()
    param_refs = load_parameter_refs(
        {plan["method_index"] for plan in PRIMITIVE_PLANS}
    )
    bridge_rows = _load_bridge_rows()
    shortlist = json.loads(SHORTLIST_PATH.read_text(encoding="utf-8"))
    xrefs = json.loads(XREFS_PATH.read_text(encoding="utf-8"))
    bridge_summary = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))

    gameassembly = manifest["GameAssembly"]
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    primitives = []
    for plan in PRIMITIVE_PLANS:
        mi = plan["method_index"]
        method = method_records[mi]
        rva = method["native_rva"]
        if not isinstance(rva, int):
            raise RuntimeError(f"method {mi} has no direct RVA")
        idx = rvas_sorted.index(rva)
        next_rva = rvas_sorted[idx + 1] if idx + 1 < len(rvas_sorted) else rva + 4096
        gap = next_rva - rva
        raw_window, full_decoded = disasm_window(pe, rva, gap)
        body = _project_body(pe, rva, gap, plan["projection"])
        _, body_decoded = disasm_window(pe, rva, len(body))
        if not body_decoded:
            raise RuntimeError(f"empty body projection at 0x{rva:X}")
        body_sha = hashlib.sha256(body).hexdigest()
        branch_count = sum(
            1
            for ins in body_decoded
            if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
        )
        call_count = sum(1 for ins in body_decoded if ins["mnemonic"] == "call")
        jmp_count = sum(1 for ins in body_decoded if ins["mnemonic"] == "jmp")
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
            "body_window_kind": (
                "NORMAL_PATH_FIRST_RET_PROJECTION"
                if plan["projection"] == "FIRST_RET"
                else "NORMAL_PATH_FIRST_TAILCALL_PROJECTION"
            ),
            "body_length_bytes": len(body),
            "body_sha256": body_sha,
            "code_table_slot_va": f"0x{pe.image_base + rva:X}",
            "code_table_slot_index": mi,
            "image_base": f"0x{pe.image_base:X}",
            "mapping_kind": method["mapping_kind"],
            "full_gap_to_next_method": gap,
            "instruction_count": len(body_decoded),
            "conditional_branch_count": branch_count,
            "direct_call_count": call_count,
            "direct_jump_count": jmp_count,
            "disassembly": [line_for(ins) for ins in body_decoded],
            "full_gap_disassembly": [line_for(ins) for ins in full_decoded],
        }
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
            "determinism": plan["determinism"],
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
            "determinism_note": (
                "task-state transitions are constant writes; no PRNG / clock / "
                "context dependency in the accepted leaves"
            ),
        }
        primitives.append(primitive)

    execution_chains = _execution_chains(bridge_rows)
    candidate_table = _candidate_table(bridge_rows)

    # First-round discovery facts (item 13 of the session plan), machine-readable.
    eval_target_refs = next(
        t for t in xrefs["targets"] if t["native_rva"] == "0xE6F1530"
    )
    eval_single_refs = next(
        t for t in xrefs["targets"] if t["native_rva"] == "0xE6D5830"
    )
    first_round_report = {
        "commits_confirmed": [
            "74c5a59 sandbox: add target selector runtime batch",
            "7ae767f reverse: recover target selector semantic batch",
            "dc668d7 sandbox: add predicate evaluation runtime",
            "8d4319e reverse: recover predicate evaluation bridge",
        ],
        "tracked_state": "clean; pre-existing untracked files left untouched",
        "config_family_count": bridge_summary["config_family_count"],
        "config_runtime_type_ref_count": bridge_summary["config_runtime_type_ref_count"],
        "generated_executor_class_count": bridge_summary["executor_class_count"],
        "generated_executor_type_ref_count": bridge_summary["executor_type_ref_count"],
        "matched_bridge_rows": len(bridge_summary["matched_rows"]),
        "unmatched_executor_type_refs": len(bridge_summary["unmatched_executor_type_refs"]),
        "config_to_executor_bridge": "YES_TYPE_REFERENCE_MATCH_E3_METADATA_PLUS_E4_CTOR_STORES",
        "task_context_action_side_callers": {
            "EvaluateTarget_rel32_call_sites": eval_target_refs["ref_counts"]["rel32"],
            "EvaluateSingleTarget_rel32_call_sites": eval_single_refs["ref_counts"]["rel32"],
            "OnTaskBegin_callers_of_EvaluateTarget": sum(
                1
                for r in eval_target_refs["rel32_refs"]
                if (r.get("caller_method") or {}).get("name") == "OnTaskBegin"
            ),
            "OnTaskBegin_callers_of_EvaluateSingleTarget": sum(
                1
                for r in eval_single_refs["rel32_refs"]
                if (r.get("caller_method") or {}).get("name") == "OnTaskBegin"
            ),
            "set_TaskActionTarget_rel32_call_sites": 0,
            "set_TaskActionTarget_note": "generated executors write TaskContext slots inline; setter has no direct rel32 callers",
            "get_SourceEntity_rel32_call_sites": 13,
            "get_SourceEntity_OnTaskBegin_callers": [
                "GPCKKEPGEDB (config AGPMEJILJBO, 4000-byte body)",
                "JAJPDPAHFOA (config RPG.GameCore.AddModifier, 6592-byte body -> modifier dependency)",
            ],
        },
        "plausible_candidate_count": len(shortlist["rows"]),
        "shortlist_candidates": [
            {
                "config": r["config_candidates"],
                "executor": r["executor_type"],
                "method_index": r["method_index"],
                "native_rva": r["native_rva"],
                "gap_bytes": r["gap_bytes"],
                "instruction_count": r["instruction_count"],
                "conditional_branch_count": r["conditional_branch_count"],
                "direct_call_count": r["direct_call_count"],
            }
            for r in shortlist["rows"][:30]
        ],
        "accepted_shortlist": [
            f"{p['source_runtime_type']}.{p['source_method']} ({p['method_index']})"
            for p in PRIMITIVE_PLANS
        ],
        "primary_chain": "RPG.GameCore.Obsolete -> HDDPKFNLMEG .ctor -> OnTaskBegin -> TaskState.Success (empty/no-op action leaf)",
        "heavy_dependency_skip_list": [
            "SequenceConfig step helper (2080B dispatcher; ordered iteration shape SUPPORTED)",
            "TriggerHitTarget leaf (hit/damage processing)",
            "AddModifier / AGPMEJILJBO OnTaskBegin (modifier subsystem)",
            "NotifyManager.Notify leaves (event system)",
            "SetDynamicValueByBattleTargetParam (TaskContext dictionary hash dispatcher)",
            "TurnBasedGameMode.SetCurrentTurnActionEntity persistent write (field identity unresolved)",
            "CPHGMLEAPJL.Tick component write (component class/field unresolved)",
        ],
        "real_runtime_layer_name": (
            "GENERATED_TASK_EXECUTOR_RUNTIME: serialized TaskConfig DSL -> "
            "generated executor class (.ctor/OnTaskBegin/OnTaskReset/Tick/"
            "Dispose) -> TaskState transition; there is no single ActionExecutor "
            "class. The batch label ACTION_EXECUTION_BRIDGE_06 is retained for "
            "the session plan; the recovered layer itself is the generated task "
            "executor runtime."
        ),
    }

    artifact = {
        "schema": SCHEMA,
        "game_version": GAME_VERSION,
        "batch_id": BATCH_ID,
        "generated_at": generated_at,
        "evidence_level": E4,
        "final_status": "BATTLE_SEMANTIC = ACTION_EXECUTION_BRIDGE_06_PROOF",
        "runtime_layer_name": "GENERATED_TASK_EXECUTOR_RUNTIME",
        "runtime_layer_shape": {
            "serialized_config_layer": (
                "TaskConfig DSL family; serializer identity = OJNNBEJLDIJ/"
                "MGMEGEDLMAK/LJACLBNEEEB/EOJLPDGNHEK (SKIP_SERIALIZATION, "
                "unchanged from Batch 03/04/05 discipline)"
            ),
            "generated_runtime_layer": (
                "generated task executor class; .ctor(TaskContext, config) "
                "stores TaskContext/config slots and initializes TaskState; "
                "OnTaskBegin / OnTaskReset / Tick / Dispose implement the task "
                "lifecycle"
            ),
            "execution_state": (
                "TaskState enum at executor [+0x10]: Ready=0x7777, "
                "Executing=0x8888, Success=0x9999, Fail=0xAAAA"
            ),
            "named_base_types": {
                "RPG.GameCore.TaskState": {
                    "type_index": 54932,
                    "members": ["Ready", "Executing", "Success", "Fail", "value__"],
                },
                "obfuscated_task_base_GELIALJDFBL": {
                    "type_index": 54936,
                    "evidence": (
                        ".ctor sets Ready; MDFBKGOJOJI reads [+0x10]; GetConfig "
                        "returns TaskConfig runtime type_reference 22744"
                    ),
                },
                "obfuscated_task_base_DJPBAKPBELL": {
                    "type_index": 36279,
                    "evidence": (
                        "FLFLCMEJEPM returns TaskConfig runtime type_reference "
                        "22744; MDFBKGOJOJI reads [+0x10]"
                    ),
                },
            },
        },
        "gameassembly": {
            "path": gameassembly["path"],
            "sha256": gameassembly["sha256"],
        },
        "primitives": primitives,
        "execution_chains": execution_chains,
        "context_reads": ["targets"],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "deferred_effects": [
            {
                "effect_id": "turn_based_game_mode_set_current_turn_action_entity",
                "entry": "RPG.GameCore.SetCurrentTurnActionEntity config -> EBHAGBCPFEN.OnTaskBegin",
                "native_rva": "0x12844660",
                "leaf": {
                    "runtime_type": "RPG.GameCore.TurnBasedGameMode",
                    "method": "SetCurrentTurnActionEntity",
                    "method_index": 499719,
                    "native_rva": "0xE75F700",
                },
                "classification": "PERSISTENT_STATE_DEPENDENCY_REQUIRED",
                "observed_writes": (
                    "[mode+0x2FA]=0, [mode+0x318]=0, conditional "
                    "[mode+0x2C9]/[mode+0x2CA]=0 when current entity differs"
                ),
                "dependency": "TurnBasedGameMode field identities +0x100/+0x2FA/+0x318/+0x2C9/+0x2CA",
            },
            {
                "effect_id": "switch_hand_item_breathing_light_tick_leaf",
                "entry": "CPHGMLEAPJL.OnTaskBegin tailcall -> CPHGMLEAPJL.Tick",
                "native_rva": "0xDD772E0",
                "classification": "COMPONENT_STATE_DEPENDENCY_REQUIRED",
                "observed_writes": "component [+0x44] bytes from TaskContext [+0x20]/[+0x21] (class global 0x983DA48)",
                "dependency": "component class identity and +0x44 field semantic",
            },
            {
                "effect_id": "trigger_hit_target_leaf",
                "entry": "RPG.GameCore.TriggerHitTarget -> FNGLHFPADGA.OnTaskBegin -> NICNFGOAOHI",
                "native_rva": "0x15547AB0",
                "classification": "SEMANTIC_DEPENDENCY_REQUIRED",
                "dependency": "hit/damage target processing subsystem",
            },
            {
                "effect_id": "notify_manager_client_event_effects",
                "entry": "ForbidBattleConditionOnStart / SetBattleTargetMultiTargetSwitch leaves",
                "native_rva": "0xD994450",
                "classification": "SKIP_EVENT_SYSTEM",
                "dependency": "RPG.Client.NotifyManager event dispatch",
            },
        ],
        "semantic_dependencies": [
            {
                "primitive_id": "battle.ir.target.collapse_single_or_null",
                "status": "SATISFIED_BATCH_05",
                "artifact": "target_selector_batch_05.json",
            },
            {
                "primitive_id": "battle.ir.target.collapse_required_single_or_null",
                "status": "SATISFIED_BATCH_05",
                "artifact": "target_selector_batch_05.json",
            },
            {
                "primitive_id": "RPG.GameCore.TaskContext.EvaluateTarget (0xE6F1530)",
                "status": "SEMANTIC_DEPENDENCY_REQUIRED",
                "note": "dispatcher itself deferred; Batch 05 collapse leaves reused",
            },
            {
                "primitive_id": "CPHGMLEAPJL.Tick gameplay leaf",
                "status": "SEMANTIC_DEPENDENCY_REQUIRED",
                "note": "component field identity unresolved",
            },
            {
                "primitive_id": "RPG.GameCore.TurnBasedGameMode.SetCurrentTurnActionEntity",
                "status": "PERSISTENT_STATE_DEPENDENCY_REQUIRED",
                "note": "BattleState field identities unresolved",
            },
        ],
        "unknowns": [
            "obfuscated base class GELIALJDFBL/DJPBAKPBELL true type names (anchored by TaskConfig typeref 22744 and TaskState field semantics)",
            "TaskState fieldDefinition provenance (typeref 586147) not resolved by a formal type-reference resolver; E4 constants + E3 enum members carry the identity",
            "generated executor slot layouts differ between generated base families (e.g. CPHGMLEAPJL: config +0x18 / ctx +0x20; KLJNMOLABGO: ctx +0x18 / config +0x20)",
            "three generated TaskConfig executors share ctor signature (GOIIFDECJBI/EPLMOIMGMIH/KOOGIKKDHBC); specialization rule not recovered",
            "SequenceConfig Step helper internals (2080B) and exact early-stop conditions beyond the proven state transitions",
            "no E5 client-side runtime observation",
            "IL2CPP class-init tail paths after the accepted normal-path windows are instrumentation and not part of the semantics",
        ],
        "candidate_table": candidate_table,
        "first_round_report": first_round_report,
        "task_state_model": {
            "runtime_type": "RPG.GameCore.TaskState",
            "type_index": 54932,
            "members": ["Ready", "Executing", "Success", "Fail", "value__"],
            "native_field_offset": "+0x10 (int32) on generated task executors",
            "raw_values": {
                "Ready": "0x7777",
                "Executing": "0x8888",
                "Success": "0x9999",
                "Fail": "0xAAAA",
            },
            "evidence": (
                "E3 enum member names + E4 constant stores in generated ctors "
                "(Ready), OnTaskBegin leaves (Executing/Success), failure paths "
                "(Fail), and the base accessor read"
            ),
        },
        "config_runtime_bridge": {
            "path": "data/raw/4.4.54/action_config_runtime_bridge_06.json",
            "config_family_count": bridge_summary["config_family_count"],
            "generated_executor_class_count": bridge_summary["executor_class_count"],
            "matched_rows": len(bridge_summary["matched_rows"]),
            "identity_rule": bridge_summary["identity_rule"],
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    sha = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    print(f"wrote {OUT_PATH}")
    print(f"sha256={sha}")
    print(f"primitives={len(primitives)} execution_chains={len(execution_chains)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
