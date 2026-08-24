# -*- coding: utf-8 -*-
"""Deterministic ordinary-scope Turn/AV runtime (Semantics 29).

Remaining delay has one source of truth: PropertyEntry property 38. The
timeline owns only list order, current actor, elapsed delay, phase, and index.
Special/immediate/insert/one-more/locked ordering is deliberately absent.
"""
from __future__ import annotations

from functools import cmp_to_key
from typing import Any, TYPE_CHECKING

from hsr_battle_agent.battle_ir.property import PropertyModifyFunction
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_ir.turns import (
    TURN_PHASE_ACTIVE,
    TURN_PHASE_READY,
    TURN_PHASE_SETTLED,
    TURN_PHASES,
    TURN_TIMELINE_SCHEMA,
    ActionCompletionBoundary,
    TurnAdvanceResult,
)
from hsr_battle_agent.battle_runtime.predicates import (
    fixpoint_is_negative,
    fixpoint_less,
)
from hsr_battle_agent.battle_runtime.property import (
    PropertyBoundarySink,
    fixedpoint_add,
    fixedpoint_subtract,
    get_property_entry,
    modify_source_zero_untransformed,
)

if TYPE_CHECKING:  # pragma: no cover
    from hsr_battle_agent.battle_sandbox.state import BattleState

SPEED_PROPERTY_ID = 32
REMAINING_ACTION_DELAY_PROPERTY_ID = 38
FIXPOINT_ZERO_RAW = 0


class TurnSemanticError(Exception):
    """Base class for explicit Turn/AV scope and state failures."""


class TurnTimelineNotInitializedError(TurnSemanticError):
    pass


class TurnCompletionRequiredError(TurnSemanticError):
    pass


class UnsupportedTurnParticipantError(TurnSemanticError):
    pass


def _require_state(state: Any) -> None:
    if not hasattr(state, "turn_timeline") or not hasattr(
        state, "entity_property_entries"
    ):
        raise TypeError("state must provide BattleState turn/property storage")


def _require_raw(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if not (-(2**63) <= value <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"{name} out of qword raw range")


def _require_nonnegative_raw(value: int, name: str) -> None:
    _require_raw(value, name)
    if fixpoint_is_negative(value):
        raise ValueError(f"{name} must be non-negative FixPoint")


def _timeline(state: Any) -> dict[str, Any]:
    _require_state(state)
    timeline = state.turn_timeline
    if not timeline:
        raise TurnTimelineNotInitializedError(
            "turn timeline is not initialized; call initialize_turn_timeline"
        )
    required = {
        "schema",
        "action_entity_runtime_ids",
        "current_actor_runtime_id",
        "elapsed_action_delay_raw",
        "turn_index",
        "phase",
        "last_completion_provenance",
    }
    if set(timeline) != required or timeline.get("schema") != TURN_TIMELINE_SCHEMA:
        raise TurnSemanticError("invalid or unsupported BattleState turn_timeline")
    ids = timeline["action_entity_runtime_ids"]
    if not isinstance(ids, list) or not ids:
        raise TurnSemanticError("turn timeline action entity list must be non-empty")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in ids):
        raise TurnSemanticError("turn timeline entity ids must be integers")
    if len(set(ids)) != len(ids):
        raise TurnSemanticError("turn timeline entity ids must be unique")
    if timeline["phase"] not in TURN_PHASES:
        raise TurnSemanticError("turn timeline phase is invalid")
    _require_nonnegative_raw(
        timeline["elapsed_action_delay_raw"], "elapsed_action_delay_raw"
    )
    if isinstance(timeline["turn_index"], bool) or not isinstance(
        timeline["turn_index"], int
    ) or timeline["turn_index"] < 0:
        raise TurnSemanticError("turn timeline turn_index must be >= 0")
    return timeline


def _delay_entry(state: Any, entity: EntityRef):
    entry = get_property_entry(state, entity, REMAINING_ACTION_DELAY_PROPERTY_ID)
    if entry is None:
        raise UnsupportedTurnParticipantError(
            f"entity {entity.runtime_id} has no property "
            f"{REMAINING_ACTION_DELAY_PROPERTY_ID} entry"
        )
    _require_nonnegative_raw(
        entry.materialized, f"entity {entity.runtime_id} remaining delay"
    )
    if entry.post_hook_context is not None or entry.post_transform_a is not None or entry.post_transform_b is not None:
        raise UnsupportedTurnParticipantError(
            f"entity {entity.runtime_id} action delay has an unresolved post stage"
        )
    return entry


