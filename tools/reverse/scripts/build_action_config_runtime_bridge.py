#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Action/Task config -> generated runtime executor bridge.

Method (identical strategy to target_selector Batch 05, E3 metadata identity
combined with the E4 native ctor evidence):

  * a config family carries ``MGMEGEDLMAK`` with exactly two parameters; its
    second parameter type_reference is the runtime object type;
  * a generated task executor class declares ``OnTaskBegin`` plus a 2-parameter
    ``.ctor`` whose **second** parameter type_reference matches that runtime
    object type (native ctors store arg0 at [+0x18] = TaskContext and arg1 at
    [+0x20] = config).

Names are discovery hints only; the bridge is closed by exact
type-reference match + native ctor/store evidence.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import NORMALIZED_BASE, iter_records  # noqa: E402

OUT = REPO / "data" / "raw" / "4.4.54" / "action_config_runtime_bridge_06.json"


def main() -> int:
    # Pass 1: parameters by method
    param_refs: dict[int, list[int]] = defaultdict(list)
    for rec in iter_records(NORMALIZED_BASE / "parameters.json"):
        param_refs[rec["method_index"]].append(rec["type_reference"])

    # Pass 2: types index
    types: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "types.json"):
        types[rec["type_index"]] = rec

    # Pass 3: methods by declaring type, one stream
    methods_by_type: dict[int, list[dict]] = defaultdict(list)
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        methods_by_type[rec["declaring_type_index"]].append(rec)

    configs: dict[int, list[dict]] = defaultdict(list)
    executors: dict[int, list[dict]] = defaultdict(list)
    executor_class_count = 0
    config_family_count = 0

    for ti, ms in methods_by_type.items():
        t = types.get(ti, {})
        name = t.get("full_name", "")
        names = {m["name"] for m in ms}

        if "MGMEGEDLMAK" in names:
            config_family_count += 1
            mg = next(m for m in ms if m["name"] == "MGMEGEDLMAK")
            refs = param_refs.get(mg["method_index"], [])
            if len(refs) == 2 and not name.endswith("`1"):
                configs[refs[1]].append(
                    {
                        "type_index": ti,
                        "full_name": name,
                        "method_index": mg["method_index"],
                        "native_rva": mg.get("native_rva"),
                    }
                )

        if "OnTaskBegin" in names:
            executor_class_count += 1
            ctor = next((m for m in ms if m["name"] == ".ctor"), None)
            if ctor is not None:
                refs = param_refs.get(ctor["method_index"], [])
                if len(refs) == 2:
                    executors[refs[1]].append(
                        {
                            "type_index": ti,
                            "full_name": name,
                            "ctor_method_index": ctor["method_index"],
                            "ctor_native_rva": ctor.get("native_rva"),
                            "exec_methods": [
                                {
                                    "method_index": m["method_index"],
                                    "name": m["name"],
                                    "native_rva": m.get("native_rva"),
                                    "parameter_count": m["parameter_count"],
                                    "parameter_refs": param_refs.get(
                                        m["method_index"], []
                                    ),
                                    "return_type_reference": m[
                                        "return_type_reference"
                                    ],
                                }
                                for m in ms
                                if m["name"]
                                in (
                                    "OnTaskBegin",
                                    "OnTaskUpdate",
                                    "OnTaskEnd",
                                    "OnTaskReset",
                                    "OnTaskFailed",
                                    "Tick",
                                    "Dispose",
                                )
                            ],
                        }
                    )

    rows = []
    for tr in sorted(executors):
        cfs = configs.get(tr, [])
        for ev in executors[tr]:
            rows.append(
                {
                    "config_type_ref": tr,
                    "config_candidates": [c["full_name"] for c in cfs],
                    "config_rows": cfs,
                    "executor_type": ev["full_name"],
                    "executor_type_index": ev["type_index"],
                    "ctor": {
                        "method_index": ev["ctor_method_index"],
                        "native_rva": ev["ctor_native_rva"],
                    },
                    "execution_methods": ev["exec_methods"],
                }
            )
    matched = [r for r in rows if r["config_rows"]]
    unmatched = sorted({r["config_type_ref"] for r in rows if not r["config_rows"]})
    report = {
        "schema": "action_config_runtime_bridge/1",
        "config_family_count": config_family_count,
        "config_runtime_type_ref_count": len(configs),
        "executor_class_count": executor_class_count,
        "executor_type_ref_count": len(executors),
        "matched_rows": matched,
        "unmatched_executor_type_refs": unmatched,
        "identity_rule": (
            "generated executor .ctor(parameter 2 type_reference) == "
            "config MGMEGEDLMAK(parameter 2 type_reference); native ctor "
            "stores arg1 at executor [+0x20] (config slot) and arg0 at "
            "[+0x18] (TaskContext slot)"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT}")
    print(
        f"config families={config_family_count} runtime_type_refs={len(configs)} "
        f"executor classes={executor_class_count} executor_type_refs={len(executors)}"
    )
    print(f"matched rows={len(matched)} unmatched type_refs={len(unmatched)}")
    for r in matched[:40]:
        print(
            f"ref={r['config_type_ref']:>7} exec={r['executor_type']:14} <- "
            f"{r['config_candidates']} "
            f"methods={[(m['name'], m['native_rva']) for m in r['execution_methods']]}"
        )
    if unmatched:
        print("first unmatched:", unmatched[:40])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
