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

from .damage_survival_reference import DamageMultiplierContext, SurvivalState, dot_damage, initial_damage, normal_damage
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
from .modifier_lifecycle_reference import ModifierInstance, ModifierState, add_or_refresh, mark_destroy
from .scheduler_semantics_reference import (
    ActionDelayState,
    InsertedActionSpec,
    OrdinaryTurnTimeline,
    complete_ordinary_action,
    ordered_ordinary_candidates,
    TaskState,
    TaskStep,
    apply_delay_operation,
    trace_completion_marker,
)
from .target_semantics_reference import BattleTargetContext, EntitySnapshot, resolve_target_payload
from .toughness_break_reference import ToughnessState, apply_toughness_damage


class SemanticExecutionError(DynamicValueSemanticError):
    """A compiled behavior cannot execute under the declared reference scope."""


EXECUTABLE_OPERATION_CONTEXT_REQUIREMENTS: Mapping[str, tuple[str, ...]] = {
    "CONDITIONAL": ("Predicate payload", "PredicateContext providers", "compiled child operation contexts"),
    "PREDICATE": ("Predicate payload", "PredicateContext providers"),
    "HEAL_REQUEST": ("target resolution", "DynamicValue scope/hash inputs", "target SurvivalState"),
    "MODIFY_PROPERTY_STACK": ("target resolution", "DynamicValue scope/hash inputs", "PropertyState"),
    "SET_DYNAMIC_VALUE": ("scope owner resolution", "DynamicValue key/value inputs or selected state read", "DynamicValueStore", "explicit ALIVE callback ModifierInstance identity for SetDynamicValueByModifierValue Layer reads", "selected ModifierOwnerEntity SurvivalState.max_hp; ParamEntity/ParamEntity2/SnapshotPropertyEntity RuntimeEntity.attack; Caster/SnapshotPropertyEntity RuntimeEntity.break_damage_added_ratio; or Caster RuntimeEntity.status_probability_base for SetDynamicValueByProperty", "unique ALIVE ModifierOwnerEntity instance named by SetModifierDynamicValue"),
    "DEFINE_DYNAMIC_VALUE": ("scope owner resolution", "DynamicValue key/value inputs", "DynamicValueStore"),
    "ADD_MODIFIER": ("target resolution", "explicit ModifierDefinition catalog", "caster runtime id", "optional modifier-local DynamicValues"),
    "REMOVE_MODIFIER": ("target resolution or explicit callback ModifierInstance identity", "ModifierInstance state", "dirty-removal lifecycle boundary"),
    "DAMAGE_REQUEST": ("damage source stats", "target resolution", "DamageMultiplierContext", "optional ToughnessCommitContext for selected normal stance only"),
    "MODIFY_WEAKNESS": ("target resolution", "entity weakness state"),
    "MODIFY_TEAM_SP": ("target resolution", "shared TeamSkillPointState", "DynamicValue scope/hash inputs"),
    "DELAY_ACTION": ("target resolution", "per-target ActionDelayState", "fixed or decoded PostfixExpr AddNormalizedValue", "DynamicValue scope/hash inputs for dynamic delay", "selected scheduler action-delay commit boundary"),
    "ACTION_COMPLETION_MARKER": ("explicit action task identity", "existing EXECUTING TaskStep", "selected scheduler task-success boundary"),
    "DAMAGE_COMPLETION_MARKER": ("explicit damage task identity", "existing EXECUTING TaskStep", "selected scheduler damage-task-success boundary"),
    "ACTION_START_MARKER": ("explicit action task identity", "existing READY TaskStep", "selected scheduler task-executing boundary"),
    "INSERT_ACTION": ("single explicit Caster owner", "strict TurnInsertAbility payload", "immutable pending inserted-action queue"),
}


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise SemanticExecutionError(f"non-numeric runtime value {value!r}") from error


def _fixed_nonnegative_integral_lifetime(value: Any, operation_id: Any) -> int:
    """Decode the compiler-approved fixed LifeTime payload defensively."""
    if not isinstance(value, Mapping) or set(value) != {"IsDynamic", "FixedValue"} or value.get("IsDynamic") is not False:
        raise SemanticExecutionError(f"{operation_id}: fixed LifeTime payload is unsupported")
    fixed = value.get("FixedValue")
    raw = fixed.get("Value") if isinstance(fixed, Mapping) and set(fixed) == {"Value"} else None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise SemanticExecutionError(f"{operation_id}: fixed LifeTime must be a non-negative integer")
    return raw


def _fixed_positive_integral_lifetime(value: Any, operation_id: Any) -> int:
    result = _fixed_nonnegative_integral_lifetime(value, operation_id)
    if result <= 0:
        raise SemanticExecutionError(f"{operation_id}: fixed LifeTime must be positive")
    return result


