# -*- coding: utf-8 -*-
"""DynamicValue runtime primitives.

``dynamic_value_equals`` is the faithful Python implementation of
``RPG.GameCore.DynamicValue.Equals(DynamicValue)`` (method_index 74632,
RVA 0x1CFBE9E0, E4_STATIC_MACHINE_CODE).

Batch 02 adds the eleven E4-recovered scalar coercions and tag/payload
queries from ``data/semantics/4.4.54/dynamic_value_batch_02.json``.  Each
function below mirrors the native body, including tag-mismatch default
values.  Native error-path log helpers are diagnostics only and have no
BattleState effect; the sandbox returns the native default without logging.

Semantic invariants deliberately preserved against Python/idiomatic defaults:

* type mismatch            -> false / 0 / 0.0 / null depending on primitive
* FLOAT uses IEEE equality, so NaN != NaN and +0.0 == -0.0
* BOOL normalizes ``payload == 1`` on both sides before comparison
* ARRAY / MAP compare ObjectRef identity only, never contents
* STRING is ordinal UTF-16 content equality (no culture, no casing)
* get_FloatValue returns **float32** (cvtsd2ss / cvtsi2ss), not Python double
* get_IntValue / get_UintValue truncate through the native 32-bit register
  semantics, including the x86 out-of-range/NaN indefinite values
"""
from __future__ import annotations

import math
import struct

from hsr_battle_agent.battle_ir.values import DynamicValue, DynamicValueType

_UTF16_ENCODING = "utf-16-le"
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1
_UINT32_MASK = 0xFFFFFFFF


def dynamic_value_equals(lhs: DynamicValue, rhs: DynamicValue) -> bool:
    """Execute ``DynamicValue.Equals`` semantic for two canonical cells."""
    _validate_operand(lhs, "lhs")
    _validate_operand(rhs, "rhs")

    left_tag = lhs.value_type
    right_tag = rhs.value_type

    # E4: tag mismatch -> false (checked before the >5 guard).
    if left_tag is not right_tag:
        return False

    # E4: tag > 5 -> false.  This covers NULL(6) and any invalid tag, so
    # NULL == NULL is false in this game method.
    if left_tag.value > 5:
        return False

    if left_tag is DynamicValueType.INT:
        return lhs.payload == rhs.payload

    if left_tag is DynamicValueType.FLOAT:
        # Python float == is IEEE-754 equality: NaN != NaN, +0.0 == -0.0.
        return lhs.payload == rhs.payload

    if left_tag is DynamicValueType.BOOL:
        # E4: (lhs.unionValue == 1) xor-NOT (rhs.unionValue == 1).
        return (lhs.payload == 1) == (rhs.payload == 1)

    if left_tag is DynamicValueType.ARRAY:
        return lhs.payload == rhs.payload  # ObjectRef identity equality

    if left_tag is DynamicValueType.MAP:
        return lhs.payload == rhs.payload  # ObjectRef identity equality

    if left_tag is DynamicValueType.STRING:
        return _string_equals(lhs.payload, rhs.payload)

    return False  # pragma: no cover - NULL and invalid tags returned above


def dynamic_value_to_int(value: DynamicValue) -> int:
    """E4 ``get_IntValue``: tag-aware DynamicValue -> signed int32.

    Native register semantics: INT reads the signed low 32-bit dword of
    unionValue; FLOAT uses ``cvttsd2si eax`` (truncate toward zero,
    out-of-range/NaN -> 0x80000000); BOOL normalizes ``union == 1``; every
    other tag logs and returns 0.
    """
    _validate_operand(value, "value")
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1 if value.payload == 1 else 0
    if tag is DynamicValueType.FLOAT:
        return _double_to_int32_trunc(value.payload)
    if tag is DynamicValueType.INT:
        return _int32_from_low32(value.payload)
    return 0  # E4 mismatch default after error-log helper


def dynamic_value_to_uint(value: DynamicValue) -> int:
    """E4 ``get_UintValue``: tag-aware DynamicValue -> unsigned int32.

    Native register semantics: INT returns the low 32-bit dword bit pattern
    as uint32; FLOAT uses ``cvttsd2si rax`` then returns the low 32 bits;
    BOOL normalizes ``union == 1``; every other tag logs and returns 0.
    """
    _validate_operand(value, "value")
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1 if value.payload == 1 else 0
    if tag is DynamicValueType.FLOAT:
        return _double_to_int64_trunc(value.payload) & _UINT32_MASK
    if tag is DynamicValueType.INT:
        return value.payload & _UINT32_MASK
    return 0  # E4 mismatch default after error-log helper


