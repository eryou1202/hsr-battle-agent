#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the bounded Modifier property-contribution bridge for 4.4.54.

This is intentionally a *contribution boundary*, not a claim about final stat
materialization.  The native property-domain dispatcher reached by the
component helper is broad and remains outside this batch.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))

from semantic_batch_evidence import (  # noqa: E402
    build_native_evidence,
    iter_records,
    load_manifest,
    load_pe,
)


GAME_VERSION = "4.4.54"
OUT = REPO / "data" / "semantics" / GAME_VERSION / "modifier_property_effect_09.json"
E4 = "E4_STATIC_MACHINE_CODE"

# These are first-successful-ret bounded bodies.  Error/throw continuations
# after that ret are deliberately not mixed into the body hash.  The artifact
# labels this projection explicitly.
CANDIDATES = {
    506081: {"native_rva": 0xB770D00, "body_bytes": 0x41, "abi": "win64"},
    506082: {"native_rva": 0xB770D90, "body_bytes": 0x469, "abi": "win64"},
    506199: {"native_rva": 0xE7851A0, "body_bytes": 0x496, "abi": "win64"},
    506495: {"native_rva": 0xE72EB90, "body_bytes": 0x267, "abi": "win64"},
    506496: {"native_rva": 0xE731B80, "body_bytes": 0x1FB, "abi": "win64"},
    506312: {"native_rva": 0xE78B740, "body_bytes": 0x9B6, "abi": "win64"},
    127753: {"native_rva": 0x1D4C1780, "body_bytes": 0x176, "abi": "win64"},
}


def selected_methods() -> dict[int, dict]:
    wanted = set(CANDIDATES)
    result: dict[int, dict] = {}
    for row in iter_records(REPO / "data" / "normalized" / GAME_VERSION / "methods.json"):
        if row["method_index"] in wanted:
            result[row["method_index"]] = row
    missing = wanted - set(result)
    if missing:
        raise RuntimeError(f"missing normalized method records: {sorted(missing)}")
    return result


def native_evidence(pe, methods: dict[int, dict], method_index: int) -> dict:
    evidence = build_native_evidence(pe, {
        "method_index": method_index,
        **CANDIDATES[method_index],
    }, methods[method_index])
    # Raw evidence belongs in the raw evidence files; keep the semantic
    # artifact machine-readable and compact.
    evidence.pop("disassembly")
    evidence["body_projection"] = "FIRST_SUCCESSFUL_RET"
    return evidence


def primitive(pe, methods: dict[int, dict], method_index: int, **plan) -> dict:
    method = methods[method_index]
    evidence = native_evidence(pe, methods, method_index)
    return {
        "primitive_id": plan.pop("primitive_id"),
        "semantic_name": plan.pop("semantic_name"),
        "evidence_level": E4,
        "determinism": plan.pop("determinism", "DETERMINISTIC"),
        "source_runtime_type": plan.pop("source_runtime_type"),
        "source_method": method["name"],
        "source_method_index": method_index,
        "source_native_rva": evidence["body_rva"],
        "native_body_hash": evidence["body_sha256"],
        "source_identity": {
            "method_index": method_index,
            "declaring_type_index": method["declaring_type_index"],
            "method_name": method["name"],
            "mapping_kind": method["mapping_kind"],
        },
        "native_evidence": evidence,
        **plan,
    }


