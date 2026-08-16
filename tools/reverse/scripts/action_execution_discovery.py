#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Candidate discovery pass for Action Execution Bridge 06.

Streams normalized types/methods once each (twice for methods when needed),
joins the already-recovered EvaluateTarget / EvaluateSingleTarget caller
artifact, and emits a machine-readable discovery report of plausible
action/task execution candidates.  Names are discovery keywords only; this
script claims no semantic mapping.
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
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

TYPE_KEYWORDS = [
    "taskaction",
    "actiontask",
    "battleaction",
    "abilitytask",
    "skilltask",
    "task",
    "action",
    "execute",
    "executor",
    "effect",
    "apply",
    "perform",
]

METHOD_KEYWORDS = [
    "execute",
    "exec",
    "run",
    "apply",
    "perform",
    "ontaskbegin",
    "ontaskupdate",
    "ontaskend",
    "ontaskfailed",
    "taskexecute",
    "executetask",
    "executeaction",
    "actionexecute",
]

ANCHOR_TARGETS = {
    "EvaluateTarget": 0xE6F1530,
    "EvaluateSingleTarget": 0xE6D5830,
}

EXISTING_XREFS = (
    REPO / "data" / "raw" / "4.4.54" / "target_selector_xrefs_05.json"
)

TYPE_HIT_CAP = 500
METHOD_HIT_CAP = 200


def iter_json_records(path: Path):
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


def _method_passes_gate(rec: dict) -> bool:
    return (
        isinstance(rec.get("native_rva"), int)
        and rec.get("mapping_kind") == "DIRECT_NATIVE"
    )


def collect_types(base: Path) -> tuple[dict[int, dict], dict[str, list[dict]], set[int]]:
    type_index_all: dict[int, dict] = {}
    type_hits: dict[str, list[dict]] = {k: [] for k in TYPE_KEYWORDS}
    selected: set[int] = set()
    for rec in iter_json_records(base / "types.json"):
        fn = rec["full_name"]
        low = fn.lower()
        row = {
            "type_index": rec["type_index"],
            "full_name": fn,
            "namespace": rec["namespace"],
            "name": rec["name"],
            "method_count": rec["method_count"],
            "field_count": rec["field_count"],
        }
        type_index_all[rec["type_index"]] = row
        for k in TYPE_KEYWORDS:
            if k in low:
                hit = dict(row)
                hit["keyword"] = k
                if len(type_hits[k]) < TYPE_HIT_CAP:
                    type_hits[k].append(hit)
                selected.add(rec["type_index"])
                break
    # anchor names
    for ti, row in type_index_all.items():
        if row["full_name"] in (
            "RPG.GameCore.TaskContext",
            "RPG.GameCore.AbilityStatic",
            "RPG.GameCore.GameEntity",
        ):
            selected.add(ti)
    return type_index_all, type_hits, selected


def collect_methods(
    base: Path,
    type_index_all: dict[int, dict],
    selected_types: set[int],
) -> tuple[dict[int, dict], list[dict], dict[str, list[dict]], list[int]]:
    """One stream for keyword hits; a second stream for selected-type methods.

    The full DIRECT_NATIVE RVA list is built on the first stream.
    """
    method_hits: dict[str, list[dict]] = {k: [] for k in METHOD_KEYWORDS}
    rvas: list[int] = []
    for rec in iter_json_records(base / "methods.json"):
        if _method_passes_gate(rec):
            rvas.append(rec["native_rva"])
        name = rec["name"]
        low = name.lower()
        for k in METHOD_KEYWORDS:
            if k in low:
                row = dict(rec)
                row["keyword"] = k
                decl = type_index_all.get(rec["declaring_type_index"], {})
                row["declaring_type"] = decl.get("full_name")
                row["declaring_namespace"] = decl.get("namespace")
                if len(method_hits[k]) < METHOD_HIT_CAP:
                    method_hits[k].append(row)
                selected_types.add(rec["declaring_type_index"])
                break
    methods_by_type: dict[int, list[dict]] = {}
    for rec in iter_json_records(base / "methods.json"):
        ti = rec["declaring_type_index"]
        if ti in selected_types:
            methods_by_type.setdefault(ti, []).append(dict(rec))
    for rows in methods_by_type.values():
        rows.sort(key=lambda r: r["native_rva"] if isinstance(r["native_rva"], int) else 10**18)
    rvas.sort()
    return methods_by_type, rvas, method_hits


def collect_fields(base: Path, selected_types: set[int]) -> list[dict]:
    out: list[dict] = []
    for rec in iter_json_records(base / "fields.json"):
        if rec["declaring_type_index"] in selected_types:
            out.append(dict(rec))
    return out


