#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Modifier Lifecycle Bridge 08 semantic artifact (4.4.54).

Recovered runtime layer (ABI-independent view):

    TurnBasedAbilityComponent.TryAddModifierInstance
      inputs: name, ModifierConfig (Stacking [+0x18]), source provider,
              runtime param (StackingFlag [+0x5c])
      -> stacking-dependent existing-instance lookup
           local:   AbilityComponent.FindModifierInstance
                      -> _IsModifierMatchSearch(name, state, StackingFlag,
                                                caster, source provider)
           global:  GlobalFindModifierInstance -> same container predicate
      -> branch on ModifierConfig.Stacking
           Multiple(4)                  : keep old, append new
           RetainGlobalLatest(11)       : Destroy(old), append new
           RetainGlobalLatestUnique(13) : caster==owner ? process existing
                                                        : Destroy(old)+append
           others                       : process existing in place
      -> new instance path:
           TurnBasedModifierInstance.ctor
           -> AbilityComponent.AddModifierInstance ordered append
           -> post-append virtual slot 13 OnAdded
           -> conditional virtual slot 14 OnActivate
      -> removal: Destroy sets State=ToBeRemoved(2);
           AbilityComponent.RemoveDirtyModifiers shift-left removes non-Alive
           entries while preserving remaining order.

Scope is modifier persistent lifecycle only.  Modifier effects, damage, DOT,
event listener runtime and duration expiration stay deferred.
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
    load_manifest,
    load_pe,
    validate_code_slot,
)

GAME_VERSION = "4.4.54"
BATCH_ID = "MODIFIER_LIFECYCLE_BRIDGE_08"
SCHEMA = "battle_semantics_batch/1"
E4 = "E4_STATIC_MACHINE_CODE"
OUT_PATH = REPO / "data" / "semantics" / "4.4.54" / "modifier_lifecycle_bridge_08.json"
DISCOVERY_PATH = (
    REPO / "data" / "raw" / "4.4.54" / "modifier_lifecycle_discovery_08.json"
)

STACKING_NAMES = {
    0: "Unknow", 1: "Unique", 2: "Refresh", 3: "Prolong", 4: "Multiple",
    5: "Replace", 6: "Merge", 7: "ReplaceByCaster",
    8: "ReplaceByCasterOrUnStack", 9: "EntityUnique",
    10: "ReplaceButKeepLifeTime", 11: "RetainGlobalLatest",
    12: "ReplaceByCasterAbility", 13: "RetainGlobalLatestUnique",
}

