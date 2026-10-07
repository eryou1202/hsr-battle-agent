"""Decoded records -> Behavior IR. No scenario assembly or content-ID dispatch."""
from __future__ import annotations

from dataclasses import replace

from .behavior import (AbilityIR, Authority, ExpressionIR, PredicateIR, TaskIR,
    TaskSequenceIR, TargetSelectorIR, UnsupportedSemanticIR, stable_hash)


# Identity-based mappings are shared by compiler/census. Availability is not admission.
TASK_MAPPINGS = {
    "TriggerAbility": ("invoke", "REFERENCE_SEMANTICS_AVAILABLE", "ORACLE_PENDING"),
    "PredicateTaskList": ("branch", "REFERENCE_SEMANTICS_AVAILABLE", "ORACLE_PENDING"),
    "TriggerAnimState": ("animation", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "MoveToTargetPosition": ("movement", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "WaitAnimState": ("wait", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "TriggerEffect": ("effect", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "DispelStatus": ("dispel", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "HealHP": ("heal", "REFERENCE_SEMANTICS_AVAILABLE", "ORACLE_PENDING"),
    "SetDynamicValue": ("dynamic_write", "REFERENCE_SEMANTICS_AVAILABLE", "ORACLE_PENDING"),
    "AddModifier": ("modifier_apply", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "ModifySPNew": ("actor_resource", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "Retarget": ("retarget", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "CharacterPlayVO": ("voice", "STRUCTURE_ONLY", "ORACLE_PENDING"),
    "SkillPerformFinish": ("finish", "STRUCTURE_ONLY", "ORACLE_PENDING"),
}


class BehaviorCompiler:
    """Accepts decoded field/list records plus a source authority and primitive ledger.

    Graph envelope discovery uses task_list shape, not phase/ability/character names.
    All unknown records remain lossless blockers. Native overrides are never inferred.
    """

    def __init__(self, authority: Authority, ledger: dict, decoded_family_bindings: dict[str, str] | None = None):
        self.authority = authority
        self.ledger = ledger
        self.semantic_gaps: dict[str, dict] = {}
        self.decoded_family_bindings = dict(decoded_family_bindings or {})
        self.by_type: dict[str, list[dict]] = {}
        for entry in ledger["primitives"]:
            if entry.get("config_type"):
                self.by_type.setdefault(entry["config_type"], []).append(entry)

    def normalize_record(self, record: dict) -> dict | None:
        """Normalize reader/factory chains through caller-supplied decoder type roles.

        Some archives label concrete fields only by bitmap. Those fields stay
        unbound; normalization proves representation, never executable meanings.
        """
        if record.get("kind") in {"TaskConfig", "PredicateConfig", "TargetSelector"}:
            return record
        config_type = record.get("type")
        family = self.decoded_family_bindings.get(config_type) if isinstance(config_type, str) else None
        if family is None or "reader" not in record or "child" not in record:
            return None
        concrete = record
        while isinstance(concrete.get("child"), dict):
            concrete = concrete["child"]
        identity = concrete.get("type")
        if not isinstance(identity, str) or not identity.startswith("RPG.GameCore."):
            return None
        kinds = {"task": "TaskConfig", "predicate": "PredicateConfig", "target": "TargetSelector"}
        return {"kind": kinds[family], "concrete_type": identity, "structure": concrete,
                "start": concrete.get("start"), "end": concrete.get("end"),
                "discriminator": record.get("discriminator"), "reader_method": {"rva": concrete.get("reader")}}

    def record_gap(self, node, capability):
        key = node.stable_hash()
        entry = self.semantic_gaps.setdefault(key, {
            "primitive": node.op, "node": node.node_id,
            "content_source": node.authority.source_artifact,
            "frequency": 0, "blocking": True, "compilation_blocking": False,
            "evidence_status": node.authority.to_dict(), "required_capability": capability,
            "recommended_next_implementation": f"Implement {capability} generically",
            "observation_stage": "COMPILATION"})
        entry["frequency"] += 1
        return node

    def evidence(self, config_type: str, pointer: str, record: dict) -> Authority:
        entries = self.by_type.get(config_type, [])
        refs = {r for e in entries for r in e.get("selected_method_refs", [])}
        if isinstance(record.get("reader_method"), dict) and record["reader_method"].get("rva"):
            refs.add(record["reader_method"]["rva"])
        return replace(self.authority, source_pointer=pointer,
                       native_method_refs=tuple(sorted(refs)),
                       ledger_refs=tuple(sorted(e["id"] for e in entries)))

    def compile_graph(self, graph: dict) -> AbilityIR:
        records = [(k, v) for k, v in graph.items()
                   if isinstance(v, dict) and isinstance(v.get("task_list"), dict)
                   and isinstance(v["task_list"].get("tasks"), list)]
        if not records:
            raise ValueError("graph contains no decoded ability task lists")
        # Decoder coordinates define record order. Serialized task order stays intact.
        records.sort(key=lambda kv: (kv[1].get("trusted_start", 0), kv[0]))
        abilities = []
        for key, record in records:
            pointer = "/" + key
            tasks = self.compile_sequence(record["task_list"]["tasks"], pointer + "/task_list/tasks")
            fields = self.fields(record, pointer)
            sequence_fields = [k for k, v in fields.items() if isinstance(v, TaskSequenceIR)]
            fields = {k: v for k, v in fields.items() if k not in sequence_fields}
            abilities.append(AbilityIR(pointer, "ability", self.authority, {
                "content_name": record.get("entry_name"), "tasks": tasks,
                "fields": fields, "serialized_sequence_fields": sequence_fields}))
        return AbilityIR("/", "decoded_graph", self.authority, {"abilities": abilities,
            "ledger_identity": stable_hash(self.ledger), "source_schema": graph.get("schema")})

    def compile_sequence(self, tasks: list, pointer: str) -> TaskSequenceIR:
        return TaskSequenceIR(pointer, "immediate_sequence", self.authority,
            {"tasks": [self.convert(t, f"{pointer}/{i}") for i, t in enumerate(tasks)],
             "ordering_authority": "SERIALIZED_ORDER_ONLY"})

    def fields(self, record: dict, pointer: str) -> dict:
        result = {}
        for i, f in enumerate(record.get("fields", [])):
            name = f.get("field") or f"unbound_bit_{f.get('bit', i)}"
            values = [self.convert(v, f"{pointer}/fields/{i}/values/{j}")
                      for j, v in enumerate(f.get("values", []))]
            result[name] = values[0] if len(values) == 1 else values
        return result

    def dynamic_float(self, value: dict, pointer: str, authority: Authority) -> ExpressionIR:
        def node(op, payload, suffix=""):
            return ExpressionIR(pointer + suffix, op, authority, payload)
        if value.get("tag") == 0:
            try:
                return node("literal", {"raw": int(value["signed_payload"]["decoded_signed"]),
                                        "numeric_policy": "FIXED_MODE0_REFERENCE"})
            except (KeyError, TypeError, ValueError):
                unknown = node("unknown_opcode", {"decoded": value,
                    "required_capability": "decoded DynamicFloat literal operand"})
                return self.record_gap(unknown, "decoded DynamicFloat literal operand")
        tokens = value.get("token_ids", [])
        stack = []
        i = 0
        try:
            while i < len(tokens):
                opcode = tokens[i]
                i += 1
                if opcode in (0, 1):
                    operand = tokens[i]
                    i += 1
                    values = value["int64_operands" if opcode == 0 else "int32_operands"]
                    if operand < 0:
                        raise ValueError("negative operand index")
                    item = values[operand]
                    stack.append(node("literal" if opcode == 0 else "lookup",
                        {"raw": int(item)} if opcode == 0 else {"key": str(item), "scope": "supplied"},
                        f"/token/{i-2}"))
                elif opcode == 2:
                    right, left = stack.pop(), stack.pop()
                    stack.append(node("add", {"args": [left, right]}, f"/token/{i-1}"))
                elif opcode == 17 and i == len(tokens) and len(stack) == 1:
                    return node("identity", {"arg": stack[0], "serialized_program": value})
                else:
                    break
        except (KeyError, IndexError, ValueError, TypeError):
            pass
        unknown = node("unknown_opcode", {"decoded": value,
            "required_capability": "DynamicFloat opcode/stack semantics"})
        return self.record_gap(unknown, "DynamicFloat opcode/stack semantics")

    def convert(self, value: object, pointer: str):
        if isinstance(value, list):
            return [self.convert(v, f"{pointer}/{i}") for i, v in enumerate(value)]
        if not isinstance(value, dict):
            return value
        normalized = self.normalize_record(value)
        if normalized is not None:
            value = normalized
        config_type = value.get("concrete_type") or value.get("type")
        if isinstance(config_type, str):
            authority = self.evidence(config_type, pointer, value)
            short = config_type.rsplit(".", 1)[-1]
            if config_type == "RPG.GameCore.DynamicFloat" and "tag" in value:
                return self.dynamic_float(value, pointer, authority)
            if config_type == "RPG.GameCore.DynamicString" and "fields" in value:
                fields = self.fields(value, pointer)
                if set(fields) == {"Value"} and isinstance(fields["Value"], str):
                    return ExpressionIR(pointer, "literal", authority, {"value": fields["Value"]})
                unknown = ExpressionIR(pointer, "unknown_opcode", authority,
                    {"decoded": value, "required_capability": "dynamic string lookup/evaluation"})
                return self.record_gap(unknown, "dynamic string lookup/evaluation")
            kind = value.get("kind")
            if kind in {"TaskConfig", "PredicateConfig", "TargetSelector"}:
                structure = value.get("structure", {})
                payload = {"task_type": config_type, "fields": self.fields(structure, pointer + "/structure"),
                           "span": [value.get("start"), value.get("end")],
                           "discriminator": value.get("discriminator")}
                payload["field_bindings_status"] = "UNRESOLVED" if any(
                    not f.get("field") for f in structure.get("fields", [])) else "DECODED_FIELD_NAMES"
                if kind == "TaskConfig":
                    mapping = TASK_MAPPINGS.get(short)
                    if mapping:
                        payload["mapping_classification"] = ["IR_SUPPORTED", *mapping[1:]]
                        payload["presentation_relevance"] = "unknown" if short in {
                            "TriggerAnimState", "TriggerEffect", "MoveToTargetPosition", "CharacterPlayVO"} else None
                        return TaskIR(pointer, config_type, authority, payload)
                    payload.update(decoded=value, required_capability=f"task:{config_type}")
                    unknown = UnsupportedSemanticIR(pointer, config_type,
                        replace(authority, semantic_status="UNSUPPORTED"), payload)
                    return self.record_gap(unknown, f"task:{config_type}")
                if kind == "PredicateConfig":
                    return PredicateIR(pointer, config_type, authority, payload)
                if short == "TargetAlias":
                    payload["alias"] = structure.get("value")
                return TargetSelectorIR(pointer, config_type, authority, payload)
        if value.get("kind") == "list" and "children" in value:
            children = value["children"]
            if children and all(isinstance(v, dict) and v.get("kind") == "TaskConfig" for v in children):
                return self.compile_sequence(children, pointer + "/children")
        if value.get("kind") in {"enum", "string", "bool", "int", "float"} and "value" in value:
            return value["value"]
        # Untyped/nested decoded structures stay inspectable; don't pretend they execute.
        return {k: self.convert(v, pointer + "/" + k) for k, v in value.items()}
