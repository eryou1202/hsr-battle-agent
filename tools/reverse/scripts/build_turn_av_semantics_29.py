#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the scoped 4.4.54 Turn/AV semantic capability.

The input census is mechanical topology.  This builder projects only the
native dataflow needed by the deterministic sandbox and records the two
remaining boundaries (special ordering and post-action recharge) explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from semantic_batch_evidence import load_manifest, load_pe


GAME_VERSION = "4.4.54"
E4 = "E4_STATIC_MACHINE_CODE"
REQUIRED_METHODS = {
    499626: "CheckExecutingFinished",
    499649: "GoTurnEnd",
    499799: "DoTurnPrepareStartWork",
    499808: "SelfActionExecuting1Working",
    499876: "GetTopActionDelayActiveEntity",
    499877: "_PickTurnActiveEntity",
    499907: "_SortEntityListByActionDelay",
    499908: "_AdvanceListEntityDelay",
    500113: "<_AdvanceListEntityDelay>b__0",
    504500: "ModifyEntitiesActionDelay",
    506430: "SetupActionDelayByUnitDistance",
    506748: "get_UnitActionDelay",
    516740: "KGAFHLGGNHJ",
    537524: "CalculateNewActionDelayWhenSpeedChange",
}


def _method_evidence(census: dict, pe) -> list[dict]:
    by_index = {row["method_index"]: row for row in census["root_methods"]}
    evidence = []
    for method_index, expected_name in REQUIRED_METHODS.items():
        row = by_index.get(method_index)
        if row is None or row.get("status") != "BOUNDED_NATIVE_WINDOW":
            raise RuntimeError(f"missing bounded native method M{method_index}")
        if row.get("name") != expected_name:
            raise RuntimeError(
                f"M{method_index} name drift: {row.get('name')!r} != {expected_name!r}"
            )
        rva = int(row["native_rva"], 16)
        span = int(row["body_span"])
        raw = pe.read_rva(rva, span)
        if raw is None or len(raw) != span:
            raise RuntimeError(f"cannot read native body for M{method_index}")
        evidence.append({
            "method_index": method_index,
            "declaring_type": row.get("declaring_type"),
            "method_name": row["name"],
            "native_rva": row["native_rva"],
            "bounded_body_bytes": span,
            "bounded_body_sha256": hashlib.sha256(raw).hexdigest(),
            "evidence_level": E4,
        })
    return evidence


