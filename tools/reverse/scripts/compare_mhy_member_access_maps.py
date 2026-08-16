#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-version validation for the MHY Method/Field member registry proofs.

Loads two `mhy_member_registry_proof` JSON files (4.4.54 and 4.4.0) and
compares version-independent shape only:

  * registry table / entry-size / transform identities,
  * field access maps embedded by the analyzers (via validation files when
    provided, or from the proof's registry block),
  * boolean structural validations,
  * member names for semantic sample types that exist in both versions.

Fixed file offsets and record counts are intentionally not compared.
"""
import argparse
import json
from pathlib import Path


def get_access_maps(proof: dict) -> tuple[dict, dict]:
    # The consolidated proof carries the registry description; optional
    # `method_map` / `field_map` keys allow the caller to pass richer maps.
    registry = proof.get("registry", {})
    return registry.get("method_definition", {}), registry.get("field_definition", {})


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

    check("schema", cur.get("schema"), ref.get("schema"))
    check("status", cur.get("status"), ref.get("status"))

    cm, cf = get_access_maps(cur)
    rm, rf = get_access_maps(ref)
    check("method_table_rule", cm.get("table"), rm.get("table"))
    check("method_name_path", cm.get("name"), rm.get("name"))
    check("method_declaring_type_field", cm.get("declaring_type_index"),
          rm.get("declaring_type_index"))
    check("method_parameter_fields",
          (cm.get("parameter_start"), cm.get("parameter_count")),
          (rm.get("parameter_start"), rm.get("parameter_count")))
    check("method_return_type_field", cm.get("return_type_reference"),
          rm.get("return_type_reference"))
    check("parameter_table_rule", cur.get("registry", {}).get("parameter_definition", {}).get("table"),
          ref.get("registry", {}).get("parameter_definition", {}).get("table"))
    check("field_table_rule", cf.get("table"), rf.get("table"))
    check("field_name_path", cf.get("name"), rf.get("name"))
    check("field_type_reference_path", cf.get("type_reference"), rf.get("type_reference"))
    check("type_field_range_rule", cur.get("registry", {}).get("type_definition", {}).get("field_range"),
          ref.get("registry", {}).get("type_definition", {}).get("field_range"))
    check("type_method_range_rule", cur.get("registry", {}).get("type_definition", {}).get("method_range"),
          ref.get("registry", {}).get("type_definition", {}).get("method_range"))

    cv = cur.get("validation_summary", {})
    rv = ref.get("validation_summary", {})
    for key in ("method_partition_exact_once", "method_declaring_type_all_match",
                "parameter_partition_exact_once", "field_partition_exact_once",
                "field_names_printable"):
        check(f"validation_{key}", cv.get(key), rv.get(key))

    # First mscorlib member samples live at identical record indices in both
    # versions, so their names must be identical.
    cur_method_samples = [r["name"] for r in cur.get("method_samples", [])][:12]
    ref_method_samples = [r["name"] for r in ref.get("method_samples", [])][:12]
    check("method_samples_common_indices", cur_method_samples, ref_method_samples,
          "first method records decode identically in both versions")
    cur_field_samples = [r["name"] for r in cur.get("field_samples", [])][:12]
    ref_field_samples = [r["name"] for r in ref.get("field_samples", [])][:12]
    check("field_samples_common_indices", cur_field_samples, ref_field_samples,
          "first field records decode identically in both versions")

    # Semantic game-type samples may be ordered differently between builds, so
    # compare member-name multisets rather than ordered lists. At least five
    # common types must agree on field names and at least three on method names.
    from collections import Counter
    cur_types = {t["full_name"]: t for t in cur.get("semantic_battle_sanity", [])}
    ref_types = {t["full_name"]: t for t in ref.get("semantic_battle_sanity", [])}
    common = sorted(set(cur_types) & set(ref_types))
    sample_rows = []
    field_name_match = 0
    method_name_match = 0
    for name in common:
        a = cur_types[name]
        b = ref_types[name]
        a_methods = Counter(m["name"] for m in a["methods"])
        b_methods = Counter(m["name"] for m in b["methods"])
        a_fields = Counter(f["name"] for f in a["fields"])
        b_fields = Counter(f["name"] for f in b["fields"])
        method_ok = a_methods == b_methods
        field_ok = a_fields == b_fields
        field_name_match += int(field_ok)
        method_name_match += int(method_ok)
        sample_rows.append({
            "full_name": name,
            "current_methods": [m["name"] for m in a["methods"]],
            "reference_methods": [m["name"] for m in b["methods"]],
            "current_fields": [f["name"] for f in a["fields"]],
            "reference_fields": [f["name"] for f in b["fields"]],
            "method_name_multiset_equal": method_ok,
            "field_name_multiset_equal": field_ok,
        })
    semantic_ok = field_name_match >= 5 and method_name_match >= 3
    rows.append({
        "check": "semantic_sample_member_names_common_types",
        "current": {
            "common_types": [r["full_name"] for r in sample_rows],
            "method_name_multiset_matches": method_name_match,
            "field_name_multiset_matches": field_name_match,
        },
        "reference": {
            "common_types": [r["full_name"] for r in sample_rows],
            "method_name_multiset_matches": method_name_match,
            "field_name_multiset_matches": field_name_match,
        },
        "equal": semantic_ok,
        "note": "member order may differ between builds; multiset agreement is required",
    })

    out = {
        "schema": "mhy_member_cross_version_validation/1",
        "current": {
            "path": cur.get("metadata"),
            "template_rva": cur.get("template_rva"),
            "counts": cur.get("counts"),
        },
        "reference": {
            "path": ref.get("metadata"),
            "template_rva": ref.get("template_rva"),
            "counts": ref.get("counts"),
        },
        "checks": rows,
        "semantic_samples": sample_rows,
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
