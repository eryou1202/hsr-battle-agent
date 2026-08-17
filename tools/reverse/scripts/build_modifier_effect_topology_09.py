#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Index the battle modifier OnAdded/OnActivate native topology.

This is intentionally an indexer, not a decompiler.  It starts at the two
vtable slots proven by Batch 08, enumerates every metadata declaration of the
two callback names, and separates battle-reachable TurnBasedModifierInstance
bodies from same-named callbacks in unrelated runtime families.  For each
reachable native body it records a bounded first-return fingerprint, direct
rel32 callees, conservative register-relative memory accesses, and caller
resolved labels.  Large instruction listings are deliberately kept out of the
topology artifact; follow-up evidence tools can disassemble an exact RVA.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    NORMALIZED_BASE,
    disasm_window,
    iter_records,
    load_manifest,
    load_pe,
    validate_code_slot,
)

GAME_VERSION = "4.4.54"
OUT_PATH = REPO / "data" / "raw" / GAME_VERSION / "modifier_effect_topology_09.json"
LIFECYCLE_PATH = REPO / "data" / "semantics" / GAME_VERSION / "modifier_lifecycle_bridge_08.json"

# These slot identities are E4 evidence from AbilityComponent.AddModifierInstance
# in Batch 08.  The metadata registry does not currently encode a recovered
# inheritance graph, so this is the authoritative entry constraint.
SLOTS = {"OnAdded": 13, "OnActivate": 14}
BATTLE_RUNTIME_TYPES = {"RPG.GameCore.TurnBasedModifierInstance"}


def load_type_map() -> dict[int, dict]:
    return {r["type_index"]: r for r in iter_records(NORMALIZED_BASE / "types.json")}


def load_methods() -> tuple[list[dict], list[int], dict[int, list[dict]]]:
    named = []
    rvas = []
    by_rva: dict[int, list[dict]] = defaultdict(list)
    for r in iter_records(NORMALIZED_BASE / "methods.json"):
        rva = r.get("native_rva")
        if isinstance(rva, int) and r.get("mapping_kind") == "DIRECT_NATIVE":
            rvas.append(rva)
            by_rva[rva].append(r)
        if r["name"] in SLOTS:
            named.append(r)
    return named, sorted(set(rvas)), by_rva


def next_gap(rvas: list[int], rva: int) -> int:
    index = bisect.bisect_right(rvas, rva)
    return (rvas[index] if index < len(rvas) else rva + 0x1000) - rva


def first_ret_body(pe, rva: int, gap: int):
    raw, decoded = disasm_window(pe, rva, gap)
    first_ret = next((i for i in decoded if i["mnemonic"] == "ret"), None)
    if first_ret is None:
        raise RuntimeError(f"no ret before next native entry at 0x{rva:X}")
    size = first_ret["rva"] + first_ret["size"] - rva
    body_raw = raw[:size]
    _, body = disasm_window(pe, rva, size)
    return body_raw, body


def direct_callees(pe, decoded, by_rva: dict[int, list[dict]], types: dict[int, dict]) -> list[dict]:
    rows = []
    for ins in decoded:
        if ins["mnemonic"] not in ("call", "jmp") or " " in ins["op_str"].strip():
            continue
        try:
            dest_rva = int(ins["op_str"], 0) - pe.image_base
        except ValueError:
            continue
        labels = []
        for method in by_rva.get(dest_rva, []):
            type_info = types.get(method["declaring_type_index"], {})
            labels.append({
                "method_index": method["method_index"],
                "runtime_type": type_info.get("full_name", "UNKNOWN"),
                "method": method["name"],
            })
        rows.append({
            "site_rva": f"0x{ins['rva']:X}",
            "kind": ins["mnemonic"],
            "dest_rva": f"0x{dest_rva:X}",
            "resolved_methods": labels,
        })
    return rows


MEMORY_RE = re.compile(
    r"(?P<size>byte|word|dword|qword|xmmword|ymmword) ptr "
    r"\[(?P<expression>[^\]]+)\]"
)
WIDTHS = {"byte": 1, "word": 2, "dword": 4, "qword": 8, "xmmword": 16, "ymmword": 32}
WRITE_FIRST_OPERAND = {"mov", "movaps", "movups", "movss", "movsd", "add", "sub", "inc", "dec", "and", "or", "xor", "shl", "shr", "xchg", "cmpxchg"}


