#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare two bridge registry proofs for version-independent mapping identity.

Checks, per serialized domain:
  * same type_code set;
  * same runtime_type_name per type_code;
  * same parser_method_name per type_code;
  * native RVA / method index differ (expected version-specific);
  * factory declaring type name identical.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))


def compare(old: Path, new: Path, domain: str) -> dict:
    a = load(old)
    b = load(new)
    checks = {}
    rows = []
    am = {m["type_code"]: m for m in a["mappings"]}
    bm = {m["type_code"]: m for m in b["mappings"]}
    checks["same_case_set"] = set(am) == set(bm)
    checks["same_factory_type"] = (a["factory"]["runtime_type_name"]
                                   == b["factory"]["runtime_type_name"])
    checks["same_mechanism_kind"] = (a["mechanism"]["kind"]
                                     == b["mechanism"]["kind"])
    for code in sorted(set(am) | set(bm)):
        x = am.get(code)
        y = bm.get(code)
        rows.append({
            "type_code": code,
            "old": x,
            "new": y,
            "same_runtime_type": bool(
                x and y and x["runtime_type_name"] == y["runtime_type_name"]),
            "same_parser_method": bool(
                x and y and x["parser_method_name"] == y["parser_method_name"]),
            "rva_differs": bool(
                x and y and x["parser_native_rva"] != y["parser_native_rva"]),
        })
    checks["all_same_runtime_type"] = all(r["same_runtime_type"] for r in rows)
    checks["all_same_parser_method"] = all(r["same_parser_method"] for r in rows)
    checks["all_rva_differ"] = all(r["rva_differs"] for r in rows)
    return {
        "domain": domain,
        "old_file": str(old),
        "new_file": str(new),
        "checks": checks,
        "rows": rows,
        "status": ("BRIDGE_CROSS_VERSION_OK"
                   if checks["same_case_set"] and checks["same_factory_type"]
                   and checks["all_same_runtime_type"]
                   and checks["all_same_parser_method"]
                   else "BRIDGE_CROSS_VERSION_MISMATCH"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, type=Path, nargs="+")
    ap.add_argument("--new", required=True, type=Path, nargs="+")
    ap.add_argument("--domain", required=True, action="append")
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()
    if not (len(args.old) == len(args.new) == len(args.domain)):
        raise SystemExit("--old/--new/--domain must have equal item counts")
    results = [compare(o, n, d) for o, n, d in zip(args.old, args.new, args.domain)]
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"schema": "mhy_bridge_cross_version/1",
                   "results": results,
                   "all_ok": all(r["status"] == "BRIDGE_CROSS_VERSION_OK"
                                 for r in results)}, f, indent=2)
    for r in results:
        print(f"{r['domain']}: {r['status']} "
              f"same_case={r['checks']['same_case_set']} "
              f"same_types={r['checks']['all_same_runtime_type']} "
              f"rva_differs={r['checks']['all_rva_differ']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
