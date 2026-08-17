# -*- coding: utf-8 -*-
"""Scoped HP-transition Runtime for Handoff 12.

Implements only the completed DirectDamageHP mode-0 HP-transition contract:

* ``TryGetLockHP`` (M506532) against the ordered ``component_lock_hp_records``
  BattleState representation.
* ``DirectDamageHP`` mode-0 (M506499) for normal finite FixPoint values:
  lock threshold, DirtyHPRatio bound, shared source-0 CurrentHP write, and the
  bounded NegativeHP property path.
* SetHP negative-delta composition helpers (target / delta computation) without
  modeling a general DamageRequest.

Unresolved native consumers are preserved as deterministic boundary outputs /
traces only.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from hsr_battle_agent.battle_ir.hp import (
    HPTransitionResult,
    LockHPRecord,
    LockHPResult,
)
from hsr_battle_agent.battle_ir.property import (
    PROPERTY_BOUNDARY_AFTER_PROPERTY_CHANGED,
    PropertyChangeBoundary,
)
from hsr_battle_agent.battle_ir.targets import EntityRef
from hsr_battle_agent.battle_runtime.predicates import (
    fixpoint_equal,
    fixpoint_from_int32,
    fixpoint_greater,
    fixpoint_greater_equal,
    fixpoint_is_positive,
    fixpoint_less,
    fixpoint_less_equal,
)
from hsr_battle_agent.battle_runtime.property import (
    PropertyEntryNotFoundError,
    fixedpoint_add,
    fixedpoint_multiply,
    fixedpoint_subtract,
    get_property_entry,
    set_property_entry,
    update_source_slot,
)

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from hsr_battle_agent.battle_sandbox.state import BattleState

PropertyBoundarySink = Callable[[PropertyChangeBoundary], None]
HPBoundarySink = Callable[[str, str], None]

CURRENT_HP_PROPERTY_ID = 10
NEGATIVE_HP_PROPERTY_ID = 9
MAX_HP_PROPERTY_ID = 1
DIRTY_HP_RATIO_PROPERTY_ID = 7

_MASK64 = 0xFFFFFFFFFFFFFFFF
_SIGN64 = 1 << 63
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


class HPSemanticError(Exception):
    """Base class for scoped HP runtime errors."""


class UnsupportedDirectDamageHPModeError(HPSemanticError):
    """DirectDamageHP modes outside the completed mode-0 contract."""

    def __init__(self, mode: int) -> None:
        super().__init__(
            f"DirectDamageHP mode {mode} is outside the completed Handoff 12 "
            "mode-0 HP-transition contract"
        )
        self.mode = mode


class UnsupportedDirectChangeHPPositiveError(HPSemanticError):
    """SetHP/DirectChangeHP positive delta is not coding-ready."""

    def __init__(self, delta: int) -> None:
        super().__init__(
            "DirectChangeHP mode=1 with a non-negative delta is outside the "
            "completed Handoff 12 scope; no guessed positive HP behavior is used"
        )
        self.delta = delta


def _validate_raw(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if not (_INT64_MIN <= value <= _MASK64):
        raise ValueError(f"{name} out of qword raw range: {value}")


def _validate_component(component: Any) -> EntityRef:
    if not isinstance(component, EntityRef):
        raise TypeError(
            f"component must be EntityRef, got {type(component).__name__}"
        )
    return component


def _require_state(state: Any) -> None:
    if not hasattr(state, "component_lock_hp_records"):
        raise TypeError(
            "state must be a BattleState with component_lock_hp_records"
        )


def _record_from_dict(raw: Mapping[str, Any]) -> LockHPRecord:
    return LockHPRecord.from_dict(raw)


def _records_from_state(state: Any, component: EntityRef) -> list[LockHPRecord]:
    _require_state(state)
    raw_records = state.component_lock_hp_records.get(
        str(component.runtime_id), []
    )
    if not isinstance(raw_records, list):
        raise TypeError(
            f"component_lock_hp_records[{component.runtime_id}] must be a list"
        )
    return [_record_from_dict(item) for item in raw_records]


def set_lock_hp_records(
    state: Any,
    component: EntityRef,
    records: list[LockHPRecord] | list[dict[str, Any]],
) -> None:
    """Persist an ordered lock-HP record list for a component.

    This is a deterministic sandbox composition helper for the native
    component[+0x50] field; it does not invent lifecycle add/remove APIs.
    """
    _require_state(state)
    _validate_component(component)
    normalized: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, LockHPRecord):
            normalized.append(record.to_dict())
        elif isinstance(record, Mapping):
            normalized.append(_record_from_dict(record).to_dict())
        else:
            raise TypeError(
                "lock records must be LockHPRecord or LockHPRecord dict, "
                f"got {type(record).__name__}"
            )
    state.component_lock_hp_records[str(component.runtime_id)] = normalized


def try_get_lock_hp(
    records: list[LockHPRecord],
    damage_kind: int,
) -> LockHPResult:
    """M506532 TryGetLockHP with the exact proven scan semantics.

    Scans descending, skips ``kind < damage_kind``, accepts the first
    qualifying value, extends to lower equal values, stops at a non-equal
    accepted value, and returns forward actions from the best index.
    """
    if isinstance(damage_kind, bool) or not isinstance(damage_kind, int):
        raise TypeError(
            f"damage_kind must be an int, got {type(damage_kind).__name__}"
        )
    if not isinstance(records, list):
        raise TypeError("records must be a list")
    for record in records:
        if not isinstance(record, LockHPRecord):
            raise TypeError("records items must be LockHPRecord")

    if not records:
        return LockHPResult(success=False, lock_value=0, actions=())

    selected_value: int | None = None
    best = -1
    for index in range(len(records) - 1, -1, -1):
        record = records[index]
        if record.kind < damage_kind:
            continue
        if selected_value is None:
            selected_value = record.value
            best = index
        elif fixpoint_equal(selected_value, record.value):
            best = index
        else:
            break

    if best < 0:
        return LockHPResult(success=False, lock_value=0, actions=())

    actions = tuple(record.action_ref for record in records[best:])
    return LockHPResult(success=True, lock_value=selected_value, actions=actions)


def try_get_lock_hp_from_state(
    state: Any,
    component: EntityRef,
    damage_kind: int,
) -> LockHPResult:
    """TryGetLockHP against BattleState's ordered lock-HP records."""
    _validate_component(component)
    return try_get_lock_hp(
        _records_from_state(state, component),
        damage_kind,
    )