def dynamic_value_to_long(value: DynamicValue) -> int:
    """E4 ``get_LongValue``: tag-aware DynamicValue -> signed int64.

    INT returns the full signed unionValue qword; FLOAT uses ``cvttsd2si
    rax``; BOOL normalizes ``union == 1``; other tags log and return 0.
    The native one-time IL2CPP class-init branch is infrastructure and has
    no BattleState effect.
    """
    _validate_operand(value, "value")
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1 if value.payload == 1 else 0
    if tag is DynamicValueType.FLOAT:
        return _double_to_int64_trunc(value.payload)
    if tag is DynamicValueType.INT:
        return value.payload
    return 0  # E4 mismatch default after error-log helper


def dynamic_value_to_float(value: DynamicValue) -> float:
    """E4 ``get_FloatValue``: tag-aware DynamicValue -> IEEE-754 float32.

    The result is quantized to binary32, matching ``cvtsd2ss`` /
    ``cvtsi2ss`` with the default round-to-nearest-even MXCSR mode assumed
    by the evidence.  BOOL returns +1.0f only for unionValue == 1 and +0.0f
    otherwise (silently); other tags log and return +0.0f.
    """
    _validate_operand(value, "value")
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1.0 if value.payload == 1 else 0.0
    if tag is DynamicValueType.FLOAT:
        return _as_float32(value.payload)
    if tag is DynamicValueType.INT:
        return _int64_to_float32(value.payload)
    return 0.0  # E4 mismatch default after error-log helper


def dynamic_value_to_double(value: DynamicValue) -> float:
    """E4 ``get_DoubleValue``: tag-aware DynamicValue -> IEEE-754 float64.

    INT uses ``cvtsi2sd``; FLOAT returns the raw double payload; BOOL
    returns +1.0 only for unionValue == 1 and +0.0 otherwise; other tags
    log and return +0.0.  The native one-time IL2CPP class-init branch is
    infrastructure and has no BattleState effect.
    """
    _validate_operand(value, "value")
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return 1.0 if value.payload == 1 else 0.0
    if tag is DynamicValueType.FLOAT:
        return value.payload
    if tag is DynamicValueType.INT:
        return float(value.payload)  # cvtsi2sd, correctly-rounded int64->double
    return 0.0  # E4 mismatch default after error-log helper


def dynamic_value_to_bool(value: DynamicValue) -> bool:
    """E4 ``get_BoolValue``: tag-aware DynamicValue -> bool.

    BOOL returns ``unionValue == 1`` (silently false for other raw values).
    INT returns ``unionValue == 1`` for raw values 0/1; raw values >= 2 or
    negative hit the native invalid-value log path and still return false.
    Every other tag hits the mismatch log path and returns false.
    """
    _validate_operand(value, "value")
    tag = value.value_type
    if tag is DynamicValueType.BOOL:
        return value.payload == 1
    if tag is DynamicValueType.INT:
        # Native logs when raw < 0 or raw >= 2; logging has no value effect.
        return value.payload == 1
    return False  # E4 mismatch default after error-log helper


def dynamic_value_type(value: DynamicValue) -> int:
    """E4 ``get_ValueType``: raw tag ordinal (zero-extended byte @ +0x30)."""
    _validate_operand(value, "value")
    return value.tag


def dynamic_value_string(value: DynamicValue) -> str | None:
    """E4 ``get_StringValue``: STRING payload access.

    STRING returns the payload pointer as-is (null included); every other
    tag hits the mismatch log path and returns null.
    """
    _validate_operand(value, "value")
    if value.value_type is DynamicValueType.STRING:
        return value.payload
    return None  # E4 mismatch default after error-log helper


def dynamic_value_is_array(value: DynamicValue) -> bool:
    """E4 ``get_IsArray``: tag == ARRAY and arrayValue != null.

    Canonical ARRAY cells always carry a non-null ObjectRef; the native
    null-payload branch is retained defensively (REPRESENTATION_CONFLICT
    recorded in the Batch 02 artifact).
    """
    _validate_operand(value, "value")
    return (
        value.value_type is DynamicValueType.ARRAY
        and value.payload is not None
    )