def _fixed_one_chance(value: Any, operation_id: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != {"IsDynamic", "FixedValue"} or value.get("IsDynamic") is not False:
        raise SemanticExecutionError(f"{operation_id}: Chance must be a fixed certainty")
    fixed = value.get("FixedValue")
    raw = fixed.get("Value") if isinstance(fixed, Mapping) and set(fixed) == {"Value"} else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw != 1:
        raise SemanticExecutionError(f"{operation_id}: Chance must equal fixed 1")


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
    break_damage_added_ratio: Decimal = Decimal("0")
    status_probability_base: Decimal = Decimal("0")
    speed: Decimal = Decimal("0")
    ordinary_action_eligible: bool = True
    toughness: ToughnessState | None = None
    weaknesses: tuple[str, ...] = ()

    def snapshot(self) -> EntitySnapshot:
        return EntitySnapshot(
            entity_id=self.entity_id,
            team=self.team,
            alive=self.survival.alive,
            selectable=self.selectable,
            position=self.position,
        )


@dataclass(frozen=True)
class TeamSkillPointState:
    """Immutable shared BP/skill-point holder for one battle team.

    ``ModifySPNew`` is targeted at an entity alias in content, but the local
    MVP evidence identifies its write holder as ``SkillPointEntity``.  The
    selected reference model therefore resolves the target to its team and
    commits the positive contribution to this shared holder.
    """

    current: Decimal
    maximum: Decimal

    def __post_init__(self) -> None:
        if self.maximum < 0:
            raise SemanticExecutionError("team skill-point maximum cannot be negative")
        if not Decimal("0") <= self.current <= self.maximum:
            raise SemanticExecutionError("team skill points must be within [0, maximum]")

    def add_positive(self, delta: Decimal) -> "TeamSkillPointState":
        """Apply only the positive post-commit contribution and clamp it."""
        return replace(self, current=min(self.maximum, self.current + max(Decimal("0"), delta)))


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
class PendingInsertedAction:
    """A source-accurate action insertion before scheduler arbitration.

    The selected bridge preserves that an ability was inserted, who inserted
    it, the source task order and its declared priority.  It deliberately does
    not select the ability target, arbitrate equal priorities, advance AV, or
    execute the ability.  Those are separate scheduler contracts.
    """

    enqueue_index: int
    operation_id: str
    owner_id: str
    spec: InsertedActionSpec

    def as_json(self) -> dict[str, Any]:
        return {
            "enqueue_index": self.enqueue_index,
            "operation_id": self.operation_id,
            "owner_id": self.owner_id,
            "ability_name": self.spec.ability_name,
            "ability_target": self.spec.ability_target,
            "auto_cast": self.spec.auto_cast,
            "auto_cast_target": self.spec.auto_cast_target,
            "insert_priority": self.spec.insert_priority,
            "show_in_action_bar": self.spec.show_in_action_bar,
            "can_run_on_unselectable_target": self.spec.can_run_on_unselectable_target,
            "can_run_after_fight_finish": self.spec.can_run_after_fight_finish,
            "custom_tags": list(self.spec.custom_tags),
            "raw_payload": self.spec.raw_payload,
        }


@dataclass(frozen=True)
class SchedulerCandidateState:
    """Lossless pre-arbitration view of the currently known scheduler inputs.

    Only ordinary property-38 candidates have a closed ordering model.  Pending
    inserted actions remain source-order records; no priority, target, AV or
    turn-consumption policy is inferred from this view.
    """

    ordinary_candidate_ids: tuple[str, ...]
    pending_inserted_actions: tuple[PendingInsertedAction, ...]
    arbitration_status: str = "UNRESOLVED_PENDING_INSERT_ACTION_ARBITRATION"

    def as_json(self) -> dict[str, Any]:
        return {
            "ordinary_candidate_ids": list(self.ordinary_candidate_ids),
            "pending_inserted_actions": [item.as_json() for item in self.pending_inserted_actions],
            "arbitration_status": self.arbitration_status,
        }


@dataclass(frozen=True)
class ReferenceBattleState:
    """Immutable state consumed by all first-bridge semantic adapters."""

    entities: Mapping[str, RuntimeEntity]
    dynamic_store: DynamicValueStore = DynamicValueStore.empty()
    property_states: Mapping[str, PropertyState] = field(default_factory=dict)
    modifier_instances: Mapping[str, tuple[ModifierInstance, ...]] = field(default_factory=dict)
    team_skill_points: Mapping[str, TeamSkillPointState] = field(default_factory=dict)
    special_resources: Mapping[str, Decimal] = field(default_factory=dict)
    action_delays: Mapping[str, ActionDelayState] = field(default_factory=dict)
    action_tasks: Mapping[str, TaskStep] = field(default_factory=dict)
    damage_tasks: Mapping[str, TaskStep] = field(default_factory=dict)
    pending_inserted_actions: tuple[PendingInsertedAction, ...] = ()
    ordinary_turn_timeline: OrdinaryTurnTimeline | None = None
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

    def team_skill_point_state(self, team: str) -> TeamSkillPointState:
        try:
            return self.team_skill_points[team]
        except KeyError as error:
            raise SemanticExecutionError(f"team {team!r} has no shared skill-point holder") from error

    def replace_team_skill_point_state(self, team: str, value: TeamSkillPointState) -> "ReferenceBattleState":
        states = dict(self.team_skill_points)
        states[team] = value
        return replace(self, team_skill_points=states)

    def action_delay_state(self, entity_id: str) -> ActionDelayState:
        self.entity(entity_id)
        return self.action_delays.get(entity_id, ActionDelayState(Decimal("0")))

    def replace_action_delay_state(self, entity_id: str, value: ActionDelayState) -> "ReferenceBattleState":
        self.entity(entity_id)
        states = dict(self.action_delays)
        states[entity_id] = value
        return replace(self, action_delays=states)

    def action_task(self, task_id: str) -> TaskStep:
        try:
            return self.action_tasks[task_id]
        except KeyError as error:
            raise SemanticExecutionError(f"unknown scheduler action task {task_id!r}") from error

    def replace_action_task(self, task: TaskStep) -> "ReferenceBattleState":
        tasks = dict(self.action_tasks)
        tasks[task.task_id] = task
        return replace(self, action_tasks=tasks)

    def damage_task(self, task_id: str) -> TaskStep:
        try:
            return self.damage_tasks[task_id]
        except KeyError as error:
            raise SemanticExecutionError(f"unknown scheduler damage task {task_id!r}") from error

    def replace_damage_task(self, task: TaskStep) -> "ReferenceBattleState":
        tasks = dict(self.damage_tasks)
        tasks[task.task_id] = task
        return replace(self, damage_tasks=tasks)

    def append_inserted_action(self, action: PendingInsertedAction) -> "ReferenceBattleState":
        if action.enqueue_index != len(self.pending_inserted_actions):
            raise SemanticExecutionError("inserted action enqueue_index must equal the current pending queue length")
        return replace(self, pending_inserted_actions=self.pending_inserted_actions + (action,))

    def replace_ordinary_turn_timeline(self, timeline: OrdinaryTurnTimeline) -> "ReferenceBattleState":
        for entity_id in timeline.action_order:
            self.entity(entity_id)
        return replace(self, ordinary_turn_timeline=timeline)

    def ordinary_eligible_entity_ids(self) -> tuple[str, ...]:
        """Project the closed ordinary action domain from immutable state.

        The ordinary property-38 timeline retains historical action-list order,
        including entities that may subsequently die.  This projection removes
        only entities explicitly not participating in the ordinary domain or
        no longer alive.  Pending inserted actions and behavior-level delay
        modifiers remain separate scheduler state and cannot enter through
        this method.
        """
        timeline = self.ordinary_turn_timeline
        if timeline is None:
            raise SemanticExecutionError("ordinary eligibility requires an initialized ordinary timeline")
        return tuple(
            entity_id
            for entity_id in timeline.action_order
            if self.entity(entity_id).ordinary_action_eligible and self.entity(entity_id).survival.alive
        )

    def scheduler_candidate_state(self) -> SchedulerCandidateState:
        """Return ordinary and inserted candidate categories without selection.

        This is the composition boundary after queue creation and before any
        unclosed inserted-action arbitration.  In particular, ActionDelayState
        modifiers remain behavior-level state and are intentionally absent.
        """
        timeline = self.ordinary_turn_timeline
        if timeline is None:
            raise SemanticExecutionError("scheduler candidate state requires an initialized ordinary timeline")
        ordinary = ordered_ordinary_candidates(timeline, self.ordinary_eligible_entity_ids())
        return SchedulerCandidateState(
            ordinary_candidate_ids=ordinary,
            pending_inserted_actions=self.pending_inserted_actions,
        )

    def target_context(self, context: "ExecutionContext") -> BattleTargetContext:
        return BattleTargetContext(
            entities={key: entity.snapshot() for key, entity in self.entities.items()},
            caster_id=context.caster_id,
            ability_target_id=context.ability_target_id,
            modifier_owner_id=context.modifier_owner_id,
            param_entity_ids=context.param_entity_ids,
            param_entity2_ids=context.param_entity2_ids,
            damage_attacker_id=context.damage_attacker_id,
            damage_defender_id=context.damage_defender_id,
            current_turn_action_entity_id=context.current_turn_action_entity_id,
            current_turn_owner_id=context.current_turn_owner_id,
            snapshot_property_entity_id=context.snapshot_property_entity_id,
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
                    "break_damage_added_ratio": str(entity.break_damage_added_ratio),
                    "status_probability_base": str(entity.status_probability_base),
                    "speed": str(entity.speed),
                    "ordinary_action_eligible": entity.ordinary_action_eligible,
                    "toughness": None if entity.toughness is None else dict(entity.toughness.as_json()),
                    "weaknesses": list(entity.weaknesses),
                }
                for key, entity in sorted(self.entities.items())
            },
            "dynamic_store": self.dynamic_store.snapshot(),
            "property_states": {key: value.as_json() for key, value in sorted(self.property_states.items())},
            "modifier_instances": {
                key: [
                    {"instance_id": item.instance_id, "name": item.name, "stacking": item.stacking, "state": item.state.name,
                     "current_life": item.current_life, "count": item.count, "caster_runtime_id": item.caster_runtime_id,
                     "layer": item.layer, "dynamic_values": {key: str(value) for key, value in sorted(item.dynamic_values.items())}}
                    for item in values
                ]
                for key, values in sorted(self.modifier_instances.items())
            },
            "team_skill_points": {
                key: {"current": str(value.current), "maximum": str(value.maximum)}
                for key, value in sorted(self.team_skill_points.items())
            },
            "special_resources": {key: str(value) for key, value in sorted(self.special_resources.items())},
            "action_delays": {
                key: {"normalized_value": str(value.normalized_value), "skip_target_turn": value.skip_target_turn}
                for key, value in sorted(self.action_delays.items())
            },
            "action_tasks": {
                key: {"state": value.state.name, "owner_id": value.owner_id}
                for key, value in sorted(self.action_tasks.items())
            },
            "damage_tasks": {
                key: {"state": value.state.name, "owner_id": value.owner_id}
                for key, value in sorted(self.damage_tasks.items())
            },
            "pending_inserted_actions": [action.as_json() for action in self.pending_inserted_actions],
            "ordinary_turn_timeline": None if self.ordinary_turn_timeline is None else self.ordinary_turn_timeline.as_json(),
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
    modifier_instance_id: str | None = None
    param_entity_ids: tuple[str, ...] = ()
    param_entity2_ids: tuple[str, ...] = ()
    damage_attacker_id: str | None = None
    damage_defender_id: str | None = None
    ability_target_id: str | None = None
    ability_target_ids: tuple[str, ...] = ()
    skill_target_ids: tuple[str, ...] = ()
    attack_target_ids: tuple[str, ...] = ()
    current_turn_action_entity_id: str | None = None
    current_turn_owner_id: str | None = None
    snapshot_property_entity_id: str | None = None
    action_task_id: str | None = None
    damage_task_id: str | None = None
    dynamic_hash_values: Mapping[str, Any] = field(default_factory=dict)
    dynamic_scope_owners: Mapping[str, str] = field(default_factory=dict)
    skill_type: str = ""
    skill_name: str = ""
    modifier_callback_name: str = ""
    caster_runtime_id: int | None = None
    modifier_catalog: Mapping[str, ModifierDefinition] = field(default_factory=dict)
    damage_source_id: str | None = None
    damage_multiplier_contexts: Mapping[str, DamageMultiplierContext] = field(default_factory=dict)
    toughness_contexts: Mapping[str, "ToughnessCommitContext"] = field(default_factory=dict)
    crit_rate: Decimal = Decimal("0")
    crit_damage: Decimal = Decimal("0")

    def default_owner_id(self) -> str:
        for candidate in (self.caster_id, self.modifier_owner_id, self.ability_target_id):
            if candidate:
                return candidate
        raise SemanticExecutionError("context has no caster, modifier owner or ability target")


