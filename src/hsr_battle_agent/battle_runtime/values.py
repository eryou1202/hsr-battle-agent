# -*- coding: utf-8 -*-
"""DynamicValue runtime primitives.

``dynamic_value_equals`` is the faithful Python implementation of
``RPG.GameCore.DynamicValue.Equals(DynamicValue)`` (method_index 74632,
RVA 0x1CFBE9E0, E4_STATIC_MACHINE_CODE).  See
``docs/battle_semantics/vertical_slice_01.md`` for the recovered pseudocode
and ``docs/battle_sandbox/kernel_01.md`` for the mapping to Python.

Semantic invariants deliberately preserved against Python/idiomatic defaults:

* type mismatch            -> false
* tag > 5 (NULL, invalid)  -> false, so NULL == NULL is false
* FLOAT uses IEEE equality, so NaN != NaN and +0.0 == -0.0
* BOOL normalizes ``payload == 1`` on both sides before comparison
* ARRAY / MAP compare ObjectRef identity only, never contents
* STRING is ordinal UTF-16 content equality (no culture, no casing)
"""
from __future__ import annotations

from hsr_battle_agent.battle_ir.values import DynamicValue, DynamicValueType

_UTF16_ENCODING = "utf-16-le"


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
