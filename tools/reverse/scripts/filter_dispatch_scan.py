#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filter a dispatch-table scan JSON by containing type/method name patterns."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scan", type=Path)
    ap.add_argument("--name-regex", default=".")
    ap.add_argument("--min-cases", type=int, default=0)
    ap.add_argument("--max-cases", type=int, default=999999)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    data = json.load(open(args.scan, encoding="utf-8"))
    rx = re.compile(args.name_regex, re.IGNORECASE)
    rows = []
    for hit in data["dispatchers"]:
        cm = hit.get("containing_method") or {}
        full = f"{cm.get('declaring_type') or ''}.{cm.get('name') or ''}"
        if not rx.search(full):
            continue
        if not (args.min_cases <= hit["case_count"] <= args.max_cases):
            continue
        hit["containing_full_name"] = full
        rows.append(hit)
    rows.sort(key=lambda h: h["case_count"], reverse=True)
    out = {
        "schema": "mhy_dispatch_scan_filter/1",
        "source": str(args.scan.resolve()),
        "name_regex": args.name_regex,
        "matched": len(rows),
        "dispatchers": rows,
    }
    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"matched={len(rows)} -> {out_path}")
    for hit in rows[:60]:
        print(f"{hit['dispatch_rva']} cases={hit['case_count']} "
              f"{hit['containing_full_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
