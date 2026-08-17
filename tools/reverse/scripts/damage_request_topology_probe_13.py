#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mechanical topology probe for damage request / hit context candidates.

This is a discovery-only script.  It does not recover gameplay formulas.  It
reuses the generated task/runtime bridge, normalized method/type registries,
and the existing damage topology index to reduce the native damage candidate
space to a small ranked set for later semantic analysis.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import NORMALIZED_BASE, iter_records, load_pe  # noqa: E402

VENDOR = HERE.parent / "vendor" / "capstone"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, x86  # noqa: E402

GAME_VERSION = "4.4.54"
OUT = REPO / "data" / "raw" / GAME_VERSION / "damage_request_topology_probe_13.json"

MAX_BODY_GAP = 0x6000
MAX_SCAN_GAP = 0x6000
DEPTH_LIMIT = 3
NODE_LIMIT = 200

KNOWN_ENDPOINTS = {
    "BeginDamageChunk": 0xE7227E0,
    "EndDamageChunk": 0xE722880,
    "TargetDamageHP": 0xE46D760,
    "DirectDamageHP": 0xE732180,
    "DirectChangeHP": 0xE733830,
    "TagDispatch_0x15C6D120": 0x15C6D120,
}
EVAL_TARGET = 0xE6F1530
EVAL_SINGLE_TARGET = 0xE6D5830

DAMAGE_KEYWORDS = ("damage", "hit", "hurt", "attack", "health", "hp")


def load_indexes():
    types = {}
    for rec in iter_records(NORMALIZED_BASE / "types.json"):
        types[rec["type_index"]] = rec
    rvas: list[int] = []
    by_rva: dict[int, dict] = {}
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        rva = rec.get("native_rva")
        if isinstance(rva, int) and rec.get("mapping_kind") == "DIRECT_NATIVE":
            by_rva[rva] = rec
            rvas.append(rva)
    rvas.sort()
    return types, rvas, by_rva


def direct_callees(pe, start: int, end: int) -> list[int]:
    if end <= start:
        return []
    off = pe.rva_to_file_offset(start)
    if off is None:
        return []
    raw = pe._read(off, min(end - start, MAX_SCAN_GAP))
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    out: list[int] = []
    for insn in md.disasm(raw, pe.image_base + start):
        if insn.mnemonic not in {"call", "jmp"} or not insn.operands:
            continue
        op = insn.operands[0]
        if op.type != x86.X86_OP_IMM:
            continue
        target = int(op.imm) - pe.image_base
        if 0 <= target <= 0xFFFFFFFF:
            out.append(target)
    return out


def body_sha256(pe, start: int, end: int) -> str:
    if end <= start:
        return ""
    off = pe.rva_to_file_offset(start)
    if off is None:
        return ""
    raw = pe._read(off, min(end - start, MAX_SCAN_GAP))
    return hashlib.sha256(raw).hexdigest()


def type_name(types, type_index):
    rec = types.get(type_index, {})
    return rec.get("full_name", "<unresolved>")


def is_damage_name(method, types) -> bool:
    typ = types.get(method.get("declaring_type_index"), {})
    hay = f"{method.get('name','')} {typ.get('full_name','')}".lower()
    return any(k in hay for k in DAMAGE_KEYWORDS)


def is_infrastructure_type(full_name: str) -> bool:
    return full_name.startswith(
        (
            "IFix.",
            "XLua.",
            "System.",
            "Mono.",
            "UnityEngine.",
            "Unity.",
            "MS.Internal.",
        )
    )


