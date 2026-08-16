#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Candidate discovery pass for Modifier Application Bridge 07.

Starts from the Batch 06 deferred AddModifier row in
``data/raw/4.4.54/action_config_runtime_bridge_06.json`` (config
``RPG.GameCore.AddModifier`` type_index 22786 -> generated executor
``JAJPDPAHFOA`` type_index 54975 -> ``OnTaskBegin`` method_index 506048,
RVA ``0x161801C0``) and follows the real execution chain down to modifier
application helpers / persistent containers.

Names are discovery hints only.  All accepted semantic claims still require
the E4 bounded native-body evidence assembled by the batch builder.
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    NORMALIZED_BASE,
    disasm_window,
    iter_records,
    load_pe,
    line_for,
)

GAME_VERSION = "4.4.54"
OUT = REPO / "data" / "raw" / "4.4.54" / "modifier_application_discovery_07.json"

# Batch 06 deferred entry (machine-recorded, not re-derived blindly).
ADD_MODIFIER_CONFIG_TYPE_INDEX = 22786
ADD_MODIFIER_EXECUTOR_TYPE_INDEX = 54975
ADD_MODIFIER_ON_TASK_BEGIN = 506048
ADD_MODIFIER_CTOR = 506046
ADD_MODIFIER_DISPOSE = 506047
ADD_MODIFIER_RVA = 0x161801C0
ADD_MODIFIER_GAP = 6592

TYPE_KEYWORDS = [
    "addmodifier",
    "applymodifier",
    "createmodifier",
    "removemodifier",
    "getmodifier",
    "findmodifier",
    "hasmodifier",
    "modifiermanager",
    "modifiercomponent",
    "modifierinstance",
    "modifier",
]

METHOD_KEYWORDS = [
    "addmodifier",
    "applymodifier",
    "createmodifier",
    "removemodifier",
    "getmodifier",
    "findmodifier",
    "hasmodifier",
    "modifier",
]

TYPE_HIT_CAP = 400
METHOD_HIT_CAP = 300
CANDIDATE_DISASM_CAP = 60


def _passes_gate(rec: dict) -> bool:
    return (
        isinstance(rec.get("native_rva"), int)
        and rec.get("mapping_kind") == "DIRECT_NATIVE"
    )


def _records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        in_records = False
        for line in f:
            if not in_records:
                if '"records": [' in line:
                    in_records = True
                continue
            s = line.strip()
            if not s or s == "]":
                continue
            if s.endswith(","):
                s = s[:-1]
            if s.startswith("{") and s.endswith("}"):
                try:
                    yield json.loads(s)
                except json.JSONDecodeError:
                    pass


def collect_types(base: Path):
    """One types.json pass: full type names + keyword hits."""
    all_types: dict[int, dict] = {}
    hits: dict[str, list[dict]] = {k: [] for k in TYPE_KEYWORDS}
    selected: set[int] = {
        ADD_MODIFIER_CONFIG_TYPE_INDEX,
        ADD_MODIFIER_EXECUTOR_TYPE_INDEX,
    }
    for rec in _records(base / "types.json"):
        fn = rec["full_name"]
        row = {
            "type_index": rec["type_index"],
            "full_name": fn,
            "namespace": rec["namespace"],
            "name": rec["name"],
            "method_count": rec["method_count"],
            "field_count": rec["field_count"],
        }
        all_types[rec["type_index"]] = row
        low = fn.lower()
        for kw in TYPE_KEYWORDS:
            if kw in low:
                hit = dict(row)
                hit["keyword"] = kw
                if len(hits[kw]) < TYPE_HIT_CAP:
                    hits[kw].append(hit)
                selected.add(rec["type_index"])
                break
    return all_types, hits, selected