PRIMITIVE_PLANS = [
    {
        "primitive_id": "battle.ir.modifier.try_add_modifier_instance",
        "semantic_name": "TryAddModifierInstance",
        "description": (
            "Bounded E4 decision-tree projection of "
            "TurnBasedAbilityComponent.TryAddModifierInstance "
            "(string name + ModifierConfig + source provider + runtime param). "
            "Stacking-dependent existing lookup by (name, StackingFlag, "
            "optional caster runtime-id and source-provider identity), then "
            "branch: Multiple(4) appends duplicate; RetainGlobalLatest(11) "
            "Destroys old then appends; RetainGlobalLatestUnique(13) compares "
            "resolved caster with the owner entity and either processes or "
            "Destroys+appends; every other Stacking processes the existing "
            "instance through _ProcessModifierRedd (State 0 goes to the "
            "delayed-add queue). New-instance path is the Batch 07 append "
            "plus OnAdded/OnActivate virtual mounts. Effect internals are "
            "deferred; lifecycle transitions are canonicalized."
        ),
        "inputs": [
            {"name": "target", "type": "entity_ref"},
            {"name": "modifier", "type": "modifier_state"},
            {"name": "stacking", "type": "int32"},
            {"name": "stacking_flag", "type": "int32"},
            {"name": "caster_entity", "type": "entity_ref_or_null"},
            {"name": "source_provider_ref", "type": "object_ref_or_null"},
            {"name": "activate", "type": "boolean"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": ["modifier_state_by_entity"],
        "state_writes": ["modifier_state_by_entity"],
        "result": "modifier_lifecycle_result",
        "source_runtime_type": "RPG.GameCore.TurnBasedAbilityComponent",
        "source_method": "TryAddModifierInstance",
        "method_index": 506463,
        "projection": "FULL_GAP",
        "branch_conditions": [
            "param [+0x94] null marker -> return null",
            "config null / source provider null -> IL2CPP throw",
            "config [+0x18] Stacking switch (ordinal 7..13 primary dispatch)",
            "existing found + Stacking == 4 -> append duplicate",
            "existing found + Stacking == 11 -> Destroy + append",
            "existing found + Stacking == 13 -> caster==owner ? process : Destroy+append",
            "existing found + other Stacking -> State==0 delayed add else _ProcessModifierRedd",
        ],
        "required_callees": [
            "0xE72B410 TurnBasedAbilityComponent.FindModifierInstance",
            "0xE43E2B0 GlobalFindModifierInstance",
            "0xE7384B0 TurnBasedModifierInstance.Destroy",
            "0xE77EB00 TurnBasedModifierInstance..ctor",
            "0xE431890 AbilityComponent.AddModifierInstance",
            "0xE72A3C0 _ProcessModifierRedd",
            "0xE72A260 _AddModifierDelayParam",
            "0xE74E070 _PostProcessAfterModifierAdd",
        ],
        "null_behavior": (
            "null config/source provider throws on used paths; null match result "
            "falls through to allocation; canonical input validation"
        ),
        "ordering_behavior": (
            "append path = ordered tail append (Batch 07); global lookup scans "
            "entity collections in deterministic runtime-id order in the "
            "sandbox projection (native global-list order unresolved)"
        ),
    },
    {
        "primitive_id": "battle.ir.modifier.container_find_modifier_instance",
        "semantic_name": "FindModifierInstanceContainer",
        "description": (
            "AbilityComponent.FindModifierInstance ordered scan: iterate "
            "_ModifierList [+0x38] front-to-back and return the first item "
            "accepted by _IsModifierMatchSearch; no match -> null. Duplicate "
            "lookup identity is the match predicate, not Python list equality."
        ),
        "inputs": [
            {"name": "container", "type": "modifier_container"},
            {"name": "match_key", "type": "modifier_duplicate_match_key"},
            {"name": "state_filter", "type": "int32"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "result": "modifier_state_or_null",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "FindModifierInstance",
        "method_index": 520243,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "ordered forward scan",
            "per-item _IsModifierMatchSearch boolean",
            "no match -> null",
        ],
        "required_callees": ["0xE4326E0 _IsModifierMatchSearch"],
        "null_behavior": "null container items skipped; null list -> throw",
        "ordering_behavior": "forward scan; first match wins",
    },
    {
        "primitive_id": "battle.ir.modifier.match_modifier_search",
        "semantic_name": "ModifierMatchSearchPredicate",
        "description": (
            "AbilityComponent._IsModifierMatchSearch predicate used by both "
            "local and global duplicate lookup: ordinal name [+0x60] equality; "
            "optional State filter (0: ToBeAdded/Alive, 1: Alive only, other: "
            "none); StackingFlag [+0x88] equality (100 = wildcard); optional "
            "caster RuntimeID filter resolved through [+0x48] lazy resolver "
            "(0/-1 = wildcard); optional source-provider object identity check."
        ),
        "inputs": [
            {"name": "modifier", "type": "modifier_state"},
            {"name": "match_key", "type": "modifier_duplicate_match_key"},
            {"name": "state_filter", "type": "int32"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "result": "boolean",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "_IsModifierMatchSearch",
        "method_index": 520252,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "name pointer identity -> true",
            "name length mismatch -> false",
            "name ordinal content equality",
            "state_filter 0 -> State <= 1; 1 -> State == 1; else no state filter",
            "stacking_flag 100 -> wildcard; else equality",
            "caster runtime-id 0/-1 -> wildcard; else caster RuntimeID equality",
            "source provider object non-null -> object identity equality",
        ],
        "required_callees": ["0xB429790 lazy entity resolver (unregistered helper)"],
        "null_behavior": "null modifier -> false; null name only matches null name",
        "ordering_behavior": "pure predicate",
    },
    {
        "primitive_id": "battle.ir.modifier.lifecycle_destroy",
        "semantic_name": "DestroyModifierInstanceBoundary",
        "description": (
            "TurnBasedModifierInstance.Destroy(int) bounded lifecycle "
            "transition: State > 1 (ToBeRemoved/Removed) returns immediately; "
            "otherwise State [+0x80] = 2 (ToBeRemoved), destroy-reason int "
            "[+0x98] is stored, cleanup callbacks and recursive child destroy "
            "run (deferred effects), and the container removal itself happens "
            "later in AbilityComponent.RemoveDirtyModifiers. Canonical "
            "projection materializes the proven State transition only."
        ),
        "inputs": [
            {"name": "target", "type": "entity_ref"},
            {"name": "modifier", "type": "modifier_state"},
            {"name": "destroy_arg", "type": "int32"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": ["modifier_state_by_entity"],
        "state_writes": ["modifier_state_by_entity"],
        "result": "modifier_state",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "Destroy",
        "method_index": 506250,
        "projection": "FULL_GAP",
        "branch_conditions": [
            "State > 1 -> idempotent no-op return",
            "State <= 1 -> State [+0x80] = 2 (ToBeRemoved)",
            "destroy reason [+0x98] = arg",
            "recursive child-modifier destroy loop over [+0x120] list",
        ],
        "required_callees": [
            "0xE72BD90 IsContainModifierBehavior",
            "0xE7880D0 _OnModifierDestroy",
            "0xE77E9C0 _CleanupAfterModifierDestroy",
            "0xE4EE0A0 BaseModifierInstance.Destroy (tailcall)",
        ],
        "null_behavior": "null owner component -> throw; null child modifiers skipped",
        "ordering_behavior": "state transition before cleanup; removal deferred",
    },
    {
        "primitive_id": "battle.ir.modifier.container_remove_dirty",
        "semantic_name": "RemoveDirtyModifiers",
        "description": (
            "AbilityComponent.RemoveDirtyModifiers E4 ordered removal leaf: "
            "scan _ModifierList backwards; skip State == 1 (Alive) and items "
            "with destroy guard [+0x94] > 0; otherwise invoke the resolved "
            "Dispose virtual (deferred effect), count--, shift-left remaining "
            "items one slot, clear the freed tail slot and version++. "
            "Remaining order is preserved exactly like List<T>.RemoveAt; this "
            "is the native proof that permits the canonical tuple filter in "
            "the sandbox."
        ),
        "inputs": [{"name": "target", "type": "entity_ref"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": ["modifier_state_by_entity"],
        "state_writes": ["modifier_state_by_entity"],
        "result": "modifier_container",
        "source_runtime_type": "RPG.GameCore.AbilityComponent",
        "source_method": "RemoveDirtyModifiers",
        "method_index": 520247,
        "projection": "FIRST_RET",
        "branch_conditions": [
            "backward index scan",
            "State == 1 -> keep",
            "destroy guard > 0 -> keep",
            "other -> dispose + count-- + shift-left + tail clear + version++",
        ],
        "required_callees": ["0x183C63670 virtual dispose resolver"],
        "null_behavior": "null list/items -> throw; empty list -> no-op",
        "ordering_behavior": "shift-left removal; remaining order preserved",
    },
    {
        "primitive_id": "battle.ir.modifier.lifecycle_process_redd",
        "semantic_name": "ProcessModifierReddBoundary",
        "description": (
            "TurnBasedAbilityComponent._ProcessModifierRedd E4 boundary for "
            "existing-instance refresh/replace: recomputes is-max-layer "
            "[+0x8e], copies config-derived fields from the runtime param, "
            "then switches on existing.ConfigRef[+0x18] Stacking (2..12). "
            "Recovered deterministic core: Replace-family (2/5/7/8/12) sets "
            "CurrentLife [+0x2c4] and Count [+0x7c]; Prolong(3) adds lives; "
            "Merge(6) takes max lives; ReplaceButKeepLifeTime(10) keeps life "
            "and sets Count; Multiple/EntityUnique/RetainGlobalLatest-family "
            "take the config-only branch. OnReplace and UI/notify effects are "
            "deferred."
        ),
        "inputs": [
            {"name": "target", "type": "entity_ref"},
            {"name": "modifier", "type": "modifier_state"},
            {"name": "stacking", "type": "int32"},
            {"name": "new_count", "type": "int32"},
            {"name": "new_life", "type": "int32"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": ["modifier_state_by_entity"],
        "state_writes": ["modifier_state_by_entity"],
        "result": "modifier_state",
        "source_runtime_type": "RPG.GameCore.TurnBasedAbilityComponent",
        "source_method": "_ProcessModifierRedd",
        "method_index": 506464,
        "projection": "FULL_GAP",
        "branch_conditions": [
            "existing null / param null -> throw",
            "is_max_layer [+0x8e] = layer >= max(1, [+0x2e0]+[+0x270])",
            "Stacking 2/5/7/8/12 -> life=new_life; count=new_count",
            "Stacking 3 -> life=current+new unless -1 sentinel",
            "Stacking 6 -> life=max(current,new) unless -1 sentinel",
            "Stacking 10 -> count=new_count; life kept",
            "Stacking 4/9/11/13 -> config-only branch",
            "OnReplace / _OnModifierValueChanged / UI refresh deferred",
        ],
        "required_callees": [
            "0xE4EDD00 set_Count",
            "0xE77F9E0 OnReplace",
            "0xE77FB60 _OnModifierValueChanged",
            "0xE784190 TriggerCharacterUIRefresh",
        ],
        "null_behavior": "null modifier/param -> throw",
        "ordering_behavior": "single existing instance update; no list mutation",
    },
    {
        "primitive_id": "battle.ir.modifier.lifecycle_on_added",
        "semantic_name": "OnAddedLifecycleMount",
        "description": (
            "TurnBasedModifierInstance.OnAdded (post-append virtual slot 13 "
            "from AbilityComponent.AddModifierInstance): calls "
            "OnModifierCasterChanged then initializes sequence-state fields "
            "[+0x168]/[+0x16a]/[+0x170]. Those component fields are outside "
            "the canonical ModifierState; the canonical projection is an "
            "identity transition with effects deferred."
        ),
        "inputs": [{"name": "modifier", "type": "modifier_state"}],
        "context_reads": [],
        "context_writes": [],
        "state_reads": [],
        "state_writes": [],
        "result": "modifier_state",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "OnAdded",
        "method_index": 506175,
        "projection": "FIRST_RET",
        "branch_conditions": ["IL2CPP instrumentation excluded"],
        "required_callees": ["0xE781930 OnModifierCasterChanged"],
        "null_behavior": "native null-instance throw paths; canonical input validation",
        "ordering_behavior": "no canonical state ordering effect",
    },
    {
        "primitive_id": "battle.ir.modifier.lifecycle_on_activate",
        "semantic_name": "OnActivateLifecycleTransition",
        "description": (
            "TurnBasedModifierInstance.OnActivate (post-append virtual slot "
            "14, called only when AddModifierInstance bool arg is true): "
            "writes is-activating [+0x8d] = 1 and State [+0x80] = 1 (Alive). "
            "Canonical projection materializes the proven State transition; "
            "all downstream activation effects are deferred."
        ),
        "inputs": [
            {"name": "target", "type": "entity_ref"},
            {"name": "modifier", "type": "modifier_state"},
        ],
        "context_reads": [],
        "context_writes": [],
        "state_reads": ["modifier_state_by_entity"],
        "state_writes": ["modifier_state_by_entity"],
        "result": "modifier_state",
        "source_runtime_type": "RPG.GameCore.TurnBasedModifierInstance",
        "source_method": "OnActivate",
        "method_index": 506176,
        "projection": "FIRST_RET",
        "branch_conditions": ["State [+0x80] = 1 (Alive); is-activating [+0x8d] = 1"],
        "required_callees": [],
        "null_behavior": "null owner component -> throw; canonical input validation",
        "ordering_behavior": "single instance state write; no list mutation",
    },
]


def load_discovery() -> dict:
    return json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))


def evidence_from_discovery(discovery: dict, method_index: int) -> dict:
    for cand in discovery["candidate_table"]:
        if cand["method_index"] == method_index:
            return cand["native_evidence"]
    raise RuntimeError(f"missing discovery evidence for method {method_index}")


def duplicate_application_cases() -> list[dict]:
    rows = []
    for ordinal, name in STACKING_NAMES.items():
        lookup_scope = "local_component"
        caster_filter = "wildcard"
        source_filter = "none"
        if name in ("ReplaceByCaster", "ReplaceByCasterOrUnStack", "ReplaceByCasterAbility"):
            lookup_scope = "local_component"
            caster_filter = "source_provider_resolved_entity_runtime_id"
            source_filter = "source_provider_object_identity"
        elif name in ("RetainGlobalLatest", "RetainGlobalLatestUnique"):
            lookup_scope = "global_manager_scope"
        if name == "Multiple":
            policy = "APPEND_DUPLICATE_KEEP_EXISTING"
        elif name == "RetainGlobalLatest":
            policy = "DESTROY_EXISTING_THEN_APPEND"
        elif name == "RetainGlobalLatestUnique":
            policy = "CASTER_IS_OWNER_REFRESH_EXISTING_ELSE_DESTROY_AND_APPEND"
        else:
            policy = "PROCESS_EXISTING_IN_PLACE"
        rows.append({
            "stacking_ordinal": ordinal,
            "stacking_name": name,
            "existing": False,
            "policy": "APPEND_NEW_INSTANCE",
            "lookup_scope": lookup_scope,
            "match_filters": {
                "name": "ordinal string equality",
                "stacking_flag": "runtime param [+0x5c]",
                "caster_entity": caster_filter,
                "source_provider": source_filter,
            },
        })
        rows.append({
            "stacking_ordinal": ordinal,
            "stacking_name": name,
            "existing": True,
            "policy": policy,
            "lookup_scope": lookup_scope,
            "match_filters": {
                "name": "ordinal string equality",
                "stacking_flag": "runtime param [+0x5c]",
                "caster_entity": caster_filter,
                "source_provider": source_filter,
            },
        })
    return rows


def build() -> dict:
    discovery = load_discovery()
    pe = load_pe()
    manifest = load_manifest()
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    primitives = []
    for plan in PRIMITIVE_PLANS:
        method_index = plan["method_index"]
        ev = evidence_from_discovery(discovery, method_index)
        validate_code_slot(pe, method_index, int(ev["body_rva"], 16))
        primitives.append({
            "primitive_id": plan["primitive_id"],
            "semantic_name": plan["semantic_name"],
            "description": plan["description"],
            "inputs": plan["inputs"],
            "context_reads": plan["context_reads"],
            "context_writes": plan["context_writes"],
            "state_reads": plan.get("state_reads", []),
            "state_writes": plan.get("state_writes", []),
            "result": plan["result"],
            "determinism": "DETERMINISTIC",
            "evidence_level": E4,
            "source_runtime_type": plan["source_runtime_type"],
            "source_method": plan["source_method"],
            "source_method_index": method_index,
            "source_native_rva": ev["body_rva"],
            "native_body_hash": ev["body_sha256"],
            "source_identity": {
                "method_index": method_index,
                "method_name": ev["method_name"],
                "declaring_type_index": ev["declaring_type_index"],
            },
            "native_evidence": ev,
            "branch_conditions": plan["branch_conditions"],
            "required_callees": plan["required_callees"],
            "null_behavior": plan["null_behavior"],
            "ordering_behavior": plan["ordering_behavior"],
            "determinism_note": (
                "constant field writes and ordered list scans; no PRNG/clock/"
                "context dependency in accepted canonical projections"
            ),
        })

    return {
        "schema": SCHEMA,
        "game_version": GAME_VERSION,
        "batch_id": BATCH_ID,
        "generated_at": generated_at,
        "evidence_level": E4,
        "final_status": "BATTLE_SEMANTIC = MODIFIER_LIFECYCLE_BRIDGE_08_PROOF",
        "runtime_layer_name": "TURNBASED_MODIFIER_LIFECYCLE_RUNTIME",
        "runtime_layer_shape": {
            "entry": (
                "TurnBasedAbilityComponent.TryAddModifierInstance "
                "(M506463, 0xE729500, 3424-byte gap)"
            ),
            "lookup": (
                "TurnBasedAbilityComponent.FindModifierInstance -> "
                "AbilityComponent.FindModifierInstance -> "
                "_IsModifierMatchSearch; GlobalFindModifierInstance reuses the "
                "same container predicate across global component scope"
            ),
            "branch": (
                "ModifierConfig.Stacking [+0x18] enum (E3 members + E4 "
                "parser layout + two E4 switch consumers)"
            ),
            "mount": (
                "TurnBasedModifierInstance ctor -> AbilityComponent."
                "AddModifierInstance append -> virtual slot 13 OnAdded -> "
                "conditional slot 14 OnActivate"
            ),
            "removal": (
                "Destroy sets State=ToBeRemoved(2); "
                "RemoveDirtyModifiers performs shift-left list mutation"
            ),
        },
        "gameassembly": {
            "path": manifest["GameAssembly"]["path"],
            "sha256": manifest["GameAssembly"]["sha256"],
        },
        "primitives": primitives,
        "duplicate_application_cases": duplicate_application_cases(),
        "removal_chains": [
            {
                "chain_id": "destroy_then_remove_dirty_chain",
                "status": "E4_CHAIN_CLOSED_CONTAINER_MUTATION_EFFECTS_DEFERRED",
                "steps": [
                    "TurnBasedModifierInstance.Destroy(0) -> State [+0x80] = 2 (ToBeRemoved)",
                    "AbilityComponent.RemoveDirtyModifiers -> non-Alive & guard==0 entries removed",
                    "list count--; remaining entries shift left one slot; freed tail cleared; version++",
                    "remaining order preserved (List<T>.RemoveAt equivalence)",
                ],
            },
            {
                "chain_id": "retain_global_latest_duplicate_chain",
                "status": "E4_CHAIN_CLOSED_BOUNDARY_PROJECTION",
                "steps": [
                    "existing found by global lookup",
                    "Destroy(existing, 0) -> State=ToBeRemoved",
                    "fresh TurnBasedModifierInstance + AddModifierInstance append",
                    "old entry remains until RemoveDirtyModifiers removes it",
                ],
            },
        ],
        "lifecycle_chains": [
            {
                "chain_id": "try_add_duplicate_decision_chain",
                "status": "E4_CHAIN_CLOSED_DECISION_TREE",
                "steps": [
                    "read config [+0x18] Stacking",
                    "select lookup scope/filter",
                    "existing lookup by duplicate_match_key",
                    "branch by Stacking + existing State",
                    "append / destroy+append / process-in-place / delayed-add",
                ],
            },
            {
                "chain_id": "post_apply_virtual_mount_chain",
                "status": "E4_CHAIN_CLOSED_SLOT_IDENTITY_EFFECTS_DEFERRED",
                "steps": [
                    "AddModifierInstance append",
                    "virtual slot 13 -> OnAdded (unconditional, arg 0)",
                    "virtual slot 14 -> OnActivate (conditional on bool arg)",
                    "OnActivate writes State=Alive(1); effect internals deferred",
                ],
            },
        ],
        "persistent_reads": [
            "TurnBasedAbilityComponent [+0x10] owner entity, [+0x110] base component, [+0x1e0] delayed queue, [+0x2b4] counter",
            "AbilityComponent [+0x38] _ModifierList (list [+0x10]/[+0x18]/[+0x1c])",
            "BaseModifierInstance [+0x60] Name, [+0x7c] Count, [+0x80] State, [+0x88] StackingFlag, [+0x48] lazy resolver, [+0x94] destroy guard",
            "TurnBasedModifierInstance [+0xa0] ConfigRef, [+0x198] owner component, [+0x270]/[+0x2e0] max-layer slots, [+0x288] Layer, [+0x2c4] CurrentLife, [+0x2e4] previous life, [+0x8e] is-max-layer",
            "ModifierConfig [+0x18] Stacking (parser M103117 layout evidence)",
        ],
        "persistent_writes": [
            "new path: list version++ / tail append / count++ (Batch 07 reuse)",
            "Destroy: instance State [+0x80] = 2",
            "RemoveDirtyModifiers: count--, shift-left, tail clear, version++",
            "_ProcessModifierRedd: [+0x8e], [+0x7c], [+0x2c4], [+0x2e4] and config-derived slots",
            "BattleState canonical write: modifier_state_by_entity[owner_runtime_id]",
        ],
        "instance_identity": [
            {
                "role": "sandbox_logical_instance_identity",
                "key": "ModifierRef(name, owner_entity, instance_ordinal)",
                "status": "PROVEN_ORDERED_APPEND_ORDINAL",
                "note": "ordinal assigned from deterministic container state; never Python id()/UUID",
            },
            {
                "role": "native_runtime_object_handle",
                "status": "UNKNOWN",
                "note": "native duplicate predicate uses object pointers only for source provider identity",
            },
        ],
        "duplicate_match_identity": [
            {
                "field": "name",
                "native_source": "BaseModifierInstance.Name [+0x60]; ordinal string equality in _IsModifierMatchSearch",
                "status": "PROVEN",
            },
            {
                "field": "stacking_flag",
                "native_source": "BaseModifierInstance.StackingFlag [+0x88] == runtime param [+0x5c]; 100 wildcard",
                "status": "PROVEN",
            },
            {
                "field": "caster_entity",
                "native_source": "lazy resolver [+0x48] -> GameEntity.RuntimeID [+0xd0]; 0/-1 wildcard; required by Stacking 7/8/12 lookup",
                "status": "PROVEN",
            },
            {
                "field": "source_provider",
                "native_source": "object identity through resolver vtable slot [+0x130]; canonical ObjectRef materialization; native instance id UNKNOWN",
                "status": "E4_PREDICATE_SHAPE_OBJECT_IDENTITY_UNRESOLVED",
            },
            {
                "field": "owner_entity",
                "native_source": "implicit: lookup happens inside the owner AbilityComponent collection",
                "status": "PROVEN_IMPLICIT_SCOPE",
            },
        ],
        "stack_semantics": [
            {
                "scope": "ModifierConfig.Stacking enum",
                "members": [
                    {"ordinal": o, "name": n} for o, n in STACKING_NAMES.items()
                ],
                "status": "E3_MEMBER_ORDER + E4_SWITCH_CONSUMERS",
            },
            {
                "scope": "instance Layer/Count integer increments",
                "status": "PARTIAL_STRUCTURE_ONLY",
                "note": "Count/Layer getters proven in Batch 07; ProcessRedd writes Count and life fields; full OnStack effect graph deferred",
            },
        ],
        "duration_semantics": [
            {
                "scope": "CurrentLife [+0x2c4] / previous life [+0x2e4] refresh arithmetic",
                "status": "E4_STRUCTURE_SUPPORTED",
                "note": "Refresh/Prolong/Merge/Replace core arithmetic recovered; expiration trigger still deferred",
            },
            {
                "scope": "duration expiration engine",
                "status": "MODIFIER_EXPIRATION_DEPENDENCY_REQUIRED",
                "note": "Turn/Round/Event/Timeline not entered",
            },
        ],
        "effect_dependencies": [
            "OnAdded/OnActivate effect internals (sequence state fields [+0x168..+0x170])",
            "_ProcessModifierRedd OnReplace / _OnModifierValueChanged / UI refresh",
            "Destroy cleanup callbacks and child modifier recursion",
            "_PostProcessAfterModifierAdd RemoveUnStackModifier fan-out",
        ],
        "event_dependencies": [
            "NotifyManager.Notify tailcalls in Destroy and _ProcessModifierRedd",
            "behavior-flag event graph not entered",
        ],
        "turn_dependencies": [
            "duration expiration, _ModifierLifeStep, turn/round phase processors not entered",
        ],
        "unknowns": [
            "runtime param typeref 608873 canonical type name",
            "source provider resolver vtable slot [+0x130] method identity",
            "TurnBasedAbilityComponent [+0x2b4] counter and activation bool semantics",
            "global modifier manager search ordering (native list order unresolved)",
            "delayed-add queue [+0x1e0] processing trigger internals",
            "no E5 client-side runtime observation",
        ],
        "first_round_report": {
            "commits": [
                "f3476d9 sandbox: add modifier application runtime",
                "33cf283 reverse: recover modifier application bridge",
                "b62910f sandbox: add action execution runtime",
                "1ec6983 reverse: recover action execution bridge",
            ],
            "entry": "TryAddModifierInstance M506463 0xE729500 full gap 0xD60",
            "lookup_helper": "FindModifierInstance M506476 -> M520243 -> _IsModifierMatchSearch M520252",
            "lookup_key": "(name, StackingFlag, optional caster runtime-id, optional source-provider identity)",
            "destroy_remove_path": "Destroy M506250 State=2 -> RemoveDirtyModifiers M520247 shift-left",
            "readd_path": "fresh ctor M506132 -> AddModifierInstance M520236 append",
            "post_apply_virtual": "slot 13 OnAdded M506175, slot 14 OnActivate M506176",
            "candidate_count": len(discovery["candidate_table"]),
            "shortlist": discovery["shortlist_method_indexes"],
            "primary_chain": "try_add_modifier_instance_duplicate_chain",
            "boundary": "Event/Damage/DOT/Turn dependencies recorded; not entered",
            "can_close_duplicate_policy": True,
        },
        "candidate_table": discovery["candidate_table"],
        "discovery_artifact": str(DISCOVERY_PATH.relative_to(REPO)).replace("\\", "/"),
    }


def main() -> int:
    artifact = build()
    OUT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH} primitives={len(artifact['primitives'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
