"""Versioned caller policy and objectives for the local reference battle scope."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.reference_sandbox import ReferenceBattleSession, SCOPE

POLICY_SCHEMA = "ReferenceBattleSearchPolicy/1"
OBJECTIVE_SCHEMA = "ReferenceBattleObjective/1"
HORIZON_ENTITY = "ENTITY_FIELD_AT_HORIZON"
HORIZON_RESOURCE = "RESOURCE_AT_HORIZON"
REACH_ENTITY = "REACH_ENTITY_FIELD_COMPARISON"
MIN_ENTITY = "MIN_STEPS_TO_ENTITY_FIELD_COMPARISON"
REACH_RESOURCE = "REACH_RESOURCE_COMPARISON"
MIN_RESOURCE = "MIN_STEPS_TO_RESOURCE_COMPARISON"
HORIZON_KINDS = frozenset((HORIZON_ENTITY, HORIZON_RESOURCE))
ENTITY_KINDS = frozenset((HORIZON_ENTITY, REACH_ENTITY, MIN_ENTITY))
RESOURCE_KINDS = frozenset((HORIZON_RESOURCE, REACH_RESOURCE, MIN_RESOURCE))
OPERATORS = frozenset(("LT", "LE", "EQ", "GE", "GT"))


class BattlePlannerContractError(ValueError):
    pass


def digest(document: Mapping[str, Any], domain: str) -> str:
    return hashlib.sha256(domain.encode("utf-8") + b"\0" + canonical_v2_bytes(document)).hexdigest()


def _token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise BattlePlannerContractError(f"invalid {name}")
    return value


def _decimal_text(value: Decimal) -> str:
    return "0" if value == 0 else format(value.normalize(), "f")


@dataclass(frozen=True)
class ReferenceBattleSearchPolicy:
    namespace: str
    version: str
    max_depth: int
    node_limit: int
    max_plans: int

    def __post_init__(self) -> None:
        _token(self.namespace, "namespace")
        _token(self.version, "version")
        for name in ("max_depth", "node_limit", "max_plans"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "max_depth" else 1):
                raise BattlePlannerContractError(f"invalid {name}")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": POLICY_SCHEMA, "namespace": self.namespace, "version": self.version,
                "transition_scope": SCOPE, "strategy": "BOUNDED_DFS",
                "branch_ordering": "SOURCE_ORDER", "dedup_mode": "ACCOUNT_ONLY",
                "max_depth": self.max_depth, "node_limit": self.node_limit,
                "max_plans": self.max_plans, "search_rng_draws": 0}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReferenceBattleSearchPolicy":
        fields = set(cls("x", "1", 0, 1, 1).to_dict())
        if not isinstance(data, Mapping) or set(data) != fields:
            raise BattlePlannerContractError("invalid search policy shape")
        if any(data[key] != value for key, value in (
            ("schema", POLICY_SCHEMA), ("transition_scope", SCOPE),
            ("strategy", "BOUNDED_DFS"), ("branch_ordering", "SOURCE_ORDER"),
            ("dedup_mode", "ACCOUNT_ONLY"))):
            raise BattlePlannerContractError("unsupported search policy")
        if type(data["search_rng_draws"]) is not int or data["search_rng_draws"] != 0:
            raise BattlePlannerContractError("search RNG forbidden")
        return cls(data["namespace"], data["version"], data["max_depth"],
                   data["node_limit"], data["max_plans"])

    @property
    def identity(self) -> str:
        return digest(self.to_dict(), "reference-battle-search-policy/1")


@dataclass(frozen=True)
class ReferenceBattleObjective:
    namespace: str
    version: str
    kind: str
    field: str
    entity_id: str | None = None
    direction: str | None = None
    operator: str | None = None
    threshold: Decimal | None = None

    def __post_init__(self) -> None:
        _token(self.namespace, "namespace")
        _token(self.version, "version")
        if self.kind not in ENTITY_KINDS | RESOURCE_KINDS:
            raise BattlePlannerContractError("unsupported objective kind")
        if self.kind in ENTITY_KINDS:
            if self.field not in ("HP", "TOUGHNESS"):
                raise BattlePlannerContractError("unsupported entity field")
            _token(self.entity_id, "entity_id")
        elif self.field != "REFERENCE_TEAM_RESOURCE" or self.entity_id is not None:
            raise BattlePlannerContractError("invalid resource field/entity")
        if self.kind in HORIZON_KINDS:
            if self.direction not in ("MAXIMIZE", "MINIMIZE") or self.operator is not None or self.threshold is not None:
                raise BattlePlannerContractError("invalid horizon objective")
        else:
            if self.direction is not None or self.operator not in OPERATORS:
                raise BattlePlannerContractError("invalid reach operator")
            if not isinstance(self.threshold, Decimal) or not self.threshold.is_finite():
                raise BattlePlannerContractError("threshold must be an explicit finite Decimal")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": OBJECTIVE_SCHEMA, "namespace": self.namespace, "version": self.version,
                "transition_scope": SCOPE, "kind": self.kind, "field": self.field,
                "entity_id": self.entity_id, "direction": self.direction,
                "operator": self.operator,
                "threshold": None if self.threshold is None else _decimal_text(self.threshold),
                "preference_scope": "CALLER_DECLARED_LOCAL"}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReferenceBattleObjective":
        fields = set(cls("x", "1", HORIZON_RESOURCE, "REFERENCE_TEAM_RESOURCE", direction="MAXIMIZE").to_dict())
        if not isinstance(data, Mapping) or set(data) != fields or data["schema"] != OBJECTIVE_SCHEMA:
            raise BattlePlannerContractError("invalid objective shape")
        if data["transition_scope"] != SCOPE or data["preference_scope"] != "CALLER_DECLARED_LOCAL":
            raise BattlePlannerContractError("invalid objective scope")
        threshold = data["threshold"]
        if threshold is not None:
            if not isinstance(threshold, str):
                raise BattlePlannerContractError("threshold must be serialized as text")
            try:
                parsed = Decimal(threshold)
            except InvalidOperation as exc:
                raise BattlePlannerContractError("invalid threshold") from exc
            if not parsed.is_finite() or _decimal_text(parsed) != threshold:
                raise BattlePlannerContractError("noncanonical threshold")
            threshold = parsed
        return cls(data["namespace"], data["version"], data["kind"], data["field"],
                   data["entity_id"], data["direction"], data["operator"], threshold)

    @property
    def identity(self) -> str:
        return digest(self.to_dict(), "reference-battle-objective/1")

    def supports(self, session: ReferenceBattleSession) -> bool:
        return isinstance(session, ReferenceBattleSession) and (
            self.kind in RESOURCE_KINDS or
            self.entity_id in {entity.entity_id for entity in session.combat_state.entities})

    def evaluate(self, session: ReferenceBattleSession, depth: int, horizon: int) -> tuple[bool, dict[str, Any]]:
        if not self.supports(session):
            raise BattlePlannerContractError("objective entity is absent")
        combat = session.combat_state
        if self.kind in ENTITY_KINDS:
            entity = combat.entity(self.entity_id)
            amount = entity.hp if self.field == "HP" else entity.toughness
        else:
            amount = combat.resource_current
        value = {"field": self.field, "entity_id": self.entity_id,
                 "amount": _decimal_text(amount), "committed_steps": depth}
        if self.kind in HORIZON_KINDS:
            return depth == horizon, value
        assert self.threshold is not None
        return {"LT": amount < self.threshold, "LE": amount <= self.threshold,
                "EQ": amount == self.threshold, "GE": amount >= self.threshold,
                "GT": amount > self.threshold}[self.operator], value

    def rank_key(self, value: Mapping[str, Any], ordinals: tuple[int, ...]) -> tuple[Any, ...]:
        if self.kind in HORIZON_KINDS:
            amount = Decimal(value["amount"])
            return (-amount if self.direction == "MAXIMIZE" else amount, ordinals)
        return (value["committed_steps"], ordinals)