def caller_body_metrics(
    pe, rvas: list[int], caller: dict, cap: int = 1024,
    include_disassembly: bool = False,
) -> dict:
    rva = int(caller["native_rva"], 16)
    j = bisect.bisect_right(rvas, rva)
    gap = (rvas[j] - rva) if j < len(rvas) else 0
    window = min(gap, cap) if gap > 0 else cap
    raw, decoded = disasm_window(pe, rva, window)
    branch = sum(1 for i in decoded if i["mnemonic"].startswith("j") and i["mnemonic"] != "jmp")
    calls = []
    for i in decoded:
        if i["mnemonic"] == "call":
            disp = 0
            if i["op_str"].startswith("0x"):
                try:
                    dest = int(i["op_str"], 0)
                    calls.append({"site_rva": f"0x{i['rva']:X}", "dest_rva": f"0x{dest - pe.image_base:X}"})
                except ValueError:
                    calls.append({"site_rva": f"0x{i['rva']:X}", "dest": i["op_str"]})
    globals_used = [i["comment"] for i in decoded if i["comment"]]
    rets = [i["rva"] for i in decoded if i["mnemonic"] in ("ret", "retf")]
    row = {
        "method_index": caller["method_index"],
        "declaring_type_index": caller["declaring_type_index"],
        "name": caller["name"],
        "native_rva": f"0x{rva:X}",
        "gap_bytes": gap,
        "window_bytes": window,
        "instruction_count": len(decoded),
        "conditional_branch_count": branch,
        "direct_call_count": len(calls),
        "direct_calls": calls[:16],
        "globals_used": globals_used[:16],
        "first_ret_offset": (rets[0] - rva) if rets else None,
    }
    if include_disassembly:
        row["disassembly"] = [line_for(i) for i in decoded]
    return row


def analyze_ontaskbegin_callers(
    base: Path, pe, rvas: list[int], type_index_all: dict[int, dict]
) -> list[dict]:
    xrefs = json.loads(EXISTING_XREFS.read_text(encoding="utf-8"))
    by_method: dict[int, dict] = {}
    for target in xrefs["targets"]:
        if target["native_rva"] not in {f"0x{v:X}" for v in ANCHOR_TARGETS.values()}:
            continue
        for ref in target["rel32_refs"]:
            cm = ref.get("caller_method") or {}
            if cm.get("name") != "OnTaskBegin":
                continue
            if cm["method_index"] not in by_method:
                by_method[cm["method_index"]] = {
                    "caller_method": cm,
                    "caller_type": ref.get("caller_type") or {},
                    "target_rva": target["native_rva"],
                    "call_site_rva": ref.get("instruction_rva"),
                }
    rows = []
    for mi, entry in sorted(by_method.items()):
        metrics = caller_body_metrics(
            pe, rvas, entry["caller_method"],
            include_disassembly=False,
        )
        # Full disassembly is kept only for the bounded small-body candidates;
        # the 685-entry caller list stays compact and is complemented by
        # action_execution_shortlist_06.json for ranked metrics.
        if metrics["gap_bytes"] <= 400:
            metrics = caller_body_metrics(
                pe, rvas, entry["caller_method"],
                include_disassembly=True,
            )
        row = dict(entry)
        row.update(metrics)
        rows.append(row)
    rows.sort(key=lambda r: (r["gap_bytes"], r["native_rva"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=NORMALIZED_BASE)
    ap.add_argument("--output", type=Path,
                    default=REPO / "data" / "raw" / "4.4.54"
                    / "action_execution_discovery_06.json")
    args = ap.parse_args()

    type_index_all, type_hits, selected_types = collect_types(args.base)
    methods_by_type, rvas, method_hits = collect_methods(
        args.base, type_index_all, selected_types
    )
    pe = load_pe()
    ontask = analyze_ontaskbegin_callers(
        args.base, pe, rvas, type_index_all
    )

    selected_types_out = sorted(
        (type_index_all[ti] for ti in selected_types), key=lambda r: r["type_index"]
    )
    report = {
        "schema": "action_execution_discovery/1",
        "type_keywords": TYPE_KEYWORDS,
        "method_keywords": METHOD_KEYWORDS,
        "type_hits": type_hits,
        "method_hits": method_hits,
        "selected_type_count": len(selected_types_out),
        "selected_types": selected_types_out,
        "fields_for_selected_types": [],
        "anchor_methods": {
            k: {
                "method_index": v["method_index"],
                "native_rva": f"0x{v['native_rva']:X}",
            }
            for k, v in {
                k: next(
                    (
                        m
                        for rows in methods_by_type.values()
                        for m in rows
                        if m.get("native_rva") == rva
                        and m.get("name") == k
                    ),
                    None,
                )
                for k, rva in ANCHOR_TARGETS.items()
            }.items()
            if v is not None
        },
        "ontaskbegin_callers": ontask,
        "ontaskbegin_unique_count": len(ontask),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {args.output}")
    for k, rows in type_hits.items():
        print(f"== type keyword {k}: {len(rows)}")
        for r in rows[:25]:
            print(f"  {r['type_index']:>7}  {r['full_name']}")
    for k, rows in method_hits.items():
        if rows:
            print(f"== method keyword {k}: {len(rows)}")
            for r in rows[:10]:
                print(f"  M {r['method_index']:>7} {r.get('declaring_type')}.{r['name']} "
                      f"rva={r.get('native_rva')}")
    print(f"selected types: {len(selected_types_out)}")
    print(f"OnTaskBegin unique callers: {len(ontask)}")
    for r in ontask[:30]:
        print(f"  gap={r['gap_bytes']:>6} insn={r['instruction_count']:>3} "
              f"calls={r['direct_call_count']:>2} {r['native_rva']} "
              f"{r['caller_type'].get('full_name')} mi={r['method_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