def collect_methods(base: Path, all_types: dict[int, dict], selected_types: set[int]):
    """One methods.json pass: selected-type methods, keyword hits, RVA index."""
    selected_methods: list[dict] = []
    selected_method_indexes: set[int] = set()
    method_hits: dict[str, list[dict]] = {k: [] for k in METHOD_KEYWORDS}
    rvas: list[int] = []
    methods_by_rva: dict[int, dict] = {}
    for rec in _records(base / "methods.json"):
        rva = rec.get("native_rva")
        if _passes_gate(rec):
            rvas.append(rva)
            methods_by_rva[rva] = rec
        if rec["declaring_type_index"] in selected_types:
            selected_methods.append(dict(rec))
            selected_method_indexes.add(rec["method_index"])
            continue
        low = rec["name"].lower()
        for kw in METHOD_KEYWORDS:
            if kw in low and _passes_gate(rec):
                row = dict(rec)
                row["keyword"] = kw
                decl = all_types.get(rec["declaring_type_index"], {})
                row["declaring_type"] = decl.get("full_name")
                row["declaring_namespace"] = decl.get("namespace")
                if len(method_hits[kw]) < METHOD_HIT_CAP:
                    method_hits[kw].append(row)
                selected_method_indexes.add(rec["method_index"])
                break
    rvas.sort()
    return selected_methods, selected_method_indexes, method_hits, rvas, methods_by_rva


def collect_fields(base: Path, selected_types: set[int]):
    fields: list[dict] = []
    for rec in _records(base / "fields.json"):
        if rec["declaring_type_index"] in selected_types:
            fields.append(dict(rec))
    return fields


def collect_params(base: Path, selected_method_indexes: set[int]):
    by_method: dict[int, list[dict]] = defaultdict(list)
    for rec in _records(base / "parameters.json"):
        if rec["method_index"] in selected_method_indexes:
            by_method[rec["method_index"]].append(dict(rec))
    return by_method


def method_for_site_local(
    site_rva: int, rvas: list[int], methods_by_rva: dict[int, dict]
) -> dict | None:
    i = bisect.bisect_right(rvas, site_rva) - 1
    if i < 0:
        return None
    start = rvas[i]
    if i + 1 < len(rvas) and site_rva >= rvas[i + 1]:
        return None
    return {"method_start_rva": start, "method": methods_by_rva[start]}


def annotate_insns(decoded: list[dict], pe) -> list[dict]:
    out = []
    for ins in decoded:
        row = dict(ins)
        row["target_rva"] = None
        if ins["mnemonic"] in ("call", "jmp") and ins["op_str"].startswith("0x"):
            try:
                va = int(ins["op_str"], 0)
                row["target_rva"] = va - pe.image_base
            except ValueError:
                pass
        if ins["comment"]:
            marker = "rva 0x"
            pos = ins["comment"].find(marker)
            if pos >= 0:
                token = ins["comment"][pos + len(marker) :].split(")")[0]
                try:
                    row["rip_target_rva"] = int(token, 16)
                except ValueError:
                    pass
        out.append(row)
    return out


