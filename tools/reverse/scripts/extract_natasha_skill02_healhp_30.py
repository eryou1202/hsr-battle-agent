#!/usr/bin/env python3
"""Extract the real Natasha Skill02 Phase02 HealHP subtree.

This is a deliberately narrow DesignData decoder.  It consumes the generic
ability-container and global generated-config registry artifacts, validates
their provenance against the supplied archive, and decodes only the field
layouts independently recovered for PredicateTaskList, DispelStatus, HealHP,
TargetConfig and DynamicFloat.

It does not evaluate predicates, DynamicFloat bytecode, or apply healing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
from pathlib import Path
from typing import Any


SKILL_NAME = "Avatar_Natasha_00_Skill02_Phase02"
NEXT_ABILITY_NAME = "Avatar_Natasha_00_Skill03_EnterReady"
PARENT_PREFIX = bytes.fromhex("A8 0F 06 F0 03 08 0C 02")


class DecodeError(RuntimeError):
    """Raised when the source bytes do not satisfy the proven layout."""


def _offset(value: str) -> int:
    return int(value, 0)


def _hex(value: int) -> str:
    return f"0x{value:X}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DecodeError(f"{path} must contain a JSON object")
    return value


class Reader:
    def __init__(self, data: mmap.mmap, start: int, limit: int) -> None:
        self.data = data
        self.offset = start
        self.limit = limit

    def uleb(self, label: str, max_bytes: int = 10) -> tuple[int, int, int]:
        start = self.offset
        value = 0
        shift = 0
        for _ in range(max_bytes):
            if self.offset >= self.limit:
                raise DecodeError(f"{label}: ULEB crosses decode limit")
            byte = self.data[self.offset]
            self.offset += 1
            value |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                return value, start, self.offset
            shift += 7
        raise DecodeError(f"{label}: ULEB exceeds {max_bytes} bytes")

    def raw(self, size: int, label: str) -> tuple[bytes, int, int]:
        start = self.offset
        end = start + size
        if size < 0 or end > self.limit:
            raise DecodeError(f"{label}: byte range crosses decode limit")
        self.offset = end
        return bytes(self.data[start:end]), start, end

    def string(self, label: str) -> dict[str, Any]:
        size, start, _ = self.uleb(f"{label}.length", max_bytes=5)
        raw, _, end = self.raw(size, label)
        try:
            value = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DecodeError(f"{label}: invalid UTF-8") from exc
        return {
            "value": value,
            "length": size,
            "start": _hex(start),
            "end_exclusive": _hex(end),
        }


def _zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _dynamic_float(reader: Reader, label: str) -> dict[str, Any]:
    start = reader.offset
    bitmap, _, _ = reader.uleb(f"{label}.field_presence_bitmap")
    if bitmap != 1:
        raise DecodeError(f"{label}: expected formula bitmap 1, got {bitmap}")
    opcode_count, _, _ = reader.uleb(f"{label}.opcode_count", max_bytes=5)
    opcodes, _, _ = reader.raw(opcode_count, f"{label}.opcodes")
    qword_count, _, _ = reader.uleb(f"{label}.qword_operand_count", max_bytes=5)
    qword_operands = []
    for index in range(qword_count):
        encoded, operand_start, operand_end = reader.uleb(
            f"{label}.qword_operands[{index}]"
        )
        qword_operands.append(
            {
                "encoded_uleb": encoded,
                "signed_value": _zigzag(encoded),
                "start": _hex(operand_start),
                "end_exclusive": _hex(operand_end),
            }
        )
    int32_count, _, _ = reader.uleb(f"{label}.int32_operand_count", max_bytes=5)
    int32_operands = []
    for index in range(int32_count):
        encoded, operand_start, operand_end = reader.uleb(
            f"{label}.int32_operands[{index}]", max_bytes=5
        )
        value = _zigzag(encoded)
        if not (-(2**31) <= value <= 2**31 - 1):
            raise DecodeError(f"{label}: decoded int32 operand is out of range")
        int32_operands.append(
            {
                "encoded_uleb": encoded,
                "signed_value": value,
                "start": _hex(operand_start),
                "end_exclusive": _hex(operand_end),
            }
        )
    return {
        "serialized_type": "RPG.GameCore.DynamicFloat.formula",
        "start": _hex(start),
        "end_exclusive": _hex(reader.offset),
        "field_presence_bitmap": bitmap,
        "opcodes_hex": opcodes.hex(" ").upper(),
        "opcodes": list(opcodes),
        "qword_operands": qword_operands,
        "int32_operands": int32_operands,
        "evaluation_status": "BYTECODE_SEMANTICS_NOT_RECOVERED",
    }


def _target_config(reader: Reader, label: str) -> dict[str, Any]:
    start = reader.offset
    discriminator, _, _ = reader.uleb(f"{label}.discriminator")
    bitmap, _, _ = reader.uleb(f"{label}.field_presence_bitmap")
    if bitmap != 1:
        raise DecodeError(f"{label}: expected bitmap 1, got {bitmap}")
    name = reader.string(f"{label}.name")
    return {
        "start": _hex(start),
        "end_exclusive": _hex(reader.offset),
        "discriminator": discriminator,
        "field_presence_bitmap": bitmap,
        "name": name["value"],
        "runtime_resolution_status": "TARGET_SELECTOR_REGISTRY_NOT_JOINED",
    }


def _registry_mapping(registry: dict[str, Any], discriminator: int) -> dict[str, Any]:
    mappings = registry.get("mappings")
    if not isinstance(mappings, list):
        raise DecodeError("registry artifact has no mappings list")
    matches = [row for row in mappings if row.get("discriminator") == discriminator]
    if len(matches) != 1:
        raise DecodeError(
            f"registry discriminator {discriminator} has {len(matches)} mappings"
        )
    row = matches[0]
    return {
        "discriminator": discriminator,
        "runtime_type_name": row.get("concrete_runtime_type_name"),
        "parser_method_index": row.get("concrete_parser_method_index"),
        "parser_native_rva": row.get("concrete_parser_native_rva"),
        "mapping_status": row.get("mapping_status"),
    }


def _require_mapping(
    registry: dict[str, Any], discriminator: int, expected_name: str
) -> dict[str, Any]:
    mapping = _registry_mapping(registry, discriminator)
    if mapping["runtime_type_name"] != expected_name:
        raise DecodeError(
            f"discriminator {discriminator}: expected {expected_name}, "
            f"got {mapping['runtime_type_name']}"
        )
    return mapping


def _entry(container: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [row for row in container.get("entries", []) if row.get("name") == name]
    if len(matches) != 1:
        raise DecodeError(f"ability container has {len(matches)} entries named {name}")
    return matches[0]


def extract(
    archive: Path,
    container_path: Path,
    task_registry_path: Path,
    predicate_registry_path: Path,
) -> dict[str, Any]:
    container = _read_json(container_path)
    task_registry = _read_json(task_registry_path)
    predicate_registry = _read_json(predicate_registry_path)
    actual_sha256 = _sha256(archive)
    expected_sha256 = str(container.get("source", {}).get("archive_sha256", "")).lower()
    if actual_sha256.lower() != expected_sha256:
        raise DecodeError(
            f"archive SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    skill_entry = _entry(container, SKILL_NAME)
    next_entry = _entry(container, NEXT_ABILITY_NAME)
    skill_start = _offset(skill_entry["payload_anchor"])
    skill_end = _offset(next_entry["payload_anchor"])

    expected_task_mappings = {
        1199: "RPG.GameCore.DispelStatus",
        1481: "RPG.GameCore.HealHP",
        1960: "RPG.GameCore.PredicateTaskList",
        3726: "RPG.GameCore.WaitAnimState",
    }
    task_mappings = {
        str(discriminator): _require_mapping(task_registry, discriminator, name)
        for discriminator, name in expected_task_mappings.items()
    }
    predicate_mapping = _require_mapping(
        predicate_registry, 496, "RPG.GameCore.BySkillPointActivated"
    )

    with archive.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        phase = Reader(data, skill_start, skill_end)
        ability_bitmap, bitmap_start, bitmap_end = phase.uleb("AbilityConfig.bitmap")
        if ability_bitmap != 0x33:
            raise DecodeError(
                f"{SKILL_NAME}: expected AbilityConfig bitmap 0x33, got {ability_bitmap:#x}"
            )
        ability_name = phase.string("AbilityConfig.Name")
        if ability_name["value"] != SKILL_NAME:
            raise DecodeError(f"ability name mismatch: {ability_name['value']!r}")

        target_info_start = phase.offset
        target_info_bitmap, _, _ = phase.uleb("AbilityConfig.TargetInfo.bitmap")
        target_info_selector, _, target_info_end = phase.uleb(
            "AbilityConfig.TargetInfo.selector"
        )
        if target_info_bitmap != 1 or target_info_selector != 16:
            raise DecodeError(
                "unexpected phase TargetInfo prefix; expected bitmap=1 selector=16"
            )
        on_start_count, count_start, count_end = phase.uleb("AbilityConfig.OnStart.count")
        if on_start_count != 22:
            raise DecodeError(f"expected 22 OnStart tasks, got {on_start_count}")
        first_task, first_task_start, first_task_end = phase.uleb(
            "AbilityConfig.OnStart.first_task"
        )
        if first_task != 3726:
            raise DecodeError(f"expected first OnStart task 3726, got {first_task}")

        parent_start = data.find(PARENT_PREFIX, first_task_start, skill_end)
        if parent_start < 0:
            raise DecodeError("PredicateTaskList/HealHP subtree prefix not found")
        if data.find(PARENT_PREFIX, parent_start + 1, skill_end) >= 0:
            raise DecodeError("PredicateTaskList/HealHP subtree prefix is not unique")

        node = Reader(data, parent_start, skill_end)
        parent_discriminator, _, _ = node.uleb("PredicateTaskList.discriminator")
        parent_bitmap, _, _ = node.uleb("PredicateTaskList.bitmap")
        predicate_discriminator, predicate_start, _ = node.uleb(
            "PredicateTaskList.Predicate.discriminator"
        )
        predicate_bitmap, _, _ = node.uleb("BySkillPointActivated.bitmap")
        predicate_trigger_key, _, predicate_end = node.uleb(
            "BySkillPointActivated.trigger_key"
        )
        success_count, _, _ = node.uleb("PredicateTaskList.SuccessTaskList.count")
        if (
            parent_discriminator,
            parent_bitmap,
            predicate_discriminator,
            predicate_bitmap,
            predicate_trigger_key,
            success_count,
        ) != (1960, 6, 496, 8, 12, 2):
            raise DecodeError("PredicateTaskList subtree header does not match recovered layout")

        dispel_start = node.offset
        dispel_discriminator, _, _ = node.uleb("DispelStatus.discriminator")
        dispel_bitmap, _, _ = node.uleb("DispelStatus.bitmap")
        if (dispel_discriminator, dispel_bitmap) != (1199, 194):
            raise DecodeError("unexpected DispelStatus child header")
        dispel_target = _target_config(node, "DispelStatus.TargetType")
        dispel_numbers = _dynamic_float(node, "DispelStatus.Numbers")
        dispel_order, _, _ = node.uleb("DispelStatus.Order")
        if dispel_order != 2:
            raise DecodeError(f"expected DispelStatus.Order=2, got {dispel_order}")
        dispel_end = node.offset

        heal_start = node.offset
        heal_discriminator, _, _ = node.uleb("HealHP.discriminator")
        heal_bitmap, _, _ = node.uleb("HealHP.bitmap")
        if (heal_discriminator, heal_bitmap) != (1481, 178):
            raise DecodeError("unexpected HealHP child header")
        heal_target = _target_config(node, "HealHP.TargetType")
        formula_type, formula_start, formula_end = node.uleb("HealHP.FormulaType")
        if formula_type != 4:
            raise DecodeError(f"expected HealHP.FormulaType=4, got {formula_type}")
        heal_percentage = _dynamic_float(node, "HealHP.HealPercentage")
        modify_value = _dynamic_float(node, "HealHP.ModifyValue")
        heal_end = node.offset
        next_selector, next_start, next_end = node.uleb("next_outer_task.discriminator")
        if next_selector != 1960:
            raise DecodeError(
                f"HealHP boundary check expected next selector 1960, got {next_selector}"
            )

        source_window = bytes(data[parent_start:next_end]).hex(" ").upper()

    return {
        "schema": "natasha_skill02_healhp_content/2",
        "game_version": "4.4.54",
        "status": "REAL_SKILL_HEALHP_NODE_AND_FORMULA4_CONFIG_CONFIRMED",
        "source": {
            "archive": str(archive.resolve()),
            "archive_size": archive.stat().st_size,
            "archive_sha256": actual_sha256,
            "ability_container_artifact": str(container_path),
            "task_registry_artifact": str(task_registry_path),
            "predicate_registry_artifact": str(predicate_registry_path),
        },
        "ability": {
            "name": SKILL_NAME,
            "start": _hex(skill_start),
            "end_exclusive": _hex(skill_end),
            "field_presence_bitmap": ability_bitmap,
            "field_presence_bitmap_range": [_hex(bitmap_start), _hex(bitmap_end)],
            "present_fields": ["Name", "TargetInfo", "OnStart", "DynamicValues"],
            "target_info": {
                "start": _hex(target_info_start),
                "end_exclusive": _hex(target_info_end),
                "field_presence_bitmap": target_info_bitmap,
                "selector": target_info_selector,
            },
            "on_start": {
                "count": on_start_count,
                "count_range": [_hex(count_start), _hex(count_end)],
                "first_task": {
                    "discriminator": first_task,
                    "range": [_hex(first_task_start), _hex(first_task_end)],
                    "registry_mapping": task_mappings[str(first_task)],
                },
            },
        },
        "recovered_subtree": {
            "placement": (
                "unique recovered PredicateTaskList subtree after the validated "
                "OnStart list header and before the next ability anchor"
            ),
            "start": _hex(parent_start),
            "end_exclusive": _hex(heal_end),
            "source_window_through_next_selector_hex": source_window,
            "parent": {
                "discriminator": parent_discriminator,
                "field_presence_bitmap": parent_bitmap,
                "present_fields": ["Predicate", "SuccessTaskList"],
                "registry_mapping": task_mappings[str(parent_discriminator)],
            },
            "predicate": {
                "start": _hex(predicate_start),
                "end_exclusive": _hex(predicate_end),
                "discriminator": predicate_discriminator,
                "field_presence_bitmap": predicate_bitmap,
                "trigger_key": predicate_trigger_key,
                "registry_mapping": predicate_mapping,
                "evaluation_status": "RUNTIME_CONTEXT_SEMANTICS_NOT_RECOVERED",
            },
            "success_task_count": success_count,
            "success_tasks": [
                {
                    "ordinal": 0,
                    "start": _hex(dispel_start),
                    "end_exclusive": _hex(dispel_end),
                    "discriminator": dispel_discriminator,
                    "field_presence_bitmap": dispel_bitmap,
                    "present_fields": ["TargetType", "Numbers", "Order"],
                    "registry_mapping": task_mappings[str(dispel_discriminator)],
                    "target_type": dispel_target,
                    "numbers": dispel_numbers,
                    "order": dispel_order,
                },
                {
                    "ordinal": 1,
                    "start": _hex(heal_start),
                    "end_exclusive": _hex(heal_end),
                    "discriminator": heal_discriminator,
                    "field_presence_bitmap": heal_bitmap,
                    "present_fields": [
                        "TargetType",
                        "FormulaType",
                        "HealPercentage",
                        "ModifyValue",
                    ],
                    "absent_default_fields": [
                        "HealerTargetType",
                        "AliveOnly",
                        "SPHitRatio",
                        "IsHealRallyHP",
                        "ScreenSpaceFloatMsg",
                        "DisplayData",
                        "PerformanceDelay",
                    ],
                    "registry_mapping": task_mappings[str(heal_discriminator)],
                    "target_type": heal_target,
                    "formula_type": {
                        "value": formula_type,
                        "range": [_hex(formula_start), _hex(formula_end)],
                    },
                    "heal_percentage": heal_percentage,
                    "modify_value": modify_value,
                },
            ],
            "boundary_proof": {
                "heal_end_exclusive": _hex(heal_end),
                "next_outer_task_start": _hex(next_start),
                "next_outer_task_discriminator": next_selector,
                "next_outer_task_discriminator_end": _hex(next_end),
            },
        },
        "native_formula_provenance": {
            "executor": "AAOLFLMHBEK.OnTaskBegin M507657 RVA 0xB3F43C0",
            "setup": "RPG.GameCore.AbilityStatic.SetupHealData M504574 RVA 0xE468390",
            "formula": "RPG.GameCore.AbilityStatic.HealFormula M504575 RVA 0xE468720",
            "formula_type_4_base": "target.MaxHP(property 1) - target.CurrentHP(property 10)",
            "ordinary_multiplier_properties": [
                "healer.HealRatio (property 124)",
                "target.HealTakenRatio (property 127)",
            ],
            "special_healer_properties": [
                "ExtraHealAddedRatio (property 179)",
                "ExtraHealBase (property 208)",
                "ExtraHealConvert (property 220)",
            ],
            "fixedpoint_constants": {"one_raw": "0x200000000", "hundred_raw": "0xC800000000"},
        },
        "bounded_external_dependencies": [
            "BySkillPointActivated runtime-context evaluation",
            "DynamicFloat opcode and hashed-operand evaluation",
            "TargetConfig discriminator 12 runtime selector join",
            "positive HealData event consumer and CurrentHP mutation",
        ],
        "claims_not_made": [
            "the trigger_key value is a SkillPoint count",
            "DynamicFloat int32 operands are literal numeric amounts",
            "the HealHP executor directly mutates CurrentHP",
            "the positive-heal event consumer is equivalent to DirectChangeHP mode 1",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--container", required=True, type=Path)
    parser.add_argument("--task-registry", required=True, type=Path)
    parser.add_argument("--predicate-registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = extract(
        args.archive,
        args.container,
        args.task_registry,
        args.predicate_registry,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} status={result['status']} "
        f"heal={result['recovered_subtree']['success_tasks'][1]['start']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
