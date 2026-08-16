#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-version validation for the MHY method code registry proofs.

Compares version-independent mapping shape, not absolute RVAs:

  * MethodDefinition schema / count source
  * consumer shape: method_index -> registry.field -> qword[method_index*8]
  * table stats: one slot per method, null slots, all non-null executable,
    all non-null pointers unique
  * semantic method identity: same metadata name for common indices maps to
    valid executable entries in both versions (RVA is expected to differ)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-proof", required=True, type=Path)
    ap.add_argument("--new-proof", required=True, type=Path)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    old = load(args.old_path if hasattr(args, "old_path") else args.old_proof)
    new = load(args.new_proof)

    checks = {}
    rows = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks[name] = {"pass": bool(ok), "detail": detail}

    check("schema_matches", old.get("schema") == new.get("schema"),
          f"{old.get('schema')} vs {new.get('schema')}")
    check("method_definition_entry_size_26",
          old["method_definition"]["entry_size"] == 26
          and new["method_definition"]["entry_size"] == 26,
          "both entry_size=26")

    oc = old["mapping_rule"]["consumer"]
    nc = new["mapping_rule"]["consumer"]
    check("consumer_shape_matches",
          "mov rax, qword ptr" in oc["disassembly"][1]
          and "mov rax, qword ptr" in nc["disassembly"][1]
          and all("mov r12, qword ptr [rax + r14*8]" in line
                  for line in (oc["disassembly"][2], nc["disassembly"][2])),
          f"old field offset=0x{oc['registry_code_table_field_offset']:X}, "
          f"new field offset=0x{nc['registry_code_table_field_offset']:X}")
    check("consumer_method_index_markers_present",
          oc["method_index_markers_present"] and nc["method_index_markers_present"],
          "both decode TypeDefinition method index +0x08 ^ 0x1A7AF5FE / +0x34 + 0x5F93")
    check("first_4_slots_zero_both",
          old["mapping_rule"]["locator"]["first_4_slots_zero"]
          and new["mapping_rule"]["locator"]["first_4_slots_zero"],
          "generic AnonymousType methods have no direct body in both versions")

    os_ = old["statistics"]
    ns = new["statistics"]
    check("one_table_slot_per_method",
          os_["table_slots"] == os_["total_method_defs"]
          and ns["table_slots"] == ns["total_method_defs"],
          f"old={os_['table_slots']}/{os_['total_method_defs']} "
          f"new={ns['table_slots']}/{ns['total_method_defs']}")
    check("all_nonnull_executable",
          os_["out_of_range_nonnull_slots"] == 0 and ns["out_of_range_nonnull_slots"] == 0,
          f"old bad={os_['out_of_range_nonnull_slots']} new bad={ns['out_of_range_nonnull_slots']}")
    check("all_nonnull_unique",
          os_["duplicate_native_pointer_slots"] == 0 and ns["duplicate_native_pointer_slots"] == 0,
          "every non-null slot has a unique native RVA in both versions")
    check("native_sections_il2cpp",
          set(os_["native_sections"].keys()) == {"il2cpp"}
          and set(ns["native_sections"].keys()) == {"il2cpp"},
          f"old={os_['native_sections']} new={ns['native_sections']}")

    old_by_idx = {int(r["method_index"]): r for r in old["samples"]}
    new_by_idx = {int(r["method_index"]): r for r in new["samples"]}
    common = sorted(set(old_by_idx) & set(new_by_idx))
    semantic_matches = 0
    both_native = 0
    rva_different = 0
    for idx in common:
        o = old_by_idx[idx]
        n = new_by_idx[idx]
        if (o["declaring_type"], o["method_name"]) == (n["declaring_type"], n["method_name"]):
            semantic_matches += 1
        if o["native_rva"] is not None and n["native_rva"] is not None:
            both_native += 1
            if o["native_rva"] != n["native_rva"]:
                rva_different += 1
    check("common_method_semantic_identity",
          semantic_matches == len(common),
          f"{semantic_matches}/{len(common)} common samples have identical type+method names")
    check("common_native_methods_have_valid_rva_both",
          both_native == len([i for i in common
                              if old_by_idx[i]["native_rva"] is not None
                              or new_by_idx[i]["native_rva"] is not None]),
          f"{both_native} common direct-native samples resolve in both versions")
    check("native_rva_expected_to_differ",
          rva_different == both_native,
          f"{rva_different}/{both_native} RVAs differ between versions")

    status = "METHOD_CODE = RVA_REGISTRY_PROOF" if all(
        v["pass"] for v in checks.values()) else "METHOD_CODE = PARTIAL_MAPPING_RECOVERED"
    result = {
        "schema": "mhy_method_code_cross_version_validation/1",
        "status": status,
        "old": str(args.old_proof),
        "new": str(args.new_proof),
        "version_independent_mechanism": {
            "mapping_rule": "qword(code_table + method_index * 8)",
            "null_semantic": "no direct body (virtual slots use vtable, others classified NO_BODY)",
            "consumer_shape": "mov r12, qword ptr [rax + r14*8] with method_index from TypeDefinition +0x08/+0x34",
            "registry_field_offset_old": f"0x{oc['registry_code_table_field_offset']:X}",
            "registry_field_offset_new": f"0x{nc['registry_code_table_field_offset']:X}",
        },
        "checks": checks,
        "common_samples_checked": len(common),
        "not_claimed": [
            "native RVA equality across versions (expected to differ)",
            "semantic decompilation",
            "vtable/dispatcher deep dive",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote {out}")
    print(f"status={status}")
    for name, v in checks.items():
        print(f"  {name}: {'PASS' if v['pass'] else 'FAIL'} {v['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
