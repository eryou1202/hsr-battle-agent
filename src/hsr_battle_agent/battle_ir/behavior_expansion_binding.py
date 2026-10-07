"""R13 structural roles for explicit reference execution, never native field names.

Masks below are decoded reader coordinates. The binding is a REFERENCE_MODEL
interpretation of that exact shape; original anonymous fields remain in payload.
Unknown masks are never assigned meanings from their order.
"""
from __future__ import annotations

from dataclasses import replace

from .behavior import (AbilityIR, ExpressionIR, IRNode, PredicateIR, TaskIR, TaskSequenceIR,
                       TargetSelectorIR, UnsupportedSemanticIR)
from .behavior_binding import BehaviorCompiler, TASK_MAPPINGS


# Each entry documents a structural slot, rather than a recovered native name.
REFERENCE_ROLES = {
    "TargetSequence": {1: "steps"}, "TargetConcat": {1: "selectors"},
    "TargetFilter": {1: "predicate"}, "TargetSortByFormation": {1: "serialized_direction"},
    "TargetSortByActionOrder": {2: "serialized_direction"},
    "TargetIndex": {1: "serialized_index"}, "TargetTake": {1: "count"},
    "TargetQuery": {2: "team_mask", 4: "entity_mask", 8: "alive_mask"},
    "TargetFetchUniqueNameEntity": {1: "name"},
    "ByAnd": {4: "args"}, "ByNot": {4: "arg"},
    "ByCharacterDamageType": {4: "target", 8: "value"},
    "ByTargetTeam": {4: "target", 8: "value"},
    "ByIsContainModifier": {4: "target", 8: "modifier"},
    "ByCompareHP": {4: "target", 8: "serialized_comparison", 16: "value"},
    "ByCompareHPRatio": {4: "target", 8: "serialized_comparison", 16: "value"},
    "ByCompareGridFightProperty": {4: "target", 8: "property", 16: "serialized_comparison", 32: "value"},
    "ByCompareStanceCount": {4: "target", 8: "serialized_comparison", 16: "value"},
    "ByCompareCharacterID": {4: "target", 8: "value"}, "ByIsTeammate": {4: "target"},
    "ByIsBattleEventEntity": {4: "target", 8: "value"},
    "ByTargetAliveState": {4: "target", 8: "value"},
    "ByContainBehaviorFlag": {4: "target", 8: "value"},
    "ByTargetListIntersects": {4: "left", 8: "left_option", 16: "right", 32: "right_option"},
    "IncludeTaskListTemplate": {2: "template", 4: "parameters"},
    "PredicateTaskList": {2: "predicate", 4: "then", 8: "else"},
    "RemoveModifier": {2: "target", 4: "modifier"},
    "StackProperty": {2: "target", 4: "property", 8: "value"},
    "TargetFetchParamEntityByIndex": {1: "index"},
    "AddModifier": {2: "target", 8: "modifier"},
}

EXPANSION_TASK_MAPPINGS = {**TASK_MAPPINGS, **{key: (op, "REFERENCE_SEMANTICS_AVAILABLE", "ORACLE_PENDING")
    for key, op in {"IncludeTaskListTemplate": "template", "RemoveModifier": "modifier_remove",
                    "StackProperty": "property_stack"}.items()}}


class ExpansionCompiler(BehaviorCompiler):
    """Extends R12 lossless representation without changing its binding defaults."""

    def convert(self, value, pointer):
        if isinstance(value, dict) and value.get("kind") == "int32" and "value" in value:
            return int(value["value"])
        if isinstance(value, dict) and value.get("type") == "RPG.GameCore.DynamicString":
            fields = value.get("fields", [])
            if len(fields) == 1 and fields[0].get("mask") == 4:
                values = fields[0].get("values", [])
                if len(values) == 1 and values[0].get("kind") == "string":
                    return ExpressionIR(pointer, "literal", self.evidence(value["type"], pointer, value),
                        {"value": values[0]["value"], "serialized": value,
                         "reference_binding": "explicit serialized string slot"})
        if isinstance(value, dict) and value.get("type") == "RPG.GameCore.DynamicFloat" and "tag" in value:
            operands = value.get("int64_operands", [])
            if any(isinstance(v, dict) for v in operands):
                value = {**value, "int64_operands": [int(v["decoded_signed"]) if isinstance(v, dict) else v for v in operands]}
        node = super().convert(value, pointer)
        if isinstance(value, dict) and value.get("type") == "RPG.GameCore.DynamicFloat" and isinstance(node, ExpressionIR):
            return ExpressionIR(node.node_id, node.op, node.authority,
                                {**node.payload, "serialized_type": value["type"]})
        normalized = self.normalize_record(value) if isinstance(value, dict) else None
        if normalized is None or not isinstance(node, IRNode):
            return node
        short = normalized["concrete_type"].rsplit(".", 1)[-1]
        structure = normalized.get("structure", {})
        payload = node.payload
        roles, unknown = {}, []
        table = REFERENCE_ROLES.get(short, {})
        for i, field in enumerate(structure.get("fields", [])):
            mask = field.get("mask")
            if mask is None and field.get("bit") is not None:
                mask = 1 << field["bit"]
            role = table.get(int(mask)) if mask is not None else None
            if role is None:
                if not field.get("field"):
                    unknown.append({"field_index": i, "mask": mask})
                continue
            key = field.get("field") or f"unbound_bit_{field.get('bit', i)}"
            roles[role] = payload["fields"][key]
        named = payload["fields"]
        if short == "PredicateTaskList":
            roles.update({role: named[key] for key, role in {
                "Predicate": "predicate", "SuccessTaskList": "then", "FailedTaskList": "else"}.items() if key in named})
        payload["reference_binding"] = {"roles": roles, "unknown_slots": unknown,
            "authority": "CONDITIONAL_REFERENCE", "native_field_names_recovered": False,
            "policy_required": "r13_reference_v1"}
        authority = replace(node.authority, semantic_status="CONDITIONAL_REFERENCE")
        cls = type(node)
        if short in EXPANSION_TASK_MAPPINGS and cls is UnsupportedSemanticIR:
            cls = TaskIR
            payload["mapping_classification"] = ["IR_SUPPORTED", *EXPANSION_TASK_MAPPINGS[short][1:]]
        return cls(node.node_id, node.op, authority, payload)

    def compile_record(self, record, pointer, identity=None):
        """Every accepted root, including modifiers/aliases, remains canonical IR."""
        node = self.convert(record, pointer)
        if isinstance(node, IRNode):
            return node
        tasks = []
        # Only a decoded TurnBasedAbilityConfig task-list slot is an entry point.
        if record.get("type") == "RPG.GameCore.TurnBasedAbilityConfig":
            for field in record.get("fields", []):
                if field.get("mask") == 16 or field.get("field") == "TaskList":
                    for value in field.get("values", []):
                        if value.get("kind") == "list":
                            tasks = value["children"]
            sequence = self.compile_sequence(tasks, pointer + "/task_list")
            other_sequences = [field["mask"] for field in record.get("fields", []) if field.get("mask") in (4, 8, 1024)
                and any(v.get("kind") == "list" and v.get("children") for v in field.get("values", []))]
            return AbilityIR(pointer, "ability", self.authority,
                {"content_name": identity, "tasks": sequence, "decoded": node,
                 "reference_unbound_sequences": other_sequences,
                 "reference_root_binding": "TurnBasedAbilityConfig task-list bitmap 16"})
        return AbilityIR(pointer, "structure_record", self.authority,
                         {"content_name": identity, "root_type": record.get("type"), "decoded": node})
