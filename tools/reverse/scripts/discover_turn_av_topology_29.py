#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a bounded native topology census for the 4.4.54 Turn/AV frontier.

This deliberately starts from the already identified action-completion and
TurnBasedGameMode scheduler methods.  It is not a broad ``Turn`` keyword scan
and it does not assign gameplay semantics from metadata names alone.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from semantic_batch_evidence import (
    NORMALIZED_BASE,
    disasm_window,
    iter_records,
    line_for,
    load_manifest,
    load_pe,
)


TURN_BASED_GAME_MODE = 53772

# Completion -> scheduler roots plus the smallest ordering/dataflow helpers.
ROOT_METHOD_INDEXES = {
    499626,  # CheckExecutingFinished
    499649,  # GoTurnEnd
    499650,  # SwapActionEntity
    499654,  # Tick
    499715,  # GetCurrenTurnActionEntity
    499719,  # SetCurrentTurnActionEntity
    499720,  # GetNextActionEntity
    499727,  # AddActionEntity
    499728,  # AddActionEntitiesEnd
    499729,  # RemoveActionEntity
    499750,  # UpdateAllEntityActionOrder
    499751,  # UpdateAllEntityActionOrderAndNotify
    499757,  # ShouldResetActionDelay
    499758,  # ResetAllEntityActionDelay
    499759,  # ResetEntityListActionDelay
    499795,  # ModifyTurnActionDelayCost
    499796,  # ResetTurnActionDelayCost
    499799,  # DoTurnPrepareStartWork
    499800,  # DoTurnBeginWork
    499808,  # SelfActionExecuting1Working
    499810,  # SelfActionExecuting2Working
    499835,  # ProcessTurnOwnerSwitch
    499839,  # ProcessAfterAttackEndBeforeNewAttack
    499840,  # ProcessAfterAttackEnd
    499841,  # AttackFinishComplete
    499863,  # CompareByCharacterActionDelay
    499864,  # _PackActionDelayCompareData
    499865,  # _CompareByCharacterActionDelay
    499866,  # CompareByCharacterActionDelay
    499867,  # PackActionDelayCompareData
    499868,  # PackActionDelayCompareDataForPreshow
    499869,  # UpdateActionEntityListSnapshot
    499870,  # UpdateActionEntityListSnapshotOnActionPhaseEnd
    499876,  # GetTopActionDelayActiveEntity
    499877,  # _PickTurnActiveEntity
    499878,  # _OnCurrentTurnOwnerEntityChanged
    499879,  # SetActionDelayNearTarget
    499907,  # _SortEntityListByActionDelay
    499908,  # _AdvanceListEntityDelay
    499909,  # _OnLevelEntityActionDelayChanged
    499982,  # get_TurnActionDelayCostRatio
    499983,  # set_TurnActionDelayCostRatio
    499994,  # get_CurrentTurnOwnerEntity
    499995,  # set_CurrentTurnOwnerEntity
    499996,  # get_ElapsedActionDelay
    499997,  # set_ElapsedActionDelay
    500113,  # <>c__DisplayClass301_0.<_AdvanceListEntityDelay>b__0
    504500,  # AbilityStatic.ModifyEntitiesActionDelay
    506430,  # TurnBasedAbilityComponent.SetupActionDelayByUnitDistance
    506519,  # TurnBasedAbilityComponent.OnAttackFinishComplete
    506523,  # TurnBasedAbilityComponent.ProcessAfterAttackEnd
    506553,  # TurnBasedAbilityComponent.PreCalcDelayModifyActionDelay
    506583,  # TurnBasedAbilityComponent.RefreshSpeed
    506748,  # TurnBasedAbilityComponent.get_UnitActionDelay
    506755,  # TurnBasedAbilityComponent.get_ActionDelayDistance
    506756,  # TurnBasedAbilityComponent.set_ActionDelayDistance
    516740,  # NOMOKAFFKFE action-delay comparison key comparator
    537524,  # GamePlayStatic.CalculateNewActionDelayWhenSpeedChange
}

RELATED_NAME = re.compile(
    r"(?:ActionDelay|ActionOrder|ActionEntity|CurrentTurnOwner|"
    r"GetNextActionEntity|PickTurnActiveEntity|AdvanceListEntityDelay|"
    r"CheckExecutingFinished|AttackFinishComplete|GoTurnEnd)"
)


