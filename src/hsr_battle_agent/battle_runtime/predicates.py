# -*- coding: utf-8 -*-
"""FixPoint Comparison Batch 03 runtime: compare/conversion/predicate leaves.

Every function below mirrors a bounded native body recovered in
``data/semantics/4.4.54/fixpoint_comparison_batch_03.json`` at
``E4_STATIC_MACHINE_CODE``:

* six mode-aware raw-encoding comparison operators
* one signed int32 -> FixPoint raw bridge
* three boxed sign/zero predicate leaves

FixPoint is modeled as its single recovered qword raw encoding.  The sandbox
does not simulate IL2CPP boxing; ``get_IsZero`` etc. read the boxed qword at
offset +0 in the client, so their canonical input is the raw qword itself.

Deliberate client-faithful details preserved here:

* STANDARD raw = signed64 << 0x21; EXTENDED raw = (signed64 << 0x1A) | 1.
* Mixed-mode comparison shifts the STANDARD side right by 7 (arithmetic) and
  clears the EXTENDED flag; a non-zero low-7-bit fraction on the STANDARD side
  wins a comparison tie as greater-than.
* ``IsZero`` is true for both encodings of zero (raw 0 and raw 1).
* ``IsPositive`` masks the mode flag first, so EXTENDED zero (raw 1) is false.
"""
from __future__ import annotations

from hsr_battle_agent.battle_ir.values import EvaluatorSpec

_MASK64 = 0xFFFFFFFFFFFFFFFF
_SIGN64 = 1 << 63
_INT64_MIN = -(2**63)
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1
_STANDARD_SHIFT = 0x21  # 33
_EXTENDED_SHIFT = 0x1A  # 26
_EXTENDED_THRESHOLD = 0x40000000
_MIXED_MODE_SHIFT = 7
_FRACTION_MASK = 0x7F


