#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Candidate discovery pass for Target Selector Batch 05.

Streams normalized types/methods/fields once each and emits a JSON report of
plausible target/selector/entity candidate types and methods.  Names are
discovery keywords only; this script claims no semantic mapping.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from semantic_batch_evidence import NORMALIZED_BASE  # noqa: E402

TYPE_KEYWORDS = [
    "target",
    "selector",
    "select",
    "entity",
    "camp",
    "team",
]

METHOD_KEYWORDS = [
    "get_target",
    "select_target",
    "selecttarget",
    "target_select",
    "gettarget",
    "get_entity",
    "getentity",
    "get_entities",
    "getentities",
    "select_entity",
    "selectentity",
    "get_caster",
    "getcaster",
    "get_owner",
    "getowner",
    "get_source",
    "getsource",
    "get_attacker",
    "getattacker",
    "get_defender",
    "getdefender",
    "get_modifier_owner",
    "getmodifierowner",
    "get_ability_owner",
    "getabilityowner",
    "get_param_entity",
    "getparamentity",
    "get_ability_target",
    "getabilitytarget",
    "resolve_target",
    "resolvetarget",
    "find_target",
    "findtarget",
    "collect_target",
    "collecttarget",
    "target_entity",
    "targetentity",
    "get_target_entity",
    "gettargetentity",
    "get_target_list",
    "gettargetlist",
    "get_target_set",
    "gettargetset",
]


def iter_json_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        in_records = False
        for line in f:
            if not in_records:
                if '"records": [' in line:
                    in_records = True
                continue
            s = line.strip()
            if not s or s == "]":
                continue
            if s.endswith(","):
                s = s[:-1]
            if s.startswith("{") and s.endswith("}"):
                try:
                    yield json.loads(s)
                except json.JSONDecodeError:
                    pass


def discover(base: Path) -> dict:
    type_index_all: dict[int, dict] = {}
    type_hits = {k: [] for k in TYPE_KEYWORDS}
    selected_types: dict[int, dict] = {}
    for rec in iter_json_records(base / "types.json"):
        fn = rec["full_name"]
        low = fn.lower()
        row = {
            "type_index": rec["type_index"],
            "full_name": fn,
            "namespace": rec["namespace"],
            "name": rec["name"],
            "method_count": rec["method_count"],
            "field_count": rec["field_count"],
        }
        type_index_all[rec["type_index"]] = row
        for k in TYPE_KEYWORDS:
            if k in low:
                hit = dict(row)
                hit["keyword"] = k
                if len(type_hits[k]) < 400:
                    type_hits[k].append(hit)
                selected_types[rec["type_index"]] = dict(row)
                break

    method_hits = {k: [] for k in METHOD_KEYWORDS}
    for rec in iter_json_records(base / "methods.json"):
        name = rec["name"]
        low = name.lower()
        hit_kw = None
        for k in METHOD_KEYWORDS:
            if k in low:
                hit_kw = k
                break
        if hit_kw is None:
            continue
        rec = dict(rec)
        rec["keyword"] = hit_kw
        decl = type_index_all.get(rec["declaring_type_index"], {})
        rec["declaring_type"] = decl.get("full_name")
        rec["declaring_namespace"] = decl.get("namespace")
        if len(method_hits[hit_kw]) < 160:
            method_hits[hit_kw].append(rec)
        if rec["declaring_type_index"] not in selected_types and decl:
            selected_types[rec["declaring_type_index"]] = dict(decl)

    fields = []

    return {
        "schema": "target_selector_discovery/1",
        "type_keywords": TYPE_KEYWORDS,
        "method_keywords": METHOD_KEYWORDS,
        "type_hits": type_hits,
        "method_hits": method_hits,
        "selected_type_count": len(selected_types),
        "selected_types": sorted(selected_types.values(), key=lambda r: r["type_index"]),
        "fields_for_selected_types": fields,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, default=NORMALIZED_BASE)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()
    report = discover(args.base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {args.output}")
    print(f"selected types: {report['selected_type_count']}")
    for k, rows in report["type_hits"].items():
        print(f"== type keyword {k}: {len(rows)}")
        for r in rows[:80]:
            print(f"  {r['type_index']:>7}  {r['full_name']}")
    for k, rows in report["method_hits"].items():
        if rows:
            print(f"== method keyword {k}: {len(rows)}")
            for r in rows[:30]:
                print(f"  M {r['method_index']:>7} {r['declaring_type']}.{r['name']} "
                      f"rva={r.get('native_rva')} pc={r.get('parameter_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