def _direct_target_rva(ins: dict, image_base: int) -> int | None:
    if ins["mnemonic"] not in {"call", "jmp"}:
        return None
    match = re.fullmatch(r"0x([0-9a-fA-F]+)", ins["op_str"].strip())
    if match is None:
        return None
    target_va = int(match.group(1), 16)
    if target_va < image_base:
        return None
    return target_va - image_base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--text-output", type=Path)
    parser.add_argument("--max-body", type=lambda value: int(value, 0), default=0x6000)
    args = parser.parse_args()

    types = {
        record["type_index"]: {
            "type_index": record["type_index"],
            "namespace": record["namespace"],
            "full_name": record["full_name"],
        }
        for record in iter_records(NORMALIZED_BASE / "types.json")
    }
    methods = [
        {
            "method_index": record["method_index"],
            "declaring_type_index": record["declaring_type_index"],
            "name": record["name"],
            "parameter_count": record["parameter_count"],
            "return_type_reference": record["return_type_reference"],
            "native_rva": record["native_rva"],
            "mapping_kind": record["mapping_kind"],
        }
        for record in iter_records(NORMALIZED_BASE / "methods.json")
    ]
    method_by_index = {record["method_index"]: record for record in methods}

    related_methods = []
    for method in methods:
        owner = types.get(method["declaring_type_index"], {})
        if owner.get("namespace") != "RPG.GameCore":
            continue
        if method["method_index"] in ROOT_METHOD_INDEXES or RELATED_NAME.search(method["name"]):
            related_methods.append({
                **method,
                "declaring_type": owner.get("full_name"),
            })

    related_type_indexes = {record["declaring_type_index"] for record in related_methods}
    related_fields = []
    for field in iter_records(NORMALIZED_BASE / "fields.json"):
        owner = types.get(field["declaring_type_index"], {})
        if owner.get("namespace") != "RPG.GameCore":
            continue
        if field["declaring_type_index"] in related_type_indexes and RELATED_NAME.search(field["name"]):
            related_fields.append({
                **field,
                "declaring_type": owner.get("full_name"),
            })

    native_starts = sorted({
        method["native_rva"]
        for method in methods
        if isinstance(method.get("native_rva"), int)
        and method.get("mapping_kind") == "DIRECT_NATIVE"
    })
    next_start = {
        start: native_starts[index + 1]
        for index, start in enumerate(native_starts[:-1])
    }
    rva_identities: dict[int, list[dict]] = {}
    for method in methods:
        rva = method.get("native_rva")
        if not isinstance(rva, int):
            continue
        owner = types.get(method["declaring_type_index"], {})
        rva_identities.setdefault(rva, []).append({
            "method_index": method["method_index"],
            "declaring_type": owner.get("full_name"),
            "name": method["name"],
        })

    pe = load_pe()
    roots = []
    text_sections = []
    for method_index in sorted(ROOT_METHOD_INDEXES):
        method = method_by_index.get(method_index)
        if method is None or not isinstance(method.get("native_rva"), int):
            roots.append({"method_index": method_index, "status": "NO_DIRECT_BODY"})
            continue
        rva = method["native_rva"]
        end = next_start.get(rva)
        if end is None or end <= rva:
            roots.append({"method_index": method_index, "status": "NO_BOUND"})
            continue
        length = end - rva
        if length > args.max_body:
            roots.append({
                "method_index": method_index,
                "status": "BODY_EXCEEDS_BOUND",
                "native_rva": f"0x{rva:X}",
                "next_native_rva": f"0x{end:X}",
                "body_span": length,
            })
            continue
        _, decoded = disasm_window(pe, rva, length)
        calls = []
        for ins in decoded:
            target_rva = _direct_target_rva(ins, pe.image_base)
            if target_rva is None:
                continue
            calls.append({
                "site_rva": f"0x{ins['rva']:X}",
                "kind": ins["mnemonic"],
                "target_rva": f"0x{target_rva:X}",
                "target_identities": rva_identities.get(target_rva, []),
            })
        owner = types.get(method["declaring_type_index"], {})
        root = {
            "method_index": method_index,
            "declaring_type": owner.get("full_name"),
            "name": method["name"],
            "native_rva": f"0x{rva:X}",
            "next_native_rva": f"0x{end:X}",
            "body_span": length,
            "status": "BOUNDED_NATIVE_WINDOW",
            "direct_edges": calls,
            "disassembly": [line_for(ins) for ins in decoded],
        }
        roots.append(root)
        text_sections.append(
            f"## M{method_index} {owner.get('full_name')}.{method['name']} "
            f"RVA 0x{rva:X} span 0x{length:X}\n"
            + "\n".join(root["disassembly"])
        )

    manifest = load_manifest()
    result = {
        "schema": "turn_av_topology_census/1",
        "game_version": manifest["game_version"],
        "gameassembly_sha256": manifest["GameAssembly"]["sha256"],
        "scope": {
            "anchor_type_index": TURN_BASED_GAME_MODE,
            "anchor_type": types[TURN_BASED_GAME_MODE]["full_name"],
            "selection": "completion/scheduler roots plus bounded ActionDelay/ActionOrder relations",
            "metadata_names_are_discovery_only": True,
        },
        "root_methods": roots,
        "related_methods": related_methods,
        "related_fields": related_fields,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.text_output is not None:
        args.text_output.parent.mkdir(parents=True, exist_ok=True)
        args.text_output.write_text("\n\n".join(text_sections) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} roots={len(roots)} "
        f"related_methods={len(related_methods)} related_fields={len(related_fields)}"
    )
    if args.text_output is not None:
        print(f"wrote {args.text_output} sections={len(text_sections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