def disasm_metrics(
    pe, rva: int, length: int, rvas: list[int], methods_by_rva: dict[int, dict],
    include_disassembly: bool = True,
) -> dict:
    raw, decoded = disasm_window(pe, rva, length)
    decoded = annotate_insns(decoded, pe)
    branch = sum(
        1 for i in decoded if i["mnemonic"].startswith("j") and i["mnemonic"] != "jmp"
    )
    calls = []
    for i in decoded:
        if i["target_rva"] is not None and i["mnemonic"] == "call":
            owner = method_for_site_local(i["target_rva"], rvas, methods_by_rva)
            calls.append(
                {
                    "site_rva": f"0x{i['rva']:X}",
                    "dest_rva": f"0x{i['target_rva']:X}",
                    "dest_method_index": owner["method"]["method_index"] if owner else None,
                    "dest_declaring_type_index": (
                        owner["method"]["declaring_type_index"] if owner else None
                    ),
                    "dest_method_name": owner["method"]["name"] if owner else None,
                }
            )
    jmps = [
        {"site_rva": f"0x{i['rva']:X}", "dest_rva": f"0x{i['target_rva']:X}"}
        for i in decoded
        if i["mnemonic"] == "jmp" and i["target_rva"] is not None
    ]
    rip_globals = [
        {"site_rva": f"0x{i['rva']:X}", "global_rva": f"0x{i['rip_target_rva']:X}"}
        for i in decoded
        if i.get("rip_target_rva") is not None
    ]
    rets = [i["rva"] - rva for i in decoded if i["mnemonic"] in ("ret", "retf")]
    row = {
        "native_rva": f"0x{rva:X}",
        "gap_bytes": length,
        "instruction_count": len(decoded),
        "conditional_branch_count": branch,
        "direct_call_count": len(calls),
        "direct_calls": calls,
        "direct_jumps": jmps,
        "rip_global_refs": rip_globals,
        "first_ret_offset": rets[0] if rets else None,
        "ret_offsets": rets,
        "last_instruction": line_for(decoded[-1]) if decoded else None,
    }
    if include_disassembly:
        row["disassembly"] = [line_for(i) for i in decoded]
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=NORMALIZED_BASE)
    ap.add_argument("--output", type=Path, default=OUT)
    ap.add_argument("--skip-candidates", action="store_true")
    args = ap.parse_args()

    print("types pass...")
    all_types, type_hits, selected_types = collect_types(args.base)
    print("methods pass...")
    selected_methods, selected_mi, method_hits, rvas, methods_by_rva = collect_methods(
        args.base, all_types, selected_types
    )
    print(f"types={len(all_types)} selected_types={len(selected_types)} rvas={len(rvas)}")
    print("fields pass...")
    fields = collect_fields(args.base, selected_types)
    print("params pass...")
    params = collect_params(args.base, selected_mi)

    pe = load_pe()
    print("primary disasm...")
    primary = disasm_metrics(
        pe, ADD_MODIFIER_RVA, ADD_MODIFIER_GAP, rvas, methods_by_rva, True
    )
    print("ctor/dispose disasm...")
    lifecycle = []
    for mi in (ADD_MODIFIER_CTOR, ADD_MODIFIER_DISPOSE):
        m = next((m for m in selected_methods if m["method_index"] == mi), None)
        if m is None:
            continue
        rva = m["native_rva"]
        j = bisect.bisect_right(rvas, rva)
        gap = (rvas[j] - rva) if j < len(rvas) else 0
        lifecycle.append(
            disasm_metrics(pe, rva, min(gap, 2048) if gap else 256, rvas,
                           methods_by_rva, True)
        )

    candidates = []
    if not args.skip_candidates:
        print("candidate disasm...")
        method_rows = []
        seen = set()
        for rows in method_hits.values():
            for r in rows:
                if r["method_index"] not in seen:
                    seen.add(r["method_index"])
                    method_rows.append(r)
        method_rows.sort(key=lambda r: r["native_rva"])
        for m in method_rows[:CANDIDATE_DISASM_CAP]:
            rva = m["native_rva"]
            j = bisect.bisect_right(rvas, rva)
            gap = (rvas[j] - rva) if j < len(rvas) else 0
            length = min(gap, 2048) if gap > 0 else 256
            row = disasm_metrics(pe, rva, length, rvas, methods_by_rva, False)
            row["method_index"] = m["method_index"]
            row["declaring_type_index"] = m["declaring_type_index"]
            row["declaring_type"] = m.get("declaring_type")
            row["method_name"] = m["name"]
            row["keyword"] = m["keyword"]
            candidates.append(row)

    bridge = json.loads(
        (REPO / "data" / "raw" / "4.4.54" / "action_config_runtime_bridge_06.json")
        .read_text(encoding="utf-8")
    )
    addmodifier_bridge_rows = [
        r
        for r in bridge["matched_rows"]
        if r["config_type_ref"] == 283020
        or "AddModifier" in r.get("config_candidates", [""])[0]
    ]

    report = {
        "schema": "modifier_application_discovery/1",
        "game_version": GAME_VERSION,
        "addmodifier_entry": {
            "source": "action_config_runtime_bridge_06.json",
            "config_type_index": ADD_MODIFIER_CONFIG_TYPE_INDEX,
            "executor_type_index": ADD_MODIFIER_EXECUTOR_TYPE_INDEX,
            "on_task_begin_method_index": ADD_MODIFIER_ON_TASK_BEGIN,
            "on_task_begin_rva": f"0x{ADD_MODIFIER_RVA:X}",
            "on_task_begin_gap_bytes": ADD_MODIFIER_GAP,
            "bridge_rows": addmodifier_bridge_rows,
        },
        "type_hits": type_hits,
        "method_hits": method_hits,
        "selected_type_count": len(selected_types),
        "selected_types": [
            all_types[ti] for ti in sorted(selected_types) if ti in all_types
        ],
        "selected_methods": selected_methods,
        "selected_fields": fields,
        "selected_parameters": {
            str(k): v for k, v in sorted(params.items())
        },
        "primary_chain_disassembly": [primary],
        "lifecycle_disassembly": lifecycle,
        "candidate_table": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {args.output}")
    for kw, rows in type_hits.items():
        print(f"== type {kw}: {len(rows)}")
    for kw, rows in method_hits.items():
        print(f"== method {kw}: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
