"""Deterministic weighted random selection (KERNEL-RNG-001 reference).

The sandbox RNG abstraction is already frozen in
``hsr_battle_agent.battle_sandbox.rng``: deterministic Python MT19937 with
64-bit draws and clone/snapshot/hash support.  This module adds the selected
RandomConfig semantics: one uniform draw maps to the first task whose
cumulative normalized odds exceeds the draw.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any, Iterable

from hsr_battle_agent.game_data.dynamic_value_reference import DynamicValueSemanticError


class RngSemanticError(DynamicValueSemanticError):
    """A random-selection configuration cannot be evaluated safely."""


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise RngSemanticError(f"non-numeric odds value {value!r}") from error


@dataclass(frozen=True)
class RandomSelection:
    selected_index: int
    draw: Decimal
    normalized_odds: tuple[Decimal, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "selected_index": self.selected_index,
            "draw": str(self.draw),
            "normalized_odds": [str(value) for value in self.normalized_odds],
        }


def select_weighted_index(odds: Iterable[Any], random_01: Any) -> RandomSelection:
    """Select one index with the odds list and a uniform [0,1) draw."""
    values = tuple(_d(value) for value in odds)
    if not values:
        raise RngSemanticError("RandomConfig OddsList must not be empty")
    if any(value < 0 for value in values):
        raise RngSemanticError("RandomConfig odds must be non-negative")
    total = sum(values)
    if total <= 0:
        raise RngSemanticError("RandomConfig odds sum must be positive")
    with localcontext() as context:
        context.prec = 38
        normalized = tuple(value / total for value in values)
        draw = _d(random_01)
        if not 0 <= draw <= 1:
            raise RngSemanticError("random draw must be in [0,1]")
        cumulative = Decimal("0")
        selected = len(values) - 1
        for index, value in enumerate(normalized):
            cumulative += value
            if draw < cumulative:
                selected = index
                break
    return RandomSelection(selected_index=selected, draw=draw, normalized_odds=normalized)


def rng_01_from_seed(seed: int) -> float:
    """Draw one deterministic uniform value from the frozen sandbox RNG."""
    from hsr_battle_agent.battle_sandbox.rng import SandboxRng

    rng = SandboxRng(seed=seed)
    return rng.uniform(0.0, 1.0)
