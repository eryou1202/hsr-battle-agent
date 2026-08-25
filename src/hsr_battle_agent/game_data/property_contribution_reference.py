"""Deterministic property-contribution reference (modifier property effect).

Anchored by ``modifier_property_effect_09.json``: each modifier owns stable
contribution slots keyed by (modifier identity, property); refresh updates the
slot without shifting neighbours; removal deletes exactly that slot; the
observable property value is base + sum(contributions).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .dynamic_value_reference import DynamicValueSemanticError


class PropertyContributionError(DynamicValueSemanticError):
    """A property-contribution transition is invalid."""


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as error:  # noqa: BLE001
        raise PropertyContributionError(f"non-numeric property value {value!r}") from error


@dataclass(frozen=True)
class PropertyContributionTransition:
    state: "PropertyState"
    action: str
    slot: str
    value: Decimal | None = None

    def as_json(self) -> dict[str, Any]:
        return {"action": self.action, "slot": self.slot, "value": None if self.value is None else str(self.value)}


@dataclass(frozen=True)
class PropertyState:
    base: Mapping[str, str] = ()
    contributions: Mapping[str, str] = ()

    @staticmethod
    def empty(base: Mapping[str, Any] | None = None) -> "PropertyState":
        return PropertyState(base={str(key): str(_d(value)) for key, value in (base or {}).items()}, contributions={})

    def read(self, property_name: str) -> Decimal:
        total = _d(self.base.get(property_name, 0))
        for slot, raw in self.contributions.items():
            slot_property, _separator, _modifier = slot.partition("@")
            if slot_property == property_name:
                total += _d(raw)
        return total

    def set_contribution(self, modifier_id: str, property_name: str, value: Any) -> PropertyContributionTransition:
        slot = f"{property_name}@{modifier_id}"
        contributions = dict(self.contributions)
        contributions[slot] = str(_d(value))
        return PropertyContributionTransition(PropertyState(self.base, contributions), "SET_CONTRIBUTION", slot, _d(value))

    def remove_contribution(self, modifier_id: str, property_name: str) -> PropertyContributionTransition:
        slot = f"{property_name}@{modifier_id}"
        if slot not in self.contributions:
            return PropertyContributionTransition(self, "REMOVE_CONTRIBUTION_MISSING", slot)
        contributions = dict(self.contributions)
        removed = _d(contributions.pop(slot))
        return PropertyContributionTransition(PropertyState(self.base, contributions), "REMOVE_CONTRIBUTION", slot, removed)

    def as_json(self) -> dict[str, Any]:
        return {"base": dict(sorted(self.base.items())), "contributions": dict(sorted(self.contributions.items()))}
