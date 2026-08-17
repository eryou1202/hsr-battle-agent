#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the damage evaluator provenance preprocess artifact."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "damage_evaluator_provenance_15.json"

DATA = {
    "schema": "damage_evaluator_provenance/1",
    "game_version": "4.4.54",
    "status": "PREPROCESS_PROVENANCE",
    "type_identity": {
        "runtime_type": "JCKKNDFIFLM",
        "type_index": 57813,
        "method_count": 9,
        "field_count": 2,
        "field_start": 274290,
        "method_start": 530150,
    },
    "field_mapping": [
        {
            "native_offset": "0x10",
            "field_index": 274290,
            "field_name": "<MainTarget>k__BackingField",
            "property": "MainTarget",
            "role": "optional component/entity resolver key consumed by M530155",
            "evidence": "M530151 get_MainTarget reads [rcx+0x10]; M530152 set_MainTarget writes [rcx+0x10]; M530155/M530153/M530154 resolve it with token 0x96B72E8",
        },
        {
            "native_offset": "0x18",
            "field_index": None,
            "field_name": "fallback numerator slot (within PFKOKPCDFHO area)",
            "property": None,
            "role": "fallback FixPoint numerator N when e[+0x10]==null",
            "evidence": "M530156 writes [rbx+0x18]=rdi; M530153 returns [rsi+0x18] when no component; M530155 uses as N",
        },
        {
            "native_offset": "0x20",
            "field_index": None,
            "field_name": "fallback denominator slot (within PFKOKPCDFHO area)",
            "property": None,
            "role": "fallback FixPoint denominator D when e[+0x10]==null",
            "evidence": "M530156 writes [rbx+0x20]=rsi; M530154 returns [rsi+0x20] when no component; M530155 uses as D",
        },
    ],
    "field_writers": [
        {
            "offset": "0x10",
            "method_index": 530152,
            "method_name": "set_MainTarget",
            "method_rva": "0x154B9720",
            "instruction_rva": "0x154B9720",
            "declaring_type": "JCKKNDFIFLM",
            "source_provenance": "setter argument rdx",
            "source_classification": "ENTITY_OR_COMPONENT_REFERENCE",
        },
        {
            "offset": "0x10",
            "method_index": 504579,
            "method_name": "TargetDamageHP",
            "method_rva": "0xE46D760",
            "instruction_rva": "0xE46D90B",
            "declaring_type": "RPG.GameCore.AbilityStatic",
            "source_provenance": "[[0x967A0C8+0x98]][0] (global main-target slot)",
            "source_classification": "ENTITY_OR_COMPONENT_REFERENCE",
        },
        {
            "offset": "0x18",
            "method_index": 530156,
            "method_name": "LDBHMDLCCLA",
            "method_rva": "0x154B7F10",
            "instruction_rva": "0x154B7F29",
            "declaring_type": "JCKKNDFIFLM",
            "source_provenance": "constructor/init argument rdx",
            "source_classification": "FIXPOINT_LITERAL_OR_CONFIG_VALUE",
        },
        {
            "offset": "0x18",
            "method_index": 530157,
            "method_name": "EFOKNMPOIPE",
            "method_rva": "0x154B9830",
            "instruction_rva": "0x154B98F3",
            "declaring_type": "JCKKNDFIFLM",
            "source_provenance": "computed from 0x19D65EF80 + 0x19D6682C0 when e[+0x10]==null",
            "source_classification": "GENERATED_RUNTIME_VALUE",
        },
        {
            "offset": "0x18",
            "method_index": 530158,
            "method_name": "DGIBJJFBMMK",
            "method_rva": "0x154B9970",
            "instruction_rva": "0x154B99F7",
            "declaring_type": "JCKKNDFIFLM",
            "source_provenance": "computed from 0x19D65EF80 + 0x19D6682C0 when e[+0x10]==null",
            "source_classification": "GENERATED_RUNTIME_VALUE",
        },
        {
            "offset": "0x20",
            "method_index": 530156,
            "method_name": "LDBHMDLCCLA",
            "method_rva": "0x154B7F10",
            "instruction_rva": "0x154B7F2D",
            "declaring_type": "JCKKNDFIFLM",
            "source_provenance": "constructor/init argument r8",
            "source_classification": "FIXPOINT_LITERAL_OR_CONFIG_VALUE",
        },
    ],
    "m530155_instance_origin": {
        "observed_in": "M504579 TargetDamageHP",
        "evaluator_pointer_register": "rsi",
        "construction_or_obtain_site": "0xE46D8DC call 0x183C736B0 with type token global 0x967A0C8",
        "main_target_write": {
            "instruction_rva": "0xE46D90B",
            "expression": "[rsi+0x10] = [[0x967A0C8+0x98]][0]",
            "classification": "ENTITY_OR_COMPONENT_REFERENCE",
        },
        "container_integration": "rsi passed to 0x1983C5DF0 with container [r14+0x48]",
        "stored_evaluator_slot": "[r14+0x48][+0x10]",
        "loaded_before_q_call": "[rbp+0x6A8] = [r14+0x48][+0x10] at 0xE46D949",
        "shared_across_targets": True,
        "changes_per_target": False,
        "constructed_from_executor_or_config": "materialized inside M504579 from global 0x967A0C8 and container [r14+0x48]; exact executor/config link not fully traced",
        "pre_existing_component_state": "UNKNOWN; object is obtained/materialized during M504579, lifetime not proven",
    },
    "component_identity_test": {
        "evaluator_component": "A = resolve(e[+0x10]) with resolver 0x18B429D40 token 0x96B72E8",
        "target_component": "B = resolve(r13) with resolver 0x18B429D40 token 0x96B72E8; r13 from target list [r14+0x48][+0x28]",
        "identity_rule": "same resolver and token => A==B iff e[+0x10]==r13",
        "main_target_evidence": "e[+0x10] is set once from [[0x967A0C8+0x98]][0]; M504579 compares e[+0x10] to arg1 and r13 to arg1",
        "result": "MAY_ALIAS",
        "subconditions": [
            "SAME_COMPONENT_CONFIRMED for any loop iteration where current target r13 == e[+0x10] (the main target)",
            "DISTINCT_COMPONENT_CONFIRMED for any loop iteration where current target r13 != e[+0x10]",
        ],
    },
    "fallback_value_provenance": {
        "field_0x18": {
            "writers": ["M530156 argument rdx", "M530157/M530158 generated runtime value"],
            "likely_origin": "constructor/config FixPoint argument when literal shape; overwritten by generated value in fallback mutation methods",
            "serializer_mapping": "none found in normalized fields/methods for JCKKNDFIFLM",
        },
        "field_0x20": {
            "writers": ["M530156 argument r8"],
            "likely_origin": "constructor/config FixPoint argument when literal shape; no other writer found",
            "serializer_mapping": "none found in normalized fields/methods for JCKKNDFIFLM",
        },
    },
    "damage_by_attack_property_shapes": {
        "component_ratio": {
            "available": True,
            "evidence": "M504579 writes e[+0x10] from global main-target slot and calls M530157 before M530155; M530155 component path reads property 1/10 through resolver",
        },
        "literal_ratio": {
            "available": True,
            "evidence": "M530156 constructor writes e[+0x18]/e[+0x20] from two FixPoint arguments; M530155 uses them when e[+0x10]==null",
        },
        "representative_design_data": {
            "found": False,
            "note": "No DamageByAttackProperty design records with evaluator shape were found in the current extracted DesignData set; only runtime bridge metadata exists.",
            "structural_conclusion": "BOTH paths are structurally possible; M504579's own initialization makes COMPONENT_RATIO_PATH the observed normal native path.",
        },
    },
    "recommended_next_step": "Resolve global 0x967A0C8 main-target source and find indirect/virtual callers of M530156 to determine whether literal-ratio evaluators are actually constructed for DamageByAttackProperty configs; then the component identity result can be narrowed from MAY_ALIAS.",
}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(DATA, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