def _entry_materialized(
    state: Any,
    component: EntityRef,
    property_id: int,
) -> tuple[Any, int]:
    entry = get_property_entry(state, component, property_id)
    if entry is None:
        raise PropertyEntryNotFoundError(component, property_id)
    return entry, entry.materialized


def _emit_property_boundary(
    boundary_sink: PropertyBoundarySink | None,
    state: Any,
    component: EntityRef,
    property_id: int,
    source_index: int,
    old_materialized: int,
    new_materialized: int,
) -> None:
    if boundary_sink is not None:
        boundary_sink(
            PropertyChangeBoundary(
                operation=PROPERTY_BOUNDARY_AFTER_PROPERTY_CHANGED,
                entity=component,
                property_id=property_id,
                source_index=source_index,
                old_materialized=old_materialized,
                new_materialized=new_materialized,
            )
        )


def _emit_hp_boundary(
    hp_boundary_sink: HPBoundarySink | None,
    name: str,
    summary: str,
) -> None:
    if hp_boundary_sink is not None:
        hp_boundary_sink(name, summary)


def _fp_min(left: int, right: int) -> int:
    return left if fixpoint_less(left, right) else right


def _fp_max(left: int, right: int) -> int:
    return left if fixpoint_greater(left, right) else right


def direct_damage_hp_transition(
    state: Any,
    component: EntityRef,
    delta: int,
    damage_kind: int,
    *,
    context_token: Any = None,
    input_record: Any = None,
    mode: int = 0,
    negative_hp_gate: bool = False,
    boundary_sink: PropertyBoundarySink | None = None,
    hp_boundary_sink: HPBoundarySink | None = None,
) -> HPTransitionResult:
    """DirectDamageHP mode-0 HP transition for the proven normal finite scope.

    Raises explicitly for unsupported modes.  Persistent CurrentHP/NegativeHP
    writes go through PropertyEntry source slot 0 and the existing Property
    Runtime materialization path.
    """
    _require_state(state)
    component = _validate_component(component)
    _validate_raw(delta, "delta")
    if isinstance(damage_kind, bool) or not isinstance(damage_kind, int):
        raise TypeError(
            f"damage_kind must be an int, got {type(damage_kind).__name__}"
        )
    if isinstance(mode, bool) or not isinstance(mode, int):
        raise TypeError(f"mode must be an int, got {type(mode).__name__}")
    if mode != 0:
        raise UnsupportedDirectDamageHPModeError(mode)
    if not isinstance(negative_hp_gate, bool):
        raise TypeError("negative_hp_gate must be bool")
    del context_token, input_record  # opaque; no recovered persistent read

    current_entry, old_current = _entry_materialized(
        state, component, CURRENT_HP_PROPERTY_ID
    )
    max_entry, max_hp = _entry_materialized(state, component, MAX_HP_PROPERTY_ID)

    zero = fixpoint_from_int32(0)
    candidate = fixedpoint_add(old_current, delta)

    lock_result = try_get_lock_hp_from_state(
        state, component, damage_kind
    )
    lock_hit = lock_result.success
    lock_value = lock_result.lock_value
    lock_actions = lock_result.actions

    if lock_hit and fixpoint_greater(max_hp, zero):
        k = fixpoint_from_int32(2)
        lock_cap = fixedpoint_multiply(max_hp, lock_value)
        t = _fp_min(
            old_current,
            _fp_max(_fp_min(k, max_hp), lock_cap),
        )
        if fixpoint_less(candidate, t):
            x = t
            bound = max_hp
            p = fixedpoint_subtract(t, candidate)
            flag = 1
        else:
            _, dirty_ratio = _entry_materialized(
                state, component, DIRTY_HP_RATIO_PROPERTY_ID
            )
            x = candidate
            bound = fixedpoint_subtract(
                max_hp, fixedpoint_multiply(max_hp, dirty_ratio)
            )
            p = 0
            flag = 0
    else:
        _, dirty_ratio = _entry_materialized(
            state, component, DIRTY_HP_RATIO_PROPERTY_ID
        )
        x = candidate
        bound = fixedpoint_subtract(
            max_hp, fixedpoint_multiply(max_hp, dirty_ratio)
        )
        p = 0
        flag = 0

    # Shared clamp.
    if fixpoint_less(x, bound):
        y = x
    elif fixpoint_greater_equal(x, zero) and fixpoint_greater(max_hp, zero):
        y = bound if fixpoint_greater(bound, zero) else zero
    else:
        y = _fp_min(x, max_hp)

    negative_record_boundary = fixpoint_less_equal(y, zero)
    if negative_record_boundary:
        _emit_hp_boundary(
            hp_boundary_sink,
            "NegativeHPRecordBoundary",
            (
                "negative_hp_record_boundary:y_le_0:"
                f"y=0x{y & _MASK64:X}; native consumer unresolved"
            ),
        )

    update_source_slot(current_entry, 0, y)
    new_current = current_entry.materialized
    set_property_entry(state, component, CURRENT_HP_PROPERTY_ID, current_entry)
    _emit_property_boundary(
        boundary_sink,
        state,
        component,
        CURRENT_HP_PROPERTY_ID,
        0,
        old_current,
        new_current,
    )

    applied = fixedpoint_subtract(new_current, old_current)

    negative_hp_written = False
    old_negative: int | None = None
    new_negative: int | None = None
    if negative_hp_gate and flag == 1 and fixpoint_is_positive(p):
        neg_entry, old_negative = _entry_materialized(
            state, component, NEGATIVE_HP_PROPERTY_ID
        )
        new_negative = fixedpoint_add(old_negative, p)
        update_source_slot(neg_entry, 0, new_negative)
        set_property_entry(state, component, NEGATIVE_HP_PROPERTY_ID, neg_entry)
        negative_hp_written = True
        _emit_property_boundary(
            boundary_sink,
            state,
            component,
            NEGATIVE_HP_PROPERTY_ID,
            0,
            old_negative,
            new_negative,
        )
        applied_delta = fixedpoint_subtract(zero, delta)
    else:
        applied_delta = applied

    if flag == 1:
        _emit_hp_boundary(
            hp_boundary_sink,
            "LockActionBoundary",
            (
                "lock_action_boundary:actions="
                + ",".join(lock_actions)
                + "; native submission consumer unresolved"
            ),
        )

    return HPTransitionResult(
        component=component,
        old_current=old_current,
        new_current=new_current,
        applied_delta=applied_delta,
        lock_hit=lock_hit,
        lock_value=lock_value,
        lock_actions=lock_actions,
        flag=flag,
        p=p,
        y=y,
        negative_hp_written=negative_hp_written,
        old_negative=old_negative,
        new_negative=new_negative,
        negative_record_boundary=negative_record_boundary,
    )


