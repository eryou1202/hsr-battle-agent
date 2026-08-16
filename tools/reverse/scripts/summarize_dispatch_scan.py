#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print / save a compact summary of a dispatch-table scan."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scan", type=Path)
    ap.add_argument("--section", default=None)
    ap.add_argument("--min-cases", type=int, default=0)
    ap.add_argument("--max-cases", type=int, default=999999)
    ap.add_argument("--min-rva", type=lambda x: int(x, 0), default=0)
    ap.add_argument("--name-regex", default=None)
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()

    data = json.load(open(args.scan, encoding="utf-8"))
    rows = []
    for h in data["dispatchers"]:
        rva = int(h["dispatch_rva"], 16)
        if args.section and h.get("section") != args.section:
            continue
        if rva < args.min_rva:
            continue
        if not (args.min_cases <= h["case_count"] <= args.max_cases):
            continue
        cm = h.get("containing_method") or {}
        full = f"{cm.get('declaring_type') or ''}.{cm.get('name') or ''}"
        if args.name_regex and not re.search(args.name_regex, full, re.IGNORECASE):
            continue
        rows.append({
            "case_count": h["case_count"],
            "dispatch_rva": h["dispatch_rva"],
            "declaring_type": cm.get("declaring_type"),
            "name": cm.get("name"),
        })
    rows.sort(key=lambda r: (r["case_count"], r["dispatch_rva"]))
    lines = [f"{r['case_count']:>4} {r['dispatch_rva']} "
             f"{r['declaring_type']} {r['name']}" for r in rows]
    text = "\n".join(lines) + ("\n" if lines else "")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output} rows={len(rows)}")
    else:
        print(f"rows={len(rows)}")
        print(text[:20000])
    c = Counter((r["declaring_type"], r["name"]) for r in rows)
    print("top containing methods:")
    for (t, n), cnt in c.most_common(20):
        print(f"  {cnt:>3}  {t}.{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