def dynamic_value_is_map(value: DynamicValue) -> bool:
    """E4 ``get_IsMap``: tag == MAP and mapValue != null.

    Canonical MAP cells always carry a non-null ObjectRef; the native
    null-payload branch is retained defensively (REPRESENTATION_CONFLICT
    recorded in the Batch 02 artifact).
    """
    _validate_operand(value, "value")
    return (
        value.value_type is DynamicValueType.MAP
        and value.payload is not None
    )


def dynamic_value_is_null(value: DynamicValue) -> bool:
    """E4 ``get_IsNull``: tag == NULL."""
    _validate_operand(value, "value")
    return value.value_type is DynamicValueType.NULL


def _validate_operand(value: DynamicValue, name: str) -> None:
    if not isinstance(value, DynamicValue):
        raise TypeError(
            f"{name} must be a DynamicValue cell, got {type(value).__name__}"
        )


def _string_equals(left: str | None, right: str | None) -> bool:
    """E4 STRING case: same ref -> true; one null -> false; length differs ->
    false; otherwise ordinal UTF-16 content equality.

    We do not simulate System.String memory layout.  Encoding both Python
    strings as UTF-16 code units and comparing the code-unit sequences is the
    exact semantic of ordinal UTF-16 content equality.
    """
    if left is right:
        return True
    if left is None or right is None:
        return False

    left_units = left.encode(_UTF16_ENCODING, errors="surrogatepass")
    right_units = right.encode(_UTF16_ENCODING, errors="surrogatepass")
    if len(left_units) != len(right_units):  # UTF-16 code-unit length check
        return False
    return left_units == right_units


def _as_float32(value: float) -> float:
    """Round a Python float to IEEE-754 binary32 (cvtsd2ss semantics).

    NaN and infinities are preserved as such; overflow saturates to infinity
    like the x86 conversion instead of raising Python OverflowError.
    """
    if math.isnan(value):
        return math.nan
    if value == 0.0:
        return value  # preserve +/-0.0
    if math.isinf(value):
        return value
    try:
        return struct.unpack("<f", struct.pack("<f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def _int64_to_float32(value: int) -> float:
    """Exact signed int64 -> binary32 round-to-nearest-even (cvtsi2ss).

    Python's ``float(int)`` would round through binary64 first and can
    double-round large int64 values; this implementation rounds the integer
    significand once, directly to 24 bits.
    """
    if value == 0:
        return 0.0
    sign = 1 if value < 0 else 0
    magnitude = -value if value < 0 else value
    exponent = magnitude.bit_length() - 1
    shift = exponent - 23
    if shift <= 0:
        significand = magnitude << (-shift)
    else:
        quotient, remainder = divmod(magnitude, 1 << shift)
        twice_remainder = remainder * 2
        midpoint = 1 << shift
        if twice_remainder > midpoint or (
            twice_remainder == midpoint and quotient & 1
        ):
            quotient += 1
        significand = quotient
    if significand >= (1 << 24):
        significand >>= 1
        exponent += 1
    bits = (
        (sign << 31)
        | ((exponent + 127) << 23)
        | (significand & 0x7FFFFF)
    )
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def _double_to_int64_trunc(value: float) -> int:
    """Emulate x86 ``cvttsd2si rax``, including the indefinite integer.

    Truncation toward zero; NaN and values outside the signed int64 range
    produce 0x8000000000000000 (INT64_MIN).
    """
    if math.isnan(value) or value >= 2**63 or value < _INT64_MIN:
        return _INT64_MIN
    return int(value)


def _double_to_int32_trunc(value: float) -> int:
    """Emulate x86 ``cvttsd2si eax``, including the indefinite integer.

    Truncation toward zero; NaN and values outside the signed int32 range
    produce 0x80000000 (INT32_MIN).
    """
    if math.isnan(value) or value >= 2**31 or value < _INT32_MIN:
        return _INT32_MIN
    return int(value)


def _int32_from_low32(value: int) -> int:
    bits = value & _UINT32_MASK
    return bits if bits <= _INT32_MAX else bits - (1 << 32)
