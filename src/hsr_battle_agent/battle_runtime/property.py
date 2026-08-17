# -*- coding: utf-8 -*-
"""Generic Property Runtime (Handoffs 09/10/11).

This module is the implementation binding for the machine-readable semantic
artifacts:

* ``data/semantics/4.4.54/modifier_property_effect_09.json``
* ``data/semantics/4.4.54/generic_property_materialization_10.json``
* ``data/semantics/4.4.54/generic_property_mutation_11.json``

Boundaries preserved:

* Modifier-owned contributions are tracked in ordered records keyed by the
  logical ``ModifierRef``.  Their key is the stable PropertyEntry
  ``source_index`` (Handoff 10); the early opaque contribution_key is not
  duplicated.
* Source slots are never shifted or remapped on removal.  Removed slots keep
  their stale value and only lose active/version state.
* Source slot ``0`` is reserved for the Handoff 11 generic source-0 mutation
  path.  Modifier contribution allocation starts at slot 1.
* Materialization is implemented only where the artifacts prove the operation;
  unresolved post-transform/post-hook state and unresolved kind formulas raise
  explicit unsupported errors instead of silently falling back to addition or
  silently ignoring native stages.
* The generic source-0 mutation rejects the native special property-ID set,
  including CurrentHP (property 10).
* Property changes produce one deterministic ``PropertyChangeBoundary`` per
  accepted mutation via an optional sink; listener/event dispatch is not
  invented.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, TYPE_CHECKING

from hsr_battle_agent.battle_ir.modifiers import ModifierState, ModifierStateValue
from hsr_battle_agent.battle_ir.property import (
    CURRENT_HP_PROPERTY_ID,
    PROPERTY_BOUNDARY_AFTER_PROPERTY_CHANGED,
    PROPERTY_BOUNDARY_SOURCE_ALLOCATED,
    PROPERTY_BOUNDARY_SOURCE_REMOVED,
    PROPERTY_BOUNDARY_SOURCE_UPDATED,
    SPECIAL_PROPERTY_IDS,
    MaterializationKind,
    ModifierPropertyContribution,
    PropertyChangeBoundary,
    PropertyEntry,
    PropertyModifyFunction,
    StackPropertyExecutor,
    StackPropertyTaskConfig,
    StackPropertyTaskContext,
    StackPropertyTaskResult,
    modifier_contribution_key,
    property_entry_key,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_runtime.predicates import (
    fixpoint_greater,
    fixpoint_less,
)

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from hsr_battle_agent.battle_sandbox.state import BattleState

PropertyBoundarySink = Callable[[PropertyChangeBoundary], None]

_MASK64 = 0xFFFFFFFFFFFFFFFF
_SIGN64 = 1 << 63
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_FIXPOINT_SCALE_BITS = 26
_FIXPOINT_STANDARD_SHIFT = 7
_STANDARD_VALUE_LIMIT = 1 << 30  # abs(value) < 0x40000000 -> standard encoding


class PropertySemanticError(Exception):
    """Base class for explicit property-domain unsupported/rejected states."""


class PropertyEntryNotFoundError(PropertySemanticError, LookupError):
    def __init__(self, entity: EntityRef, property_id: int) -> None:
        super().__init__(
            f"property entry not found for entity {entity.runtime_id} "
            f"property_id {property_id}; sandbox does not synthesize unproven entries"
        )
        self.entity = entity
        self.property_id = property_id


class PropertySourceSlotError(PropertySemanticError, IndexError):
    pass


class UnsupportedMaterializationKind(PropertySemanticError):
    def __init__(self, kind: int, *, detail: str = "") -> None:
        message = (
            f"unsupported materialization kind {kind}; no exact native "
            "operator/seed formula is available"
        )
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.kind = kind


class UnsupportedPropertyPostStageError(PropertySemanticError):
    """Non-null post-transform/post-hook native stage outside proven scope."""

    def __init__(self, field: str) -> None:
        super().__init__(
            f"property post-materialization stage {field} is non-null; "
            "native transform/hook semantics are UNKNOWN and must not be "
            "silently ignored"
        )
        self.field = field


class UnsupportedSpecialPropertyMutationError(PropertySemanticError):
    """Generic source-0 mutation attempted on a native special property ID."""

    def __init__(self, property_id: int) -> None:
        special = "CurrentHP(10)" if property_id == CURRENT_HP_PROPERTY_ID else str(property_id)
        super().__init__(
            f"generic source-0 property mutation does not cover special "
            f"property_id {property_id} ({special}); native branch policy is "
            "deferred"
        )
        self.property_id = property_id


# ---------------------------------------------------------------------------
# Fixed-point arithmetic (Handoff 11)
# ---------------------------------------------------------------------------


def _validate_raw(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if not (_INT64_MIN <= value <= _MASK64):
        raise ValueError(f"{name} out of qword raw range: {value}")


def _to_signed64(value: int) -> int:
    value &= _MASK64
    return value - (1 << 64) if value & _SIGN64 else value


def _decode_fixpoint_common(raw: int) -> int:
    """Decode either native raw mode to the common 2^-26 fixed-point scale.

    EXTENDED raw = (value << 26) | 1.  STANDARD raw = value << 33, which
    comparison mode aligns by arithmetic-shifting right 7 to the same
    ``value << 26`` scale.  Low seven STANDARD fraction bits are therefore
    truncated by the arithmetic shift, exactly like the recovered mixed-mode
    comparison alignment.
    """
    raw &= _MASK64
    if raw & 1:
        return _to_signed64(raw & ~1)
    return _to_signed64(raw) >> _FIXPOINT_STANDARD_SHIFT


def _saturate_common(value: int) -> int:
    if value < _INT64_MIN:
        return _INT64_MIN
    if value > _INT64_MAX:
        return _INT64_MAX
    return value


def _encode_fixpoint_common(common: int) -> int:
    """Encode a common 2^-26 value back to a deterministic native raw mode.

    Integral values whose abs(value) < 0x40000000 use STANDARD
    (``value << 33``), matching FixPointFromInt32.  Fractional or larger
    values use EXTENDED (``(common & ~1) | 1``).  This is a deterministic
    encoding policy for sandbox arithmetic results, not a new semantic spec.
    """
    common = _saturate_common(common)
    if common % (1 << _FIXPOINT_SCALE_BITS) == 0:
        value = common >> _FIXPOINT_SCALE_BITS
        if -_STANDARD_VALUE_LIMIT < value < _STANDARD_VALUE_LIMIT:
            return (value << (_FIXPOINT_SCALE_BITS + _FIXPOINT_STANDARD_SHIFT)) & _MASK64
    return (common & ~1 & _MASK64) | 1


def fixedpoint_add(left: int, right: int) -> int:
    """Saturating fixed-point sum (Handoff 11 ``battle.ir.fixedpoint.add``)."""
    _validate_raw(left, "left")
    _validate_raw(right, "right")
    return _encode_fixpoint_common(
        _decode_fixpoint_common(left) + _decode_fixpoint_common(right)
    )


def fixedpoint_subtract(left: int, right: int) -> int:
    """Saturating fixed-point difference (Handoff 11)."""
    _validate_raw(left, "left")
    _validate_raw(right, "right")
    return _encode_fixpoint_common(
        _decode_fixpoint_common(left) - _decode_fixpoint_common(right)
    )


def fixedpoint_multiply(left: int, right: int) -> int:
    """Saturating fixed-point product (Handoff 11)."""
    _validate_raw(left, "left")
    _validate_raw(right, "right")
    product = _decode_fixpoint_common(left) * _decode_fixpoint_common(right)
    return _encode_fixpoint_common(product >> _FIXPOINT_SCALE_BITS)


def apply_modify_function(
    function_id: int,
    old_materialized_value: int,
    operand: int,
) -> int:
    """``ApplyPropertyModifyFunction``: 1=Set, 2=Add, 3=Mul, 4=Min, 5=Max.

    Out-of-range ids use the proven native Set fallthrough.
    """
    if isinstance(function_id, bool) or not isinstance(function_id, int):
        raise TypeError(
            f"function_id must be an int, got {type(function_id).__name__}"
        )
    _validate_raw(old_materialized_value, "old_materialized_value")
    _validate_raw(operand, "operand")
    if function_id == int(PropertyModifyFunction.SET):
        return operand
    if function_id == int(PropertyModifyFunction.ADD):
        return fixedpoint_add(old_materialized_value, operand)
    if function_id == int(PropertyModifyFunction.MUL):
        return fixedpoint_multiply(old_materialized_value, operand)
    if function_id == int(PropertyModifyFunction.MIN_SET):
        return (
            old_materialized_value
            if fixpoint_less(old_materialized_value, operand)
            else operand
        )
    if function_id == int(PropertyModifyFunction.MAX_SET):
        return (
            operand
            if fixpoint_greater(operand, old_materialized_value)
            else old_materialized_value
        )
    return operand  # native out-of-range -> Set fallthrough


# ---------------------------------------------------------------------------
# PropertyEntry source-slot helpers (Handoff 10)
# ---------------------------------------------------------------------------


def _require_entry(entry: PropertyEntry) -> None:
    if not isinstance(entry, PropertyEntry):
        raise TypeError(
            f"entry must be PropertyEntry, got {type(entry).__name__}"
        )


def _require_source_index(entry: PropertyEntry, source_index: int) -> None:
    if isinstance(source_index, bool) or not isinstance(source_index, int):
        raise TypeError(
            f"source_index must be an int, got {type(source_index).__name__}"
        )
    if source_index < 0:
        raise ValueError("source_index must be >= 0")
    if source_index >= len(entry.source_value):
        raise PropertySourceSlotError(
            f"source_index {source_index} is outside entry source capacity "
            f"{len(entry.source_value)}; update does not allocate"
        )


def _reserve_source_zero(entry: PropertyEntry) -> None:
    """Make sure slot 0 exists as a reserved slot; never mark it active."""
    if len(entry.source_value) == 0:
        entry.source_generation.append(0)
        entry.source_active.append(False)
        entry.source_value.append(0)


def _refresh_active_extent(entry: PropertyEntry) -> None:
    entry.active_source_extent = sum(1 for active in entry.source_active if active)


def _active_indices(entry: PropertyEntry) -> list[int]:
    return [index for index, active in enumerate(entry.source_active) if active]


def _require_supported_post_stages(entry: PropertyEntry) -> None:
    if entry.post_hook_context is not None:
        raise UnsupportedPropertyPostStageError("post_hook_context")
    if entry.post_transform_a is not None:
        raise UnsupportedPropertyPostStageError("post_transform_a")
    if entry.post_transform_b is not None:
        raise UnsupportedPropertyPostStageError("post_transform_b")


def _materialize_by_kind(entry: PropertyEntry) -> int:
    """Pre-post-stage reducer for the seven recovered materialization kinds.

    Kind 3/4 use the callees whose fixed-point semantics Handoff 11 recovered
    (add/multiply).  Kind 5's ``subtract then multiply`` fold seed/order is not
    exactly recovered, so it is explicitly unsupported.  Kind 6/7 are the two
    complementary extrema directions; gameplay labels remain deliberately
    unnamed.
    """
    _require_entry(entry)
    kind = entry.materialization_kind
    active = _active_indices(entry)
    base = entry.base_or_fallback

    if kind == int(MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION):
        if len(entry.source_value) == 0:
            return base
        return entry.source_value[0]

    if kind == int(MaterializationKind.KIND_2_LAST_CHANGED_SOURCE_SELECTION):
        index = entry.last_changed_source
        if 0 <= index < len(entry.source_value):
            return entry.source_value[index]
        return base

    if kind == int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE):
        accumulator = base
        for index in active:
            accumulator = fixedpoint_add(accumulator, entry.source_value[index])
        return accumulator

    if kind == int(MaterializationKind.KIND_4_ACTIVE_FOLD_MULTIPLY_CALLEE):
        # The artifact explicitly records that the no-active path falls back
        # to entry[+0x70]; the base also seeds the active fold.
        accumulator = base
        for index in active:
            accumulator = fixedpoint_multiply(accumulator, entry.source_value[index])
        return accumulator

    if kind == int(MaterializationKind.KIND_5_ACTIVE_FOLD_SUBTRACT_MULTIPLY_CALLEES):
        raise UnsupportedMaterializationKind(
            kind,
            detail=(
                "direct callees are recovered (fixed-point subtract then "
                "multiply) but the fold seed/argument order is not exactly "
                "proven; refusing to guess a formula"
            ),
        )

    if kind == int(MaterializationKind.KIND_6_ACTIVE_EXTREMUM_DIRECTION_A):
        if not active:
            return base
        selected = entry.source_value[active[0]]
        for index in active[1:]:
            candidate = entry.source_value[index]
            if fixpoint_less(candidate, selected):
                selected = candidate
        return selected

    if kind == int(MaterializationKind.KIND_7_ACTIVE_EXTREMUM_DIRECTION_B):
        if not active:
            return base
        selected = entry.source_value[active[0]]
        for index in active[1:]:
            candidate = entry.source_value[index]
            if fixpoint_greater(candidate, selected):
                selected = candidate
        return selected

    raise UnsupportedMaterializationKind(kind)


def rebuild_materialized(entry: PropertyEntry) -> int:
    """Rebuild ``entry.materialized`` through the recovered materializer.

    Native post-transform/post-hook stages are UNKNOWN; non-null values fail
    explicitly instead of being silently ignored or guessed.
    """
    _require_entry(entry)
    _require_supported_post_stages(entry)
    candidate = _materialize_by_kind(entry)
    entry.materialized = candidate
    return candidate


def allocate_source_slot(entry: PropertyEntry, source_value: int) -> int:
    """Allocate a stable source index; source 0 is never a contribution slot.

    Reuses the first inactive slot from index 1 upward and extends the arrays
    only when every existing slot is active.  Removed slots are never shifted
    or remapped.
    """
    _require_entry(entry)
    _validate_raw(source_value, "source_value")
    _reserve_source_zero(entry)

    source_index: int | None = None
    for index in range(1, len(entry.source_value)):
        if not entry.source_active[index]:
            source_index = index
            break
    if source_index is None:
        source_index = len(entry.source_value)
        entry.source_generation.append(0)
        entry.source_active.append(False)
        entry.source_value.append(0)

    entry.source_value[source_index] = source_value
    entry.source_active[source_index] = True
    entry.generation_counter += 1
    entry.source_generation[source_index] = entry.generation_counter
    entry.last_changed_source = source_index
    _refresh_active_extent(entry)
    rebuild_materialized(entry)
    return source_index


def update_source_slot(
    entry: PropertyEntry,
    source_index: int,
    source_value: int,
) -> None:
    """Update one stable source index; never allocates a new index."""
    _require_entry(entry)
    _require_source_index(entry, source_index)
    _validate_raw(source_value, "source_value")

    entry.source_value[source_index] = source_value
    entry.source_active[source_index] = True
    entry.generation_counter += 1
    entry.source_generation[source_index] = entry.generation_counter
    entry.last_changed_source = source_index
    _refresh_active_extent(entry)
    rebuild_materialized(entry)


def remove_source_slot(entry: PropertyEntry, source_index: int) -> None:
    """Disable a stable source index; stale value and other indices remain."""
    _require_entry(entry)
    _require_source_index(entry, source_index)

    if entry.active_source_extent <= 0:
        return
    entry.source_active[source_index] = False
    entry.source_generation[source_index] = 0
    _refresh_active_extent(entry)
    rebuild_materialized(entry)


def materialize_kind_3(entry: PropertyEntry) -> int:
    _require_entry(entry)
    value = _materialize_kind_3_value(entry)
    entry.materialized = value
    return value


def materialize_kind_4(entry: PropertyEntry) -> int:
    _require_entry(entry)
    value = _materialize_kind_4_value(entry)
    entry.materialized = value
    return value


def materialize_kind_5(entry: PropertyEntry) -> int:
    _require_entry(entry)
    raise UnsupportedMaterializationKind(
        entry.materialization_kind,
        detail=(
            "kind-5 subtract/multiply fold formula is not exactly recovered; "
            "no guessed fallback is applied"
        ),
    )


def materialize_kind_6(entry: PropertyEntry) -> int:
    _require_entry(entry)
    value = _materialize_extremum_a(entry)
    entry.materialized = value
    return value


def materialize_kind_7(entry: PropertyEntry) -> int:
    _require_entry(entry)
    value = _materialize_extremum_b(entry)
    entry.materialized = value
    return value


def _materialize_kind_3_value(entry: PropertyEntry) -> int:
    accumulator = entry.base_or_fallback
    for index in _active_indices(entry):
        accumulator = fixedpoint_add(accumulator, entry.source_value[index])
    return accumulator


def _materialize_kind_4_value(entry: PropertyEntry) -> int:
    accumulator = entry.base_or_fallback
    for index in _active_indices(entry):
        accumulator = fixedpoint_multiply(accumulator, entry.source_value[index])
    return accumulator


def _materialize_extremum_a(entry: PropertyEntry) -> int:
    active = _active_indices(entry)
    if not active:
        return entry.base_or_fallback
    selected = entry.source_value[active[0]]
    for index in active[1:]:
        candidate = entry.source_value[index]
        if fixpoint_less(candidate, selected):
            selected = candidate
    return selected


def _materialize_extremum_b(entry: PropertyEntry) -> int:
    active = _active_indices(entry)
    if not active:
        return entry.base_or_fallback
    selected = entry.source_value[active[0]]
    for index in active[1:]:
        candidate = entry.source_value[index]
        if fixpoint_greater(candidate, selected):
            selected = candidate
    return selected


# ---------------------------------------------------------------------------
# Persistent BattleState property helpers
# ---------------------------------------------------------------------------


def _require_state(state: Any) -> None:
    if not (
        hasattr(state, "entity_property_entries")
        and hasattr(state, "modifier_property_contributions")
    ):
        raise TypeError("state must be a BattleState with property fields")


def _require_entity(value: EntityRef, name: str) -> None:
    if not isinstance(value, EntityRef):
        raise TypeError(f"{name} must be EntityRef, got {type(value).__name__}")


def _require_property_id(property_id: int) -> None:
    if isinstance(property_id, bool) or not isinstance(property_id, int):
        raise TypeError(
            f"property_id must be an int, got {type(property_id).__name__}"
        )


def _require_modifier(modifier: ModifierState) -> None:
    if not isinstance(modifier, ModifierState):
        raise TypeError(
            f"modifier must be ModifierState, got {type(modifier).__name__}"
        )


def _entry_from_state(state: Any, entity: EntityRef, property_id: int) -> PropertyEntry:
    raw = state.entity_property_entries.get(property_entry_key(entity, property_id))
    if raw is None:
        raise PropertyEntryNotFoundError(entity, property_id)
    return PropertyEntry.from_dict(raw)


def _store_entry(state: Any, entity: EntityRef, property_id: int, entry: PropertyEntry) -> None:
    state.entity_property_entries[property_entry_key(entity, property_id)] = entry.to_dict()


def get_property_entry(
    state: Any,
    entity: EntityRef,
    property_id: int,
) -> PropertyEntry | None:
    """Read a persistent PropertyEntry by stable ``(entity, property_id)`` key."""
    _require_state(state)
    _require_entity(entity, "entity")
    _require_property_id(property_id)
    raw = state.entity_property_entries.get(property_entry_key(entity, property_id))
    if raw is None:
        return None
    return PropertyEntry.from_dict(raw)


def set_property_entry(
    state: Any,
    entity: EntityRef,
    property_id: int,
    entry: PropertyEntry,
) -> PropertyEntry:
    """Persist a PropertyEntry under the stable ``(entity, property_id)`` key."""
    _require_state(state)
    _require_entity(entity, "entity")
    _require_property_id(property_id)
    _require_entry(entry)
    stored = entry.clone()
    _store_entry(state, entity, property_id, stored)
    return stored


def ensure_property_entry(
    state: Any,
    entity: EntityRef,
    property_id: int,
    *,
    materialization_kind: int = int(
        MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
    ),
    base_or_fallback: int = 0,
) -> PropertyEntry:
    """Get or create an entry; creation always reserves inactive source 0.

    This helper is a sandbox composition convenience, not a registered native
    primitive.
    """
    existing = get_property_entry(state, entity, property_id)
    if existing is not None:
        return existing
    created = PropertyEntry.create_empty(
        materialization_kind=materialization_kind,
        base_or_fallback=base_or_fallback,
    )
    return set_property_entry(state, entity, property_id, created)


def _emit_boundary(
    sink: PropertyBoundarySink | None,
    boundary: PropertyChangeBoundary,
) -> None:
    if sink is not None:
        if not callable(sink):
            raise TypeError("boundary_sink must be callable or None")
        sink(boundary)


# ---------------------------------------------------------------------------
# Component-level source primitives (Handoff 10)
# ---------------------------------------------------------------------------


def component_stack_source(
    state: Any,
    component: EntityRef,
    property_id: int,
    runtime_value: int,
    context_token: Any = None,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> int:
    """Component.StackProperty source allocation boundary (M506495/M506199).

    The unknown native value/context adapter (0x15C6E450) is upstream: the
    caller supplies the already-adapted runtime numeric.  This primitive does
    **not** claim raw DynamicValue equality.
    """
    _require_state(state)
    _require_entity(component, "component")
    _require_property_id(property_id)
    _validate_raw(runtime_value, "runtime_value")
    del context_token  # opaque; no recovered persistent read

    entry = _entry_from_state(state, component, property_id)
    old = entry.materialized
    source_index = allocate_source_slot(entry, runtime_value)
    new = entry.materialized
    _store_entry(state, component, property_id, entry)
    _emit_boundary(
        boundary_sink,
        PropertyChangeBoundary(
            operation=PROPERTY_BOUNDARY_SOURCE_ALLOCATED,
            entity=component,
            property_id=property_id,
            source_index=source_index,
            old_materialized=old,
            new_materialized=new,
        ),
    )
    return source_index


def update_contribution_source(
    state: Any,
    component: EntityRef,
    property_id: int,
    source_index: int,
    new_source_value: int,
    context_token: Any = None,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> None:
    """Update an existing stable source index, then rebuild + boundary."""
    _require_state(state)
    _require_entity(component, "component")
    _require_property_id(property_id)
    _validate_raw(new_source_value, "new_source_value")
    del context_token

    entry = _entry_from_state(state, component, property_id)
    old = entry.materialized
    update_source_slot(entry, source_index, new_source_value)
    new = entry.materialized
    _store_entry(state, component, property_id, entry)
    _emit_boundary(
        boundary_sink,
        PropertyChangeBoundary(
            operation=PROPERTY_BOUNDARY_SOURCE_UPDATED,
            entity=component,
            property_id=property_id,
            source_index=source_index,
            old_materialized=old,
            new_materialized=new,
        ),
    )


def remove_contribution_source(
    state: Any,
    component: EntityRef,
    property_id: int,
    source_index: int,
    context_token: Any = None,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> None:
    """Disable one stable source index, then rebuild + boundary."""
    _require_state(state)
    _require_entity(component, "component")
    _require_property_id(property_id)
    del context_token

    entry = _entry_from_state(state, component, property_id)
    old = entry.materialized
    remove_source_slot(entry, source_index)
    new = entry.materialized
    _store_entry(state, component, property_id, entry)
    _emit_boundary(
        boundary_sink,
        PropertyChangeBoundary(
            operation=PROPERTY_BOUNDARY_SOURCE_REMOVED,
            entity=component,
            property_id=property_id,
            source_index=source_index,
            old_materialized=old,
            new_materialized=new,
        ),
    )


# Handoff 09 compatibility boundaries: the same source-index system, no second
# opaque key.
def component_stack_boundary(
    state: Any,
    component: EntityRef,
    property_id: int,
    value: int,
    context_token: Any = None,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> int:
    """Handoff 09 boundary re-exported on the Handoff 10 source-index system."""
    return component_stack_source(
        state,
        component,
        property_id,
        value,
        context_token,
        boundary_sink=boundary_sink,
    )


def component_unstack_boundary(
    state: Any,
    component: EntityRef,
    property_id: int,
    contribution_key: int,
    owner_modifier: ModifierState | None = None,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> None:
    """Handoff 09 unstack boundary using the stable source index.

    ``owner_modifier`` is accepted for artifact signature compatibility; the
    exact source identity is the stable ``contribution_key``/``source_index``.
    """
    del owner_modifier
    remove_contribution_source(
        state,
        component,
        property_id,
        contribution_key,
        boundary_sink=boundary_sink,
    )


# ---------------------------------------------------------------------------
# Modifier-owned contribution lifecycle (Handoff 09 + Handoff 10)
# ---------------------------------------------------------------------------


def _records_for_modifier(state: Any, modifier: ModifierState) -> list[dict[str, Any]]:
    key = modifier_contribution_key(modifier.ref)
    raw = state.modifier_property_contributions.get(key)
    if raw is None:
        raw = []
        state.modifier_property_contributions[key] = raw
    return raw


def stack_property_contribution(
    state: Any,
    modifier: ModifierState,
    property_id: int,
    value: int,
    target_component: EntityRef,
    context_token: Any = None,
    is_refresh: bool = False,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> int | None:
    """``TurnBasedModifierInstance.StackProperty`` (M506199).

    State beyond Alive is a no-op.  Refresh scans the modifier's ordered
    records forward for ``(property_id, target_component)`` and updates the
    same stable source index; the normal path allocates a new source and
    appends one owner record.
    """
    _require_state(state)
    _require_modifier(modifier)
    _require_property_id(property_id)
    _validate_raw(value, "value")
    _require_entity(target_component, "target_component")
    if not isinstance(is_refresh, bool):
        raise TypeError(
            f"is_refresh must be bool, got {type(is_refresh).__name__}"
        )
    del context_token

    if modifier.state_raw > int(ModifierStateValue.ALIVE):
        return None

    records = _records_for_modifier(state, modifier)
    if is_refresh:
        for raw_record in records:
            record = ModifierPropertyContribution.from_dict(raw_record)
            if (
                record.property_id == property_id
                and record.target.runtime_id == target_component.runtime_id
            ):
                update_contribution_source(
                    state,
                    target_component,
                    property_id,
                    record.source_index,
                    value,
                    boundary_sink=boundary_sink,
                )
                return record.source_index

    source_index = component_stack_source(
        state,
        target_component,
        property_id,
        value,
        boundary_sink=boundary_sink,
    )
    record = ModifierPropertyContribution(
        modifier=modifier.ref,
        target=target_component,
        property_id=property_id,
        source_index=source_index,
    )
    records.append(record.to_dict())
    return source_index


def pop_property_contributions(
    state: Any,
    modifier: ModifierState,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> None:
    """``TurnBasedModifierInstance._PopStackedProperties`` (M506312).

    Walks the modifier's owned records in forward order, disables each exact
    source index, and then removes the owner-record key.  Records owned by any
    other Modifier (even same target/property) are untouched.
    """
    _require_state(state)
    _require_modifier(modifier)

    key = modifier_contribution_key(modifier.ref)
    raw_records = state.modifier_property_contributions.get(key, [])
    records = [ModifierPropertyContribution.from_dict(item) for item in raw_records]
    for record in records:
        remove_contribution_source(
            state,
            record.target,
            record.property_id,
            record.source_index,
            boundary_sink=boundary_sink,
        )
    state.modifier_property_contributions.pop(key, None)


# ---------------------------------------------------------------------------
# StackProperty task boundary (Handoff 09)
# ---------------------------------------------------------------------------


def _coerce_stack_property_task_context(value: Any) -> StackPropertyTaskContext:
    if isinstance(value, StackPropertyTaskContext):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("modifier"), ModifierState):
        return StackPropertyTaskContext(modifier=value["modifier"])
    if hasattr(value, "modifier") and isinstance(
        getattr(value, "modifier"), ModifierState
    ):
        return StackPropertyTaskContext(modifier=getattr(value, "modifier"))
    raise TypeError(
        "task_context must be StackPropertyTaskContext or an opaque context "
        "carrying modifier; sandbox cannot materialize an unproven TaskContext"
    )


def _coerce_stack_property_task_config(value: Any) -> StackPropertyTaskConfig:
    if isinstance(value, StackPropertyTaskConfig):
        return value
    if isinstance(value, Mapping):
        property_id = value.get("property_id")
        if isinstance(property_id, bool) or not isinstance(property_id, int):
            raise TypeError(
                "task_config mapping must carry int property_id; "
                f"got {property_id!r}"
            )
        return StackPropertyTaskConfig(property_id=property_id)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            "task_config must be StackPropertyTaskConfig, property_id int, "
            f"or mapping with property_id; got {type(value).__name__}"
        )
    return StackPropertyTaskConfig(property_id=value)


def stack_property_executor_init(
    task_context: Any,
    task_config: Any,
) -> StackPropertyExecutor:
    """M506081 projection: store context/config and the 0x7777 kind marker."""
    context = _coerce_stack_property_task_context(task_context)
    config = _coerce_stack_property_task_config(task_config)
    return StackPropertyExecutor(
        task_context=context,
        task_config=config,
        kind_marker=0x7777,
    )


def stack_property_execute(
    state: Any,
    executor: StackPropertyExecutor,
    selected_targets: TargetSet,
    evaluated_property_value: int,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> StackPropertyTaskResult:
    """M506082 normal-path projection.

    Target selection and DynamicValue evaluation are pre-resolved inputs (the
    recovered selector/evaluator dependencies), so this primitive only
    performs the proven forward per-target modifier contribution loop.
    """
    _require_state(state)
    if not isinstance(executor, StackPropertyExecutor):
        raise TypeError(
            f"executor must be StackPropertyExecutor, got {type(executor).__name__}"
        )
    if not isinstance(selected_targets, TargetSet):
        raise TypeError(
            f"selected_targets must be TargetSet, got {type(selected_targets).__name__}"
        )
    _validate_raw(evaluated_property_value, "evaluated_property_value")

    applied_targets: list[EntityRef] = []
    applied_source_indices: list[int | None] = []
    for target in selected_targets.items:
        if target is None:
            raise ValueError(
                "StackProperty OnTaskBegin canonical boundary received a null "
                "target element; native path would dereference the entity"
            )
        source_index = stack_property_contribution(
            state,
            executor.task_context.modifier,
            executor.task_config.property_id,
            evaluated_property_value,
            target,
            is_refresh=False,
            boundary_sink=boundary_sink,
        )
        applied_targets.append(target)
        applied_source_indices.append(source_index)

    return StackPropertyTaskResult(
        task_completion="SUCCESS",
        applied_targets=tuple(applied_targets),
        applied_source_indices=tuple(applied_source_indices),
    )


# ---------------------------------------------------------------------------
# Generic source-0 mutation (Handoff 11)
# ---------------------------------------------------------------------------


def modify_source_zero_untransformed(
    state: Any,
    component: EntityRef,
    property_id: int,
    function_id: int,
    operand: int,
    context_token: Any = None,
    *,
    boundary_sink: PropertyBoundarySink | None = None,
) -> bool:
    """``ModifyProperty`` scoped untransformed common path (M506503).

    Accepted scope only: entry exists, ``post_hook_context`` is null, and
    ``property_id`` is outside the native special-property set (CurrentHP=10
    included).  Special ids and non-null post-transform contexts fail
    explicitly; they are never routed through this generic common path.
    """
    _require_state(state)
    _require_entity(component, "component")
    _require_property_id(property_id)
    _validate_raw(operand, "operand")
    del context_token

    if property_id in SPECIAL_PROPERTY_IDS:
        raise UnsupportedSpecialPropertyMutationError(property_id)

    entry = _entry_from_state(state, component, property_id)
    if entry.post_hook_context is not None:
        raise UnsupportedPropertyPostStageError("post_hook_context")
    # Remaining post stages are rejected by update_source_slot -> rebuild
    # before any materialized write is persisted.
    old = entry.materialized
    candidate = apply_modify_function(function_id, old, operand)
    update_source_slot(entry, 0, candidate)
    new = entry.materialized
    _store_entry(state, component, property_id, entry)
    _emit_boundary(
        boundary_sink,
        PropertyChangeBoundary(
            operation=PROPERTY_BOUNDARY_AFTER_PROPERTY_CHANGED,
            entity=component,
            property_id=property_id,
            source_index=0,
            old_materialized=old,
            new_materialized=new,
        ),
    )
    return True
