#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rank matched action config -> generated executor rows by native body size.

Reads ``action_config_runtime_bridge_06.json``, computes exact next-method gaps
and bounded body metrics for every ``OnTaskBegin``, and joins the
EvaluateTarget / EvaluateSingleTarget caller counts from Batch 05 xrefs.
Output is the discovery shortlist used by the E4 recovery builder.
"""
from __future__ import annotations

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
)

OUT = REPO / "data" / "raw" / "4.4.54" / "action_execution_shortlist_06.json"


def build_rva_index() -> list[int]:
    rvas: list[int] = []
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        rva = rec.get("native_rva")
        if isinstance(rva, int) and rec.get("mapping_kind") == "DIRECT_NATIVE":
            rvas.append(rva)
    rvas.sort()
    return rvas


def main() -> int:
    bridge = json.loads(
        (REPO / "data" / "raw" / "4.4.54" / "action_config_runtime_bridge_06.json").read_text(
            encoding="utf-8"
        )
    )
    xrefs = json.loads(
        (REPO / "data" / "raw" / "4.4.54" / "target_selector_xrefs_05.json").read_text(
            encoding="utf-8"
        )
    )
    caller_rvas: dict[int, dict] = {}
    for target in xrefs["targets"]:
        for ref in target["rel32_refs"]:
            cm = ref.get("caller_method") or {}
            if isinstance(cm.get("native_rva"), str):
                rva = int(cm["native_rva"], 16)
                entry = caller_rvas.setdefault(rva, {"targets": set(), "sites": []})
                entry["targets"].add(target["native_rva"])
                entry["sites"].append(ref.get("instruction_rva"))

    rvas = build_rva_index()
    pe = load_pe()
    rows = []
    for row in bridge["matched_rows"]:
        for m in row["execution_methods"]:
            if m["name"] != "OnTaskBegin":
                continue
            rva = m["native_rva"]
            if not isinstance(rva, int):
                continue
            j = bisect.bisect_right(rvas, rva)
            gap = (rvas[j] - rva) if j < len(rvas) else 0
            window = min(gap, 1024)
            _, decoded = disasm_window(pe, rva, window)
            branch = sum(
                1
                for i in decoded
                if i["mnemonic"].startswith("j") and i["mnemonic"] != "jmp"
            )
            calls = [
                int(i["op_str"], 0) - pe.image_base
                for i in decoded
                if i["mnemonic"] == "call" and i["op_str"].startswith("0x")
            ]
            entry = caller_rvas.get(rva, {"targets": set(), "sites": []})
            rows.append(
                {
                    "config_candidates": row["config_candidates"],
                    "executor_type": row["executor_type"],
                    "executor_type_index": row["executor_type_index"],
                    "method_index": m["method_index"],
                    "native_rva": f"0x{rva:X}",
                    "gap_bytes": gap,
                    "window_bytes": window,
                    "instruction_count": len(decoded),
                    "conditional_branch_count": branch,
                    "direct_call_count": len(calls),
                    "callee_rvas": [f"0x{c:X}" for c in calls[:24]],
                    "target_eval_call_sites": sorted(entry["sites"]),
                    "calls_evaluate_target": any(
                        t == "0xE6F1530" for t in entry["targets"]
                    ),
                    "calls_evaluate_single_target": any(
                        t == "0xE6D5830" for t in entry["targets"]
                    ),
                }
            )
    rows.sort(key=lambda r: (r["gap_bytes"], r["native_rva"]))
    report = {
        "schema": "action_execution_shortlist/1",
        "row_count": len(rows),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT} rows={len(rows)}")
    for r in rows[:80]:
        print(
            f"gap={r['gap_bytes']:>5} insn={r['instruction_count']:>3} "
            f"branch={r['conditional_branch_count']:>2} "
            f"calls={r['direct_call_count']:>2} evalT={int(r['calls_evaluate_target'])} "
            f"evalS={int(r['calls_evaluate_single_target'])} "
            f"{r['native_rva']} {r['executor_type']} <- {r['config_candidates']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
