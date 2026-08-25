"""Deterministic reference semantics for damage and survival (PRIM-DAMAGE /
PRIM-SURVIVAL selected models).

Damage amount formulas are R2 mature-implementation reconstructions from the
pinned hsr-optimizer damageCalculator.ts snapshot; ordering/commit boundaries
are the reconstruction program's selected deterministic model anchored by
KERNEL-EVENT-001 and the ordinary-MVP HP packets.  This module is a reference,
not the production battle runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from typing import Any, Mapping

from .dynamic_value_reference import DynamicValueSemanticError


class DamageSemanticError(DynamicValueSemanticError):
    """A damage/survival transition cannot be reconstructed safely."""


LEVEL_CONST = Decimal("100")


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise DamageSemanticError("boolean is not numeric")
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise DamageSemanticError(f"non-numeric damage value: {value!r}") from error


@dataclass(frozen=True)
class DamageMultiplierContext:
    enemy_level: int = 80
    def_pen: Decimal = Decimal("0")
    damage_resistance: Decimal = Decimal("0")
    res_pen: Decimal = Decimal("0")
    vulnerability: Decimal = Decimal("0")
    final_dmg_boost: Decimal = Decimal("0")
    dmg_boost: Decimal = Decimal("0")
    base_universal_multiplier: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if self.enemy_level <= 0:
            raise DamageSemanticError("enemy_level must be positive")


def initial_damage(*, atk: Any, hp: Any, defense: Any, atk_scaling: Any = 0, hp_scaling: Any = 0, def_scaling: Any = 0, be_scaling: Any | None = None, break_effect: Any = 0, be_cap: Any | None = None) -> Decimal:
    total_atk_scaling = _d(atk_scaling)
    if be_scaling is not None:
        be = _d(break_effect)
        if be_cap is not None:
            be = min(be, _d(be_cap))
        total_atk_scaling += _d(be_scaling) * be
    return total_atk_scaling * _d(atk) + _d(hp_scaling) * _d(hp) + _d(def_scaling) * _d(defense)


def defense_multiplier(enemy_level: int, def_pen: Any = 0) -> Decimal:
    denominator = (Decimal(enemy_level) + Decimal("20")) * max(Decimal("0"), Decimal("1") - _d(def_pen)) + LEVEL_CONST
    return LEVEL_CONST / denominator


def resistance_multiplier(damage_resistance: Any = 0, res_pen: Any = 0) -> Decimal:
    return Decimal("1") - (_d(damage_resistance) - _d(res_pen))


def crit_multiplier(crit_rate: Any, crit_damage: Any) -> Decimal:
    cr = min(Decimal("1"), _d(crit_rate))
    cd = _d(crit_damage)
    return cr * (Decimal("1") + cd) + (Decimal("1") - cr)


def normal_damage(ability_amount: Decimal, context: DamageMultiplierContext, *, crit_rate: Any = 1, crit_damage: Any = 0) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 38
        return ability_amount * context.base_universal_multiplier * defense_multiplier(context.enemy_level, context.def_pen) * resistance_multiplier(context.damage_resistance, context.res_pen) * (Decimal("1") + _d(context.vulnerability)) * (Decimal("1") + _d(context.final_dmg_boost)) * (Decimal("1") + _d(context.dmg_boost)) * crit_multiplier(crit_rate, crit_damage)


def break_damage(*, elemental_break_scaling: Any, enemy_max_toughness: Any, special_scaling: Any = 1, break_effect: Any = 0, context: DamageMultiplierContext) -> Decimal:
    base = Decimal("3767.5533") * _d(elemental_break_scaling) * (Decimal("0.5") + _d(enemy_max_toughness) / Decimal("120")) * _d(special_scaling)
    with localcontext() as ctx:
        ctx.prec = 38
        return context.base_universal_multiplier * defense_multiplier(context.enemy_level, context.def_pen) * resistance_multiplier(context.damage_resistance, context.res_pen) * (Decimal("1") + _d(context.vulnerability)) * (Decimal("1") + _d(context.final_dmg_boost)) * (Decimal("1") + _d(context.dmg_boost)) * base * (Decimal("1") + _d(break_effect))


def super_break_damage(*, toughness_damage: Any, fixed_toughness_damage: Any = 0, break_efficiency: Any = 1, super_break_modifier: Any = 1, break_effect: Any = 0, context: DamageMultiplierContext) -> Decimal:
    effective_toughness = _d(break_efficiency) * _d(toughness_damage) + _d(fixed_toughness_damage)
    base = (Decimal("3767.5533") / Decimal("10")) * effective_toughness
    with localcontext() as ctx:
        ctx.prec = 38
        return context.base_universal_multiplier * defense_multiplier(context.enemy_level, context.def_pen) * resistance_multiplier(context.damage_resistance, context.res_pen) * (Decimal("1") + _d(context.vulnerability)) * (Decimal("1") + _d(context.final_dmg_boost)) * (Decimal("1") + _d(context.dmg_boost)) * base * (Decimal("1") + _d(break_effect)) * _d(super_break_modifier)


def dot_chance_multiplier(*, dot_base_chance: Any, ehr: Any = 0, enemy_effect_res: Any = 0, effect_res_pen: Any = 0, dot_split: Any = 0, dot_stacks: Any = 1) -> Decimal:
    effective_chance = min(Decimal("1"), _d(dot_base_chance) * (Decimal("1") + _d(ehr)) * (Decimal("1") - _d(enemy_effect_res) + _d(effect_res_pen)))
    split = _d(dot_split)
    stacks = max(1, int(_d(dot_stacks)))
    if split > 0:
        return (Decimal("1") + split * effective_chance * (stacks - 1)) / (Decimal("1") + split * (stacks - 1))
    return effective_chance


@dataclass(frozen=True)
class SurvivalState:
    hp: Decimal
    max_hp: Decimal
    shield: Decimal = Decimal("0")
    lock_hp: bool = False
    alive: bool = True

    def __post_init__(self) -> None:
        if self.hp < 0 or self.max_hp <= 0 or self.shield < 0:
            raise DamageSemanticError("invalid survival state")

    def heal(self, amount: Any) -> "SurvivalState":
        if not self.alive or self.lock_hp:
            return self
        healed = self.hp + _d(amount)
        return replace(self, hp=min(self.max_hp, max(self.hp, healed)))

    def apply_shield(self, amount: Any) -> "SurvivalState":
        if not self.alive:
            return self
        return replace(self, shield=self.shield + _d(amount))

    def absorb(self, amount: Any) -> tuple["SurvivalState", Decimal, Decimal]:
        """Damage first consumes shield, then HP. Locked HP never drops."""
        if not self.alive:
            return self, Decimal("0"), Decimal("0")
        remaining = _d(amount)
        absorbed = min(self.shield, remaining)
        remaining -= absorbed
        hp_before = self.hp
        if self.lock_hp:
            hp_after = self.hp
        else:
            hp_after = max(Decimal("0"), self.hp - remaining)
        hp_lost = hp_before - hp_after
        return replace(self, shield=self.shield - absorbed, hp=hp_after, alive=hp_after > 0), absorbed, hp_lost

    def set_lock_hp(self, locked: bool) -> "SurvivalState":
        return replace(self, lock_hp=bool(locked))

    def force_kill(self) -> "SurvivalState":
        if self.lock_hp:
            return self
        return replace(self, hp=Decimal("0"), alive=False)

    def as_json(self) -> Mapping[str, Any]:
        return {"hp": str(self.hp), "max_hp": str(self.max_hp), "shield": str(self.shield), "lock_hp": self.lock_hp, "alive": self.alive}