def build() -> dict:
    pe = load_pe()
    manifest = load_manifest()
    methods = selected_methods()

    serializer = native_evidence(pe, methods, 127753)
    primitives = [
        primitive(
            pe, methods, 506081,
            primitive_id="battle.ir.task.stack_property_executor_init",
            semantic_name="StackPropertyTaskExecutorInit",
            source_runtime_type="LEIHMEGJNME",
            inputs=[
                {"name": "task_context", "type": "task_context_ref"},
                {"name": "task_config", "type": "stack_property_config_ref"},
            ],
            output="stack_property_executor",
            field_reads=[],
            field_writes=[
                "executor[+0x18] = task_context",
                "executor[+0x20] = task_config",
                "executor[+0x10] = 0x7777 task kind marker",
            ],
            context_reads=[],
            context_writes=[],
            persistent_reads=[],
            persistent_writes=[],
            branches=["null executor/context -> IL2CPP throw paths", "task_context[+0x68] is lazily initialized if absent"],
            necessary_callees=["0x1962C0160 task-context lazy initializer (unregistered helper)"],
            null_default_error_behavior="null executor/task_context enters throw path; constructor has no default config.",
            pseudocode=[
                "executor.task_context = task_context",
                "executor.task_config = task_config",
                "executor.kind_marker = 0x7777",
                "ensure task_context.modifier_source exists",
            ],
        ),
        primitive(
            pe, methods, 506082,
            primitive_id="battle.ir.task.stack_property_execute",
            semantic_name="ExecuteStackPropertyTask",
            source_runtime_type="LEIHMEGJNME",
            inputs=[
                {"name": "executor", "type": "stack_property_executor"},
                {"name": "selected_targets", "type": "resolved_target_sequence"},
                {"name": "evaluated_property_value", "type": "runtime_numeric_value"},
            ],
            output="task_completion",
            field_reads=[
                "executor[+0x18] task_context",
                "executor[+0x20] task_config",
                "task_context[+0x68] modifier_source",
                "task_config[+0x18] target-selection payload",
                "task_config[+0x20] property identity",
                "task_config[+0x28] dynamic value payload",
            ],
            field_writes=["executor[+0x10] failure/status marker on invalid preconditions"],
            context_reads=["TaskContext modifier source", "DynamicValue evaluation context", "Target selector context"],
            context_writes=[],
            persistent_reads=["target sequence", "modifier State checked by callee"],
            persistent_writes=["one property contribution record per processed target (through M506199)"],
            branches=[
                "missing modifier source or task config -> error path",
                "target sequence iterates forward from index 0 to count-1",
                "each target is resolved before the contribution call",
            ],
            necessary_callees=[
                "0xE6F1530 target-selection helper (Batch 05 selector runtime)",
                "0xE6EFAE0 DynamicValue evaluator (Batch 02 reuse)",
                "0xB429D40 target-wrapper -> ability component resolver",
                "0xE7851A0 TurnBasedModifierInstance.StackProperty (M506199)",
            ],
            null_default_error_behavior="missing used context/config/target element enters IL2CPP throw paths; empty selected list completes without a contribution call.",
            ordering_behavior="forward target-list order; one M506199 call for each resolved target.",
            pseudocode=[
                "modifier = executor.task_context.modifier_source",
                "targets = select(executor.task_config.slot_18, task_context)",
                "value = evaluate_dynamic_value(executor.task_config.slot_28, task_context)",
                "for target in targets in order:",
                "    component = resolve_target_component(target)",
                "    modifier.stack_property(executor.task_config.slot_20, value, component, context_token, false)",
            ],
        ),
        primitive(
            pe, methods, 506199,
            primitive_id="battle.ir.modifier.stack_property_contribution",
            semantic_name="ModifierStackPropertyContribution",
            source_runtime_type="RPG.GameCore.TurnBasedModifierInstance",
            inputs=[
                {"name": "modifier", "type": "modifier_ref"},
                {"name": "property_id", "type": "opaque_property_id"},
                {"name": "value", "type": "runtime_numeric_value"},
                {"name": "target_component", "type": "ability_component_ref"},
                {"name": "context_token", "type": "opaque_context_token"},
                {"name": "is_refresh", "type": "boolean"},
            ],
            output="contribution_key_or_noop",
            field_reads=[
                "modifier[+0x80] State",
                "modifier[+0x240] tracked property-contribution list",
                "modifier[+0x2d1], [+0x264], [+0x2c0] internal reentrancy/guard state",
            ],
            field_writes=[
                "normal path appends {property_id:int32, contribution_key:int32, target_component:ref} to modifier[+0x240]",
                "refresh path delegates an update to the existing contribution key",
            ],
            context_reads=[],
            context_writes=[],
            persistent_reads=["modifier property-contribution records", "target component property domain"],
            persistent_writes=["modifier property-contribution records", "target component contribution domain (via M506495/M506497)"],
            branches=[
                "State > Alive(1) -> no-op",
                "is_refresh -> ordered scan for same property_id and target_component; matching record routes to M506497",
                "normal path -> M506495 returns opaque contribution_key, then record append",
                "internal guard/reentrancy paths may suppress work; exact policy remains UNKNOWN",
            ],
            necessary_callees=[
                "0xE72EB90 TurnBasedAbilityComponent.StackProperty (M506495)",
                "0xE731D90 TurnBasedAbilityComponent.UpdateStackPropertyValue (M506497; refresh only)",
                "0xE78C6C0 tracked-record reader (local helper, not separately registered)",
            ],
            null_default_error_behavior="State guard returns normally; used null list/component paths enter IL2CPP throw paths rather than creating an implicit contribution.",
            ordering_behavior="refresh scan is forward; normal record append occurs after the component-stack call returns its key.",
            pseudocode=[
                "if modifier.state > Alive: return NOOP",
                "if is_refresh and (record = first tracked record matching property_id and target_component):",
                "    update_component_contribution(target_component, property_id, record.contribution_key, value, context_token)",
                "    return record.contribution_key",
                "key = component_stack_property(target_component, property_id, value, context_token, modifier_tracking_list)",
                "append modifier.tracked_property_contributions, (property_id, key, target_component)",
                "return key",
            ],
        ),
        primitive(
            pe, methods, 506495,
            primitive_id="battle.ir.property.component_stack_boundary",
            semantic_name="ComponentStackPropertyBoundary",
            source_runtime_type="RPG.GameCore.TurnBasedAbilityComponent",
            inputs=[
                {"name": "target_component", "type": "ability_component_ref"},
                {"name": "property_id", "type": "opaque_property_id"},
                {"name": "value", "type": "runtime_numeric_value"},
                {"name": "context_token", "type": "opaque_context_token"},
            ],
            output="opaque_contribution_key",
            field_reads=["component property lookup/domain state"],
            field_writes=["property-domain contribution storage through 0xE72EFC0"],
            context_reads=[],
            context_writes=[],
            persistent_reads=["target component property domain"],
            persistent_writes=["target component property contribution domain"],
            branches=["property-id normalization/special cases", "property lookup may be absent", "broad generic dispatcher has 83 observed case arms"],
            necessary_callees=[
                "0xE72EE10 internal property lookup helper",
                "0xE72C6F0 TurnBasedAbilityComponent.GetProperty",
                "0xE72EFC0 generic property-domain dispatcher",
            ],
            null_default_error_behavior="null used component/property-domain path enters IL2CPP throw path; no default property is synthesized.",
            pseudocode=[
                "return property_domain_stack(target_component, property_id, value, context_token)",
            ],
            semantic_limit="CONFIRMED boundary and opaque contribution key only. Base/final value materialization and per-property arithmetic are UNKNOWN.",
        ),
        primitive(
            pe, methods, 506312,
            primitive_id="battle.ir.modifier.pop_property_contributions",
            semantic_name="PopModifierPropertyContributions",
            source_runtime_type="RPG.GameCore.TurnBasedModifierInstance",
            inputs=[{"name": "modifier", "type": "modifier_ref"}],
            output="none",
            field_reads=["modifier[+0x240] tracked property-contribution list"],
            field_writes=["modifier[+0x2d1] = true during property-pop loop, then false", "tracked contribution list is consumed/cleared after the loop"],
            context_reads=[],
            context_writes=[],
            persistent_reads=["ordered modifier property-contribution records"],
            persistent_writes=["target component contribution domain via M506496", "modifier property-contribution records"],
            branches=["forward loop over modifier[+0x240]", "each record has target component, property_id, contribution_key", "additional non-property cleanup follows and is out of scope"],
            necessary_callees=["0xE731B80 TurnBasedAbilityComponent.UnStackProperty (M506496)"],
            null_default_error_behavior="null tracked list skips the loop; malformed used record/component paths enter IL2CPP throw paths.",
            ordering_behavior="forward tracked-record order; each UnStackProperty call completes before the next record.",
            pseudocode=[
                "modifier.is_popping_stack_property = true",
                "for record in modifier.tracked_property_contributions in order:",
                "    component_unstack_property(record.target_component, record.property_id, record.contribution_key, modifier)",
                "clear modifier.tracked_property_contributions",
                "modifier.is_popping_stack_property = false",
            ],
        ),
        primitive(
            pe, methods, 506496,
            primitive_id="battle.ir.property.component_unstack_boundary",
            semantic_name="ComponentUnStackPropertyBoundary",
            source_runtime_type="RPG.GameCore.TurnBasedAbilityComponent",
            inputs=[
                {"name": "target_component", "type": "ability_component_ref"},
                {"name": "property_id", "type": "opaque_property_id"},
                {"name": "contribution_key", "type": "opaque_contribution_key"},
                {"name": "owner_modifier", "type": "modifier_ref"},
            ],
            output="none",
            field_reads=["component property lookup/domain state"],
            field_writes=["property-domain contribution storage through 0xE72EFC0"],
            context_reads=[],
            context_writes=[],
            persistent_reads=["target component property contribution domain"],
            persistent_writes=["target component property contribution domain"],
            branches=["property-id normalization/special cases", "property lookup may be absent", "broad generic dispatcher is shared with add path"],
            necessary_callees=["0xE72EE10 internal property lookup helper", "0xE72C6F0 GetProperty", "0xE72EFC0 generic property-domain dispatcher"],
            null_default_error_behavior="null used component/property-domain path enters IL2CPP throw path; absent property is not materialized by this boundary.",
            pseudocode=[
                "property_domain_unstack(target_component, property_id, contribution_key, owner_modifier)",
            ],
            semantic_limit="CONFIRMED remove boundary keyed by the opaque key returned on add; final numeric materialization remains UNKNOWN.",
        ),
    ]

    return {
        "schema": "battle_semantic_capability/1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "game_version": GAME_VERSION,
        "capability_id": "MODIFIER_PROPERTY_CONTRIBUTION_BOUNDARY_09_PROOF",
        "status": "CONFIRMED_CONTRIBUTION_LIFECYCLE__MATERIALIZATION_DEFERRED",
        "evidence_level": E4,
        "scope": "Generic property contribution add/update/remove ownership, not concrete stat formulas.",
        "primitives": primitives,
        "config_source": {
            "declared_runtime_type": "RPG.GameCore.StackProperty",
            "declaring_type_index": 23267,
            "serializer_method_index": 127753,
            "serializer_native_rva": serializer["body_rva"],
            "serializer_body_hash": serializer["body_sha256"],
            "serializer_projection": serializer["body_projection"],
            "declared_fields": ["TargetType", "Property", "PropertyValue", "Silence", "IsRefresh"],
            "native_slots_consumed_by_M506082": {
                "+0x18": "target-selection payload",
                "+0x20": "opaque property identity",
                "+0x28": "DynamicValue payload",
                "+0x30": "bool slot; not consumed by the proven M506082 direct property call",
                "+0x31": "bool slot; not consumed by the proven M506082 direct property call",
            },
            "association_status": "SUPPORTED",
            "association_evidence": "StackProperty serializer writes the same +0x18/+0x20/+0x28/+0x30/+0x31 layout that M506082 consumes; the executor reaches M506199. No direct allocation/factory edge from this config class to LEIHMEGJNME was recovered in this bounded batch.",
        },
        "semantic_chains": [
            {
                "chain_id": "stack_property_task_to_modifier_contribution",
                "evidence_level": "E4 except config/executor association SUPPORTED",
                "steps": [
                    "StackProperty serialized fields (+0x18 target payload, +0x20 property id, +0x28 DynamicValue)",
                    "LEIHMEGJNME.OnTaskBegin M506082 selects targets and evaluates the DynamicValue",
                    "M506082 -> TurnBasedModifierInstance.StackProperty M506199 once per target in forward order",
                    "M506199 -> TurnBasedAbilityComponent.StackProperty M506495",
                    "M506199 appends {property_id, contribution_key, target_component} to modifier[+0x240]",
                ],
                "observable_result": "persistent, owner-scoped property contribution record with an opaque component contribution key",
            },
            {
                "chain_id": "modifier_contribution_inverse",
                "evidence_level": "E4",
                "steps": [
                    "TurnBasedModifierInstance._PopStackedProperties M506312 iterates modifier[+0x240] in forward order",
                    "record fields feed TurnBasedAbilityComponent.UnStackProperty M506496",
                    "M506496 reaches the shared property-domain dispatcher with property_id and opaque contribution_key",
                    "M506312 consumes/clears tracked records and resets its pop guard",
                ],
                "observable_result": "the same owner-scoped contribution key is removed rather than applying an inverse numeric delta",
            },
        ],
        "persistent_state_contract": {
            "required_new_battle_state_fields": [
                {
                    "name": "modifier_property_contributions",
                    "key": "ModifierRef",
                    "value": "ordered sequence of PropertyContribution",
                    "record": {
                        "target_entity_or_component_ref": "identity only",
                        "property_id": "opaque int32 identity",
                        "contribution_key": "opaque int32 returned by add boundary",
                    },
                },
                {
                    "name": "entity_property_contributions",
                    "key": "(entity_ref, property_id)",
                    "value": "ordered keyed contributions; materialized final value intentionally absent",
                },
            ],
            "forbidden_shortcut": "Do not implement this contract as final_property_value += value or -= value.",
        },
        "dependencies": {
            "reuse": [
                "DynamicValue runtime batch 02 for M506082 value evaluation",
                "Target selector runtime batch 05 for M506082 target resolution",
                "Generated task executor runtime batch 06 for task lifecycle",
                "Modifier lifecycle runtime batch 08 for persistent modifier identity and State",
            ],
            "deferred": [
                "0xE72EFC0 generic property-domain dispatcher (83 observed case arms)",
                "base/contribution/final property materialization formulae",
                "exact semantic meaning of StackProperty.Silence and StackProperty.IsRefresh in this executor path",
                "lifecycle caller that invokes _PopStackedProperties during every destroy/remove path",
            ],
        },
        "reads": [
            "modifier State [+0x80]",
            "modifier tracked property list [+0x240]",
            "executor task context/config [+0x18]/[+0x20]",
            "StackProperty config slots [+0x18]/[+0x20]/[+0x28]",
            "target component property domain",
        ],
        "writes": [
            "modifier tracked contribution record {property_id, contribution_key, target_component}",
            "target component generic contribution domain via M506495/M506496",
            "temporary modifier pop guard [+0x2d1]",
        ],
        "unknowns": [
            "How 0xE72EFC0 materializes each property identity into final gameplay values",
            "Exact contribution-key allocation/collision policy inside generic property domain",
            "Direct config-class allocation/factory edge to LEIHMEGJNME",
            "Whether the M506199 refresh flag is sourced from StackProperty.IsRefresh for a different generated path",
            "Which property identities are required for the first simple skill's damage formula",
        ],
        "source_hashes": {
            "gameassembly_sha256": manifest["GameAssembly"]["sha256"],
            "metadata_sha256": manifest["global_metadata"]["sha256"],
        },
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
