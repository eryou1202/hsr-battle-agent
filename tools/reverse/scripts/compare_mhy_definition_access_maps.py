#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-version validation for the 0x70 -> 0x84 -> 0x12C access maps.

Loads two `mhy_0x84_record_access_map` JSON files (current and reference) and
compares only the version-independent shape:

  * template field decode (field/op/const) for the chain,
  * entry sizes,
  * field access map (offset / width / decode / consumer RVAs),
  * identifier resolver constants,
  * identifier samples for equal record indices,
  * boolean structural validations (method-range cumulative, bounds).

Fixed file offsets are intentionally NOT compared.
"""
import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("current")
    ap.add_argument("reference")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    cur = json.load(open(args.current, encoding="utf-8"))
    ref = json.load(open(args.reference, encoding="utf-8"))

    rows = []

    def check(name, a, b, note=""):
        rows.append({"check": name, "current": a, "reference": b,
                     "equal": a == b, "note": note})

    check("schema", cur["schema"], ref["schema"])
    check("entry_size_0x84", cur["record_table"]["entry_size"],
          ref["record_table"]["entry_size"])
    check("index_stride", cur["record_table"]["index_stride"],
          ref["record_table"]["index_stride"])
    check("field_access_map", cur["field_access_map"], ref["field_access_map"],
          "decode rules, widths, consumer RVAs")
    check("identifier_resolver_constants", cur["identifier_resolver"]["constants"],
          ref["identifier_resolver"]["constants"])
    check("method_range_cumulative_ok",
          cur["field_validations"]["method_range"]["cumulative_start_plus_count_ok"],
          ref["field_validations"]["method_range"]["cumulative_start_plus_count_ok"])
    check("type_descriptor_0x12C_bounds_ok",
          cur["field_validations"]["type_descriptor_range_0x12C"]["all_referenced_ranges_in_bounds"],
          ref["field_validations"]["type_descriptor_range_0x12C"]["all_referenced_ranges_in_bounds"])
    check("type_relation_0xF0_bounds_ok",
          cur["field_validations"]["type_relation_index_0xF0"]["all_indices_in_bounds"],
          ref["field_validations"]["type_relation_index_0xF0"]["all_indices_in_bounds"])
    check("consumer_scan_site_count", cur["consumer_scan"]["site_count"],
          ref["consumer_scan"]["site_count"])

    # Identifier samples: compare first 12 common indices.
    cur_ids = {r["record_index"]: r for r in cur["identifier_resolver"]["samples"]}
    ref_ids = {r["record_index"]: r for r in ref["identifier_resolver"]["samples"]}
    common = sorted(set(cur_ids) & set(ref_ids))[:12]
    sample_rows = []
    for i in common:
        sample_rows.append({
            "record_index": i,
            "current": f"{cur_ids[i]['namespace']}.{cur_ids[i]['identifier']}",
            "reference": f"{ref_ids[i]['namespace']}.{ref_ids[i]['identifier']}",
            "equal": (cur_ids[i]["identifier"] == ref_ids[i]["identifier"]
                      and cur_ids[i]["namespace"] == ref_ids[i]["namespace"]),
        })
    all_samples_equal = all(r["equal"] for r in sample_rows)
    rows.append({"check": "identifier_samples_common_indices",
                 "current": [r["current"] for r in sample_rows],
                 "reference": [r["reference"] for r in sample_rows],
                 "equal": all_samples_equal, "note": "first common record indices"})

    # Proof status (when present).
    cur_status = (cur.get("type_registry_proof") or {}).get("status")
    ref_status = (ref.get("type_registry_proof") or {}).get("status")
    if cur_status or ref_status:
        check("type_registry_proof_status", cur_status, ref_status)

    out = {
        "schema": "mhy_0x84_cross_version_validation/1",
        "current": {"path": cur["metadata"], "template_rva": cur["template_rva"],
                    "record_count": cur["record_table"]["capacity_to_next_table"],
                    "magic_eq_count": cur["record_table"]["field_0x0C_stats"]["field_0x0C_equal_0x1C2AD2AB"]},
        "reference": {"path": ref["metadata"], "template_rva": ref["template_rva"],
                      "record_count": ref["record_table"]["capacity_to_next_table"],
                      "magic_eq_count": ref["record_table"]["field_0x0C_stats"]["field_0x0C_equal_0x1C2AD2AB"]},
        "checks": rows,
        "all_equal": all(r["equal"] for r in rows),
        "fixed_file_offsets_not_compared": True,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {args.output}; all_equal={out['all_equal']}")
    for r in rows:
        mark = "PASS" if r["equal"] else "DIFF"
        print(f"  {mark} {r['check']}")
    return 0 if out["all_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
