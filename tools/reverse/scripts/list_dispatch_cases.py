#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print selected case targets from a dispatch-table scan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scan", type=Path)
    ap.add_argument("--cases", nargs="+", type=int, default=[2, 8, 14, 16])
    ap.add_argument("--min-cases", type=int, default=17)
    ap.add_argument("--section", default="il2cpp")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    data = json.load(open(args.scan, encoding="utf-8"))
    rows = []
    for hit in data["dispatchers"]:
        if hit.get("section") != args.section:
            continue
        if hit["case_count"] < args.min_cases:
            continue
        cm = hit.get("containing_method") or {}
        by_case = {t["case"]: t for t in hit["targets"]}
        selected = []
        for c in args.cases:
            if c in by_case:
                t = by_case[c]
                selected.append({
                    "case": c,
                    "native_rva": t.get("native_rva"),
                    "name": t.get("name"),
                    "declaring_type": t.get("declaring_type"),
                })
        if not selected:
            continue
        rows.append({
            "dispatch_rva": hit["dispatch_rva"],
            "case_count": hit["case_count"],
            "containing_type": cm.get("declaring_type"),
            "containing_method": cm.get("name"),
            "cases": selected,
        })
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"matched": len(rows), "rows": rows}, f, indent=2)
    print(f"matched={len(rows)} -> {out}")
    for row in rows:
        print(f"{row['dispatch_rva']} cases={row['case_count']} "
              f"{row['containing_type']}.{row['containing_method']}")
        for c in row["cases"]:
            print(f"    case {c['case']:>3} -> {c['declaring_type']}.{c['name']} "
                  f"{c['native_rva']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