def memory_accesses(decoded, instance_bases: set[str]) -> dict[str, list[dict]]:
    """Conservative instance accesses after an explicitly recorded prologue alias."""
    reads: set[tuple[str, int, int]] = set()
    writes: set[tuple[str, int, int]] = set()
    for ins in decoded:
        matches = list(MEMORY_RE.finditer(ins["op_str"]))
        for ordinal, match in enumerate(matches):
            expression = match.group("expression").replace(" ", "")
            base_match = re.match(r"(?P<base>[a-z0-9]+)(?P<tail>[+-].+)?$", expression)
            if base_match is None:
                continue
            base = base_match.group("base")
            if base not in instance_bases:
                continue
            tail = base_match.group("tail") or ""
            try:
                displacement = int(tail, 0) if tail else 0
            except ValueError:
                # Indexed addresses are not instance-field evidence.
                continue
            row = (base, displacement, WIDTHS[match.group("size")])
            is_write = ordinal == 0 and ins["mnemonic"] in WRITE_FIRST_OPERAND and ins["op_str"].lstrip().startswith(match.group(0))
            if is_write:
                writes.add(row)
                if ins["mnemonic"] not in {"mov", "movaps", "movups", "movss", "movsd"}:
                    reads.add(row)
            else:
                reads.add(row)
    def render(rows):
        return [
            {"base_expression": b, "displacement": f"{d:+#x}", "width": w}
            for b, d, w in sorted(rows)
        ]
    return {"reads": render(reads), "writes": render(writes)}


