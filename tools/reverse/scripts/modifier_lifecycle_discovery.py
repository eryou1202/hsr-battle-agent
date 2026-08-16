#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded candidate discovery for Modifier Lifecycle Bridge 08 (4.4.54).

This is the historical evidence tool for Batch 08.  It does **not** re-run a
blind modifier search.  The session already entered
``TurnBasedAbilityComponent.TryAddModifierInstance`` (0xE729500); this script
materializes the bounded control-flow evidence around that entry:

* TryAddModifierInstance full-gap disassembly + switch table decode
* existing-instance lookup chain
  (TurnBasedAbilityComponent.FindModifierInstance ->
   AbilityComponent.FindModifierInstance ->
   AbilityComponent._IsModifierMatchSearch)
* destroy / remove-dirty container mutation leaves
* _ProcessModifierRedd refresh boundary + switch decode
* post-apply OnAdded / OnActivate lifecycle leaves
* ModifierConfig.MGMEGEDLMAK layout evidence (Stacking at [+0x18])

Output:
``data/raw/4.4.54/modifier_lifecycle_discovery_08.json``
"""
from __future__ import annotations

import bisect
import hashlib
import json
import struct
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
    line_for,
    load_manifest,
    load_pe,
)

GAME_VERSION = "4.4.54"
OUT_PATH = REPO / "data" / "raw" / "4.4.54" / "modifier_lifecycle_discovery_08.json"

IMAGE_BASE_HINT = 0x180000000

# (method_index, classification, reason)
CANDIDATE_ROWS = [
    (506463, "ACCEPT_LIFECYCLE", "PRIMARY: bounded TryAdd duplicate/lifecycle decision tree (3424-byte gap)"),
    (506476, "ACCEPT_DUPLICATE_POLICY", "TurnBased component FindModifierInstance wrapper: delegate + runtime type check"),
    (520243, "ACCEPT_DUPLICATE_POLICY", "AbilityComponent.FindModifierInstance: ordered list scan + _IsModifierMatchSearch per item"),
    (520252, "ACCEPT_DUPLICATE_POLICY", "_IsModifierMatchSearch: name/state/StackingFlag/caster/source provider predicate"),
    (504365, "ACCEPT_DUPLICATE_POLICY", "GlobalFindModifierInstance: global component scope, same container match predicate"),
    (520247, "ACCEPT_REMOVAL", "RemoveDirtyModifiers: backward scan + shift-left removal + count/version writes"),
    (506250, "ACCEPT_LIFECYCLE", "TurnBasedModifierInstance.Destroy: State -> ToBeRemoved(2), cleanup boundary, recursive child destroy"),
    (506464, "ACCEPT_LIFECYCLE", "_ProcessModifierRedd: existing-instance refresh/replace boundary; Stacking switch 2..12 decoded"),
    (506465, "ACCEPT_LIFECYCLE", "_AddModifierDelayParam: component [+0x1e0] delayed-add queue append"),
    (506672, "ACCEPT_LIFECYCLE", "_PostProcessAfterModifierAdd: ReplaceByCasterOrUnStack(8) RemoveUnStackModifier fan-out"),
    (506175, "ACCEPT_LIFECYCLE", "TurnBasedModifierInstance.OnAdded: post-append virtual slot 13 leaf"),
    (506176, "ACCEPT_LIFECYCLE", "TurnBasedModifierInstance.OnActivate: post-append virtual slot 14 leaf; State=Alive(1) write"),
    (506321, "ACCEPT_STATE_LEAF", "TurnBasedModifierInstance.get_ConfigRef: [+0xa0] config pointer used by duplicate switches"),
    (504721, "ACCEPT_STATE_LEAF", "BaseModifierInstance..ctor: State [+0x80] = Alive(1), Name [+0x60] init"),
    (103117, "ACCEPT_STATE_LEAF", "ModifierConfig.MGMEGEDLMAK parser: Priority [+0x10], Count [+0x14], Stacking [+0x18] layout"),
    (520236, "SKIP_ALREADY_PROVEN", "Batch 07 append leaf; re-used with post-append slot 13/14 annotation"),
    (506325, "SKIP_ALREADY_PROVEN", "get_Layer / get_MaxLayer already proven in Batch 07"),
    (520237, "SKIP_EVENT_HEAVY", "ClearAllModifierInstance: pending-dispose fan-out and per-modifier destroy dispatches"),
    (520223, "SKIP_EVENT_HEAVY", "ProccessPendingDisposeModifiers: [+0x20] pending list disposal fan-out"),
    (506299, "SKIP_EVENT_HEAVY", "ExecuteEvent: full event graph"),
    (506304, "SKIP_EFFECT_HEAVY", "IncLayer / OnStack / UnStack stack-effect family; not needed for duplicate closure"),
    (506288, "SKIP_TURN_DEPENDENT", "_ModifierLifeStep: turn/phase duration engine"),
    (506329, "SKIP_ALREADY_PROVEN", "get_CurrentLife already proven in Batch 07"),
    (506163, "SKIP_EFFECT_HEAVY", "ContainsBehaviorFlag: effect/behavior flag subsystem"),
    (506482, "SKIP_EFFECT_HEAVY", "IsContainModifierBehavior: behavior flag subsystem"),
]

SHORTLIST = [
    506463,  # TryAddModifierInstance
    520243,  # AbilityComponent.FindModifierInstance
    520252,  # _IsModifierMatchSearch
    506250,  # Destroy
    520247,  # RemoveDirtyModifiers
    506464,  # _ProcessModifierRedd
    506175,  # OnAdded
    506176,  # OnActivate
]


def load_method_index() -> tuple[list[int], dict[int, dict]]:
    rvas: list[int] = []
    methods: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        rva = rec.get("native_rva")
        if isinstance(rva, int) and rec.get("mapping_kind") == "DIRECT_NATIVE":
            rvas.append(rva)
            methods[rva] = rec
    rvas.sort()
    return rvas, methods


def load_type_map() -> dict[int, dict]:
    return {rec["type_index"]: rec for rec in iter_records(NORMALIZED_BASE / "types.json")}


def method_for_index(method_index: int) -> dict:
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        if rec["method_index"] == method_index:
            return rec
    raise RuntimeError(f"missing method {method_index}")


def next_gap(rvas: list[int], rva: int) -> int:
    idx = bisect.bisect_right(rvas, rva)
    nxt = rvas[idx] if idx < len(rvas) else rva + 4096
    return nxt - rva


def bounded_evidence(pe, method: dict, rvas: list[int], projection: str) -> dict:
    rva = method["native_rva"]
    if not isinstance(rva, int):
        raise RuntimeError(f"method {method['method_index']} has no native RVA")
    gap = next_gap(rvas, rva)
    raw, decoded = disasm_window(pe, rva, gap)
    kind = "FULL_GAP_TO_NEXT_METHOD"
    body_raw = raw
    if projection == "FIRST_RET":
        first_ret = next((ins for ins in decoded if ins["mnemonic"] == "ret"), None)
        if first_ret is not None:
            end = first_ret["rva"] + first_ret["size"] - rva
            body_raw = raw[:end]
            kind = "NORMAL_PATH_FIRST_RET_PROJECTION"
    _, body_decoded = disasm_window(pe, rva, len(body_raw))
    branches = sum(
        1 for ins in body_decoded
        if ins["mnemonic"].startswith("j") and ins["mnemonic"] != "jmp"
    )
    calls = sum(1 for ins in body_decoded if ins["mnemonic"] == "call")
    jumps = sum(1 for ins in body_decoded if ins["mnemonic"] == "jmp")
    return {
        "method_index": method["method_index"],
        "declaring_type_index": method["declaring_type_index"],
        "method_name": method["name"],
        "body_rva": f"0x{rva:X}",
        "body_window_kind": kind,
        "full_gap_to_next_method": gap,
        "body_length_bytes": len(body_raw),
        "body_sha256": hashlib.sha256(body_raw).hexdigest(),
        "instruction_count": len(body_decoded),
        "conditional_branch_count": branches,
        "direct_call_count": calls,
        "direct_jump_count": jumps,
        "disassembly": [line_for(ins) for ins in body_decoded],
        "full_gap_disassembly": [line_for(ins) for ins in decoded],
    }


def decode_switch_table(pe, table_rva: int, entry_count: int, base_rva: int) -> list[dict]:
    off = pe.rva_to_file_offset(table_rva)
    if off is None:
        raise RuntimeError(f"switch table RVA not mapped: 0x{table_rva:X}")
    raw = pe._read(off, entry_count * 4)
    out = []
    for i in range(entry_count):
        disp = struct.unpack_from("<i", raw, i * 4)[0]
        target = table_rva + disp
        out.append({
            "index": i,
            "entry_rva": f"0x{table_rva + i * 4:X}",
            "delta": disp,
            "target_rva": f"0x{target:X}",
            "role": None,
        })
    return out


def direct_callees(pe, rva: int, length: int) -> list[dict]:
    _, decoded = disasm_window(pe, rva, length)
    out = []
    for ins in decoded:
        if ins["mnemonic"] == "call" and " " not in ins["op_str"].strip(" "):
            try:
                va = int(ins["op_str"], 0)
            except ValueError:
                continue
            out.append({
                "site_rva": f"0x{ins['rva']:X}",
                "dest_rva": f"0x{va - pe.image_base:X}",
            })
    return out


def enum_rows(type_index: int) -> list[dict]:
    rows = []
    for rec in iter_records(NORMALIZED_BASE / "fields.json"):
        if rec["declaring_type_index"] == type_index:
            rows.append(rec)
    return rows


def build() -> dict:
    pe = load_pe()
    manifest = load_manifest()
    rvas, _ = load_method_index()
    type_map = load_type_map()

    methods = {mi: method_for_index(mi) for mi in dict.fromkeys(
        [row[0] for row in CANDIDATE_ROWS]
    )}
    candidates = []
    for method_index, classification, reason in CANDIDATE_ROWS:
        method = methods[method_index]
        type_info = type_map.get(method["declaring_type_index"], {})
        projection = "FIRST_RET"
        if method_index in (506463, 506464, 506250):
            projection = "FULL_GAP"
        ev = bounded_evidence(pe, method, rvas, projection)
        candidates.append({
            "method_index": method_index,
            "candidate": (
                f"{type_info.get('full_name', '')}.{method['name']}"
            ),
            "native_rva": f"0x{method['native_rva']:X}",
            "classification": classification,
            "reason": reason,
            "shortlist": method_index in SHORTLIST,
            "body_length_bytes": ev["body_length_bytes"],
            "instruction_count": ev["instruction_count"],
            "conditional_branch_count": ev["conditional_branch_count"],
            "direct_call_count": ev["direct_call_count"],
            "native_evidence": ev,
        })

    tryadd_rva = methods[506463]["native_rva"]
    tryadd_switch = decode_switch_table(pe, 0xE72A244, 7, tryadd_rva)
    stacking_names = {
        7: "ReplaceByCaster", 8: "ReplaceByCasterOrUnStack", 9: "EntityUnique",
        10: "ReplaceButKeepLifeTime", 11: "RetainGlobalLatest",
        12: "ReplaceByCasterAbility", 13: "RetainGlobalLatestUnique",
    }
    for row in tryadd_switch:
        idx = row["index"] + 7
        row["stacking_ordinal"] = idx
        row["stacking_name"] = stacking_names[idx]
        row["role"] = {
            7: "local_caster_plus_source_lookup",
            8: "local_caster_plus_source_lookup",
            9: "local_default_lookup",
            10: "local_default_lookup",
            11: "global_lookup",
            12: "local_caster_plus_source_lookup",
            13: "global_lookup",
        }.get(idx, "default_local_lookup")

    redd_switch = decode_switch_table(pe, 0xE72AAA0, 11, 0xE72A3C0)
    for row in redd_switch:
        idx = row["index"] + 2
        row["stacking_ordinal"] = idx
        row["stacking_name"] = {
            2: "Refresh", 3: "Prolong", 4: "Multiple", 5: "Replace",
            6: "Merge", 7: "ReplaceByCaster", 8: "ReplaceByCasterOrUnStack",
            9: "EntityUnique", 10: "ReplaceButKeepLifeTime",
            11: "RetainGlobalLatest", 12: "ReplaceByCasterAbility",
        }[idx]

    enum_evidence = {
        "modifier_stacking": [
            {"ordinal": i, "name": rec["name"]}
            for i, rec in enumerate(enum_rows(15463))
            if rec["name"] != "value__"
        ],
        "modifier_stacking_flag": [
            {"ordinal": i, "name": rec["name"]}
            for i, rec in enumerate(enum_rows(24371))
            if rec["name"] != "value__"
        ],
        "modifier_state": [
            {"ordinal": i, "name": rec["name"]}
            for i, rec in enumerate(enum_rows(54605))
            if rec["name"] != "value__"
        ],
    }

    primary_chain = {
        "chain_id": "try_add_modifier_instance_duplicate_chain",
        "entry": {
            "runtime_type": "RPG.GameCore.TurnBasedAbilityComponent",
            "type_index": 55009,
            "method": "TryAddModifierInstance",
            "method_index": 506463,
            "native_rva": f"0x{tryadd_rva:X}",
            "parameter_relations": [
                {"type_reference": 37, "role": "string modifier name"},
                {"type_reference": 104288, "role": "ModifierConfig; Stacking at [+0x18]"},
                {"type_reference": 286703, "role": "source ability/provider (consumer-anchored)"},
                {"type_reference": 608873, "role": "runtime param; StackingFlag at [+0x5c]"},
                {"type_reference": 433618, "role": "bool (IL2CPP instrumentation tail only)"},
            ],
        },
        "switch_evidence": {
            "site_rva": "0xE7295CC",
            "table_rva": "0xE72A244",
            "index_transform": "ordinal = config[+0x18] - 7",
            "rows": tryadd_switch,
        },
        "duplicate_branch_summary": [
            "existing == null -> allocate + AddModifierInstance append (any Stacking)",
            "existing != null + Stacking Multiple(4) -> allocate + append duplicate",
            "existing != null + Stacking RetainGlobalLatest(11) -> Destroy(old); allocate + append",
            "existing != null + Stacking RetainGlobalLatestUnique(13) + caster==owner -> process existing",
            "existing != null + Stacking RetainGlobalLatestUnique(13) + caster!=owner -> Destroy(old); allocate + append",
            "existing != null + other Stacking -> _ProcessModifierRedd or delayed-add; return existing",
        ],
    }

    return {
        "schema": "modifier_lifecycle_discovery/1",
        "game_version": GAME_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gameassembly": {
            "path": manifest["GameAssembly"]["path"],
            "sha256": manifest["GameAssembly"]["sha256"],
        },
        "candidate_table": candidates,
        "shortlist_method_indexes": SHORTLIST,
        "primary_chain": primary_chain,
        "redd_switch_evidence": {
            "site_rva": "0xE72A649",
            "table_rva": "0xE72AAA0",
            "index_transform": "ordinal = existing.ConfigRef[+0x18] - 2",
            "rows": redd_switch,
        },
        "enum_evidence": enum_evidence,
        "tryadd_direct_callees": direct_callees(pe, tryadd_rva, next_gap(rvas, tryadd_rva)),
    }


def main() -> int:
    report = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"candidates={len(report['candidate_table'])} shortlist={len(SHORTLIST)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