def fixpoint_from_int32(value: int) -> int:
    """E4 ``op_Implicit(int32 -> FixPoint)`` raw encoding.

    ``abs(n) < 0x40000000`` produces STANDARD raw ``n << 0x21``; otherwise the
    EXTENDED raw ``(n << 0x1A) | 1`` is returned.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"value must be int, got {type(value).__name__}")
    if not (_INT32_MIN <= value <= _INT32_MAX):
        raise ValueError(f"value out of int32 range: {value}")
    if abs(value) >= _EXTENDED_THRESHOLD:
        return ((value << _EXTENDED_SHIFT) & _MASK64) | 1
    return (value << _STANDARD_SHIFT) & _MASK64


def fixpoint_equal(lhs: int, rhs: int) -> bool:
    """E4 ``FixPoint.op_Equality``: mode-aware raw equality."""
    _validate_raw(lhs, "lhs")
    _validate_raw(rhs, "rhs")
    return _fixpoint_compare(lhs, rhs) == 0


def fixpoint_not_equal(lhs: int, rhs: int) -> bool:
    """E4 ``FixPoint.op_Inequality``: mode-aware raw inequality."""
    _validate_raw(lhs, "lhs")
    _validate_raw(rhs, "rhs")
    return _fixpoint_compare(lhs, rhs) != 0


def fixpoint_less(lhs: int, rhs: int) -> bool:
    """E4 ``FixPoint.op_LessThan``: mode-aware raw less-than."""
    _validate_raw(lhs, "lhs")
    _validate_raw(rhs, "rhs")
    return _fixpoint_compare(lhs, rhs) < 0


def fixpoint_less_equal(lhs: int, rhs: int) -> bool:
    """E4 ``FixPoint.op_LessThanOrEqual``: mode-aware raw less-or-equal."""
    _validate_raw(lhs, "lhs")
    _validate_raw(rhs, "rhs")
    return _fixpoint_compare(lhs, rhs) <= 0


def fixpoint_greater(lhs: int, rhs: int) -> bool:
    """E4 ``FixPoint.op_GreaterThan``: mode-aware raw greater-than."""
    _validate_raw(lhs, "lhs")
    _validate_raw(rhs, "rhs")
    return _fixpoint_compare(lhs, rhs) > 0


def fixpoint_greater_equal(lhs: int, rhs: int) -> bool:
    """E4 ``FixPoint.op_GreaterThanOrEqual``: mode-aware raw greater-or-equal."""
    _validate_raw(lhs, "lhs")
    _validate_raw(rhs, "rhs")
    return _fixpoint_compare(lhs, rhs) >= 0


def fixpoint_is_zero(value: int) -> bool:
    """E4 ``get_IsZero``: raw < 2 unsigned -> true (raw 0 or 1)."""
    _validate_raw(value, "value")
    return (value & _MASK64) < 2


def fixpoint_is_negative(value: int) -> bool:
    """E4 ``get_IsNegative``: sign bit (bit 63) of the raw qword."""
    _validate_raw(value, "value")
    return ((value & _MASK64) >> 63) == 1


def fixpoint_is_positive(value: int) -> bool:
    """E4 ``get_IsPositive``: signed(raw & ~1) > 0."""
    _validate_raw(value, "value")
    return _to_signed64(value & ~1) > 0


def _fixpoint_compare(lhs: int, rhs: int) -> int:
    """Consolidated native dataflow of all six compare bodies.

    Returns -1 / 0 / 1 exactly like the sign computation each native operator
    feeds into its final ``sete``/``setne``/``setl``/``setle``/``setg``/
    ``setns``.  This is not a client callee; it is the ABI-independent
    consolidation documented in the semantic artifact.
    """
    lhs = lhs & _MASK64
    rhs = rhs & _MASK64
    lhs_extended = lhs & 1
    rhs_extended = rhs & 1

    if lhs_extended and not rhs_extended:
        comparison = _signed_cmp(
            _to_signed64(lhs & ~1),
            _to_signed64(_sar64(rhs, _MIXED_MODE_SHIFT)),
        )
        if comparison == 0 and (rhs & _FRACTION_MASK):
            return -1
        return comparison

    if not lhs_extended and rhs_extended:
        comparison = _signed_cmp(
            _to_signed64(_sar64(lhs, _MIXED_MODE_SHIFT)),
            _to_signed64(rhs & ~1),
        )
        if comparison == 0 and (lhs & _FRACTION_MASK):
            return 1
        return comparison

    if not lhs_extended and not rhs_extended:
        return _signed_cmp(_to_signed64(lhs), _to_signed64(rhs))

    return _signed_cmp(
        _to_signed64(lhs & ~1),
        _to_signed64(rhs & ~1),
    )


def _signed_cmp(lhs: int, rhs: int) -> int:
    return (lhs > rhs) - (lhs < rhs)


def _to_signed64(value: int) -> int:
    value &= _MASK64
    return value - (1 << 64) if value & _SIGN64 else value


def _sar64(value: int, shift: int) -> int:
    """Arithmetic shift right of a 64-bit raw qword."""
    return (_to_signed64(value) >> shift) & _MASK64


def _validate_raw(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    # The native operand is a qword.  Accept both signed int64 spellings and
    # unsigned qword spellings; every value is normalized with _MASK64 below.
    if not (_INT64_MIN <= value <= _MASK64):
        raise ValueError(f"{name} out of qword raw range: {value}")


def evaluator_spec_from_int32(value: int) -> EvaluatorSpec:
    """E4 ``ValueEvaluatorConfig.BBNJCKPKPDN(int32)``.

    Native: allocate the evaluator-spec operand object and store
    ``FixPointFromInt32(value)`` at ``[obj+0x20]``.  The canonical sandbox
    representation is an immutable ``EvaluatorSpec``; no allocation occurs.
    """
    return EvaluatorSpec(fixpoint_from_int32(value))


def evaluator_spec_from_fixpoint_raw(value: int) -> EvaluatorSpec:
    """E4 ``ValueEvaluatorConfig.BBNJCKPKPDN(FixPoint)``.

    Native: allocate the same operand object and store the raw FixPoint qword
    at ``[obj+0x20]``.
    """
    _validate_raw(value, "value")
    return EvaluatorSpec(value)


def evaluator_spec_fixpoint_equal_int32(
    evaluator_spec: EvaluatorSpec | None,
    rhs: int,
) -> bool:
    """E4 ``ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, int32)``.

    Native chain: null / wrong-type operand -> false; otherwise read
    ``[obj+0x20]``, convert ``rhs`` with ``FixPointFromInt32`` and return
    ``FixPointEqual(lhs_raw, rhs_raw)``.  Comparison logic is the Batch 03
    shared helper, never a second implementation.
    """
    spec = _coerce_evaluator_spec(evaluator_spec)
    if spec is None:
        return False
    return fixpoint_equal(spec.fixpoint_raw, fixpoint_from_int32(rhs))


def evaluator_spec_fixpoint_equal_raw(
    evaluator_spec: EvaluatorSpec | None,
    rhs: int,
) -> bool:
    """E4 ``ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, FixPoint)``.

    Native chain: null / wrong-type operand -> false; otherwise read
    ``[obj+0x20]`` and return ``FixPointEqual(lhs_raw, rhs)``.
    """
    spec = _coerce_evaluator_spec(evaluator_spec)
    if spec is None:
        return False
    return fixpoint_equal(spec.fixpoint_raw, rhs)


def evaluator_spec_fixpoint_not_equal_raw(
    evaluator_spec: EvaluatorSpec | None,
    rhs: int,
) -> bool:
    """E4 ``ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, FixPoint)``.

    Native chain: null / wrong-type operand -> **true** (operator default,
    confirmed by the ``mov al,1`` prelude); otherwise read ``[obj+0x20]`` and
    return ``FixPointNotEqual(lhs_raw, rhs)``.
    """
    spec = _coerce_evaluator_spec(evaluator_spec)
    if spec is None:
        return True
    return fixpoint_not_equal(spec.fixpoint_raw, rhs)


def _coerce_evaluator_spec(value: object) -> EvaluatorSpec | None:
    """Mirror the native is-instance gate.

    The client accepts the runtime class and its subclasses.  The canonical
    model has exactly one such class, ``EvaluatorSpec``; any other object maps
    to the proven null/wrong-type default path.
    """
    if isinstance(value, EvaluatorSpec):
        return value
    return None