def known_lifecycle_evidence() -> dict[int, dict]:
    data = json.loads(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    out = {}
    for row in data.get("candidate_table", []):
        ev = row.get("native_evidence", {})
        if ev.get("method_index") in (506175, 506176):
            out[ev["method_index"]] = ev
    return out


def build() -> dict:
    pe = load_pe()
    manifest = load_manifest()
    types = load_type_map()
    named, rvas, by_rva = load_methods()
    lifecycle = known_lifecycle_evidence()
    callback_rows = []
    shared_callee_counts = Counter()
    field_offset_counts = Counter()
    helper_occurrences: Counter[tuple[str, str]] = Counter()

    for method in sorted(named, key=lambda r: r["method_index"]):
        type_info = types[method["declaring_type_index"]]
        runtime_type = type_info["full_name"]
        rva = method.get("native_rva")
        battle_reachable = runtime_type in BATTLE_RUNTIME_TYPES
        row = {
            "runtime_type": runtime_type,
            "type_index": method["declaring_type_index"],
            "slot": SLOTS[method["name"]],
            "callback": method["name"],
            "method_index": method["method_index"],
            "mapping_kind": method["mapping_kind"],
            "battle_reachable_from_try_add": battle_reachable,
            "reachability_evidence": (
                "Batch 08 AddModifierInstance virtual slot dispatch + "
                "TurnBasedModifierInstance allocation path"
                if battle_reachable else
                "same callback name only; excluded from the Battle modifier chain"
            ),
        }
        if not isinstance(rva, int):
            row["native_body"] = None
            callback_rows.append(row)
            continue
        gap = next_gap(rvas, rva)
        raw, decoded = first_ret_body(pe, rva, gap)
        # E4 prologue aliases: OnAdded saves RCX in RSI; OnActivate saves it
        # in RDI.  Do not promote stack/local/temporary-object stores to
        # persistent modifier fields.
        instance_bases = {"rsi"} if method["method_index"] == 506175 else {"rdi"}
        accesses = memory_accesses(decoded, instance_bases)
        callees = direct_callees(pe, decoded, by_rva, types)
        slot = validate_code_slot(pe, method["method_index"], rva)
        row["native_body"] = {
            "rva": f"0x{rva:X}",
            "body_window_kind": "NORMAL_PATH_FIRST_RET_PROJECTION",
            "body_size": len(raw),
            "body_hash": hashlib.sha256(raw).hexdigest(),
            "instruction_count": len(decoded),
            "branch_count": sum(1 for i in decoded if i["mnemonic"].startswith("j") and i["mnemonic"] != "jmp"),
            "code_table_slot_va": f"0x{slot:X}",
        }
        row["field_accesses_conservative"] = accesses
        row["direct_callees"] = callees
        if battle_reachable:
            for c in callees:
                shared_callee_counts[c["dest_rva"]] += 1
                for label in c["resolved_methods"]:
                    if label["runtime_type"].startswith("RPG.GameCore."):
                        helper_occurrences[(c["dest_rva"], f"{label['runtime_type']}.{label['method']}")] += 1
            for a in accesses["writes"]:
                field_offset_counts[a["displacement"]] += 1
        callback_rows.append(row)

    reachable = [r for r in callback_rows if r["battle_reachable_from_try_add"] and r["native_body"]]
    clusters: dict[tuple, list[dict]] = defaultdict(list)
    for row in reachable:
        body = row["native_body"]
        clusters[(row["slot"], body["body_hash"])].append(row)
    cluster_rows = [
        {
            "cluster_id": f"slot{slot}_{digest[:12]}",
            "slot": slot,
            "body_hash": digest,
            "member_method_indexes": [r["method_index"] for r in rows],
            "member_runtime_types": [r["runtime_type"] for r in rows],
        }
        for (slot, digest), rows in sorted(clusters.items())
    ]

    # OnAdded's exact mount writes and OnActivate's leading persistent writes
    # are already E4-proven in Batch 08; state them without over-claiming the
    # very large activation tail.
    semantic_summary = {
        "OnAdded": {
            "method_index": 506175,
            "known_writes": ["TurnBasedModifierInstance [+0x168] = 0", "[+0x16a] = 1", "[+0x170] = null"],
            "effect_family": "LIFECYCLE_ONLY",
            "status": "CONFIRMED_E4",
        },
        "OnActivate": {
            "method_index": 506176,
            "known_writes": ["TurnBasedModifierInstance [+0x8d] = 1", "State [+0x80] = Alive(1)"],
            "effect_family": "COMPOSITE",
            "status": "CONFIRMED_E4_BOUNDARY; downstream effects require shared-callee recovery",
        },
    }
    return {
        "schema": "modifier_effect_topology/1",
        "game_version": GAME_VERSION,
        "capability_id": "modifier_effect_topology_09",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_hashes": {"GameAssembly.dll": manifest["GameAssembly"]["sha256"]},
        "entry_slots": [{"slot": slot, "callback": name} for name, slot in SLOTS.items()],
        "scope_note": "Concrete means the battle-reachable TurnBasedModifierInstance override; callback-name matches outside that allocation/dispatch chain are reported but excluded.",
        "override_count": len(reachable),
        "unique_body_count": len(clusters),
        "all_callback_name_matches": len(callback_rows),
        "runtime_types": callback_rows,
        "clusters": cluster_rows,
        "shared_callees": [{"dest_rva": rva, "direct_call_occurrences": count} for rva, count in shared_callee_counts.most_common()],
        "top_reusable_helpers": [
            {"dest_rva": rva, "resolved_runtime_method": label, "direct_call_occurrences": count}
            for (rva, label), count in helper_occurrences.most_common()
        ],
        "high_frequency_persistent_writes": [{"instance_displacement": disp, "write_occurrences": count} for disp, count in field_offset_counts.most_common()],
        "family_distribution": {"LIFECYCLE_ONLY": 1, "COMPOSITE": 1, "UNKNOWN": 0},
        "semantic_summary": semantic_summary,
        "known_evidence_reuse": {str(mi): {"body_hash": ev["body_sha256"], "rva": ev["body_rva"]} for mi, ev in lifecycle.items()},
        "unknowns": [
            "Recovered metadata has no canonical type-inheritance graph; reachability is constrained by the proved allocation + vtable dispatch chain.",
            "Indirect virtual calls inside OnActivate are not misrepresented as direct callees.",
            "No callback-name match outside TurnBasedModifierInstance is claimed to be a battle modifier effect.",
        ],
    }


def main() -> int:
    artifact = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"battle_overrides={artifact['override_count']} unique_bodies={artifact['unique_body_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
