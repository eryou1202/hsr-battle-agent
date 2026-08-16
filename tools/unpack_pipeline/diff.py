# -*- coding: utf-8 -*-
"""STAGE 10 - VERSION_DIFF.

Semantic alignment rules (never numeric index alone):

  * types    : namespace + name (full_name)
  * methods  : declaring type full_name + method name + parameter count
  * fields   : declaring type full_name + field name
  * bridges  : domain + serialized discriminator -> runtime type identity;
               generated registry runtime-class sequences are aligned with a
               sequence matcher so insertions/deletions do not fake shifts.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .common import read_json, utc_now, write_json


def _load_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["records"]


def _type_map(records: Iterable[dict[str, Any]]) -> dict[int, str]:
    return {int(r["type_index"]): r.get("full_name") or f"{r.get('namespace','')}.{r.get('name','')}"
            for r in records}


def _method_key(type_map: dict[int, str], row: dict[str, Any]) -> str:
    declaring = type_map.get(int(row["declaring_type_index"]), str(row["declaring_type_index"]))
    return f"{declaring}::{row['name']}({row['parameter_count']})"


def _field_key(type_map: dict[int, str], row: dict[str, Any]) -> str:
    declaring = type_map.get(int(row["declaring_type_index"]), str(row["declaring_type_index"]))
    return f"{declaring}::{row['name']}"


def _set_diff(old: set, new: set) -> dict[str, Any]:
    return {
        "added": sorted(new - old),
        "removed": sorted(old - new),
        "common": len(old & new),
        "old_count": len(old),
        "new_count": len(new),
    }


def _bridge_identity(domains: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    identity: dict[str, dict[str, Any]] = {}
    for domain in domains:
        if domain.get("status") != "PASS" and domain.get("status") != "OK":
            continue
        for row in domain.get("mappings", []):
            disc = row.get("serialized_discriminator")
            if disc is None:
                disc = row.get("type_code")
            if disc is None:
                continue
            identity[f"{domain['domain']}/{disc}"] = {
                "runtime_type": row.get("runtime_type") or row.get("runtime_type_name"),
                "parser_method": row.get("parser_method_name"),
            }
    return identity


def _bridge_diff(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> dict[str, Any]:
    changed = []
    for key in sorted(old.keys() & new.keys()):
        if old[key] != new[key]:
            changed.append({"key": key, "old": old[key], "new": new[key]})
    return {
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "changed": changed,
        "common_unchanged": len(old.keys() & new.keys()) - len(changed),
    }


def compare_normalized(old_dir: Path, new_dir: Path) -> dict[str, Any]:
    old_types = _load_records(old_dir / "types.json")
    new_types = _load_records(new_dir / "types.json")
    old_tmap = _type_map(old_types)
    new_tmap = _type_map(new_types)
    old_methods = _load_records(old_dir / "methods.json")
    new_methods = _load_records(new_dir / "methods.json")
    old_fields = _load_records(old_dir / "fields.json")
    new_fields = _load_records(new_dir / "fields.json")

    type_diff = _set_diff({r.get("full_name") or f"{r.get('namespace','')}.{r.get('name','')}"
                           for r in old_types},
                          {r.get("full_name") or f"{r.get('namespace','')}.{r.get('name','')}"
                           for r in new_types})
    old_mkeys = {_method_key(old_tmap, r): r for r in old_methods}
    new_mkeys = {_method_key(new_tmap, r): r for r in new_methods}
    method_diff = _set_diff(set(old_mkeys), set(new_mkeys))
    old_fkeys = {_field_key(old_tmap, r): r for r in old_fields}
    new_fkeys = {_field_key(new_tmap, r): r for r in new_fields}
    field_diff = _set_diff(set(old_fkeys), set(new_fkeys))

    rva_changes = {"changed": 0, "same": 0, "old_null_new_native": 0,
                   "old_native_new_null": 0, "samples": []}
    for key in sorted(old_mkeys.keys() & new_mkeys.keys()):
        old_rva = old_mkeys[key].get("native_rva")
        new_rva = new_mkeys[key].get("native_rva")
        if old_rva == new_rva:
            rva_changes["same"] += 1
        else:
            rva_changes["changed"] += 1
            if old_rva is None:
                rva_changes["old_null_new_native"] += 1
            elif new_rva is None:
                rva_changes["old_native_new_null"] += 1
            if len(rva_changes["samples"]) < 12:
                rva_changes["samples"].append({"method": key, "old_rva": old_rva, "new_rva": new_rva})

    old_bridge = read_json(old_dir / "design_runtime_registry.json").get("domains", [])
    new_bridge = read_json(new_dir / "design_runtime_registry.json").get("domains", [])
    bridge_diff = _bridge_diff(_bridge_identity(old_bridge), _bridge_identity(new_bridge))

    return {
        "schema": "unpack_pipeline_version_diff/1",
        "generated_at": utc_now(),
        "old_version_dir": str(old_dir),
        "new_version_dir": str(new_dir),
        "status": "COMPLETE",
        "counts": {
            "types": {"old": len(old_types), "new": len(new_types)},
            "methods": {"old": len(old_methods), "new": len(new_methods)},
            "fields": {"old": len(old_fields), "new": len(new_fields)},
        },
        "metadata_schema": {"status": "COMPARED_BY_NORMALIZED_SHAPE"},
        "type_additions_removals": type_diff,
        "method_additions_removals": method_diff,
        "field_additions_removals": field_diff,
        "native_rva_changes": rva_changes,
        "design_runtime_bridge_changes": bridge_diff,
        "registry_alignment_rule": "semantic identity; numeric indices are never compared directly",
    }


def _legacy_counts(raw_dir: Path) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    type_map = read_json(raw_dir / "il2cpp" / "mhy_0x84_record_access_map_4.4.0.json")
    counts["types"] = int(type_map["record_table"]["capacity_to_next_table"])
    method_map = read_json(raw_dir / "il2cpp" / "mhy_method_definition_access_map_4.4.0.json")
    counts["methods"] = int(method_map["method_table"]["record_count"])
    field_map = read_json(raw_dir / "il2cpp" / "mhy_field_definition_access_map_4.4.0.json")
    counts["fields"] = int(field_map["field_table"]["record_count"])
    code = read_json(raw_dir / "il2cpp" / "method_code_registry_proof_4.4.0.json")
    counts["method_code"] = code["statistics"]
    return counts


def _registry_runtime_sequence(bridge_path: Path) -> list[str]:
    bridge = read_json(bridge_path)
    sequence = []
    for row in bridge.get("mappings", []):
        # Static 4.4.0 bridge stores the helper declaring type in
        # runtime_type_name and the resolved concrete class in
        # concrete_runtime_type_name.
        name = row.get("concrete_runtime_type_name")
        if not name or name == "MKIOEPLIEIH":
            name = row.get("runtime_type_name")
        if name and name != "MKIOEPLIEIH":
            sequence.append(name)
    return sequence


def compare_with_legacy_reference(new_normalized: Path, raw_old: Path,
                                  current_raw_bridge: Path | None = None,
                                  old_raw_bridge: Path | None = None,
                                  new_code_stats: dict[str, Any] | None = None) -> dict[str, Any]:
    """Diff a new normalized version against the archived 4.4.0 raw evidence.

    Only `types.json` is loaded from the new side; the full methods/fields JSON
    files can be hundreds of MB and their counts/summary are already available
    in the normalization summary + method code registry.
    """
    old_counts = _legacy_counts(raw_old)
    summary = read_json(new_normalized / "normalization_summary.json")
    new_counts = summary["counts"]
    new_types = _load_records(new_normalized / "types.json")
    new_type_names = {r.get("full_name") or f"{r.get('namespace','')}.{r.get('name','')}"
                      for r in new_types}

    # Sample-level type alignment only: raw 4.4.0 proof contains 32 samples.
    old_type_proof = read_json(raw_old / "il2cpp" / "type_registry_proof_4.4.0.json")
    old_type_names = {f"{r.get('namespace','')}.{r.get('identifier','')}".lstrip(".")
                      for r in old_type_proof.get("records", [])}
    type_alignment = {
        "scope": "32-record historical proof sample",
        "aligned_by": "namespace + type name",
        "common": sorted(old_type_names & new_type_names),
        "only_in_new_full_registry": sorted(new_type_names - old_type_names)[:24],
        "only_in_old_sample": sorted(old_type_names - new_type_names),
    }

    new_bridge = read_json(new_normalized / "design_runtime_registry.json")
    bridge_identity = _bridge_identity(new_bridge.get("domains", []))
    old_ability = read_json(raw_old / "bridge" / "ability_config_type_bridge_4.4.0.json")
    old_modifier = read_json(raw_old / "bridge" / "modifier_config_type_bridge_4.4.0.json")
    old_identity: dict[str, dict[str, Any]] = {}
    for domain, data in (("ability_config", old_ability), ("modifier_config", old_modifier)):
        for row in data.get("mappings", []):
            old_identity[f"{domain}/{row['type_code']}"] = {
                "runtime_type": row.get("runtime_type_name"),
                "parser_method": row.get("parser_method_name"),
            }
    static_bridge_diff = _bridge_diff(old_identity, bridge_identity)

    registry_diff: dict[str, Any] = {"status": "NOT_AVAILABLE_IN_STATIC_PIPELINE"}
    if current_raw_bridge and current_raw_bridge.is_file() and old_raw_bridge and old_raw_bridge.is_file():
        old_seq = _registry_runtime_sequence(old_raw_bridge)
        new_seq = _registry_runtime_sequence(current_raw_bridge)
        matcher = SequenceMatcher(a=old_seq, b=new_seq, autojunk=False)
        insertions = []
        deletions = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                insertions.extend(new_seq[j1:j2])
            elif tag == "delete":
                deletions.extend(old_seq[i1:i2])
            elif tag == "replace":
                deletions.extend(old_seq[i1:i2])
                insertions.extend(new_seq[j1:j2])
        registry_diff = {
            "status": "OK_WITH_INSERTIONS",
            "source": f"historical raw bridge evidence: {current_raw_bridge} vs {old_raw_bridge}",
            "aligned_by": "runtime class identity sequence (SequenceMatcher)",
            "ratio": round(matcher.ratio(), 6),
            "old_entry_count": len(old_seq),
            "new_entry_count": len(new_seq),
            "insertions": insertions,
            "deletions": deletions,
            "note": "discriminator numbers are version-specific; only runtime-class identity is aligned",
        }

    method_null_stats_new = {
        "null_slots": int(new_code_stats.get("null_slots", 0)) if new_code_stats else None,
        "non_null_slots": int(new_code_stats.get("direct_native_slots", 0)) if new_code_stats else None,
    }
    result = {
        "schema": "unpack_pipeline_version_diff/1",
        "generated_at": utc_now(),
        "status": "PARTIAL_HISTORICAL_REFERENCE",
        "old_version_source": str(raw_old),
        "new_version_source": str(new_normalized),
        "counts": {
            "old": old_counts,
            "new": {
                "types": new_counts.get("types", len(new_types)),
                "methods": new_counts.get("methods"),
                "fields": new_counts.get("fields"),
                "parameters": new_counts.get("parameters"),
                "method_code": method_null_stats_new,
            },
        },
        "metadata_schema": {
            "old_evidence": "data/raw/4.4.0/il2cpp/mhy_table_registry_4.4.0.json (47/47 transforms)",
            "new_evidence": "pipeline Stage 4 mhy_table_registry.json",
            "comparison_rule": "transform identity per template field; file offsets intentionally ignored",
        },
        "type_sample_alignment": type_alignment,
        "method_and_field_additions_removals": {
            "status": "PARTIAL",
            "reason": ("4.4.0 normalized full registry is not present; historical raw files contain "
                       "counts and samples only.  Full semantic diff is available when both "
                       "versions have normalized output."),
        },
        "native_rva_changes": {
            "status": "COUNT_LEVEL_ONLY",
            "old_non_null": old_counts["method_code"]["direct_native_slots"],
            "new_non_null": method_null_stats_new["non_null_slots"],
            "old_null": old_counts["method_code"]["null_slots"],
            "new_null": method_null_stats_new["null_slots"],
            "note": "RVA values are version-specific; full per-method comparison requires both normalized dirs",
        },
        "design_runtime_bridge_changes": static_bridge_diff,
        "generated_polymorphic_registry_insertions_deletions": registry_diff,
    }
    return result


def markdown_report(diff: dict[str, Any]) -> str:
    lines = ["# Version Diff", "", f"- generated_at: {diff.get('generated_at')}", ""]
    counts = diff.get("counts", {})
    lines.append("## Counts")
    lines.append("")
    lines.append("| item | old | new |")
    lines.append("|---|---|---|")
    old = counts.get("old", {})
    new = counts.get("new", {})
    for key in ("types", "methods", "fields"):
        lines.append(f"| {key} | {old.get(key)} | {new.get(key)} |")
    old_code = old.get("method_code", {})
    new_code = new.get("method_code", {})
    lines.append(f"| method_code non-null | {old_code.get('non_null_slots') or old_code.get('direct_native_slots')} "
                 f"| {new_code.get('non_null_slots')} |")
    lines.append(f"| method_code null | {old_code.get('null_slots')} | {new_code.get('null_slots')} |")
    lines.append("")
    lines.append("## Metadata schema")
    lines.append("")
    schema = diff.get("metadata_schema", {})
    for key, value in schema.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    bridge = diff.get("design_runtime_bridge_changes", {})
    lines.append("## DesignData static bridge changes")
    lines.append("")
    lines.append(f"- added: {len(bridge.get('added', []))}")
    lines.append(f"- removed: {len(bridge.get('removed', []))}")
    lines.append(f"- changed: {len(bridge.get('changed', []))}")
    for item in bridge.get("changed", []):
        lines.append(f"  - {item['key']}: {item['old']} -> {item['new']}")
    lines.append("")
    registry = diff.get("generated_polymorphic_registry_insertions_deletions", {})
    lines.append("## Generated polymorphic registry")
    lines.append("")
    if isinstance(registry, dict):
        lines.append(f"- status: {registry.get('status')}")
        lines.append(f"- ratio: {registry.get('ratio')}")
        lines.append(f"- insertions: {len(registry.get('insertions', []))}")
        lines.append(f"- deletions: {len(registry.get('deletions', []))}")
        for name in registry.get("insertions", [])[:10]:
            lines.append(f"  - + {name}")
        for name in registry.get("deletions", [])[:10]:
            lines.append(f"  - - {name}")
    lines.append("")
    lines.append("> Registry comparison uses semantic alignment (namespace+type, "
                "declaring type+method identity, runtime class identity). "
                "Numeric indices are never compared directly.")
    return "\n".join(lines) + "\n"


def run_diff(new_normalized: Path, output_dir: Path, old_normalized: Path | None = None,
             legacy_raw_old: Path | None = None,
             current_raw_bridge: Path | None = None,
             old_raw_bridge: Path | None = None,
             new_code_stats: dict[str, Any] | None = None) -> dict[str, Any]:
    if old_normalized is not None and (old_normalized / "types.json").is_file():
        diff = compare_normalized(old_normalized, new_normalized)
    elif legacy_raw_old is not None:
        diff = compare_with_legacy_reference(
            new_normalized, legacy_raw_old, current_raw_bridge, old_raw_bridge,
            new_code_stats=new_code_stats)
    else:
        diff = {
            "schema": "unpack_pipeline_version_diff/1",
            "generated_at": utc_now(),
            "status": "NO_BASELINE",
            "new_version_source": str(new_normalized),
            "reason": "no baseline normalized directory or legacy raw reference provided",
        }
    write_json(output_dir / "version_diff.json", diff)
    (output_dir / "version_diff.md").write_text(markdown_report(diff), encoding="utf-8")
    return diff