@dataclass(frozen=True)
class ToughnessCommitContext:
    """Explicit inputs for the stance part of a mixed normal request.

    Break Effect and elemental-break scaling are not inferred from a target
    alias or an external fixture.  Weakness may be explicitly supplied, or
    derived from the immutable entity weakness state when this field is
    ``None``. The behavior adapter may execute a StanceValue only when the
    scenario/reference context supplies the remaining target inputs.
    """

    weakness_active: bool | None = None
    elemental_break_scaling: Decimal = Decimal("1")
    special_scaling: Decimal = Decimal("1")
    break_effect: Decimal = Decimal("0")


@dataclass(frozen=True)
class ExecutionResult:
    state: ReferenceBattleState
    trace: tuple[Mapping[str, Any], ...]


class SemanticExecutor:
    """Execute ``EXECUTABLE_REFERENCE`` operations in deterministic order."""

    @classmethod
    def executable_operation_contract(cls) -> Mapping[str, tuple[str, ...]]:
        """Expose the exact handler/context surface for compiler audits."""
        return EXECUTABLE_OPERATION_CONTEXT_REQUIREMENTS

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

    def advance_ordinary_after_completed_action(
        self,
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Compose an already-completed ordinary task with DYN-MVP-AV-001.

        This method is intentionally a global scheduler boundary rather than
        a compiler operation.  It requires the explicit action marker to have
        committed first and ignores pending inserted actions and behavior-level
        ActionDelayState modifiers until their arbitration semantics close.
        """
        task_id = context.action_task_id
        if not task_id:
            raise SemanticExecutionError("ordinary action completion requires explicit action_task_id")
        task = state.action_task(task_id)
        if task.state is not TaskState.SUCCESS or not task.owner_id:
            raise SemanticExecutionError("ordinary action completion requires a SUCCESS action task with an owner")
        timeline = state.ordinary_turn_timeline
        if timeline is None:
            raise SemanticExecutionError("ordinary action completion requires an initialized ordinary timeline")
        eligible = state.ordinary_eligible_entity_ids()
        speeds = {entity_id: state.entity(entity_id).speed for entity_id in eligible}
        transition = complete_ordinary_action(
            timeline,
            actor_id=task.owner_id,
            eligible_ids=eligible,
            speeds=speeds,
        )
        current = state.replace_ordinary_turn_timeline(transition.timeline)
        return ExecutionResult(current, ({
            "disposition": "ORDINARY_ACTION_RECHARGED_AND_NEXT_SELECTED",
            "completed_task_id": task_id,
            "recharged_actor_id": transition.recharged_actor_id,
            "recharged_delay": str(transition.recharged_delay),
            "candidate_order_before_advance": list(transition.ordered_candidates_before_advance),
            "selected_delay": str(transition.selected_delay),
            "next_actor_id": transition.selected_actor_id,
            "elapsed_action_delay": str(transition.timeline.elapsed_action_delay),
            "turn_index": transition.timeline.turn_index,
            "eligible_entity_ids": list(eligible),
            "eligible_domain_source": "ReferenceBattleState.ordinary_eligible_entity_ids",
            "pending_inserted_actions_ignored": len(current.pending_inserted_actions),
        },))

    def scheduler_candidate_state(self, state: ReferenceBattleState) -> SchedulerCandidateState:
        """Read the deterministic candidate categories without arbitrating them."""
        return state.scheduler_candidate_state()

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
        if kind == "MODIFY_WEAKNESS":
            return self._execute_attach_weakness(operation, state, context)
        if kind == "MODIFY_TEAM_SP":
            return self._execute_modify_team_sp(operation, state, context)
        if kind == "DELAY_ACTION":
            return self._execute_delay_action(operation, state, context)
        if kind == "ACTION_COMPLETION_MARKER":
            return self._execute_action_completion_marker(operation, state, context)
        if kind == "DAMAGE_COMPLETION_MARKER":
            return self._execute_damage_completion_marker(operation, state, context)
        if kind == "ACTION_START_MARKER":
            return self._execute_action_start_marker(operation, state, context)
        if kind == "INSERT_ACTION":
            return self._execute_insert_action(operation, state, context)
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
        if operation.get("source_type") == "RPG.GameCore.SetModifierDynamicValue":
            return self._execute_set_modifier_dynamic_value(operation, state, context)
        if operation.get("source_type") == "RPG.GameCore.SetDynamicValueByModifierValue":
            if "ReadTargetType" not in operation.get("arguments", {}):
                return self._execute_set_dynamic_value_from_own_modifier_layer(operation, state, context)
            return self._execute_set_dynamic_value_from_modifier_layer(operation, state, context)
        if operation.get("source_type") == "RPG.GameCore.SetDynamicValueByProperty":
            if operation.get("arguments", {}).get("Value") == "Attack":
                return self._execute_set_dynamic_value_from_entity_attack(operation, state, context)
            if operation.get("arguments", {}).get("Value") == "BreakDamageAddedRatio":
                return self._execute_set_dynamic_value_from_break_damage_added_ratio(operation, state, context)
            if operation.get("arguments", {}).get("Value") == "StatusProbabilityBase":
                return self._execute_set_dynamic_value_from_status_probability_base(operation, state, context)
            return self._execute_set_dynamic_value_from_max_hp(operation, state, context)
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

    def _execute_set_modifier_dynamic_value(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Overwrite one named, live modifier-local DynamicValue.

        The selected source form carries neither a target selector nor a
        mutation function.  It is therefore deliberately narrower than a
        general cross-modifier API: the callback ModifierOwnerEntity must be
        explicit, and exactly one ``ALIVE`` instance with ``ModifierName``
        must exist on it.  Pending, removed, missing, and ambiguous instances
        remain hard failures rather than guessed lifecycle behavior.
        """
        arguments = operation.get("arguments", {})
        owner_id = context.modifier_owner_id
        if not owner_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: SetModifierDynamicValue requires modifier_owner_id")
        state.entity(owner_id)
        modifier = arguments.get("ModifierName", {})
        name = modifier.get("Value") if isinstance(modifier, Mapping) else None
        if not isinstance(name, str) or not name:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: SetModifierDynamicValue has no ModifierName")
        matches = tuple(
            item
            for item in state.modifiers(owner_id)
            if item.name == name and item.state == ModifierState.ALIVE
        )
        if len(matches) != 1:
            raise SemanticExecutionError(
                f"{operation.get('operation_id')}: SetModifierDynamicValue requires exactly one ALIVE {name!r} on {owner_id!r}, got {len(matches)}"
            )
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = self._evaluate_value(arguments.get("NewValue"), state, context)
        instance = matches[0]
        values = dict(instance.dynamic_values)
        values[key] = value
        replacement = replace(instance, dynamic_values=values)
        updated = tuple(replacement if item.instance_id == instance.instance_id else item for item in state.modifiers(owner_id))
        return ExecutionResult(state.replace_modifiers(owner_id, updated), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "MODIFIER_LOCAL_DYNAMIC_VALUE_SET",
            "owner_id": owner_id,
            "modifier_instance_id": instance.instance_id,
            "modifier_name": name,
            "key": key,
            "value": str(value),
        },))

    def _execute_set_dynamic_value_from_modifier_layer(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Store a selected current ModifierInstance.Layer projection.

        Local evidence distinguishes the runtime ``Layer`` getter from the
        base modifier ``Count`` field.  The bridge therefore requires an
        explicit current instance identity and never substitutes Count or a
        guessed default layer.  Only the compiler-validated
        ModifierOwnerEntity/Layer shape reaches this handler.
        """
        arguments = operation.get("arguments", {})
        read_targets = self._resolve_targets(arguments.get("ReadTargetType"), state, context)
        if len(read_targets) != 1:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier Layer read requires one owner target")
        if not context.modifier_instance_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier Layer read requires modifier_instance_id")
        instance = next((item for item in state.modifiers(read_targets[0]) if item.instance_id == context.modifier_instance_id), None)
        if instance is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier instance is not owned by read target")
        if context.modifier_id and instance.name != context.modifier_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier instance name does not match callback context")
        if instance.layer is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier Layer is not supplied by ReferenceBattleState")
        if isinstance(instance.layer, bool) or not isinstance(instance.layer, int) or instance.layer < 0:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: modifier Layer must be a non-negative integer")
        multiplier = self._evaluate_value(arguments.get("Multiplier"), state, context)
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = Decimal(instance.layer) * multiplier
        transition = state.dynamic_store.set_value(owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET_FROM_MODIFIER_LAYER",
            "owner_id": owner_id,
            "key": key,
            "value": str(value),
            "read_target_id": read_targets[0],
            "modifier_instance_id": instance.instance_id,
            "modifier_layer": instance.layer,
        },))

    def _execute_set_dynamic_value_from_own_modifier_layer(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Store a targetless callback modifier's own explicit Layer.

        The one selected source payload carries no ``ReadTargetType``.  It is
        therefore not safely equivalent to a named/targeted modifier lookup:
        the bridge binds it exclusively to the current callback instance on
        the explicit ModifierOwnerEntity.  The write owner still follows the
        selected DynamicValue scope (the source's default ContextCaster).
        """
        owner_id = context.modifier_owner_id
        instance_id = context.modifier_instance_id
        if not owner_id or not instance_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: targetless modifier Layer read requires modifier_owner_id and modifier_instance_id")
        state.entity(owner_id)
        instance = next((item for item in state.modifiers(owner_id) if item.instance_id == instance_id), None)
        if instance is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: callback modifier instance is not owned by modifier_owner_id")
        if context.modifier_id and instance.name != context.modifier_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: callback modifier instance name does not match modifier_id")
        if instance.state != ModifierState.ALIVE:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: targetless modifier Layer read requires an ALIVE callback instance")
        if instance.layer is None or isinstance(instance.layer, bool) or not isinstance(instance.layer, int) or instance.layer < 0:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: callback modifier Layer must be a non-negative integer")
        arguments = operation.get("arguments", {})
        multiplier = self._evaluate_value(arguments.get("Multiplier"), state, context)
        write_owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = Decimal(instance.layer) * multiplier
        transition = state.dynamic_store.set_value(write_owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET_FROM_OWN_MODIFIER_LAYER",
            "owner_id": write_owner_id,
            "key": key,
            "value": str(value),
            "modifier_owner_id": owner_id,
            "modifier_instance_id": instance.instance_id,
            "modifier_layer": instance.layer,
        },))

    def _execute_set_dynamic_value_from_max_hp(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Store a selected ModifierOwnerEntity ``MaxHP`` state projection.

        ``SetDynamicValueByProperty`` has broader stat/property semantics than
        this bridge.  Its sole accepted source shape reads the immutable
        survival max-HP field of exactly one ModifierOwnerEntity.  It does not
        materialize contribution slots, derive any other stat, or guess a
        multi-target reduction policy.
        """
        arguments = operation.get("arguments", {})
        read_targets = self._resolve_targets(arguments.get("ReadTargetType"), state, context)
        if len(read_targets) != 1:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: MaxHP read requires one owner target")
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = state.entity(read_targets[0]).survival.max_hp
        transition = state.dynamic_store.set_value(owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET_FROM_MAX_HP",
            "owner_id": owner_id,
            "key": key,
            "value": str(value),
            "read_target_id": read_targets[0],
        },))

    def _execute_set_dynamic_value_from_entity_attack(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Store one selected immutable Attack read from an explicit alias.

        This packet does not materialize property contributions or resolve the
        broader property system.  It copies only the explicitly supplied
        ParamEntity/ParamEntity2/SnapshotPropertyEntity runtime entity's
        already-materialized ``attack`` leaf into the existing selected
        DynamicValue scope.  Snapshot creation/timing stays outside this
        read-only bridge and must be provided by the caller.
        """
        arguments = operation.get("arguments", {})
        read_target = arguments.get("ReadTargetType")
        alias = read_target.get("Alias") if isinstance(read_target, Mapping) else None
        if alias not in {"ParamEntity", "ParamEntity2", "SnapshotPropertyEntity"}:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: Attack read requires ParamEntity, ParamEntity2 or SnapshotPropertyEntity")
        read_targets = self._resolve_targets(read_target, state, context)
        if len(read_targets) != 1:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: Attack read requires one source entity")
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = state.entity(read_targets[0]).attack
        transition = state.dynamic_store.set_value(owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET_FROM_ENTITY_ATTACK",
            "owner_id": owner_id,
            "key": key,
            "value": str(value),
            "read_target_id": read_targets[0],
            "read_target_alias": alias,
        },))

    def _execute_set_dynamic_value_from_break_damage_added_ratio(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Copy one explicit materialized BreakDamageAddedRatio property.

        This is a state-read bridge only: it neither calculates Break damage
        nor reconstructs when a snapshot is created.  Caster and
        SnapshotPropertyEntity are intentionally distinct alias inputs, while
        both provide their already-materialized ratio leaf to DynamicValue.
        """
        arguments = operation.get("arguments", {})
        read_target = arguments.get("ReadTargetType")
        alias = read_target.get("Alias") if isinstance(read_target, Mapping) else None
        if alias not in {"Caster", "SnapshotPropertyEntity"}:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: BreakDamageAddedRatio requires Caster or SnapshotPropertyEntity")
        read_targets = self._resolve_targets(read_target, state, context)
        if len(read_targets) != 1:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: BreakDamageAddedRatio requires one source entity")
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = state.entity(read_targets[0]).break_damage_added_ratio
        transition = state.dynamic_store.set_value(owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET_FROM_BREAK_DAMAGE_ADDED_RATIO",
            "owner_id": owner_id,
            "key": key,
            "value": str(value),
            "read_target_id": read_targets[0],
            "read_target_alias": alias,
        },))

    def _execute_set_dynamic_value_from_status_probability_base(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Copy the current caster's explicitly materialized effect-hit leaf.

        ``StatusProbabilityBase`` is represented separately from the external
        stat catalog or property contribution calculation.  The executor only
        reads an input the BattleState has already materialized for Caster.
        """
        arguments = operation.get("arguments", {})
        read_target = arguments.get("ReadTargetType")
        alias = read_target.get("Alias") if isinstance(read_target, Mapping) else None
        if alias != "Caster":
            raise SemanticExecutionError(f"{operation.get('operation_id')}: StatusProbabilityBase requires Caster")
        read_targets = self._resolve_targets(read_target, state, context)
        if len(read_targets) != 1:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: StatusProbabilityBase requires one caster")
        owner_id = self._scope_owner(operation, state, context)
        key = dynamic_key_from_payload(arguments.get("DynamicKey"))
        value = state.entity(read_targets[0]).status_probability_base
        transition = state.dynamic_store.set_value(owner_id, key, value)
        return ExecutionResult(replace(state, dynamic_store=transition.store), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DYNAMIC_VALUE_SET_FROM_STATUS_PROBABILITY_BASE",
            "owner_id": owner_id,
            "key": key,
            "value": str(value),
            "read_target_id": read_targets[0],
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
        if "AliveOnly" in arguments and arguments.get("AliveOnly") is not False:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: selected AddModifier bridge accepts only AliveOnly=false")
        current_life = None
        if "LifeTime" in arguments:
            target_payload = operation.get("target") if isinstance(operation.get("target"), Mapping) else {}
            if set(arguments) == {"ModifierName", "LifeTime"}:
                if target_payload.get("Alias") != "ModifierOwnerEntity":
                    raise SemanticExecutionError(f"{operation.get('operation_id')}: fixed LifeTime AddModifier requires ModifierOwnerEntity")
                current_life = _fixed_nonnegative_integral_lifetime(arguments.get("LifeTime"), operation.get("operation_id"))
            elif set(arguments) == {"Chance", "DynamicValues", "InheritCaster", "LifeTime", "ModifierName"}:
                if target_payload.get("Alias") != "ParamEntity":
                    raise SemanticExecutionError(f"{operation.get('operation_id')}: selected inherited fixed LifeTime AddModifier requires ParamEntity")
                if arguments.get("InheritCaster") != "CasterSelf":
                    raise SemanticExecutionError(f"{operation.get('operation_id')}: selected inherited AddModifier requires CasterSelf")
                _fixed_one_chance(arguments.get("Chance"), operation.get("operation_id"))
                current_life = _fixed_positive_integral_lifetime(arguments.get("LifeTime"), operation.get("operation_id"))
            else:
                raise SemanticExecutionError(f"{operation.get('operation_id')}: LifeTime AddModifier argument shape is unsupported")
        modifier = arguments.get("ModifierName", {})
        name = modifier.get("Value") if isinstance(modifier, Mapping) else None
        definition = context.modifier_catalog.get(str(name))
        if definition is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: Modifier definition {name!r} is not in ExecutionContext")
        targets = self._resolve_targets(operation.get("target"), state, context)
        raw_dynamic_values = arguments.get("DynamicValues", {})
        if not isinstance(raw_dynamic_values, Mapping):
            raise SemanticExecutionError(f"{operation.get('operation_id')}: DynamicValues is not a mapping")
        dynamic_values = {
            str(key): self._evaluate_value(value, state, context)
            for key, value in raw_dynamic_values.items()
            if isinstance(key, str) and key and isinstance(value, Mapping)
        }
        if len(dynamic_values) != len(raw_dynamic_values):
            raise SemanticExecutionError(f"{operation.get('operation_id')}: invalid modifier DynamicValues payload")
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
                current_life=current_life,
                count=None,
                dynamic_values=dynamic_values,
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
                "dynamic_value_keys": sorted(dynamic_values),
                "alive_only": arguments.get("AliveOnly"),
                "current_life": current_life,
                "inherit_caster": arguments.get("InheritCaster"),
            })
        return ExecutionResult(current, tuple(trace))

    def _execute_delay_action(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Commit one selected normalized-delay transition per resolved target.

        This adapter deliberately stops at the scheduler reference's
        ``ActionDelayState`` boundary.  It applies only compiler-approved
        ModifyActionDelay add, SetActionDelay set or ResetActionDelay reset
        payloads. Dynamic values resolve only through the existing explicit
        DynamicValue context. The adapter does
        not recalculate AV, choose the next actor, consume a turn, or infer a
        native interrupt ordering.
        """
        targets = self._resolve_targets(operation.get("target"), state, context)
        if not targets:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: ModifyActionDelay resolved no targets")
        current = state
        trace: list[Mapping[str, Any]] = []
        for target_id in targets:
            transition = apply_delay_operation(
                operation,
                current.action_delay_state(target_id),
                dynamic_resolver=lambda key: self._resolve_dynamic(current, context, key),
            )
            current = current.replace_action_delay_state(target_id, transition.delay)
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": "ACTION_DELAY_MODIFIED",
                "target_id": target_id,
                "action": transition.action,
                "normalized_value": str(transition.delay.normalized_value),
                "skip_target_turn": transition.delay.skip_target_turn,
            })
        return ExecutionResult(current, tuple(trace))

    def _execute_action_completion_marker(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Commit a no-argument ``SkillPerformFinish`` task-success boundary.

        The selected scheduler reference proves only the task-state marker:
        the caller supplies the concrete action task already in ``EXECUTING``
        state, and this boundary turns it into ``SUCCESS``.  AV recharge,
        next-actor selection, turn consumption and arbitration remain outside
        this adapter.
        """
        task_id = context.action_task_id
        if not task_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: SkillPerformFinish requires explicit action_task_id")
        before = state.action_task(task_id)
        if before.state is not TaskState.EXECUTING:
            raise SemanticExecutionError(
                f"{operation.get('operation_id')}: SkillPerformFinish requires EXECUTING action task {task_id!r}"
            )
        transition = trace_completion_marker(operation, task_id=task_id)
        committed = TaskStep(task_id=transition.task_id, state=transition.state, owner_id=before.owner_id)
        current = state.replace_action_task(committed)
        return ExecutionResult(current, ({
            "operation_id": operation.get("operation_id"),
            "disposition": "ACTION_COMPLETION_MARKED_SUCCESS",
            "task_id": task_id,
            "previous_state": before.state.name,
            "state": committed.state.name,
            "owner_id": committed.owner_id,
        },))

    def _execute_action_start_marker(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Commit a no-argument ``SkillExecutionStart`` task-start boundary.

        The selected model consumes neither a turn nor a timeline slot.  It
        only makes an already-created ``READY`` action task observable as
        ``EXECUTING``; all action selection and scheduler policies remain
        external to this narrow reference bridge.
        """
        task_id = context.action_task_id
        if not task_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: SkillExecutionStart requires explicit action_task_id")
        before = state.action_task(task_id)
        if before.state is not TaskState.READY:
            raise SemanticExecutionError(
                f"{operation.get('operation_id')}: SkillExecutionStart requires READY action task {task_id!r}"
            )
        transition = trace_completion_marker(operation, task_id=task_id)
        committed = TaskStep(task_id=transition.task_id, state=transition.state, owner_id=before.owner_id)
        current = state.replace_action_task(committed)
        return ExecutionResult(current, ({
            "operation_id": operation.get("operation_id"),
            "disposition": "ACTION_MARKED_EXECUTING",
            "task_id": task_id,
            "previous_state": before.state.name,
            "state": committed.state.name,
            "owner_id": committed.owner_id,
        },))

    def _execute_insert_action(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Append one strict ``TurnInsertAbility`` record for later arbitration.

        This is intentionally not an action execution path.  The queue retains
        source task order and the declared priority only; it does not resolve
        the inserted ability's inner target, reset AV, consume a turn, choose
        the next actor, or arbitrate an Ultimate/FUA/extra action conflict.
        """
        targets = self._resolve_targets(operation.get("target"), state, context)
        if len(targets) != 1:
            raise SemanticExecutionError(
                f"{operation.get('operation_id')}: strict TurnInsertAbility requires one explicit Caster owner"
            )
        spec = InsertedActionSpec.from_operation(operation)
        if not spec.ability_name or spec.ability_target is None or not spec.insert_priority:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: incomplete strict TurnInsertAbility payload")
        pending = PendingInsertedAction(
            enqueue_index=len(state.pending_inserted_actions),
            operation_id=str(operation.get("operation_id")),
            owner_id=targets[0],
            spec=spec,
        )
        current = state.append_inserted_action(pending)
        return ExecutionResult(current, ({
            "operation_id": operation.get("operation_id"),
            "disposition": "ACTION_INSERTED_PENDING",
            "enqueue_index": pending.enqueue_index,
            "owner_id": pending.owner_id,
            "ability_name": spec.ability_name,
            "insert_priority": spec.insert_priority,
            "ability_target": spec.ability_target,
        },))

    def _execute_damage_completion_marker(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Commit a no-argument ``DamagePerformFinish`` damage-task boundary.

        This task state is intentionally separate from both the action task
        and the HP/toughness mutations that a prior DamageRequest may have
        performed.  The marker does not itself apply damage or choose a
        timeline transition.
        """
        task_id = context.damage_task_id
        if not task_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: DamagePerformFinish requires explicit damage_task_id")
        before = state.damage_task(task_id)
        if before.state is not TaskState.EXECUTING:
            raise SemanticExecutionError(
                f"{operation.get('operation_id')}: DamagePerformFinish requires EXECUTING damage task {task_id!r}"
            )
        transition = trace_completion_marker(operation, task_id=task_id)
        committed = TaskStep(task_id=transition.task_id, state=transition.state, owner_id=before.owner_id)
        current = state.replace_damage_task(committed)
        return ExecutionResult(current, ({
            "operation_id": operation.get("operation_id"),
            "disposition": "DAMAGE_COMPLETION_MARKED_SUCCESS",
            "task_id": task_id,
            "previous_state": before.state.name,
            "state": committed.state.name,
            "owner_id": committed.owner_id,
        },))

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
        if operation.get("source_type") == "RPG.GameCore.RemoveSelfModifier":
            return self._execute_remove_self_modifier(operation, state, context)
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

    def _execute_remove_self_modifier(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Mark exactly the callback's own live modifier for dirty removal.

        ``RemoveSelfModifier`` has no source target or name.  The selected
        reference contract therefore binds it to the callback instance, not
        to every same-named modifier on an inferred target.  Physical cleanup
        remains a later lifecycle boundary and callback/property keys stay
        attached while the instance is ``TO_BE_REMOVED``.
        """
        owner_id = context.modifier_owner_id
        instance_id = context.modifier_instance_id
        if not owner_id or not instance_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: RemoveSelfModifier requires modifier_owner_id and modifier_instance_id")
        state.entity(owner_id)
        instance = next((item for item in state.modifiers(owner_id) if item.instance_id == instance_id), None)
        if instance is None:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: callback modifier instance is not owned by modifier_owner_id")
        if context.modifier_id and instance.name != context.modifier_id:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: callback modifier instance name does not match modifier_id")
        if instance.state != ModifierState.ALIVE:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: RemoveSelfModifier requires an ALIVE callback instance")
        transition = mark_destroy(state.modifiers(owner_id), instance_id, reason=0)
        return ExecutionResult(state.replace_modifiers(owner_id, transition.instances), ({
            "operation_id": operation.get("operation_id"),
            "disposition": "MODIFIER_SELF_MARKED_FOR_DIRTY_REMOVAL",
            "owner_id": owner_id,
            "modifier_instance_id": instance_id,
            "modifier_name": instance.name,
            "lifecycle_action": transition.action,
        },))

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
        attack_type = str(attack_property.get("AttackType") or "Normal")
        stance_value = attack_property.get("StanceValue")
        has_stance = stance_value is not None
        stance_amount = self._evaluate_value(stance_value, state, context) if has_stance else None
        targets = self._resolve_targets(operation.get("target"), state, context)
        current = state
        trace: list[Mapping[str, Any]] = []
        for target_id in targets:
            multiplier_context = context.damage_multiplier_contexts.get(target_id)
            if multiplier_context is None:
                raise SemanticExecutionError(f"{operation.get('operation_id')}: missing DamageMultiplierContext for {target_id!r}")
            if attack_type == "DOT":
                amount = dot_damage(ability_amount, multiplier_context)
                disposition = "DOT_DAMAGE_COMMITTED"
            else:
                amount = normal_damage(ability_amount, multiplier_context, crit_rate=context.crit_rate, crit_damage=context.crit_damage)
                disposition = "DAMAGE_COMMITTED"
            target = current.entity(target_id)
            survival, shield_absorbed, hp_lost = target.survival.absorb(amount)
            toughness = target.toughness
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": disposition,
                "attack_type": attack_type,
                "formula_type": formula,
                "source_id": source_id,
                "target_id": target_id,
                "ability_amount": str(ability_amount),
                "amount": str(amount),
                "shield_absorbed": str(shield_absorbed),
                "hp_lost": str(hp_lost),
                "target_alive": survival.alive,
                "crit_applied": attack_type != "DOT",
            })
            if has_stance:
                toughness_context = context.toughness_contexts.get(target_id)
                if toughness_context is None:
                    raise SemanticExecutionError(f"{operation.get('operation_id')}: missing ToughnessCommitContext for {target_id!r}")
                if toughness is None:
                    raise SemanticExecutionError(f"{operation.get('operation_id')}: target {target_id!r} has no toughness state")
                weakness_active = toughness_context.weakness_active
                if weakness_active is None:
                    stance_type = attack_property.get("StanceDamageType")
                    stance_type = stance_type.get("DamageType") if isinstance(stance_type, Mapping) else None
                    damage_data = attack_property.get("DamageType")
                    damage_type = stance_type or (damage_data.get("DamageType") if isinstance(damage_data, Mapping) else None)
                    if not isinstance(damage_type, str) or not damage_type:
                        raise SemanticExecutionError(f"{operation.get('operation_id')}: state-derived weakness requires DamageType")
                    weakness_active = damage_type in target.weaknesses
                if not weakness_active or not survival.alive:
                    trace.append({
                        "operation_id": operation.get("operation_id"),
                        "disposition": "TOUGHNESS_SKIPPED",
                        "target_id": target_id,
                        "reason": "WEAKNESS_INACTIVE" if not weakness_active else "TARGET_DEAD",
                    })
                else:
                    transition = apply_toughness_damage(
                        toughness,
                        stance_amount,
                        elemental_break_scaling=toughness_context.elemental_break_scaling,
                        special_scaling=toughness_context.special_scaling,
                        break_effect=toughness_context.break_effect,
                        damage_context=multiplier_context,
                    )
                    toughness = transition.state
                    if transition.break_damage is not None:
                        survival, break_shield_absorbed, break_hp_lost = survival.absorb(transition.break_damage)
                        trace.append({
                            "operation_id": operation.get("operation_id"),
                            "disposition": "BREAK_DAMAGE_COMMITTED",
                            "target_id": target_id,
                            "amount": str(transition.break_damage),
                            "shield_absorbed": str(break_shield_absorbed),
                            "hp_lost": str(break_hp_lost),
                            "target_alive": survival.alive,
                        })
                    trace.append({
                        "operation_id": operation.get("operation_id"),
                        "disposition": transition.action,
                        "target_id": target_id,
                        "stance_amount": str(stance_amount),
                        "current_toughness": str(toughness.current_toughness),
                        "broken": toughness.broken,
                    })
            current = current.replace_entity(replace(target, survival=survival, toughness=toughness))
        return ExecutionResult(current, tuple(trace))

    def _execute_attach_weakness(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Attach explicitly named weakness types with stable de-duplication."""
        arguments = operation.get("arguments", {})
        if arguments.get("OPType") != "Attach":
            raise SemanticExecutionError(f"{operation.get('operation_id')}: unsupported weakness operation")
        weak_list = arguments.get("WeakList")
        if not isinstance(weak_list, list) or not all(isinstance(item, str) and item for item in weak_list):
            raise SemanticExecutionError(f"{operation.get('operation_id')}: invalid WeakList")
        targets = self._resolve_targets(operation.get("target"), state, context)
        current = state
        trace: list[Mapping[str, Any]] = []
        for target_id in targets:
            entity = current.entity(target_id)
            weaknesses = tuple(dict.fromkeys((*entity.weaknesses, *weak_list)))
            current = current.replace_entity(replace(entity, weaknesses=weaknesses))
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": "WEAKNESS_ATTACHED",
                "target_id": target_id,
                "weaknesses": list(weaknesses),
            })
        return ExecutionResult(current, tuple(trace))

    def _execute_modify_team_sp(
        self,
        operation: Mapping[str, Any],
        state: ReferenceBattleState,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Commit the selected positive ``ModifySPNew`` post-action gain.

        In the ordinary MVP packet an entity alias identifies the team whose
        shared ``SkillPointEntity`` changes.  It never means that the target
        entity carries a private SP pool.  Both observed source spellings,
        ``AddRatio`` and ``AddValue``, provide the positive BP contribution;
        zero or negative evaluated values deliberately make no signed write.
        Cost/pre-commit semantics remain action-level scheduler work.
        """
        arguments = operation.get("arguments", {})
        if not isinstance(arguments, Mapping):
            raise SemanticExecutionError(f"{operation.get('operation_id')}: invalid ModifySPNew arguments")
        if set(arguments) == {"AddRatio"}:
            value_payload = arguments["AddRatio"]
            source_field = "AddRatio"
        elif set(arguments) == {"AddValue"}:
            value_payload = arguments["AddValue"]
            source_field = "AddValue"
        else:
            raise SemanticExecutionError(f"{operation.get('operation_id')}: unsupported ModifySPNew payload")
        delta = self._evaluate_value(value_payload, state, context)
        target_ids = self._resolve_targets(operation.get("target"), state, context)
        current = state
        trace: list[Mapping[str, Any]] = []
        committed_teams: set[str] = set()
        for target_id in target_ids:
            team = current.entity(target_id).team
            # A collection target can include multiple units on one team;
            # ModifySPNew still writes one shared holder only once.
            if team in committed_teams:
                continue
            committed_teams.add(team)
            holder = current.team_skill_point_state(team)
            updated = holder.add_positive(delta)
            current = current.replace_team_skill_point_state(team, updated)
            trace.append({
                "operation_id": operation.get("operation_id"),
                "disposition": "TEAM_SP_COMMITTED",
                "target_id": target_id,
                "team": team,
                "source_field": source_field,
                "requested_delta": str(delta),
                "committed_delta": str(updated.current - holder.current),
                "before": str(holder.current),
                "after": str(updated.current),
                "maximum": str(holder.maximum),
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
            has_stance_weak=lambda entity, damage_type: damage_type in state.entity(entity).weaknesses,
        )
