#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate historical Black Swan first_mixin_type observations against the
recovered MKIOEPLIEIH polymorphic registry.

The historical manifest fields `wrapper_type_code` / `ability_bit_field` /
`first_mixin_type` were parsed before the runtime mechanism was known and are
NOT semantic type names. This tool only checks:

  * each observed first_mixin_type value is inside the code-proven registry
    discriminator range and has a concrete mapping;
  * the observed values 2/8/14/16 resolve to distinct Runtime Classes.

It does NOT claim that the historical byte at that offset is the registry
discriminator field of the final serializer; that byte-level identity remains
a separate serialized-record parsing question.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headers-csv", required=True, type=Path)
    ap.add_argument("--bridge-json", required=True, type=Path)
    ap.add_argument("--game-version", default="4.4.54")
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    bridge = json.load(open(args.bridge_json, encoding="utf-8"))
    by_disc = {m["discriminator"]: m for m in bridge["mappings"]}

    rows = []
    with open(args.headers_csv, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = row.get("first_mixin_type", "").strip()
            if not raw:
                continue
            code = int(raw)
            mapping = by_disc.get(code)
            rows.append({
                "record_index": int(row["index"]),
                "record_name": row["expected_name"],
                "historical_first_mixin_type": code,
                "registry_discriminator": code,
                "registry_mapping_present": mapping is not None,
                "runtime_type_name": (mapping.get("concrete_runtime_type_name")
                                      if mapping else None),
                "parser_method_name": (mapping.get("concrete_parser_method_name")
                                       if mapping else None),
                "parser_method_index": (mapping.get("concrete_parser_method_index")
                                        if mapping else None),
                "parser_native_rva": (mapping.get("concrete_parser_native_rva")
                                      if mapping else None),
            })

    codes = Counter(r["historical_first_mixin_type"] for r in rows)
    checks = {
        "observed_code_set": sorted(codes),
        "all_in_registry_range": all(by_disc.get(c) is not None for c in codes),
        "observed_2_8_14_16_distinct_types": len({
            by_disc[c].get("concrete_runtime_type_name") for c in (2, 8, 14, 16)
            if by_disc.get(c) and by_disc[c].get("concrete_runtime_type_name")}) == 4,
        "mapping_2": by_disc[2].get("concrete_runtime_type_name") if by_disc.get(2) else None,
        "mapping_8": by_disc[8].get("concrete_runtime_type_name") if by_disc.get(8) else None,
        "mapping_14": by_disc[14].get("concrete_runtime_type_name") if by_disc.get(14) else None,
        "mapping_16": by_disc[16].get("concrete_runtime_type_name") if by_disc.get(16) else None,
    }
    result = {
        "schema": "ability_mixin_black_swan_validation/1",
        "game_version": args.game_version,
        "headers_csv": str(args.headers_csv.resolve()),
        "bridge_json": str(args.bridge_json.resolve()),
        "record_count": len(rows),
        "code_frequencies": dict(codes),
        "checks": checks,
        "records": rows,
        "semantic_status": "REGISTRY_RANGE_VALIDATED_ONLY",
        "note": "Historical field name 'first_mixin_type' remains a provisional "
                "label; only the registry discriminator range/mapping is checked.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {args.output} records={len(rows)} codes={dict(codes)}")
    for c in sorted(codes):
        print(f"  code {c:>3} x{codes[c]:>2} -> {checks.get(f'mapping_{c}')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
