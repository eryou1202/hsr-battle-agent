"""Strict loader for the recovered Natasha Skill02 real-content slice."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.healing import (
    NatashaSkill02HealConfig,
    SerializedDynamicFloatFormula,
)

EXPECTED_STATUS = "REAL_SKILL_HEALHP_NODE_AND_FORMULA4_CONFIG_CONFIRMED"


class RealSkillContentError(ValueError):
    """The content artifact does not match the recovered capability contract."""


def default_natasha_skill02_artifact_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "raw"
        / "4.4.54"
        / "natasha_skill02_healhp_content_30.json"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RealSkillContentError(f"{label} must be a mapping")
    return value


def _formula(value: Any, label: str) -> SerializedDynamicFloatFormula:
    row = _require_mapping(value, label)
    if row.get("serialized_type") != "RPG.GameCore.DynamicFloat.formula":
        raise RealSkillContentError(f"{label} is not a DynamicFloat formula")
    if row.get("field_presence_bitmap") != 1:
        raise RealSkillContentError(f"{label} must use formula bitmap 1")
    if row.get("evaluation_status") != "BYTECODE_SEMANTICS_NOT_RECOVERED":
        raise RealSkillContentError(f"{label} evaluation boundary changed")
    qwords = row.get("qword_operands")
    int32s = row.get("int32_operands")
    if not isinstance(qwords, list) or not isinstance(int32s, list):
        raise RealSkillContentError(f"{label} operands must be lists")
    return SerializedDynamicFloatFormula(
        opcodes=tuple(int(item) for item in row.get("opcodes", [])),
        qword_operands=tuple(int(item["signed_value"]) for item in qwords),
        int32_operands=tuple(int(item["signed_value"]) for item in int32s),
        source_start=str(row["start"]),
        source_end_exclusive=str(row["end_exclusive"]),
    )


def _mapping_name(node: Mapping[str, Any], label: str) -> str:
    mapping = _require_mapping(node.get("registry_mapping"), f"{label}.registry_mapping")
    name = mapping.get("runtime_type_name")
    if not isinstance(name, str):
        raise RealSkillContentError(f"{label} has no runtime type name")
    return name


def load_natasha_skill02_heal_config(
    path: str | Path | None = None,
) -> NatashaSkill02HealConfig:
    artifact_path = (
        Path(path) if path is not None else default_natasha_skill02_artifact_path()
    )
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealSkillContentError(f"cannot load {artifact_path}: {exc}") from exc
    root = _require_mapping(data, "artifact")
    if root.get("schema") != "natasha_skill02_healhp_content/2":
        raise RealSkillContentError("unsupported Natasha content schema")
    if root.get("game_version") != "4.4.54" or root.get("status") != EXPECTED_STATUS:
        raise RealSkillContentError("Natasha content version/status is not accepted")

    ability = _require_mapping(root.get("ability"), "ability")
    if ability.get("name") != "Avatar_Natasha_00_Skill02_Phase02":
        raise RealSkillContentError("unexpected ability name")
    if ability.get("field_presence_bitmap") != 51:
        raise RealSkillContentError("AbilityConfig field bitmap changed")
    subtree = _require_mapping(root.get("recovered_subtree"), "recovered_subtree")
    parent = _require_mapping(subtree.get("parent"), "parent")
    predicate = _require_mapping(subtree.get("predicate"), "predicate")
    tasks = subtree.get("success_tasks")
    if not isinstance(tasks, list) or len(tasks) != 2:
        raise RealSkillContentError("expected exactly two success tasks")
    dispel = _require_mapping(tasks[0], "success_tasks[0]")
    heal = _require_mapping(tasks[1], "success_tasks[1]")
    target = _require_mapping(heal.get("target_type"), "HealHP.TargetType")
    boundary = _require_mapping(subtree.get("boundary_proof"), "boundary_proof")

    required = (
        (int(parent.get("discriminator", -1)), 1960, _mapping_name(parent, "parent"), "RPG.GameCore.PredicateTaskList"),
        (int(predicate.get("discriminator", -1)), 496, _mapping_name(predicate, "predicate"), "RPG.GameCore.BySkillPointActivated"),
        (int(dispel.get("discriminator", -1)), 1199, _mapping_name(dispel, "dispel"), "RPG.GameCore.DispelStatus"),
        (int(heal.get("discriminator", -1)), 1481, _mapping_name(heal, "heal"), "RPG.GameCore.HealHP"),
    )
    for actual_id, expected_id, actual_name, expected_name in required:
        if (actual_id, actual_name) != (expected_id, expected_name):
            raise RealSkillContentError(
                f"registry identity mismatch: {(actual_id, actual_name)!r}"
            )
    if (
        heal.get("start") != "0xBC9A4B"
        or heal.get("end_exclusive") != "0xBC9A7E"
        or boundary.get("next_outer_task_start") != "0xBC9A7E"
        or boundary.get("next_outer_task_discriminator") != 1960
    ):
        raise RealSkillContentError("HealHP boundary proof changed")
    formula_type = _require_mapping(heal.get("formula_type"), "formula_type")
    if int(formula_type.get("value", -1)) != 4:
        raise RealSkillContentError("only FormulaType 4 is accepted")
    if target.get("discriminator") != 12 or target.get("name") != "AbilityTargetEntity":
        raise RealSkillContentError("HealHP target alias changed")
    if (
        parent.get("field_presence_bitmap") != 6
        or predicate.get("field_presence_bitmap") != 8
        or predicate.get("trigger_key") != 12
        or dispel.get("field_presence_bitmap") != 194
        or dispel.get("order") != 2
        or heal.get("field_presence_bitmap") != 178
        or target.get("field_presence_bitmap") != 1
    ):
        raise RealSkillContentError("real skill field contract changed")
    absent = heal.get("absent_default_fields")
    if not isinstance(absent, list) or "IsHealRallyHP" not in absent:
        raise RealSkillContentError("ordinary non-rally default is no longer proven")

    dispel_formula = _formula(dispel.get("numbers"), "DispelStatus.Numbers")
    percentage_formula = _formula(
        heal.get("heal_percentage"), "HealHP.HealPercentage"
    )
    modify_formula = _formula(heal.get("modify_value"), "HealHP.ModifyValue")
    expected_formulas = (
        (dispel_formula, -2124210825),
        (percentage_formula, -1544075911),
        (modify_formula, -203632277),
    )
    if any(
        formula.opcodes != (1, 0, 17)
        or formula.qword_operands
        or formula.int32_operands != (expected_operand,)
        for formula, expected_operand in expected_formulas
    ):
        raise RealSkillContentError("real skill DynamicFloat structure changed")

    source = _require_mapping(root.get("source"), "source")
    if source.get("archive_sha256") != (
        "098ec31c5c03a0f6fbf030d6b2579a5e60c03639ce7060f68fa52371a03dc64b"
    ):
        raise RealSkillContentError("DesignData archive provenance changed")
    return NatashaSkill02HealConfig(
        ability_name=str(ability["name"]),
        content_artifact_ref=str(artifact_path),
        content_artifact_sha256=_sha256(artifact_path),
        archive_sha256=str(source["archive_sha256"]),
        parent_discriminator=int(parent["discriminator"]),
        predicate_discriminator=int(predicate["discriminator"]),
        predicate_trigger_key=int(predicate["trigger_key"]),
        target_discriminator=int(target["discriminator"]),
        target_name=str(target["name"]),
        dispel_discriminator=int(dispel["discriminator"]),
        dispel_order=int(dispel["order"]),
        dispel_numbers=dispel_formula,
        heal_discriminator=int(heal["discriminator"]),
        heal_formula_type=int(formula_type["value"]),
        heal_percentage=percentage_formula,
        modify_value=modify_formula,
    )