def build(census: dict) -> dict:
    manifest = load_manifest()
    if census.get("game_version") != GAME_VERSION:
        raise RuntimeError("unexpected census game version")
    if census.get("gameassembly_sha256") != manifest["GameAssembly"]["sha256"]:
        raise RuntimeError("census/GameAssembly provenance mismatch")
    pe = load_pe()
    return {
        "schema": "turn_av_semantics/1",
        "game_version": GAME_VERSION,
        "capability_id": "TURN_AV_SEMANTICS_29_PROOF",
        "status": "CONFIRMED_SCOPED_TURN_PREPARE_SELECTION_AND_AV_ADVANCE",
        "evidence_level": E4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            "GameAssembly_sha256": manifest["GameAssembly"]["sha256"],
        },
        "native_methods": _method_evidence(census, pe),
        "property_bindings": [
            {
                "property_id": 32,
                "semantic_role": "speed_input",
                "status": "CONFIRMED",
                "proof": "M506748 reads property 32 and divides the unit-distance constant by it; M506430 uses the same property as the divisor for remaining delay.",
            },
            {
                "property_id": 38,
                "semantic_role": "remaining_action_delay",
                "status": "CONFIRMED",
                "proof": "M499867 packs property 38 as the leading ordering key; M499877 reads it from the selected actor; M500113 reads and rewrites it for every advanced actor.",
            },
        ],
        "formulas": [
            {
                "id": "unit_action_delay",
                "status": "CONFIRMED_WITH_UNKNOWN_CONSTANT",
                "formula": "speed > 0 ? unit_distance_constant / speed : FixPoint(0)",
                "evidence": "M506748",
                "unknowns": ["Concrete value and lifetime policy of unit_distance_constant."],
            },
            {
                "id": "setup_remaining_action_delay",
                "status": "CONFIRMED_WITH_UNKNOWN_CONSTANT",
                "formula": "distance = unit_distance_constant * input_ratio; remaining = speed > 0 ? distance / speed : FixPoint(0); set property 38 = remaining",
                "evidence": "M506430",
                "unknowns": ["Concrete value and content source of input_ratio for a general actor."],
            },
            {
                "id": "advance_all_remaining_delay",
                "status": "CONFIRMED",
                "formula": "for each admitted action entity: property38 = max(property38 - selected_delay, FixPoint(0)); elapsed_action_delay += selected_delay",
                "evidence": "M499908 -> M504500 -> M500113",
                "unknowns": [],
            },
        ],
        "turn_prepare_transition": {
            "status": "CONFIRMED_SCOPED",
            "sequence": [
                "M499799 sorts the action-entity list through M499907.",
                "M499799 calls M499877 to pick the next active entity.",
                "M499876 returns the first eligible HasActionTurn entity after native filters.",
                "M499877 stores the current actor/owner, reads its property 38, then advances the list by that value.",
            ],
            "sandbox_preconditions": [
                "Every registered participant is eligible and has an action turn.",
                "No lock-action-delay, immediate-action, one-more-action, or special-list priority is active.",
                "Every participant has an existing untransformed PropertyEntry for property 38.",
            ],
        },
        "ordering": {
            "status": "CONFIRMED_KEYS_PARTIAL_EQUAL_KEY_POLICY",
            "native_key_order": [
                "remaining action delay ascending",
                "continuation/current-actor boolean: true first",
                "when delay <= 0: immediate/special boolean true first, then special integer ascending",
                "additional integer key A ascending",
                "additional integer key B ascending",
            ],
            "ordinary_scope_equal_key_policy": "Sandbox preserves prior action-list order as an explicit deterministic policy.",
            "unknowns": [
                "The native List<T>.Sort reorder behavior for actors equal across every packed key is not claimed stable.",
                "Gameplay meanings and population rules of the special packed keys remain outside the ordinary scope.",
            ],
        },
        "completion_boundary": {
            "status": "CONFIRMED_BOUNDARY_PARTIAL_RECHARGE",
            "facts": [
                "M499626 and M499808 gate completion on skill/limbo/add-buff/hold-frame cleanup state rather than task success alone.",
                "M499649 transitions the turn FSM to TurnEnd (enum value 20).",
            ],
            "runtime_contract": "The sandbox requires an explicit settled-action acknowledgement before another TurnPrepare transition.",
            "unknowns": [
                "The generic post-action writer that recharges the acting entity's property 38 for its next ordinary turn is not closed.",
                "The sandbox therefore requires a caller-supplied, provenance-bearing next_action_delay_raw at completion; it does not synthesize 10000/SPD or 150/SPD.",
            ],
        },
        "primitive": {
            "primitive_id": "battle.ir.turn.advance_to_next_actor",
            "semantic_name": "AdvanceToNextActorOrdinaryScope",
            "source_method_index": 499799,
            "source_method": "RPG.GameCore.TurnBasedGameMode.DoTurnPrepareStartWork",
            "source_native_rva": "0xE769000",
            "inputs": [],
            "context_reads": [
                "BattleState.turn_timeline.action_entity_runtime_ids",
                "BattleState.entity_property_entries[property 38]",
            ],
            "context_writes": [
                "BattleState.turn_timeline",
                "BattleState.entity_property_entries[property 38]",
            ],
            "output": "turn_advance_result",
            "determinism": "DETERMINISTIC_WITH_STABLE_EQUAL_KEY_SANDBOX_POLICY",
        },
        "explicit_unknowns": [
            "Concrete unit-distance constant.",
            "Generic post-action delay recharge/cost formula and writer.",
            "Special/immediate/insert/one-more/locked action ordering.",
            "Native all-keys-equal List<T>.Sort stability.",
            "Opaque event/listener effects outside the persistent scheduler writes.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("census", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    census = json.loads(args.census.read_text(encoding="utf-8"))
    artifact = build(census)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} methods={len(artifact['native_methods'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
