"""Deterministic toughness/break reference (PRIM-SURVIVAL extension).

Selected model: toughness damage subtracts from current toughness; crossing
zero sets broken=true and triggers the Break damage amount formula from
PRIM-DAMAGE-001 at the same primitive boundary; recovery restores max
toughness and clears broken.  Native break delay values and weakness-provider
inputs remain separate packets.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Mapping

from .damage_survival_reference import break_damage, DamageMultiplierContext
from .dynamic_value_reference import DynamicValueSemanticError


class ToughnessError(DynamicValueSemanticError):
    """A toughness transition is invalid."""


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise ToughnessError(f"non-numeric toughness value {value!r}") from error


@dataclass(frozen=True)
class ToughnessState:
    max_toughness: Decimal
    current_toughness: Decimal
    broken: bool = False

    def __post_init__(self) -> None:
        if self.max_toughness < 0 or self.current_toughness < 0:
            raise ToughnessError("toughness values must be non-negative")
        if self.current_toughness > self.max_toughness:
            raise ToughnessError("current toughness exceeds max toughness")

    def apply_damage(self, amount: Any) -> "ToughnessState":
        if self.broken:
            return self
        remaining = self.current_toughness - _d(amount)
        if remaining > 0:
            return replace(self, current_toughness=remaining)
        return replace(self, current_toughness=Decimal("0"), broken=True)

    def recover(self) -> "ToughnessState":
        return replace(self, current_toughness=self.max_toughness, broken=False)

    def as_json(self) -> Mapping[str, Any]:
        return {"max_toughness": str(self.max_toughness), "current_toughness": str(self.current_toughness), "broken": self.broken}


@dataclass(frozen=True)
class BreakTransition:
    state: ToughnessState
    action: str
    break_damage: Decimal | None = None

    def as_json(self) -> dict[str, Any]:
        return {"action": self.action, "state": self.state.as_json(), "break_damage": None if self.break_damage is None else str(self.break_damage)}


def apply_toughness_damage(
    state: ToughnessState,
    amount: Any,
    *,
    elemental_break_scaling: Any = 1,
    enemy_max_toughness: Any | None = None,
    special_scaling: Any = 1,
    break_effect: Any = 0,
    damage_context: DamageMultiplierContext | None = None,
) -> BreakTransition:
    """Apply toughness damage; on zero-crossing return the Break damage."""
    before = state
    after = state.apply_damage(amount)
    if not before.broken and after.broken:
        max_toughness = _d(enemy_max_toughness if enemy_max_toughness is not None else state.max_toughness)
        context = damage_context or DamageMultiplierContext()
        damage = break_damage(
            elemental_break_scaling=elemental_break_scaling,
            enemy_max_toughness=max_toughness,
            special_scaling=special_scaling,
            break_effect=break_effect,
            context=context,
        )
        return BreakTransition(after, "BREAK_TRIGGERED", damage)
    return BreakTransition(after, "TOUGHNESS_REDUCED")


def recover_toughness(state: ToughnessState) -> BreakTransition:
    if not state.broken and state.current_toughness == state.max_toughness:
        return BreakTransition(state, "RECOVERY_NOOP")
    return BreakTransition(state.recover(), "RECOVERY_RESTORED")
