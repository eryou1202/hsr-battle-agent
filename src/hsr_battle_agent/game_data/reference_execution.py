"""Strict generic reference execution for a closed subset of Behavior IR.

This module is the bridge between canonical Behavior IR and the individual
semantic references.  It is intentionally *not* the production battle
runtime: its contract is to execute only source-independent operations whose
dependencies have selected reference semantics, and reject every other
behavior-affecting operation.  In particular, it never reaches back into raw
external JSON and it never treats an unknown operation as a no-op.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
import random
from typing import Any, Iterable, Mapping, Sequence

from .damage_survival_reference import DamageMultiplierContext, SurvivalState, initial_damage, normal_damage
from .dynamic_value_reference import (
    DynamicValueSemanticError,
    DynamicValueStore,
    context_scope_from_payload,
    dynamic_key_from_payload,
    value_spec_from_payload,
)
from .predicate_semantics_reference import PredicateContext, evaluate_predicate
from .property_contribution_reference import PropertyState
from .modifier_catalog import ModifierDefinition
from .modifier_lifecycle_reference import ModifierInstance, add_or_refresh, mark_destroy
from .target_semantics_reference import BattleTargetContext, EntitySnapshot, resolve_target_payload


class SemanticExecutionError(DynamicValueSemanticError):
    """A compiled behavior cannot execute under the declared reference scope."""


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise SemanticExecutionError(f"non-numeric runtime value {value!r}") from error


@dataclass(frozen=True)
class RuntimeEntity:
    """The shared entity facts needed by the initial generic executor."""

    entity_id: str
    team: str
    survival: SurvivalState
    selectable: bool = True
    position: tuple[int, int] = (0, 0)
    character_id: int | None = None
    modifier_names: tuple[str, ...] = ()
    attack: Decimal = Decimal("0")
    defense: Decimal = Decimal("0")

    def snapshot(self) -> EntitySnapshot:
        return EntitySnapshot(
            entity_id=self.entity_id,
            team=self.team,
            alive=self.survival.alive,
            selectable=self.selectable,
            position=self.position,
        )


@dataclass(frozen=True)
class SandboxRng:
    """Frozen deterministic MT19937 wrapper with explicit replay state."""

    seed: int
    state: object | None = None

    def draw_01(self) -> tuple[float, "SandboxRng"]:
        generator = random.Random(self.seed)
        if self.state is not None:
            generator.setstate(self.state)
        value = generator.random()
        return value, SandboxRng(seed=self.seed, state=generator.getstate())


@dataclass(frozen=True)
class ReferenceBattleState:
    """Immutable state consumed by all first-bridge semantic adapters."""

    entities: Mapping[str, RuntimeEntity]
    dynamic_store: DynamicValueStore = DynamicValueStore.empty()
    property_states: Mapping[str, PropertyState] = field(default_factory=dict)
    modifier_instances: Mapping[str, tuple[ModifierInstance, ...]] = field(default_factory=dict)
    special_resources: Mapping[str, Decimal] = field(default_factory=dict)
    rng: SandboxRng = SandboxRng(seed=0)
    wave_count: int = 1
    challenge_left: int | None = None

    def __post_init__(self) -> None:
        if not self.entities:
            raise SemanticExecutionError("ReferenceBattleState requires at least one entity")

    def entity(self, entity_id: str) -> RuntimeEntity:
        try:
            return self.entities[entity_id]
        except KeyError as error:
            raise SemanticExecutionError(f"unknown entity {entity_id!r}") from error

    def replace_entity(self, entity: RuntimeEntity) -> "ReferenceBattleState":
        entities = dict(self.entities)
        entities[entity.entity_id] = entity
        return replace(self, entities=entities)

    def property_state(self, entity_id: str) -> PropertyState:
        return self.property_states.get(entity_id, PropertyState.empty())

    def replace_property_state(self, entity_id: str, property_state: PropertyState) -> "ReferenceBattleState":
        states = dict(self.property_states)
        states[entity_id] = property_state
        return replace(self, property_states=states)

    def modifiers(self, entity_id: str) -> tuple[ModifierInstance, ...]:
        return tuple(self.modifier_instances.get(entity_id, ()))

    def replace_modifiers(self, entity_id: str, instances: Iterable[ModifierInstance]) -> "ReferenceBattleState":
        states = dict(self.modifier_instances)
        states[entity_id] = tuple(instances)
        return replace(self, modifier_instances=states)

    def target_context(self, context: "ExecutionContext") -> BattleTargetContext:
        return BattleTargetContext(
            entities={key: entity.snapshot() for key, entity in self.entities.items()},
            caster_id=context.caster_id,
            ability_target_id=context.ability_target_id,
            modifier_owner_id=context.modifier_owner_id,
            current_turn_action_entity_id=context.current_turn_action_entity_id,
            current_turn_owner_id=context.current_turn_owner_id,
            ability_target_list=context.ability_target_ids,
            skill_target_list=context.skill_target_ids,
            attack_target_list=context.attack_target_ids,
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "entities": {
                key: {
                    "entity_id": entity.entity_id,
                    "team": entity.team,
                    "survival": dict(entity.survival.as_json()),
                    "selectable": entity.selectable,
                    "position": list(entity.position),
                    "character_id": entity.character_id,
                    "modifier_names": list(entity.modifier_names),
                    "attack": str(entity.attack),
                    "defense": str(entity.defense),
                }
                for key, entity in sorted(self.entities.items())
            },
            "dynamic_store": self.dynamic_store.snapshot(),
            "property_states": {key: value.as_json() for key, value in sorted(self.property_states.items())},
            "modifier_instances": {
                key: [
                    {"instance_id": item.instance_id, "name": item.name, "stacking": item.stacking, "state": item.state.name,
                     "current_life": item.current_life, "count": item.count, "caster_runtime_id": item.caster_runtime_id}
                    for item in values
                ]
                for key, values in sorted(self.modifier_instances.items())
            },
            "special_resources": {key: str(value) for key, value in sorted(self.special_resources.items())},
            "rng_seed": self.rng.seed,
            "wave_count": self.wave_count,
            "challenge_left": self.challenge_left,
        }


@dataclass(frozen=True)
class ExecutionContext:
    """All non-state inputs shared by DynamicValue, Target and Predicate."""

    caster_id: str | None = None
    modifier_owner_id: str | None = None
    modifier_id: str | None = None
    ability_target_id: str | None = None
    ability_target_ids: tuple[str, ...] = ()
    skill_target_ids: tuple[str, ...] = ()
    attack_target_ids: tuple[str, ...] = ()
    current_turn_action_entity_id: str | None = None
    current_turn_owner_id: str | None = None
    dynamic_hash_values: Mapping[str, Any] = field(default_factory=dict)
    dynamic_scope_owners: Mapping[str, str] = field(default_factory=dict)
    skill_type: str = ""
    skill_name: str = ""
    modifier_callback_name: str = ""
    caster_runtime_id: int | None = None
    modifier_catalog: Mapping[str, ModifierDefinition] = field(default_factory=dict)
    damage_source_id: str | None = None
    damage_multiplier_contexts: Mapping[str, DamageMultiplierContext] = field(default_factory=dict)
    crit_rate: Decimal = Decimal("0")
    crit_damage: Decimal = Decimal("0")

    def default_owner_id(self) -> str:
        for candidate in (self.caster_id, self.modifier_owner_id, self.ability_target_id):
            if candidate:
                return candidate
        raise SemanticExecutionError("context has no caster, modifier owner or ability target")


@dataclass(frozen=True)
class ExecutionResult:
    state: ReferenceBattleState
    trace: tuple[Mapping[str, Any], ...]


class SemanticExecutor:
    """Execute ``EXECUTABLE_REFERENCE`` operations in deterministic order."""

    def execute_entrypoint(
        self,
        behavior: Mapping[str, Any],
        event: str,
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        entry = next((item for item in behavior.get("entrypoints", []) if item.get("event") == event), None)
        if entry is None:
            raise SemanticExecutionError(f"entrypoint {event!r} is absent")
        if not entry.get("executable_reference"):
            raise SemanticExecutionError("entrypoint is not compiled for executable reference execution")
        return self._execute_operations(entry.get("operations", ()), state, context, str(behavior.get("owner_ref") or ""))

    def _execute_operations(
        self,
        operations: Iterable[Mapping[str, Any]],
        state: ReferenceBattleState,
        context: ExecutionContext,
        owner_ref: str,
    ) -> ExecutionResult:
        trace: list[Mapping[str, Any]] = []
        current = state
        for operation in operations:
            result = self._execute_operation(operation, current, context, owner_ref)
            current = result.state
            trace.extend(result.trace)
        return ExecutionResult(current, tuple(trace))

    def _execute_operation(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
        owner_ref: str,
    ) -> ExecutionResult:
        disposition = operation.get("disposition")
        operation_id = str(operation.get("operation_id"))
        if disposition == "HEADLESS_PRESENTATION_OMITTED":
            return ExecutionResult(state, ({"operation_id": operation_id, "disposition": disposition},))
        if disposition != "EXECUTABLE_REFERENCE":
            raise SemanticExecutionError(f"{operation_id}: unsupported disposition {disposition!r}")
        kind = str(operation.get("kind"))
        if kind == "CONDITIONAL":
            payload = operation.get("arguments", {}).get("Predicate")
            if not isinstance(payload, Mapping):
                raise SemanticExecutionError(f"{operation_id}: conditional has no predicate payload")
            predicate_context = self._predicate_context(state, context)
            passed = evaluate_predicate(payload, predicate_context)
            field = "SuccessTaskList" if passed else "FailedTaskList"
            group = next((group for group in operation.get("children", ()) if group.get("field_path") == field), None)
            trace = [{"operation_id": operation_id, "disposition": "BRANCH_SUCCESS" if passed else "BRANCH_FAILED"}]
            if group is None:
                return ExecutionResult(state, tuple(trace))
            children = self._execute_operations(group.get("operations", ()), state, context, owner_ref)
            return ExecutionResult(children.state, tuple(trace) + children.trace)
        if kind == "PREDICATE":
            payload = dict(operation.get("arguments", {}))
            payload["$type"] = operation.get("source_type")
            if operation.get("target") is not None:
                payload.setdefault("TargetType", operation.get("target"))
            value = evaluate_predicate(payload, self._predicate_context(state, context))
            return ExecutionResult(state, ({
                "operation_id": operation_id,
                "disposition": "PREDICATE_TRUE" if value else "PREDICATE_FALSE",
            },))
        if kind == "HEAL_REQUEST":
            return self._execute_heal(operation, state, context)
        if kind == "MODIFY_PROPERTY_STACK":
            return self._execute_property_stack(operation, state, context, owner_ref)
        if kind == "SET_DYNAMIC_VALUE":
            return self._execute_set_dynamic_value(operation, state, context)
        if kind == "DEFINE_DYNAMIC_VALUE":
            return self._execute_define_dynamic_value(operation, state, context)
        if kind == "ADD_MODIFIER":
            return self._execute_add_modifier(operation, state, context)
        if kind == "REMOVE_MODIFIER":
            return self._execute_remove_modifier(operation, state, context)
        if kind == "DAMAGE_REQUEST":
            return self._execute_damage(operation, state, context)
        raise SemanticExecutionError(f"{operation_id}: executable reference has no handler for {kind}")

    def _resolve_targets(self, value: Any, state: ReferenceBattleState, context: ExecutionContext) -> tuple[str, ...]:
        return resolve_target_payload(value, state.target_context(context))

    def _resolve_dynamic(self, state: ReferenceBattleState, context: ExecutionContext, key: int) -> Decimal:
        text_key = str(key)
        if text_key in context.dynamic_hash_values:
            return _decimal(context.dynamic_hash_values[text_key])
        for scope in ("ContextCaster", "ContextOwner", "ContextModifier", "TargetEntity", "ContextAbility"):
            owner = context.dynamic_scope_owners.get(scope)
            if owner is None:
                if scope == "ContextCaster":
                    owner = context.caster_id
                elif scope == "ContextOwner":
                    owner = context.modifier_owner_id
                elif scope == "ContextModifier":
                    owner = context.modifier_owner_id
                elif scope == "TargetEntity":
                    owner = context.ability_target_id
            if owner:
                try:
                    return state.dynamic_store.read(owner, text_key)
                except KeyError:
                    continue
        raise SemanticExecutionError(f"unresolved DynamicHash {text_key}")

    def _evaluate_value(self, payload: Any, state: ReferenceBattleState, context: ExecutionContext) -> Decimal:
        spec = value_spec_from_payload(payload)
        return spec.evaluate(lambda key: self._resolve_dynamic(state, context, key))

    def _execute_heal(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        arguments = operation.get("arguments", {})
        targets = self._resolve_targets(operation.get("target"), state, context)
        formula = str(arguments.get("FormulaType", ""))
        percentage = self._evaluate_value(arguments.get("HealPercentage"), state, context)
        modify = self._evaluate_value(arguments.get("ModifyValue"), state, context)
        if formula == "HealByHealerMaxHP":
            base = state.entity(context.default_owner_id()).survival.max_hp
        elif formula == "HealByTargetMaxHP":
            base = None
        else:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: unsupported heal formula {formula!r}")
        current = state
        amounts: list[str] = []
        for target_id in targets:
            amount = ((base if base is not None else current.entity(target_id).survival.max_hp) * percentage) + modify
            entity = current.entity(target_id)
            current = current.replace_entity(replace(entity, survival=entity.survival.heal(amount)))
            amounts.append(str(amount))
        return ExecutionResult(current, ({
            "operation_id": operation.get("operation_id"),
            "disposition": "HEAL_COMMITTED",
            "formula_type": formula,
            "target_ids": list(targets),
            "amounts": amounts,
        },))

    def _execute_property_stack(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
        owner_ref: str,
    ) -> ExecutionResult:
        arguments = operation.get("arguments", {})
        property_name = str(arguments.get("Property", ""))
        if not property_name:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: StackProperty has no Property")
        value = self._evaluate_value(arguments.get("PropertyValue"), state, context)
        modifier_id = context.modifier_id or owner_ref
        if not modifier_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier identity is required")
        targets = self._resolve_targets(operation.get("target"), state, context)
        current = state
        slots: list[str] = []
        for target_id in targets:
            transition = current.property_state(target_id).set_contribution(modifier_id, property_name, value)
            current = current.replace_property_state(target_id, transition.state)
            slots.append(transition.slot)
        return ExecutionResult(current, ({
            "operation_id": operation.get("operation_id"),
            "disposition": "PROPERTY_CONTRIBUTION_SET",
            "modifier_id": modifier_id,
            "property": property_name,
            "value": str(value),
            "target_ids": list(targets),
            "slots": slots,
        },))

    def _scope_owner(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> str:
        arguments = operation.get("arguments", {})
        scope = context_scope_from_payload(arguments.get("ContextScope"))
        mapped = context.dynamic_scope_owners.get(scope)
        if mapped:
            return mapped
        if scope in {"ContextCaster", "ContextAbility"}:
            if context.caster_id:
                return context.caster_id
        elif scope in {"ContextOwner", "ContextModifier"}:
            if context.modifier_owner_id:
                return context.modifier_owner_id
        elif scope == "TargetEntity":
            targets = self._resolve_targets(operation.get("target"), state, context)
            if len(targets) == 1:
                return targets[0]
            raise SemanticExecutionError(f"{operation.get('operation_id')}: TargetEntity scope requires one target")
        raise SemanticExecutionError(f"{operation.get('operation_id')}: unresolved DynamicValue scope {scope!r}")

    def _execute_set_dynamic_value(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        arguments = operation.get("arguments", {})
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = self._evaluate_value(arguments.get("Value"), state, context)
        transition = state.dynamic_store.set_value(owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET",
            "owner_id": owner_id,
            "key": key,
            "value": str(value),
        },))

    def _execute_define_dynamic_value(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        arguments = operation.get("arguments", {})
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        transition = state.dynamic_store.define(owner_id, key, arguments.get("ResetValue"))
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": transition.action,
            "owner_id": owner_id,
            "key": key,
            "value": None if transition.value is None else str(transition.value),
        },))

    def _execute_add_modifier(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        arguments = operation.get("arguments", {})
        modifier = arguments.get("ModifierName", {})
        name = modifier.get("Value") if isinstance(modifier, Mapping) else None
        definition = context.modifier_catalog.get(str(name))
        if definition is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: Modifier definition {name!r} is not in ExecutionContext")
        targets = self._resolve_targets(operation.get("target"), state, context)
        current = state
        trace: list[Mapping[str, Any]] = []
        for target_id in targets:
            instances = current.modifiers(target_id)
            instance_id = f"{target_id}:{definition.name}:{len(instances) + 1}"
            incoming = ModifierInstance(
                instance_id=instance_id,
                name=definition.name,
                stacking=definition.stacking,
                caster_runtime_id=context.caster_runtime_id,
                source_provider_id=context.caster_id,
                current_life=None,
                count=None,
            )
            transition = add_or_refresh(instances, incoming)
            current = current.replace_modifiers(target_id, transition.instances)
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": "MODIFIER_APPEND_OR_REFRESH_PENDING",
                "target_id": target_id,
                "modifier_name": definition.name,
                "instance_id": transition.affected_instance_id,
                "lifecycle_action": transition.action,
            })
        return ExecutionResult(current, tuple(trace))

    def _execute_remove_modifier(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Mark all named target instances for later dirty cleanup.

        The selected local lifecycle model keeps callback/property ownership
        until ``remove_dirty``.  Therefore this handler must not shortcut the
        boundary by deleting entries from the state map.
        """
        arguments = operation.get("arguments", {})
        modifier = arguments.get("ModifierName", {})
        name = modifier.get("Value") if isinstance(modifier, Mapping) else None
        targets = self._resolve_targets(operation.get("target"), state, context)
        current = state
        trace: list[Mapping[str, Any]] = []
        for target_id in targets:
            transition_instances = current.modifiers(target_id)
            affected = [item.instance_id for item in transition_instances if item.name == name]
            for instance_id in affected:
                transition = mark_destroy(transition_instances, instance_id, reason=0)
                transition_instances = transition.instances
            current = current.replace_modifiers(target_id, transition_instances)
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": "MODIFIER_MARKED_FOR_DIRTY_REMOVAL",
                "target_id": target_id,
                "modifier_name": name,
                "instance_ids": affected,
            })
        return ExecutionResult(current, tuple(trace))

    def _execute_damage(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Commit the selected ordinary damage model through shield then HP.

        A request is intentionally executable only when the caller supplies
        the target multiplier context.  This avoids silently importing level,
        resistance, vulnerability or crit assumptions from a fixture.
        """
        arguments = operation.get("arguments", {})
        attack_property = arguments.get("AttackProperty", {})
        if not isinstance(attack_property, Mapping):
            raise SemanticExecutionError(f"{operation.get('operation_id')}: missing AttackProperty")
        source_id = context.damage_source_id or context.caster_id
        if not source_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: damage source is required")
        source = state.entity(source_id)
        formula = str(attack_property.get("FormulaType") or "ByAttack")
        percentage = self._evaluate_value(attack_property.get("DamagePercentage"), state, context)
        scaling = {"ByAttack": (percentage, Decimal("0"), Decimal("0")), "ByMaxHP": (Decimal("0"), percentage, Decimal("0")), "ByDefence": (Decimal("0"), Decimal("0"), percentage)}.get(formula)
        if scaling is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: unsupported damage formula {formula!r}")
        ability_amount = initial_damage(
            atk=source.attack,
            hp=source.survival.max_hp,
            defense=source.defense,
            atk_scaling=scaling[0],
            hp_scaling=scaling[1],
            def_scaling=scaling[2],
        )
        targets = self._resolve_targets(operation.get("target"), state, context)
        current = state
        trace: list[Mapping[str, Any]] = []
        for target_id in targets:
            multiplier_context = context.damage_multiplier_contexts.get(target_id)
            if multiplier_context is None:
                raise SemanticExecutionError(f"{operation.get('operation_id')}: missing DamageMultiplierContext for {target_id!r}")
            amount = normal_damage(ability_amount, multiplier_context, crit_rate=context.crit_rate, crit_damage=context.crit_damage)
            target = current.entity(target_id)
            survival, shield_absorbed, hp_lost = target.survival.absorb(amount)
            current = current.replace_entity(replace(target, survival=survival))
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": "DAMAGE_COMMITTED",
                "formula_type": formula,
                "source_id": source_id,
                "target_id": target_id,
                "ability_amount": str(ability_amount),
                "amount": str(amount),
                "shield_absorbed": str(shield_absorbed),
                "hp_lost": str(hp_lost),
                "target_alive": survival.alive,
            })
        return ExecutionResult(current, tuple(trace))

    def _predicate_context(self, state: ReferenceBattleState, context: ExecutionContext) -> PredicateContext:
        target_context = state.target_context(context)

        def resolve(alias: str) -> Sequence[str]:
            return self._resolve_targets({"Alias": alias}, state, context)

        def dynamic_get(scope: str | None, key: str) -> Decimal:
            owner = context.dynamic_scope_owners.get(scope or "") if scope else context.default_owner_id()
            if owner:
                try:
                    return state.dynamic_store.read(owner, key)
                except KeyError:
                    pass
            return self._resolve_dynamic(state, context, int(key))

        return PredicateContext(
            resolve_target=resolve,
            dynamic_get=dynamic_get,
            has_modifier=lambda entity, name, _alive, _is_caster: name in state.entity(entity).modifier_names,
            entity_team=lambda entity: state.entity(entity).team,
            entity_alive=lambda entity: state.entity(entity).survival.alive,
            entity_character_id=lambda entity: state.entity(entity).character_id or 0,
            random_01=lambda: state.rng.draw_01()[0],
            skill_type=context.skill_type,
            skill_name=context.skill_name,
            wave_count=state.wave_count,
            challenge_left=state.challenge_left,
            current_entity_id=context.modifier_owner_id or context.caster_id,
            current_turn_owner_id=context.current_turn_owner_id,
            current_turn_action_entity_id=context.current_turn_action_entity_id,
            current_hp=(state.entity(context.modifier_owner_id).survival.hp if context.modifier_owner_id else None),
            current_max_hp=(state.entity(context.modifier_owner_id).survival.max_hp if context.modifier_owner_id else None),
            modifier_callback_name=context.modifier_callback_name,
        )