def set_hp_target(
    modify_value: int,
    max_hp: int,
    modify_ratio: int,
) -> int:
    """SetHP target = ModifyValue + fp_mul(MaxHP, ModifyRatio)."""
    _validate_raw(modify_value, "modify_value")
    _validate_raw(max_hp, "max_hp")
    _validate_raw(modify_ratio, "modify_ratio")
    return fixedpoint_add(
        modify_value,
        fixedpoint_multiply(max_hp, modify_ratio),
    )


def set_hp_delta(target: int, current: int) -> int:
    """SetHP delta = target - CurrentHP."""
    _validate_raw(target, "target")
    _validate_raw(current, "current")
    return fixedpoint_subtract(target, current)


def direct_change_hp_mode1_negative(
    state: Any,
    component: EntityRef,
    modify_value: int,
    modify_ratio: int,
    *,
    damage_kind: int = 100,
    context_token: Any = None,
    input_record: Any = None,
    negative_hp_gate: bool = False,
    boundary_sink: PropertyBoundarySink | None = None,
    hp_boundary_sink: HPBoundarySink | None = None,
) -> HPTransitionResult:
    """Scoped SetHP -> DirectChangeHP(mode=1) negative-delta composition.

    Only the proven negative-delta path is implemented.  A non-negative delta
    raises ``UnsupportedDirectChangeHPPositiveError`` instead of guessing.
    """
    _require_state(state)
    component = _validate_component(component)
    _validate_raw(modify_value, "modify_value")
    _validate_raw(modify_ratio, "modify_ratio")

    _, current = _entry_materialized(state, component, CURRENT_HP_PROPERTY_ID)
    _, max_hp = _entry_materialized(state, component, MAX_HP_PROPERTY_ID)
    target = set_hp_target(modify_value, max_hp, modify_ratio)
    delta = set_hp_delta(target, current)
    if not fixpoint_less(delta, fixpoint_from_int32(0)):
        raise UnsupportedDirectChangeHPPositiveError(delta)
    return direct_damage_hp_transition(
        state,
        component,
        delta,
        damage_kind,
        context_token=context_token,
        input_record=input_record,
        mode=0,
        negative_hp_gate=negative_hp_gate,
        boundary_sink=boundary_sink,
        hp_boundary_sink=hp_boundary_sink,
    )
