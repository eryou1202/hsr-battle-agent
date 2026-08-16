#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-version validation for the MKIOEPLIEIH polymorphic parser registry.

Compares version-independent identity only:
  * same discriminator set (1..min_count),
  * same concrete Runtime TypeDefinition name per discriminator,
  * same concrete parser method name per discriminator,
  * native RVAs / method indices differ (expected per version),
  * builder/dispatcher declaring type name identical,
  * dispatch shape (discriminator -> array slot -> [entry+8]) identical.

The registry entry count itself is version-specific and is reported, not
required to be equal.
"""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, type=Path)
    ap.add_argument("--new", required=True, type=Path)
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    a = load(args.old)
    b = load(args.new)
    am = {m["discriminator"]: m for m in a["mappings"] if m["discriminator"] > 0}
    bm = {m["discriminator"]: m for m in b["mappings"] if m["discriminator"] > 0}
    common = sorted(set(am) & set(bm))
    rows = []
    for disc in common:
        x, y = am[disc], bm[disc]
        rows.append({
            "discriminator": disc,
            "old": {
                "runtime_type_name": x.get("concrete_runtime_type_name"),
                "parser_method_name": x.get("concrete_parser_method_name"),
                "parser_method_index": x.get("concrete_parser_method_index"),
                "parser_native_rva": x.get("concrete_parser_native_rva"),
            },
            "new": {
                "runtime_type_name": y.get("concrete_runtime_type_name"),
                "parser_method_name": y.get("concrete_parser_method_name"),
                "parser_method_index": y.get("concrete_parser_method_index"),
                "parser_native_rva": y.get("concrete_parser_native_rva"),
            },
            "same_runtime_type": bool(
                x.get("concrete_runtime_type_name")
                and x.get("concrete_runtime_type_name") == y.get("concrete_runtime_type_name")),
            "same_parser_method": bool(
                x.get("concrete_parser_method_name")
                and x.get("concrete_parser_method_name") == y.get("concrete_parser_method_name")),
            "rva_differs": bool(
                x.get("concrete_parser_native_rva")
                and x.get("concrete_parser_native_rva") != y.get("concrete_parser_native_rva")),
        })

    checks = {
        "same_registry_type": (a["registry"]["builder_type"] == b["registry"]["builder_type"]
                               == a["registry"]["dispatcher_type"]
                               == b["registry"]["dispatcher_type"] == "MKIOEPLIEIH"),
        "same_dispatch_shape": (
            a["registry"]["array_slots_offset"] == b["registry"]["array_slots_offset"]
            and a["registry"]["entry_parser_slot_offset"]
            == b["registry"]["entry_parser_slot_offset"]
            and "ULEB128" in a["registry"]["discriminator_reader"]
            and "ULEB128" in b["registry"]["discriminator_reader"]),
        "common_discriminator_count": len(common),
        "old_entry_count": a["registry"]["entry_count"],
        "new_entry_count": b["registry"]["entry_count"],
        "all_common_same_runtime_type": all(r["same_runtime_type"] for r in rows),
        "all_common_same_parser_method": all(r["same_parser_method"] for r in rows),
        "all_common_rva_differ": all(r["rva_differs"] for r in rows if
                                     r["old"]["parser_native_rva"] and r["new"]["parser_native_rva"]),
        "discriminator_only_in_old": sorted(set(am) - set(bm)),
        "discriminator_only_in_new": sorted(set(bm) - set(am)),
    }
    # The serialized registry order is stable modulo whole-index insertions;
    # align the concrete Runtime Type sequences with difflib.
    old_discs = sorted(am)
    new_discs = sorted(bm)
    old_seq = [am[d].get("concrete_runtime_type_name") or "NULL" for d in old_discs]
    new_seq = [bm[d].get("concrete_runtime_type_name") or "NULL" for d in new_discs]
    sm = difflib.SequenceMatcher(a=old_seq, b=new_seq, autojunk=False)
    aligned_rows = []
    insertions = []
    deletions = []
    aligned_same_parser = True
    aligned_rva_differs = True
    aligned_rva_checked = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                d_old, d_new = old_discs[i1 + k], new_discs[j1 + k]
                x, y = am[d_old], bm[d_new]
                same_parser = (x.get("concrete_parser_method_name")
                               == y.get("concrete_parser_method_name"))
                rva_diff = bool(
                    x.get("concrete_parser_native_rva")
                    and x.get("concrete_parser_native_rva") != y.get("concrete_parser_native_rva"))
                aligned_same_parser &= same_parser
                if x.get("concrete_parser_native_rva") and y.get("concrete_parser_native_rva"):
                    aligned_rva_checked += 1
                    aligned_rva_differs &= rva_diff
                aligned_rows.append({
                    "old_discriminator": d_old,
                    "new_discriminator": d_new,
                    "runtime_type_name": x.get("concrete_runtime_type_name"),
                    "old_parser": {
                        "method_name": x.get("concrete_parser_method_name"),
                        "method_index": x.get("concrete_parser_method_index"),
                        "native_rva": x.get("concrete_parser_native_rva"),
                    },
                    "new_parser": {
                        "method_name": y.get("concrete_parser_method_name"),
                        "method_index": y.get("concrete_parser_method_index"),
                        "native_rva": y.get("concrete_parser_native_rva"),
                    },
                })
        elif tag == "insert":
            insertions.append({
                "position_after_old_index": i1 - 1,
                "new_discriminators": new_discs[j1:j2],
                "runtime_type_names": new_seq[j1:j2],
            })
        elif tag == "delete":
            deletions.append({
                "old_discriminators": old_discs[i1:i2],
                "runtime_type_names": old_seq[i1:i2],
            })
    checks["sequence_ratio"] = sm.ratio()
    checks["aligned_pairs"] = len(aligned_rows)
    checks["aligned_all_same_parser_method"] = aligned_same_parser
    checks["aligned_all_rva_differ"] = aligned_rva_differs
    checks["aligned_rva_checked"] = aligned_rva_checked
    checks["new_insertions"] = insertions
    checks["old_deletions"] = deletions

    direct_ok = (checks["same_registry_type"] and checks["same_dispatch_shape"]
                 and checks["all_common_same_runtime_type"]
                 and checks["all_common_same_parser_method"])
    aligned_ok = (checks["same_registry_type"] and checks["same_dispatch_shape"]
                  and checks["sequence_ratio"] >= 0.99
                  and checks["aligned_all_same_parser_method"])
    if direct_ok:
        status = "BRIDGE_CROSS_VERSION_OK"
    elif aligned_ok:
        status = "BRIDGE_CROSS_VERSION_OK_WITH_INSERTIONS"
    else:
        status = "BRIDGE_CROSS_VERSION_MISMATCH"

    result = {
        "schema": "ability_mixin_registry_cross_version/1",
        "old_file": str(args.old.resolve()),
        "old_version": a["game_version"],
        "new_file": str(args.new.resolve()),
        "new_version": b["game_version"],
        "checks": checks,
        "rows": rows,
        "aligned_rows": aligned_rows,
        "status": status,
    }
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out} status={status}")
    for k, v in checks.items():
        print(f"  {k}: {v}")
    return 0 if status.startswith("BRIDGE_CROSS_VERSION_OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
