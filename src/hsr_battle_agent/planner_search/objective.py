"""Caller-declared objectives over one explicit sandbox resource."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxResourceContract,
    read_sandbox_resource_state,
)
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.planner_search.policy import identity, token

OBJECTIVE_SCHEMA = "PlannerObjective/1"
AT_HORIZON = "RESOURCE_AT_HORIZON"
REACH = "REACH_RESOURCE_COMPARISON"
MIN_STEPS = "MIN_STEPS_TO_RESOURCE_COMPARISON"
OPERATORS = frozenset(("LT", "LE", "EQ", "GE", "GT"))


class PlannerObjectiveError(ValueError):
    pass


def decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def finite_decimal(value: Any, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise PlannerObjectiveError(f"{name} must be an explicit finite Decimal")
    return value


@dataclass(frozen=True)
class PlannerObjective:
    namespace: str
    version: str
    kind: str
    resource_key: str
    comparison: str | None = None
    operator: str | None = None
    threshold: Decimal | None = None

    def __post_init__(self) -> None:
        token(self.namespace, "namespace")
        token(self.version, "version")
        token(self.resource_key, "resource_key")
        if self.kind == AT_HORIZON:
            if self.comparison not in ("MAXIMIZE", "MINIMIZE"):
                raise PlannerObjectiveError("horizon comparison must be MAXIMIZE or MINIMIZE")
            if self.operator is not None or self.threshold is not None:
                raise PlannerObjectiveError("horizon objective cannot have a predicate")
        elif self.kind in (REACH, MIN_STEPS):
            if self.comparison is not None or self.operator not in OPERATORS:
                raise PlannerObjectiveError("predicate objective needs an explicit operator")
            finite_decimal(self.threshold, "threshold")
        else:
            raise PlannerObjectiveError("unsupported objective kind")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OBJECTIVE_SCHEMA,
            "namespace": self.namespace,
            "version": self.version,
            "kind": self.kind,
            "resource_key": self.resource_key,
            "comparison": self.comparison,
            "operator": self.operator,
            "threshold": None if self.threshold is None else decimal_text(self.threshold),
            "preference_scope": "CALLER_DECLARED_LOCAL",
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlannerObjective":
        if not isinstance(data, Mapping) or set(data) != {
            "schema", "namespace", "version", "kind", "resource_key",
            "comparison", "operator", "threshold", "preference_scope",
        }:
            raise PlannerObjectiveError("objective has missing or unknown fields")
        if data["schema"] != OBJECTIVE_SCHEMA or data["preference_scope"] != "CALLER_DECLARED_LOCAL":
            raise PlannerObjectiveError("unknown objective schema or preference scope")
        threshold = data["threshold"]
        if threshold is not None:
            if not isinstance(threshold, str):
                raise PlannerObjectiveError("serialized threshold must be a decimal string")
            try:
                threshold = Decimal(threshold)
            except InvalidOperation as exc:
                raise PlannerObjectiveError("invalid threshold") from exc
            if not threshold.is_finite() or decimal_text(threshold) != data["threshold"]:
                raise PlannerObjectiveError("threshold is non-finite or non-canonical")
        return cls(
            data["namespace"], data["version"], data["kind"],
            data["resource_key"], data["comparison"], data["operator"], threshold,
        )

    @property
    def identity(self) -> str:
        return identity(self.to_dict())

    def supports(self, contract: SandboxResourceContract) -> bool:
        return isinstance(contract, SandboxResourceContract) and self.resource_key == contract.resource_key

    def evaluate(
        self, state: TerraBattleState, contract: SandboxResourceContract,
        depth: int, horizon: int,
    ) -> tuple[bool, dict[str, Any]]:
        if not self.supports(contract):
            raise PlannerObjectiveError("objective resource differs from supplied contract")
        amount = read_sandbox_resource_state(state, contract).amount
        value = {"resource_amount": decimal_text(amount), "committed_steps": depth}
        if self.kind == AT_HORIZON:
            return depth == horizon, value
        assert self.threshold is not None
        matched = {
            "LT": amount < self.threshold,
            "LE": amount <= self.threshold,
            "EQ": amount == self.threshold,
            "GE": amount >= self.threshold,
            "GT": amount > self.threshold,
        }[self.operator]
        return matched, value

    def rank_key(self, value: Mapping[str, Any], ordinals: tuple[int, ...]) -> tuple[Any, ...]:
        if self.kind == AT_HORIZON:
            amount = Decimal(value["resource_amount"])
            return ((-amount if self.comparison == "MAXIMIZE" else amount), ordinals)
        return (value["committed_steps"], ordinals)
