"""Reference fixed-point arithmetic and the archived heal FormulaType2 core.

Only bounded signed mode0 operands are supported. Tagged/mixed/overflow domains
are blockers, not approximations. Rounding is toward zero, a reference policy.
"""
from __future__ import annotations

from dataclasses import dataclass


SCALE = 1 << 33


class NumericSemanticGap(ValueError):
    pass


def raw_checked(raw: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise NumericSemanticGap("fixed-point raw operand must be an integer")
    if not -(2**63) <= raw < 2**63:
        raise NumericSemanticGap("fixed-point overflow/domain requires native oracle")
    if raw & 1:
        raise NumericSemanticGap("tagged/mixed fixed-point domain requires native oracle")
    return raw


def truncate_ratio(numerator: int, denominator: int) -> int:
    if denominator == 0:
        raise NumericSemanticGap("fixed-point division by zero")
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    # Mode0's tag bit must remain clear. Quantize at the representable raw step.
    return sign * ((abs(numerator) // (abs(denominator) * 2)) * 2)


def fixed_binary(op: str, left: int, right: int) -> int:
    raw_checked(left)
    raw_checked(right)
    if op == "add":
        value = left + right
    elif op == "sub":
        value = left - right
    elif op == "mul":
        value = truncate_ratio(left * right, SCALE)
    elif op == "div":
        value = truncate_ratio(left * SCALE, right)
    else:
        raise NumericSemanticGap(f"unknown arithmetic operation {op}")
    return raw_checked(value)


@dataclass(frozen=True)
class HealCoreResult:
    amount_raw: int
    semantic_authority: str = "REFERENCE_MODEL"
    unresolved_extension_points: tuple[str, ...] = (
        "pre_heal_hooks", "effective_amount_modifiers", "settlement",
        "property_mutation_hooks", "post_heal_hooks", "resource_listeners")


def heal_formula2_core(operands: dict[str, int], cap_enabled: bool) -> HealCoreResult:
    """All dXX operands/flag supplied explicitly; no missing/default-zero values.

    Offsets are recovered generic HealData operand names, not content hashes.
    This function computes an amount only; it never performs HP settlement.
    """
    if not isinstance(cap_enabled, bool):
        raise NumericSemanticGap("heal cap flag must be supplied as a boolean")
    names = {"d50", "d28", "d60", "dD0", "d38", "d128", "d48", "dD8"}
    if cap_enabled:
        names |= {"d70", "d68", "d40"}
    missing = names - operands.keys()
    if missing:
        raise NumericSemanticGap("missing heal operands: " + ",".join(sorted(missing)))
    d = {key: raw_checked(operands[key]) for key in names}
    add = lambda a, b: fixed_binary("add", a, b)
    mul = lambda a, b: fixed_binary("mul", a, b)
    div = lambda a, b: fixed_binary("div", a, b)
    base = add(mul(d["d50"], d["d28"]), d["d60"])
    outgoing = mul(base, add(add(SCALE, d["dD0"]), d["d38"]))
    correction = add(mul(add(SCALE, d["d128"]), div(d["d48"], 100 * SCALE)),
                     div(d["dD8"], 100 * SCALE))
    amount = max(0, mul(outgoing, correction))
    if cap_enabled:
        amount = min(amount, max(0, fixed_binary("sub", mul(d["d70"], d["d68"]), d["d40"])))
    return HealCoreResult(amount)