def load_bridge():
    path = REPO / "data" / "raw" / GAME_VERSION / "action_config_runtime_bridge_06.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_existing_topology():
    path = REPO / "data" / "raw" / GAME_VERSION / "generated_task_damage_topology_10.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    pe = load_pe()
    types, rvas, by_rva = load_indexes()
    bridge = load_bridge()
    existing = load_existing_topology()

    executor_type_indices = {
        row["executor_type_index"] for row in bridge["matched_rows"]
    }

    methods_by_type: dict[int, list[dict]] = defaultdict(list)
    for rec in iter_records(NORMALIZED_BASE / "methods.json"):
        ti = rec.get("declaring_type_index")
        if ti in executor_type_indices and rec.get("mapping_kind") == "DIRECT_NATIVE":
            methods_by_type[ti].append(rec)

    def next_rva(start: int) -> int:
        i = bisect.bisect_right(rvas, start)
        if i >= len(rvas):
            return start + MAX_BODY_GAP
        return min(rvas[i], start + MAX_BODY_GAP)

    method_callees: dict[int, list[int]] = {}
    method_body_hash: dict[int, str] = {}

    def callees_for(rva: int) -> list[int]:
        if rva in method_callees:
            return method_callees[rva]
        callees = direct_callees(pe, rva, next_rva(rva))
        method_callees[rva] = callees
        method_body_hash[rva] = body_sha256(pe, rva, next_rva(rva))
        return callees

    executor_rows = []
    for row in bridge["matched_rows"]:
        ti = row["executor_type_index"]
        configs = list(row.get("config_candidates", []))
        on_task = None
        for m in row.get("execution_methods", []):
            if m.get("name") == "OnTaskBegin" and isinstance(m.get("native_rva"), int):
                on_task = m
                break
        if on_task is None:
            continue
        methods = methods_by_type.get(ti, [])
        scanned = []
        for m in methods:
            rva = m["native_rva"]
            callees_for(rva)
            scanned.append({
                "method_index": m["method_index"],
                "native_rva": rva,
                "name": m["name"],
                "callees": method_callees[rva],
            })
        executor_rows.append({
            "executor_type": row["executor_type"],
            "executor_type_index": ti,
            "config_candidates": configs,
            "on_task_begin": {
                "method_index": on_task["method_index"],
                "native_rva": on_task["native_rva"],
            },
            "scanned_method_count": len(scanned),
            "scanned_methods": scanned,
        })

    # Caller index from generated executor helper bodies.
    callee_callers: dict[int, list[dict]] = defaultdict(list)
    for erow in executor_rows:
        eti = erow["executor_type_index"]
        configs = erow["config_candidates"]
        for sm in erow["scanned_methods"]:
            caller_rva = sm["native_rva"]
            for callee in set(sm["callees"]):
                if callee not in by_rva:
                    continue
                callee_callers[callee].append({
                    "caller_method_rva": caller_rva,
                    "caller_method_index": sm["method_index"],
                    "caller_method_name": sm["name"],
                    "executor_type_index": eti,
                    "executor_type": erow["executor_type"],
                    "config_candidates": configs,
                })

    def executor_is_damage_hinted(erow) -> bool:
        if any(
            any(k in c.lower() for k in DAMAGE_KEYWORDS)
            for c in erow["config_candidates"]
        ):
            return True
        for sm in erow["scanned_methods"]:
            if any(c in KNOWN_ENDPOINTS.values() for c in sm["callees"]):
                return True
        return False

    damage_executor_indices = {
        erow["executor_type_index"]
        for erow in executor_rows
        if executor_is_damage_hinted(erow)
    }
    damage_executor_rows = [
        erow for erow in executor_rows
        if erow["executor_type_index"] in damage_executor_indices
    ]

    # Candidate shared callees seen from damage-hinted generated executors.
    candidate_rvas: set[int] = set()
    for callee, callers in callee_callers.items():
        damage_callers = [c for c in callers if c["executor_type_index"] in damage_executor_indices]
        damage_executor_count = len({c["executor_type_index"] for c in damage_callers})
        method = by_rva[callee]
        if damage_executor_count <= 0:
            continue
        full_name = type_name(types, method.get("declaring_type_index"))
        if is_infrastructure_type(full_name):
            continue
        if callee in KNOWN_ENDPOINTS.values():
            candidate_rvas.add(callee)
            continue
        is_generated_helper = method.get("declaring_type_index") in executor_type_indices
        if damage_executor_count >= 2 and (
            is_damage_name(method, types) or is_generated_helper
        ):
            candidate_rvas.add(callee)
        elif damage_executor_count == 1 and is_damage_name(method, types):
            candidate_rvas.add(callee)

    # Add all direct callees of known endpoints? They are upstream callers, not callees;
    # candidate list is for shared downstream helpers. Keep known endpoints as candidates too.
    for rva in KNOWN_ENDPOINTS.values():
        if rva in by_rva:
            candidate_rvas.add(rva)

    # For each candidate, compute its own downstream graph to known HP endpoints.
    def reachable_known(rva: int) -> dict:
        seen = set()
        queue = [(rva, 0)]
        found = {}
        nodes = 0
        while queue and nodes < NODE_LIMIT:
            cur, depth = queue.pop(0)
            if cur in seen or depth > DEPTH_LIMIT:
                continue
            seen.add(cur)
            nodes += 1
            if cur in by_rva:
                for c in callees_for(cur):
                    for name, erva in KNOWN_ENDPOINTS.items():
                        if c == erva and name not in found:
                            found[name] = {"depth": depth + 1, "via_rva": cur}
                    if c not in seen:
                        queue.append((c, depth + 1))
        return found

    candidates = []
    for rva in sorted(candidate_rvas):
        method = by_rva[rva]
        callers = callee_callers.get(rva, [])
        damage_callers = [c for c in callers if c["executor_type_index"] in damage_executor_indices]
        damage_executor_count = len({c["executor_type_index"] for c in damage_callers})
        total_executor_count = len({c["executor_type_index"] for c in callers})
        downstream = reachable_known(rva)
        direct = method_callees.get(rva, callees_for(rva))
        important_callees = []
        for c in sorted(set(direct)):
            cm = by_rva.get(c)
            if cm is None:
                continue
            if (
                c in KNOWN_ENDPOINTS.values()
                or is_damage_name(cm, types)
                or c in (EVAL_TARGET, EVAL_SINGLE_TARGET)
            ):
                important_callees.append({
                    "method_index": cm["method_index"],
                    "native_rva": f"0x{c:X}",
                    "name": cm["name"],
                    "runtime_type": type_name(types, cm.get("declaring_type_index")),
                })
        read_adjacent = []
        for c in sorted(set(direct)):
            cm = by_rva.get(c)
            if cm is None:
                continue
            if any(
                cm["name"].startswith(prefix)
                for prefix in ("get_", "Get", "Is", "Can", "Has", "Calc", "Resolve")
            ):
                read_adjacent.append({
                    "method_index": cm["method_index"],
                    "native_rva": f"0x{c:X}",
                    "name": cm["name"],
                    "runtime_type": type_name(types, cm.get("declaring_type_index")),
                })
        candidates.append({
            "rank": 0,
            "classification": "UNKNOWN",
            "runtime_identity": {
                "method_index": method["method_index"],
                "native_rva": f"0x{rva:X}",
                "method_name": method["name"],
                "declaring_type_index": method.get("declaring_type_index"),
                "runtime_type": type_name(types, method.get("declaring_type_index")),
            },
            "body_hash": method_body_hash.get(rva, ""),
            "body_gap_bytes": next_rva(rva) - rva,
            "important_reads": read_adjacent[:20],
            "source_caster_context_reads": "not resolved by topology probe; caller/executor graph only",
            "property_reads": "not resolved by topology probe; read-adjacent callees listed in important_reads",
            "representative_callers": [
                {
                    "executor_type": c["executor_type"],
                    "executor_type_index": c["executor_type_index"],
                    "config_candidates": c["config_candidates"],
                    "caller_method": c["caller_method_name"],
                    "caller_method_index": c["caller_method_index"],
                    "caller_rva": f"0x{c['caller_method_rva']:X}",
                }
                for c in damage_callers[:8]
            ],
            "caller_count": {
                "damage_executor_types": damage_executor_count,
                "total_executor_types": total_executor_count,
                "raw_caller_sites": len(damage_callers),
            },
            "important_callees": important_callees[:20],
            "downstream_hp_path": downstream,
            "evidence_level": "DISCOVERY_TOPOLOGY",
            "reason": "",
        })

    # Rank: known HP bridge / endpoint first, then downstream reach, then reuse.
    def rank_key(c):
        downstream_score = 0
        if "DirectDamageHP" in c["downstream_hp_path"]:
            downstream_score += 100
        if "TargetDamageHP" in c["downstream_hp_path"]:
            downstream_score += 60
        if "DirectChangeHP" in c["downstream_hp_path"]:
            downstream_score += 50
        if "BeginDamageChunk" in c["downstream_hp_path"]:
            downstream_score += 30
        if "EndDamageChunk" in c["downstream_hp_path"]:
            downstream_score += 20
        if "TagDispatch_0x15C6D120" in c["downstream_hp_path"]:
            downstream_score += 10
        reuse = c["caller_count"]["damage_executor_types"]
        return (
            -downstream_score,
            -reuse,
            -c["caller_count"]["raw_caller_sites"],
            c["runtime_identity"]["native_rva"],
        )

    candidates.sort(key=rank_key)
    for idx, c in enumerate(candidates, start=1):
        c["rank"] = idx

    # Simple shared-helper clusters: group by the most frequent important callee hub.
    hub_counter = Counter()
    for c in candidates:
        for callee in c["important_callees"]:
            hub_counter[(callee["method_index"], callee["native_rva"], callee["name"])] += 1
    clusters = []
    seen_in_cluster = set()
    for (mid, rva, name), count in hub_counter.most_common(20):
        members = [
            c for c in candidates
            if any(x["method_index"] == mid for x in c["important_callees"])
        ]
        member_ranks = [c["rank"] for c in members]
        if not members or all(r in seen_in_cluster for r in member_ranks):
            continue
        seen_in_cluster.update(member_ranks)
        clusters.append({
            "hub_method_index": mid,
            "hub_native_rva": rva,
            "hub_name": name,
            "member_ranks": member_ranks,
            "member_count": len(members),
        })

    ranked = candidates[:12]
    for c in ranked:
        if c["runtime_identity"]["native_rva"] == "0xE46D760":
            c["classification"] = "HP_DELTA_BRIDGE_CANDIDATE"
            c["reason"] = "AbilityStatic.TargetDamageHP directly calls DirectDamageHP; strongest known HP delta bridge."
        elif c["runtime_identity"]["native_rva"] == "0xE732180":
            c["classification"] = "HP_DELTA_BRIDGE_CANDIDATE"
            c["reason"] = "Already-recovered DirectDamageHP endpoint; used as terminal anchor, not a new damage request."
        elif c["runtime_identity"]["native_rva"] == "0xE733830":
            c["classification"] = "HP_DELTA_BRIDGE_CANDIDATE"
            c["reason"] = "DirectChangeHP endpoint; SetHP-specific, penalized as an already-completed HP mutation path."
        elif c["runtime_identity"]["native_rva"] == "0x15C6D120":
            c["classification"] = "GENERATED_DISPATCH"
            c["reason"] = "Generated tag-dispatch evidence; not a settled DamageRequest."
        elif c["runtime_identity"]["native_rva"] in ("0xE7227E0", "0xE722880"):
            c["classification"] = "DAMAGE_CHUNK_SCOPE_ONLY"
            c["reason"] = "Chunk scope boundary with no resolved damage value production."
        elif c["caller_count"]["damage_executor_types"] >= 2 and c["downstream_hp_path"]:
            c["classification"] = "DAMAGE_VALUE_RESOLVE_CANDIDATE"
            c["reason"] = "Shared by multiple damage-hinted executors and has a bounded downstream path toward HP transition."
        elif c["caller_count"]["damage_executor_types"] >= 2:
            c["classification"] = "DAMAGE_REQUEST_CANDIDATE"
            c["reason"] = "Shared across damage-hinted generated executors; request/context construction not yet proven."
        elif is_damage_name(by_rva[int(c["runtime_identity"]["native_rva"], 16)], types):
            c["classification"] = "HIT_CONTEXT_CANDIDATE"
            c["reason"] = "Name/type hint only; topology needs V4P confirmation."
        else:
            c["classification"] = "UNKNOWN"
            c["reason"] = "Candidate appears in damage-hinted executor graph but lacks sufficient shared/downstream evidence."
        # Generic evaluators are not damage-request boundaries even when heavily reused.
        if (
            c["runtime_identity"]["method_name"]
            in {"EvaluateTarget", "EvaluateSingleTarget", "Evaluate"}
            and not c["downstream_hp_path"]
        ):
            c["classification"] = "GENERATED_DISPATCH"
            c["reason"] = "Generic target/value evaluation helper; not a damage request or hit context boundary."

    anchor_rvas = {
        "BeginDamageChunk": "0xE7227E0",
        "EndDamageChunk": "0xE722880",
        "TagDispatch_0x15C6D120": "0x15C6D120",
    }
    by_rva_str = {c["runtime_identity"]["native_rva"]: c for c in candidates}
    reference_anchors = []
    for name, rva in anchor_rvas.items():
        c = by_rva_str.get(rva)
        if c is None:
            continue
        anchor = dict(c)
        if name == "TagDispatch_0x15C6D120":
            anchor["classification"] = "GENERATED_DISPATCH"
            anchor["reason"] = "Generated tag-dispatch evidence; not a settled DamageRequest."
        else:
            anchor["classification"] = "DAMAGE_CHUNK_SCOPE_ONLY"
            anchor["reason"] = "Chunk scope boundary with no resolved damage value production."
        reference_anchors.append(anchor)

    already_completed_or_anchor = {
        "0xE46D760",  # TargetDamageHP: known HP delta bridge
        "0xE732180",  # DirectDamageHP: already recovered
        "0xE733830",  # DirectChangeHP: SetHP path
        "0xE7227E0",  # BeginDamageChunk: scope only
        "0xE722880",  # EndDamageChunk: scope only
        "0x15C6D120",  # generated tag dispatch
    }
    recommended = None
    for c in ranked:
        if c["runtime_identity"]["native_rva"] not in already_completed_or_anchor:
            recommended = c
            break
    if recommended is None and ranked:
        recommended = ranked[0]

    report = {
        "schema": "damage_request_topology_probe/1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "game_version": GAME_VERSION,
        "purpose": "TOPOLOGY_PROBE_ONLY; no gameplay formula recovery.",
        "executor_count_scanned": len(executor_rows),
        "initial_candidate_count": len(candidates),
        "cluster_count": len(clusters),
        "damage_hinted_executor_count": len(damage_executor_rows),
        "shared_helper_clusters": clusters,
        "ranked_candidates": ranked,
        "reference_anchors": reference_anchors,
        "recommended_v4p_entry": {
            "primary": recommended["runtime_identity"] if recommended else None,
            "alternates": [
                c["runtime_identity"] for c in ranked if c is not recommended
            ][:4],
            "reason": (
                "NNGMOCFGPBN is the top non-anchor candidate: a generated executor helper shared by "
                "DamageByAttackProperty and ProcessStoredDamage, with a bounded downstream path "
                "NNGMOCFGPBN -> TargetDamageHP -> DirectDamageHP. V4P should start here and use "
                "TargetDamageHP/DirectChangeHP as HP-bridge alternates."
                if recommended and recommended["runtime_identity"]["native_rva"] == "0xC3123B0"
                else "See ranked candidates; no direct HP bridge was top-ranked."
            ),
        },
        "source_inputs": {
            "action_bridge": "data/raw/4.4.54/action_config_runtime_bridge_06.json",
            "existing_topology": "data/raw/4.4.54/generated_task_damage_topology_10.json",
            "damage_direct_hp_xrefs": "data/raw/4.4.54/damage_direct_hp_xrefs_10.json",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} executors={len(executor_rows)} damage_hinted={len(damage_executor_rows)} "
        f"candidates={len(candidates)} clusters={len(clusters)}"
    )
    for c in ranked[:10]:
        print(
            f"#{c['rank']} {c['classification']:<32} reuse={c['caller_count']['damage_executor_types']:>2} "
            f"{c['runtime_identity']['native_rva']} {c['runtime_identity']['method_name']} "
            f"down={sorted(c['downstream_hp_path'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