def initialize_turn_timeline(state: "BattleState", participants: TargetSet) -> None:
    """Initialize the native action-list analogue in explicit ordinary scope."""
    _require_state(state)
    if not isinstance(participants, TargetSet):
        raise TypeError("participants must be TargetSet")
    if not participants.items:
        raise ValueError("participants must not be empty")
    if any(item is None for item in participants.items):
        raise UnsupportedTurnParticipantError("null participants are unsupported")
    entities = tuple(participants.items)
    ids = [entity.runtime_id for entity in entities]
    if len(set(ids)) != len(ids):
        raise ValueError("participants must have unique runtime ids")
    for entity in entities:
        _delay_entry(state, entity)
    state.turn_timeline = {
        "schema": TURN_TIMELINE_SCHEMA,
        "action_entity_runtime_ids": ids,
        "current_actor_runtime_id": None,
        "elapsed_action_delay_raw": FIXPOINT_ZERO_RAW,
        "turn_index": 0,
        "phase": TURN_PHASE_READY,
        "last_completion_provenance": None,
    }


def _compare_entities(state: Any, left: EntityRef, right: EntityRef) -> int:
    left_delay = _delay_entry(state, left).materialized
    right_delay = _delay_entry(state, right).materialized
    if fixpoint_less(left_delay, right_delay):
        return -1
    if fixpoint_less(right_delay, left_delay):
        return 1
    # Deliberate Semantics-29 sandbox policy: Python's stable sort preserves
    # prior action-list order when every recovered ordinary key is equal.
    return 0


def advance_to_next_actor(
    state: "BattleState",
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> TurnAdvanceResult:
    """Sort, select, subtract selected delay from all, and advance elapsed AV."""
    timeline = _timeline(state)
    if timeline["phase"] == TURN_PHASE_ACTIVE:
        raise TurnCompletionRequiredError(
            "current action is still active; acknowledge completion before advancing"
        )

    entities = [EntityRef(runtime_id) for runtime_id in timeline["action_entity_runtime_ids"]]
    entities.sort(key=cmp_to_key(lambda left, right: _compare_entities(state, left, right)))
    actor = entities[0]
    selected_delay = _delay_entry(state, actor).materialized

    for entity in entities:
        old_delay = _delay_entry(state, entity).materialized
        candidate = fixedpoint_subtract(old_delay, selected_delay)
        if fixpoint_is_negative(candidate):
            candidate = FIXPOINT_ZERO_RAW
        changed = modify_source_zero_untransformed(
            state,
            entity,
            REMAINING_ACTION_DELAY_PROPERTY_ID,
            int(PropertyModifyFunction.SET),
            candidate,
            boundary_sink=boundary_sink,
        )
        if not changed:  # defensive: scoped generic path returns true
            raise TurnSemanticError("action-delay property mutation was rejected")

    elapsed = fixedpoint_add(
        timeline["elapsed_action_delay_raw"], selected_delay
    )
    timeline["action_entity_runtime_ids"] = [item.runtime_id for item in entities]
    timeline["current_actor_runtime_id"] = actor.runtime_id
    timeline["elapsed_action_delay_raw"] = elapsed
    timeline["turn_index"] += 1
    timeline["phase"] = TURN_PHASE_ACTIVE
    timeline["last_completion_provenance"] = None

    return TurnAdvanceResult(
        actor=actor,
        selected_delay_raw=selected_delay,
        elapsed_action_delay_raw=elapsed,
        ordered_entities=tuple(entities),
        turn_index=timeline["turn_index"],
    )


def acknowledge_action_completion(
    state: "BattleState",
    boundary: ActionCompletionBoundary,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> None:
    """Cross the explicit native completion/recharge boundary.

    The supplied recharge is persisted through the already-proven generic
    property-38 Set path. This function does not claim to discover completion
    from task state and does not derive the recharge from Speed.
    """
    timeline = _timeline(state)
    if not isinstance(boundary, ActionCompletionBoundary):
        raise TypeError("boundary must be ActionCompletionBoundary")
    if timeline["phase"] != TURN_PHASE_ACTIVE:
        raise TurnSemanticError("there is no active action to settle")
    if timeline["current_actor_runtime_id"] != boundary.actor.runtime_id:
        raise TurnSemanticError("completion actor does not match current actor")
    _require_nonnegative_raw(boundary.next_action_delay_raw, "next_action_delay_raw")
    changed = modify_source_zero_untransformed(
        state,
        boundary.actor,
        REMAINING_ACTION_DELAY_PROPERTY_ID,
        int(PropertyModifyFunction.SET),
        boundary.next_action_delay_raw,
        boundary_sink=boundary_sink,
    )
    if not changed:
        raise TurnSemanticError("action-delay recharge mutation was rejected")
    timeline["phase"] = TURN_PHASE_SETTLED
    timeline["last_completion_provenance"] = boundary.provenance


def current_actor(state: "BattleState") -> EntityRef | None:
    timeline = _timeline(state)
    runtime_id = timeline["current_actor_runtime_id"]
    return None if runtime_id is None else EntityRef(runtime_id)


def remaining_action_delay(state: "BattleState", entity: EntityRef) -> int:
    return _delay_entry(state, entity).materialized
