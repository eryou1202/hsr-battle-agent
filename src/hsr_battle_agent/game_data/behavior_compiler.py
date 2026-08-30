"""Offline compiler from canonical BehaviorRecord into source-independent IR.

The compiler is intentionally strict: a captured source operation is only
compiled when its semantic status and headless gating rule permit it.  Other
nodes become attributable diagnostics, never hidden runtime fallbacks.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .nanoka_content import stable_hash
from .modifier_catalog import ModifierDefinition, modifier_catalog_from_corpus


class BehaviorCompileError(ValueError):
    """A canonical behavior record cannot form a sound IR graph."""


PRIMITIVE_BINDINGS: Mapping[str, Mapping[str, Any]] = {
    # These bindings have an independently tested reference executor.  This
    # is deliberately narrower than a production runtime: an operation only
    # becomes executable when *every* behavior-affecting node in its record
    # has an executable-reference binding (or is safe headless presentation).
    "HEAL_REQUEST": {"packet": "dynamic_mvp_v1:HEAL_STATE_TRANSITION", "execution_scope": "EXECUTABLE_REFERENCE"},
    "MODIFY_TEAM_SP": {"packet": "dynamic_mvp_v1:SP_CORE", "execution_scope": "EXECUTABLE_REFERENCE"},
    "INVOKE_BEHAVIOR": {"packet": "KERNEL-EVENT-001", "execution_scope": "STRUCTURAL_CALL_ONLY"},
    "ADD_MODIFIER": {"packet": "PRIM-MODIFIER-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "REMOVE_MODIFIER": {"packet": "PRIM-MODIFIER-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "MODIFY_PROPERTY_STACK": {"packet": "PROPERTY-CONTRIBUTION-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "MODIFY_DAMAGE_DATA": {"packet": "PRIM-DAMAGE-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_HEAL_DATA": {"packet": "PRIM-DAMAGE-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "DISPEL_STATUS": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "CONDITIONAL": {"packet": "COMPILER-PREDICATE-001-SEMANTICS", "execution_scope": "EXECUTABLE_REFERENCE"},
    "PREDICATE": {"packet": "COMPILER-PREDICATE-001-SEMANTICS", "execution_scope": "EXECUTABLE_REFERENCE"},
    "SET_DYNAMIC_VALUE": {"packet": "DYNAMIC-VALUE-SEMANTICS-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "DEFINE_DYNAMIC_VALUE": {"packet": "DYNAMIC-VALUE-SEMANTICS-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "DAMAGE_REQUEST": {"packet": "PRIM-DAMAGE-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "DAMAGE_COMPLETION_MARKER": {"packet": "SCHEDULER-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "RETARGET": {"packet": "TARGET-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "TARGET_FILTER": {"packet": "TARGET-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "FORMATION_CHANGE": {"packet": "TARGET-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "INSERT_ACTION": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "DELAY_ACTION": {"packet": "SCHEDULER-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "MODIFY_ACTION_STATE": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_ACTION_COST": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "ACTION_START_MARKER": {"packet": "SCHEDULER-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "ACTION_COMPLETION_MARKER": {"packet": "SCHEDULER-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "INCLUDE_TASK_TEMPLATE": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "LOOP": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "CONDITIONAL_LOOP": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "PROJECTILE_DISPATCH": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "SWITCH_CASE": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "CHARM_USE_SKILL": {"packet": "SCHEDULER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "GRANT_ABILITY": {"packet": "KERNEL-ACTION-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "SET_MODIFIER_VALUE": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_MODIFIER_FLAG": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_SKILL_PROPERTY": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_SKILL_TREE_LEVEL": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "ADD_STAGE_BUFF": {"packet": "PRIM-MODIFIER-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_TOUGHNESS": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_WEAKNESS": {"packet": "TOUGHNESS-BREAK-001", "execution_scope": "EXECUTABLE_REFERENCE"},
    "TRIGGER_BREAK": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "RESET_TOUGHNESS": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "SET_RESILIENCE": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "INIT_SHIELD": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "REMOVE_SHIELD": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "LOCK_HP": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "FORCE_KILL": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "DEATH_HANDLER": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_TEAM_HP": {"packet": "PRIM-SURVIVAL-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "REGISTER_STAGE_EVENTS": {"packet": "KERNEL-EVENT-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "CREATE_STAGE_EVENT": {"packet": "KERNEL-EVENT-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "MODIFY_SPECIAL_RESOURCE": {"packet": "KERNEL-RESOURCE-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "RANDOM_SELECTION": {"packet": "KERNEL-RNG-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
    "SET_DYNAMIC_ENTITY_PARAM": {"packet": "KERNEL-STATE-001", "execution_scope": "STRUCTURAL_PACKET_ONLY"},
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


class BehaviorCompiler:
    """Compile only canonical IR; raw external payload is never consulted."""

    def __init__(self, modifier_catalog: Mapping[str, ModifierDefinition] | None = None) -> None:
        self._modifier_catalog = dict(modifier_catalog or {})

    def compile_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        entrypoints: list[dict[str, Any]] = []
        templates: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        structural_only = False
        source_operation_count = 0
        for entrypoint in record.get("entrypoints", []):
            entry = _mapping(entrypoint)
            source_operation_count += len(entry.get("operations", []))
            operations, entry_diagnostics, entry_structural = self._compile_operations(entry.get("operations", []))
            diagnostics.extend(entry_diagnostics)
            structural_only = structural_only or entry_structural
            entrypoints.append({
                "event": entry.get("event"),
                "source_event": entry.get("source_event"),
                "callback_metadata": entry.get("callback_metadata"),
                "operations": operations,
                "execution_blockers": entry_diagnostics,
                "executable_reference": bool(entry.get("operations")) and not entry_diagnostics and not entry_structural,
            })
        for template in record.get("template_definitions", []):
            raw_template = _mapping(template)
            source_operation_count += len(raw_template.get("operations", []))
            operations, template_diagnostics, template_structural = self._compile_operations(raw_template.get("operations", []))
            diagnostics.extend(template_diagnostics)
            structural_only = structural_only or template_structural
            templates.append({
                "template_id": raw_template.get("template_id"),
                "name": raw_template.get("name"),
                "source_field_path": raw_template.get("source_field_path"),
                "operations": operations,
                "execution_blockers": template_diagnostics,
                "executable_reference": bool(raw_template.get("operations")) and not template_diagnostics and not template_structural,
            })
        if source_operation_count == 0:
            compiled = {
                "schema": "hsr_battle_agent.behavior_ir/1",
                "game_version": "4.4.54",
                "behavior_id": record.get("behavior_id"),
                "owner_kind": record.get("owner_kind"),
                "owner_ref": record.get("owner_ref"),
                "source_refs": record.get("source_refs", []),
                "entrypoints": entrypoints,
                "template_definitions": templates,
                "dynamic_value_definitions": list(record.get("dynamic_value_definitions", [])),
                "compile_status": "STATIC_DEFINITION_ONLY",
                "behavior_bearing": False,
                "executable": False,
                "execution_blockers": [],
                "structural_only": False,
            }
            compiled["ir_sha256"] = stable_hash(compiled)
            return compiled
        compiled = {
            "schema": "hsr_battle_agent.behavior_ir/1",
            "game_version": "4.4.54",
            "behavior_id": record.get("behavior_id"),
            "owner_kind": record.get("owner_kind"),
            "owner_ref": record.get("owner_ref"),
            "source_refs": record.get("source_refs", []),
            "entrypoints": entrypoints,
            "template_definitions": templates,
            "dynamic_value_definitions": list(record.get("dynamic_value_definitions", [])),
            "compile_status": (
                "EXECUTABLE_REFERENCE"
                if not diagnostics and not structural_only
                else "COMPILED_STRUCTURE_ONLY" if not diagnostics else "REJECTED"
            ),
            "behavior_bearing": True,
            "executable": not diagnostics and not structural_only,
            "execution_blockers": diagnostics,
            "structural_only": structural_only,
        }
        compiled["ir_sha256"] = stable_hash(compiled)
        return compiled

    def _compile_operations(self, values: Iterable[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        operations: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        structural_only = False
        for raw in values:
            operation = _mapping(raw)
            operation_id = str(operation.get("operation_id", "UNKNOWN_OPERATION"))
            status = str(operation.get("semantic_status", "OPAQUE"))
            risk = str(operation.get("gating_risk", "UNKNOWN"))
            kind = str(operation.get("kind", "OPAQUE"))
            reference_payload_problem = None
            if status == "PRESENTATION" and risk == "NONE":
                disposition = "HEADLESS_PRESENTATION_OMITTED"
                binding = None
            elif status in {"MODELLED", "REQUIRES_PACKET"}:
                binding = PRIMITIVE_BINDINGS.get(kind)
                if binding is None:
                    diagnostics.append(self._diagnostic(operation, "REQUIRES_PACKET_HAS_NO_COMPILER_BINDING" if status == "REQUIRES_PACKET" else "MODELLED_TYPE_HAS_NO_COMPILER_BINDING"))
                    continue
                reference_payload_problem = (
                    self._reference_payload_problem(operation)
                    if binding["execution_scope"] == "EXECUTABLE_REFERENCE"
                    else None
                )
                if binding["execution_scope"] == "EXECUTABLE_REFERENCE" and reference_payload_problem is None:
                    disposition = "EXECUTABLE_REFERENCE"
                else:
                    disposition = "BOUND_UNEXECUTABLE_PACKET" if status == "REQUIRES_PACKET" else "BOUND_PRIMITIVE"
                structural_only = structural_only or binding["execution_scope"] in {"STRUCTURAL_CALL_ONLY", "STRUCTURAL_PACKET_ONLY"} or reference_payload_problem is not None
            else:
                diagnostics.append(self._diagnostic(operation, "BEHAVIOR_AFFECTING_NODE_NOT_COMPILED"))
                continue
            children, child_diagnostics, child_structural = self._compile_children(operation)
            diagnostics.extend(child_diagnostics)
            structural_only = structural_only or child_structural
            operations.append({
                "operation_id": operation_id,
                "kind": kind,
                "source_type": operation.get("source_type"),
                "semantic_status": status,
                "node_role": operation.get("node_role"),
                "target": operation.get("target"),
                "arguments": operation.get("arguments"),
                "state_reads": operation.get("state_reads"),
                "state_writes": operation.get("state_writes"),
                "event_boundary": operation.get("event_boundary"),
                "dependencies": list(operation.get("dependencies", [])) + ([binding["packet"]] if binding else []),
                "disposition": disposition,
                "reference_execution_blocker": reference_payload_problem,
                "children": children,
                "source_operation_id": operation_id,
            })
        return operations, diagnostics, structural_only

    def _reference_payload_problem(self, operation: Mapping[str, Any]) -> str | None:
        """Reject an underspecified executable-reference operation early.

        The bridge deliberately does not turn a nominally known operation
        type into executable coverage unless the canonical payload contains
        the inputs required by the selected semantic adapter.
        """
        kind = str(operation.get("kind", ""))
        arguments = _mapping(operation.get("arguments"))
        if kind == "HEAL_REQUEST":
            formula = str(arguments.get("FormulaType", ""))
            if formula not in {"HealByHealerMaxHP", "HealByTargetMaxHP"}:
                return "EXECUTABLE_REFERENCE_UNSUPPORTED_HEAL_FORMULA"
            if not isinstance(arguments.get("HealPercentage"), Mapping) or not isinstance(arguments.get("ModifyValue"), Mapping):
                return "EXECUTABLE_REFERENCE_HEAL_VALUE_MISSING"
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
        elif kind == "MODIFY_PROPERTY_STACK":
            if not arguments.get("Property") or not isinstance(arguments.get("PropertyValue"), Mapping):
                return "EXECUTABLE_REFERENCE_PROPERTY_VALUE_MISSING"
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
        elif kind == "CONDITIONAL":
            if not isinstance(arguments.get("Predicate"), Mapping):
                return "EXECUTABLE_REFERENCE_PREDICATE_MISSING"
        elif kind == "PREDICATE":
            if not str(operation.get("source_type", "")).startswith("RPG.GameCore.By"):
                return "EXECUTABLE_REFERENCE_PREDICATE_TYPE_MISSING"
        elif kind == "SET_DYNAMIC_VALUE":
            source_type = str(operation.get("source_type", ""))
            if source_type == "RPG.GameCore.SetModifierDynamicValue":
                if set(arguments) != {"DynamicKey", "ModifierName", "NewValue"}:
                    return "EXECUTABLE_REFERENCE_SET_MODIFIER_DYNAMIC_ARGUMENTS_UNSUPPORTED"
                if operation.get("target") is not None:
                    return "EXECUTABLE_REFERENCE_SET_MODIFIER_DYNAMIC_TARGET_UNSUPPORTED"
                modifier = _mapping(arguments.get("ModifierName"))
                name = modifier.get("Value")
                if not isinstance(name, str) or not name:
                    return "EXECUTABLE_REFERENCE_SET_MODIFIER_DYNAMIC_NAME_MISSING"
                dynamic_key = arguments.get("DynamicKey")
                if not (isinstance(dynamic_key, str) and dynamic_key) and not (isinstance(dynamic_key, Mapping) and isinstance(dynamic_key.get("Value"), str) and dynamic_key.get("Value")):
                    return "EXECUTABLE_REFERENCE_DYNAMIC_KEY_MISSING"
                if not isinstance(arguments.get("NewValue"), Mapping):
                    return "EXECUTABLE_REFERENCE_SET_MODIFIER_DYNAMIC_VALUE_MISSING"
            elif source_type == "RPG.GameCore.SetDynamicValueByModifierValue":
                allowed = {"DynamicKey", "ReadTargetType", "ValueType", "Multiplier", "ContextScope"}
                if not set(arguments).issubset(allowed):
                    return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_ARGUMENTS_UNSUPPORTED"
                if set(arguments) == {"DynamicKey", "ValueType", "Multiplier"}:
                    if operation.get("target") is not None:
                        return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_TARGET_UNSUPPORTED"
                    if arguments.get("ValueType") != "Layer":
                        return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_TYPE_UNSUPPORTED"
                    if not isinstance(arguments.get("Multiplier"), Mapping):
                        return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_MULTIPLIER_MISSING"
                    dynamic_key = arguments.get("DynamicKey")
                    if not (isinstance(dynamic_key, str) and dynamic_key) and not (isinstance(dynamic_key, Mapping) and isinstance(dynamic_key.get("Value"), str) and dynamic_key.get("Value")):
                        return "EXECUTABLE_REFERENCE_DYNAMIC_KEY_MISSING"
                    return None
                read_target = _mapping(arguments.get("ReadTargetType"))
                if read_target.get("Alias") != "ModifierOwnerEntity":
                    return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_TARGET_UNSUPPORTED"
                if arguments.get("ValueType") != "Layer":
                    return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_TYPE_UNSUPPORTED"
                if not isinstance(arguments.get("Multiplier"), Mapping):
                    return "EXECUTABLE_REFERENCE_MODIFIER_VALUE_MULTIPLIER_MISSING"
                try:
                    dynamic_key = arguments.get("DynamicKey")
                    if not (isinstance(dynamic_key, str) and dynamic_key) and not (isinstance(dynamic_key, Mapping) and isinstance(dynamic_key.get("Value"), str) and dynamic_key.get("Value")):
                        return "EXECUTABLE_REFERENCE_DYNAMIC_KEY_MISSING"
                except AttributeError:
                    return "EXECUTABLE_REFERENCE_DYNAMIC_KEY_MISSING"
            elif source_type == "RPG.GameCore.SetDynamicValueByProperty":
                if set(arguments) != {"DynamicKey", "ReadTargetType", "Value"}:
                    return "EXECUTABLE_REFERENCE_PROPERTY_VALUE_ARGUMENTS_UNSUPPORTED"
                read_target = _mapping(arguments.get("ReadTargetType"))
                alias = read_target.get("Alias")
                value_kind = arguments.get("Value")
                if not (
                    (alias == "ModifierOwnerEntity" and value_kind == "MaxHP")
                    or (alias in {"ParamEntity", "ParamEntity2", "SnapshotPropertyEntity"} and value_kind == "Attack")
                    or (alias in {"Caster", "SnapshotPropertyEntity"} and value_kind == "BreakDamageAddedRatio")
                    or (alias == "Caster" and value_kind == "StatusProbabilityBase")
                ):
                    return "EXECUTABLE_REFERENCE_PROPERTY_VALUE_TARGET_UNSUPPORTED" if value_kind == "Attack" else "EXECUTABLE_REFERENCE_PROPERTY_VALUE_TYPE_UNSUPPORTED"
                if value_kind not in {"MaxHP", "Attack", "BreakDamageAddedRatio", "StatusProbabilityBase"}:
                    return "EXECUTABLE_REFERENCE_PROPERTY_VALUE_TYPE_UNSUPPORTED"
                dynamic_key = arguments.get("DynamicKey")
                if not (isinstance(dynamic_key, str) and dynamic_key) and not (isinstance(dynamic_key, Mapping) and isinstance(dynamic_key.get("Value"), str) and dynamic_key.get("Value")):
                    return "EXECUTABLE_REFERENCE_DYNAMIC_KEY_MISSING"
            elif not isinstance(arguments.get("DynamicKey"), Mapping) or not isinstance(arguments.get("Value"), Mapping):
                return "EXECUTABLE_REFERENCE_DYNAMIC_VALUE_MISSING"
        elif kind == "DEFINE_DYNAMIC_VALUE":
            if not isinstance(arguments.get("DynamicKey"), Mapping):
                return "EXECUTABLE_REFERENCE_DYNAMIC_KEY_MISSING"
        elif kind == "ADD_MODIFIER":
            modifier = _mapping(arguments.get("ModifierName"))
            name = modifier.get("Value")
            if not isinstance(name, str) or not name:
                return "EXECUTABLE_REFERENCE_MODIFIER_NAME_MISSING"
            allowed_argument_sets = ({"ModifierName"}, {"ModifierName", "DynamicValues"})
            if set(arguments) == {"ModifierName", "AliveOnly"}:
                if arguments.get("AliveOnly") is not False:
                    return "EXECUTABLE_REFERENCE_ADD_MODIFIER_ALIVE_ONLY_UNSUPPORTED"
            elif set(arguments) not in allowed_argument_sets:
                return "EXECUTABLE_REFERENCE_ADD_MODIFIER_ARGUMENTS_UNSUPPORTED"
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
            if name not in self._modifier_catalog:
                return "EXECUTABLE_REFERENCE_MODIFIER_DEFINITION_UNRESOLVED"
            dynamic_values = arguments.get("DynamicValues")
            if dynamic_values is not None and (
                not isinstance(dynamic_values, Mapping)
                or not dynamic_values
                or not all(isinstance(key, str) and key and isinstance(value, Mapping) for key, value in dynamic_values.items())
            ):
                return "EXECUTABLE_REFERENCE_MODIFIER_DYNAMIC_VALUES_UNSUPPORTED"
        elif kind == "REMOVE_MODIFIER":
            source_type = str(operation.get("source_type", ""))
            if source_type == "RPG.GameCore.RemoveSelfModifier":
                if arguments:
                    return "EXECUTABLE_REFERENCE_REMOVE_SELF_ARGUMENTS_UNSUPPORTED"
                if operation.get("target") is not None:
                    return "EXECUTABLE_REFERENCE_REMOVE_SELF_TARGET_UNSUPPORTED"
            else:
                modifier = _mapping(arguments.get("ModifierName"))
                name = modifier.get("Value")
                if not isinstance(name, str) or not name:
                    return "EXECUTABLE_REFERENCE_MODIFIER_NAME_MISSING"
                if set(arguments) != {"ModifierName"}:
                    return "EXECUTABLE_REFERENCE_REMOVE_MODIFIER_ARGUMENTS_UNSUPPORTED"
                if not isinstance(operation.get("target"), Mapping):
                    return "EXECUTABLE_REFERENCE_TARGET_MISSING"
        elif kind == "DAMAGE_REQUEST":
            attack = _mapping(arguments.get("AttackProperty"))
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
            if not isinstance(attack.get("DamagePercentage"), Mapping):
                return "EXECUTABLE_REFERENCE_DAMAGE_PERCENTAGE_MISSING"
            # A TargetDamage payload can combine ordinary HP damage with
            # stance/toughness damage, DoT, inheritance and direct-value
            # paths.  The selected adapter supports the ordinary HP component
            # and an explicit StanceValue transition together.  Other mixed
            # paths remain rejected: dropping a state-affecting sibling would
            # turn an incomplete transition into false executable coverage.
            attack_type = attack.get("AttackType")
            if attack_type not in {None, "", "Normal", "DOT"}:
                return "EXECUTABLE_REFERENCE_DAMAGE_ATTACK_TYPE_UNSUPPORTED"
            if "DamageValue" in attack or "BreakDamagePercentage" in attack:
                return "EXECUTABLE_REFERENCE_DAMAGE_FORMULA_UNSUPPORTED"
            formula = str(attack.get("FormulaType") or "ByAttack")
            if formula not in {"ByAttack", "ByMaxHP", "ByDefence"}:
                return "EXECUTABLE_REFERENCE_DAMAGE_FORMULA_UNSUPPORTED"
            has_stance = "StanceValue" in attack or "StanceDamageType" in attack
            if attack_type == "DOT" and has_stance:
                return "EXECUTABLE_REFERENCE_DOT_MIXED_STATE_FIELDS"
            if has_stance and not isinstance(attack.get("StanceValue"), Mapping):
                return "EXECUTABLE_REFERENCE_STANCE_VALUE_MISSING"
            allowed_attack_fields = {
                "$type", "AttackType", "DamagePercentage", "DamageType", "FormulaType",
                # These fields only describe a visual presentation and do
                # not alter the selected normal HP calculation.
                "HitAnimation", "HitEffect", "HitAngleVertical", "HitEffectHeight",
                "HitPosHeight", "HitTimeSlowIntensity",
                # Stance is a second state transition, executed only through
                # the explicit per-target toughness context at runtime.
                "StanceValue", "StanceDamageType", "HitTimeSlowType",
            }
            if any(key not in allowed_attack_fields for key in attack):
                return "EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS"
            if any(key not in {"AttackProperty", "DisplayData", "CanTriggerLastKill", "SpecialHitSoundEvent"} for key in arguments):
                return "EXECUTABLE_REFERENCE_DAMAGE_ARGUMENTS_UNSUPPORTED"
        elif kind == "MODIFY_WEAKNESS":
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
            weak_list = arguments.get("WeakList")
            if arguments.get("OPType") != "Attach" or not isinstance(weak_list, list) or not weak_list or not all(isinstance(item, str) and item for item in weak_list):
                return "EXECUTABLE_REFERENCE_WEAKNESS_PAYLOAD_UNSUPPORTED"
            if set(arguments) != {"OPType", "WeakList"}:
                return "EXECUTABLE_REFERENCE_WEAKNESS_ARGUMENTS_UNSUPPORTED"
        elif kind == "MODIFY_TEAM_SP":
            # ModifySPNew changes the shared BP/skill-point holder, not an
            # entity-local resource.  The ordinary-MVP packet supports only
            # one positive post-commit contribution at a time.  A dynamic
            # expression is acceptable here because the reference executor
            # resolves it through the same unified DynamicValue context used
            # by the other executable primitives.
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
            if set(arguments) not in ({"AddRatio"}, {"AddValue"}):
                return "EXECUTABLE_REFERENCE_TEAM_SP_ARGUMENTS_UNSUPPORTED"
            value = arguments.get("AddRatio", arguments.get("AddValue"))
            if not isinstance(value, Mapping):
                return "EXECUTABLE_REFERENCE_TEAM_SP_VALUE_MISSING"
        elif kind == "DELAY_ACTION":
            if str(operation.get("source_type", "")) != "RPG.GameCore.ModifyActionDelay":
                return "EXECUTABLE_REFERENCE_ACTION_DELAY_TYPE_UNSUPPORTED"
            if set(arguments) != {"AddNormalizedValue"}:
                return "EXECUTABLE_REFERENCE_ACTION_DELAY_ARGUMENTS_UNSUPPORTED"
            if not isinstance(operation.get("target"), Mapping):
                return "EXECUTABLE_REFERENCE_TARGET_MISSING"
            value = _mapping(arguments.get("AddNormalizedValue"))
            if value.get("IsDynamic") is not False or not isinstance(_mapping(value.get("FixedValue")).get("Value"), (int, float)):
                return "EXECUTABLE_REFERENCE_ACTION_DELAY_DYNAMIC_VALUE_UNSUPPORTED"
        elif kind == "ACTION_COMPLETION_MARKER":
            if str(operation.get("source_type", "")) != "RPG.GameCore.SkillPerformFinish":
                return "EXECUTABLE_REFERENCE_ACTION_COMPLETION_TYPE_UNSUPPORTED"
            if arguments:
                return "EXECUTABLE_REFERENCE_ACTION_COMPLETION_ARGUMENTS_UNSUPPORTED"
            if operation.get("target") is not None:
                return "EXECUTABLE_REFERENCE_ACTION_COMPLETION_TARGET_UNSUPPORTED"
        elif kind == "DAMAGE_COMPLETION_MARKER":
            if str(operation.get("source_type", "")) != "RPG.GameCore.DamagePerformFinish":
                return "EXECUTABLE_REFERENCE_DAMAGE_COMPLETION_TYPE_UNSUPPORTED"
            if arguments:
                return "EXECUTABLE_REFERENCE_DAMAGE_COMPLETION_ARGUMENTS_UNSUPPORTED"
            if operation.get("target") is not None:
                return "EXECUTABLE_REFERENCE_DAMAGE_COMPLETION_TARGET_UNSUPPORTED"
        elif kind == "ACTION_START_MARKER":
            if str(operation.get("source_type", "")) != "RPG.GameCore.SkillExecutionStart":
                return "EXECUTABLE_REFERENCE_ACTION_START_TYPE_UNSUPPORTED"
            if arguments:
                return "EXECUTABLE_REFERENCE_ACTION_START_ARGUMENTS_UNSUPPORTED"
            if operation.get("target") is not None:
                return "EXECUTABLE_REFERENCE_ACTION_START_TARGET_UNSUPPORTED"
        return None

    def _compile_children(self, operation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        groups: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        structural_only = False
        for raw_group in operation.get("children", []):
            group = _mapping(raw_group)
            children, child_diagnostics, child_structural = self._compile_operations(group.get("operations", []))
            groups.append({"group_id": group.get("group_id"), "field_path": group.get("field_path"), "operations": children})
            diagnostics.extend(child_diagnostics)
            structural_only = structural_only or child_structural
        return groups, diagnostics, structural_only

    @staticmethod
    def _diagnostic(operation: Mapping[str, Any], reason: str) -> dict[str, Any]:
        return {
            "operation_id": operation.get("operation_id"),
            "source_type": operation.get("source_type"),
            "kind": operation.get("kind"),
            "semantic_status": operation.get("semantic_status"),
            "semantic_importance": operation.get("semantic_importance"),
            "gating_risk": operation.get("gating_risk"),
            "reason": reason,
            "policy": "REJECT_NOT_NOOP",
        }

    def compile_corpus(self, corpus: Mapping[str, Any]) -> dict[str, Any]:
        previous_catalog = self._modifier_catalog
        if not self._modifier_catalog:
            self._modifier_catalog = modifier_catalog_from_corpus(corpus)
        try:
            compiled = [self.compile_record(record) for record in corpus.get("records", [])]
        finally:
            self._modifier_catalog = previous_catalog
        compiled.sort(key=lambda record: str(record["behavior_id"]))
        successful = [record for record in compiled if record["compile_status"] == "COMPILED_STRUCTURE_ONLY"]
        executable = [record for record in compiled if record["compile_status"] == "EXECUTABLE_REFERENCE"]
        behavior_bearing = [record for record in compiled if record.get("behavior_bearing")]
        static_only = [record for record in compiled if record["compile_status"] == "STATIC_DEFINITION_ONLY"]
        failure_reasons = Counter(diagnostic["reason"] for record in compiled for diagnostic in record["execution_blockers"])
        operation_statuses: Counter[str] = Counter()
        operation_dispositions: Counter[str] = Counter()
        executable_entrypoints = 0
        for record in compiled:
            for operation in self._walk_compiled_operations(record):
                operation_statuses[str(operation.get("semantic_status", "OPAQUE"))] += 1
                operation_dispositions[str(operation.get("disposition", "UNBOUND"))] += 1
            executable_entrypoints += sum(bool(entrypoint.get("executable_reference")) for entrypoint in record.get("entrypoints", []))
            executable_entrypoints += sum(bool(template.get("executable_reference")) for template in record.get("template_definitions", []))
        by_owner = {}
        for owner in sorted({str(record["owner_kind"]) for record in compiled}):
            owner_records = [record for record in compiled if record["owner_kind"] == owner]
            by_owner[owner] = {
                "captured": len(owner_records),
                "behavior_bearing": sum(bool(record.get("behavior_bearing")) for record in owner_records),
                "static_definition_only": sum(record["compile_status"] == "STATIC_DEFINITION_ONLY" for record in owner_records),
                "structural_compiled": sum(record["compile_status"] == "COMPILED_STRUCTURE_ONLY" for record in owner_records),
                "executable_reference": sum(record["compile_status"] == "EXECUTABLE_REFERENCE" for record in owner_records),
                "golden_tested": 0,
            }
        result = {
            "schema": "hsr_battle_agent.behavior_compiler_report/1",
            "game_version": corpus.get("game_version"),
            "input_corpus_sha256": corpus.get("corpus_sha256"),
            "compiler_policy": "canonical-only strict compiler; behavior-affecting uncompiled nodes reject the record and never become no-ops; records without operational entrypoints/templates are STATIC_DEFINITION_ONLY and are not part of the behavior denominator",
            "records": compiled,
            "coverage": {
                "captured": len(compiled),
                "canonicalized": len(compiled),
                "behavior_bearing": len(behavior_bearing),
                "static_definition_only": len(static_only),
                "structural_compiled": len(successful),
                "executable": len(executable),
                "golden_tested": 0,
                "by_owner_kind": by_owner,
                "failure_reasons": dict(sorted(failure_reasons.items())),
                "operation_level": {
                    "source_semantic_status": dict(sorted(operation_statuses.items())),
                    "compiled_disposition": dict(sorted(operation_dispositions.items())),
                    "executable_bound": operation_dispositions["EXECUTABLE_REFERENCE"],
                    "executable_entrypoints": executable_entrypoints,
                },
            },
        }
        result["report_sha256"] = stable_hash(result)
        return result

    @staticmethod
    def _walk_compiled_operations(record: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
        def walk(operations: Iterable[Any]) -> Iterable[Mapping[str, Any]]:
            for operation in operations:
                if not isinstance(operation, Mapping):
                    continue
                yield operation
                for group in operation.get("children", []):
                    if isinstance(group, Mapping):
                        yield from walk(group.get("operations", []))

        for entrypoint in record.get("entrypoints", []):
            if isinstance(entrypoint, Mapping):
                yield from walk(entrypoint.get("operations", []))
        for template in record.get("template_definitions", []):
            if isinstance(template, Mapping):
                yield from walk(template.get("operations", []))
