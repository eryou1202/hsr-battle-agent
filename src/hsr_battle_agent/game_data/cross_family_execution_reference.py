"""Cross-family reference execution harness (verification scaffold).

This harness composes the reconstructed references -- DynamicValue store and
PostfixExpr evaluation, Predicate AST evaluation, TargetAlias resolution,
damage/survival transitions, scheduler markers and the event tracer -- into
one deterministic in-memory execution reference for interaction fixtures.

It executes selected canonical operation payloads under an explicit fixture
state.  It is NOT a production battle runtime and it never turns an
unsupported operation into a no-op.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from .damage_survival_reference import DamageMultiplierContext, SurvivalState
from .dynamic_value_reference import DynamicValueStore, dynamic_key_from_payload, value_spec_from_payload
from .predicate_semantics_reference import PredicateContext, evaluate_predicate
from .target_semantics_reference import BattleTargetContext, EntitySnapshot


class CrossFamilyExecutionError(RuntimeError):
    """The harness hit an unsupported or inconsistent operation."""


@dataclass(frozen=True)
class EntityState:
    entity_id: str
    survival: SurvivalState

    def as_json(self) -> dict[str, Any]:
        return {"entity_id": self.entity_id, "survival": self.survival.as_json()}


@dataclass
class ReferenceBattleState:
    entities: dict[str, EntityState]
    dynamic_store: DynamicValueStore
    modifier_names: dict[str, set[str]]
    rng: Callable[[], Decimal]
    trace: list[dict[str, Any]] = field(default_factory=list)

    def clone(self) -> "ReferenceBattleState":
        return ReferenceBattleState(
            entities=dict(self.entities),
            dynamic_store=self.dynamic_store,
            modifier_names={entity: set(names) for entity, names in self.modifier_names.items()},
            rng=self.rng,
            trace=list(self.trace),
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "entities": {key: value.as_json() for key, value in sorted(self.entities.items())},
            "dynamic_store": self.dynamic_store.snapshot(),
            "modifier_names": {entity: sorted(names) for entity, names in sorted(self.modifier_names.items())},
        }


def target_context(state: ReferenceBattleState, caster_id: str, ability_target_id: str | None) -> BattleTargetContext:
    entities = {}
    for entity_id, item in state.entities.items():
        survival = item.survival
        team = "light" if entity_id.startswith("p") else "dark"
        entities[entity_id] = EntitySnapshot(entity_id, team, alive=survival.alive, selectable=True)
    return BattleTargetContext(
        entities=entities,
        caster_id=caster_id,
        ability_target_id=ability_target_id,
        modifier_owner_id=caster_id,
        current_turn_owner_id=caster_id,
        current_turn_action_entity_id=caster_id,
        damage_attacker_id=caster_id,
        damage_defender_id=ability_target_id,
    )


def predicate_context(state: ReferenceBattleState, target_context_value: BattleTargetContext) -> PredicateContext:
    return PredicateContext(
        resolve_target=lambda alias: __import__("hsr_battle_agent.game_data.target_semantics_reference", fromlist=["resolve_target_alias"]).resolve_target_alias(alias, target_context_value),
        dynamic_get=lambda _scope, key: state.dynamic_store.read("p1", key),
        has_modifier=lambda entity, name, _added_or_alive, _caster_matches: name in state.modifier_names.get(entity, set()),
        has_behavior_flag=lambda _entity, _flag: False,
        entity_team=lambda entity: target_context_value.snapshot(entity).team if target_context_value.snapshot(entity) else "neutral",
        entity_alive=lambda entity: target_context_value.snapshot(entity).alive if target_context_value.snapshot(entity) else False,
        random_01=lambda: state.rng(),
        skill_type="Skill",
        skill_name="Skill01",
        wave_count=1,
        challenge_left=1,
    )


def execute_operations(
    state: ReferenceBattleState,
    operations: Sequence[Mapping[str, Any]],
    *,
    caster_id: str,
    ability_target_id: str | None,
    depth: int = 0,
) -> ReferenceBattleState:
    if depth > 64:
        raise CrossFamilyExecutionError("reference execution recursion limit exceeded")
    target_ctx = target_context(state, caster_id, ability_target_id)
    pred_ctx = predicate_context(state, target_ctx)
    for operation in operations:
        if not isinstance(operation, Mapping):
            continue
        kind = str(operation.get("kind", "OPAQUE"))
        status = str(operation.get("semantic_status", "OPAQUE"))
        if status == "PRESENTATION" and operation.get("gating_risk") == "NONE":
            state.trace.append({"operation_id": operation.get("operation_id"), "disposition": "HEADLESS_PRESENTATION_OMITTED"})
            continue
        if kind == "SET_DYNAMIC_VALUE":
            arguments = operation.get("arguments", {})
            key = dynamic_key_from_payload(arguments.get("DynamicKey"))
            value = value_spec_from_payload(arguments.get("Value"))
            evaluated = value.evaluate(lambda dynamic_hash: state.dynamic_store.read("p1", str(dynamic_hash)))
            transition = state.dynamic_store.set_value("p1", key, evaluated)
            state.dynamic_store = transition.store
            state.trace.append({"operation_id": operation.get("operation_id"), "disposition": "SET_DYNAMIC_VALUE", "key": key, "value": str(evaluated)})
            continue
        if kind == "DEFINE_DYNAMIC_VALUE":
            arguments = operation.get("arguments", {})
            key = dynamic_key_from_payload(arguments.get("DynamicKey"))
            transition = state.dynamic_store.define("p1", key, arguments.get("ResetValue"))
            state.dynamic_store = transition.store
            state.trace.append({"operation_id": operation.get("operation_id"), "disposition": transition.action, "key": key})
            continue
        if kind in {"PREDICATE", "CONDITIONAL"}:
            predicate_payload = operation.get("arguments", {}).get("Predicate")
            if not isinstance(predicate_payload, Mapping):
                # A singular Predicate child was lifted as a sibling group in
                # the canonical corpus; evaluate that child.
                children = [child for group in operation.get("children", []) if isinstance(group, Mapping) for child in group.get("operations", []) if isinstance(child, Mapping)]
                predicate_payload = children[0] if children else None
            if not isinstance(predicate_payload, Mapping):
                raise CrossFamilyExecutionError(f"predicate node without payload: {operation.get('operation_id')}")
            result = evaluate_predicate(predicate_payload, pred_ctx)
            branch_field = "SuccessTaskList" if result else ("FailedTaskList" if any(isinstance(group, Mapping) and group.get("field_path") == "FailedTaskList" for group in operation.get("children", [])) else "FailedTaskList")
            state.trace.append({"operation_id": operation.get("operation_id"), "disposition": f"BRANCH_{'SUCCESS' if result else 'FAILED'}"})
            for group in operation.get("children", []):
                if isinstance(group, Mapping) and group.get("field_path") == branch_field:
                    execute_operations(state, group.get("operations", []), caster_id=caster_id, ability_target_id=ability_target_id, depth=depth + 1)
            continue
        if kind == "DAMAGE_REQUEST":
            amount = Decimal(str(operation.get("arguments", {}).get("amount", 0)))
            target_id = ability_target_id or "e1"
            entity = state.entities.get(target_id)
            if entity is None:
                raise CrossFamilyExecutionError(f"unknown damage target {target_id}")
            damage_context = DamageMultiplierContext()
            # The synthetic fixture carries an explicit amount; no formula
            # scaling is inferred from level.
            after, shield_absorbed, hp_lost = entity.survival.absorb(amount)
            state.entities[target_id] = replace(entity, survival=after)
            state.trace.append({"operation_id": operation.get("operation_id"), "disposition": "DAMAGE_COMMITTED", "target_id": target_id, "shield_absorbed": str(shield_absorbed), "hp_lost": str(hp_lost)})
            continue
        if kind in {"ACTION_START_MARKER", "ACTION_COMPLETION_MARKER", "DAMAGE_COMPLETION_MARKER"}:
            state.trace.append({"operation_id": operation.get("operation_id"), "disposition": kind})
            continue
        raise CrossFamilyExecutionError(f"unsupported operation kind {kind} at {operation.get('operation_id')}")
    return state
