"""Versioned, deterministic search policy for the local resource seam."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes

POLICY_SCHEMA = "PlannerSearchPolicy/1"
SCOPE = "SANDBOX_RESOURCE_V1"


class PlannerPolicyError(ValueError):
    pass


def identity(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_v2_bytes(document)).hexdigest()


def token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PlannerPolicyError(f"{name} must be a non-empty trimmed string")
    return value


def positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PlannerPolicyError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class PlannerSearchPolicy:
    namespace: str
    version: str
    max_depth: int
    node_limit: int
    max_plans: int
    strategy: str = "BOUNDED_DFS"
    branch_ordering: str = "SOURCE_ORDER"
    dedup_mode: str = "ACCOUNT_ONLY"
    scope: str = SCOPE

    def __post_init__(self) -> None:
        token(self.namespace, "namespace")
        token(self.version, "version")
        for name in ("max_depth", "node_limit", "max_plans"):
            positive_int(getattr(self, name), name)
        required = {
            "strategy": "BOUNDED_DFS",
            "branch_ordering": "SOURCE_ORDER",
            "dedup_mode": "ACCOUNT_ONLY",
            "scope": SCOPE,
        }
        for name, expected in required.items():
            if getattr(self, name) != expected:
                raise PlannerPolicyError(f"{name} must be {expected}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": POLICY_SCHEMA,
            "namespace": self.namespace,
            "version": self.version,
            "strategy": self.strategy,
            "max_depth": self.max_depth,
            "node_limit": self.node_limit,
            "max_plans": self.max_plans,
            "branch_ordering": self.branch_ordering,
            "dedup_mode": self.dedup_mode,
            "scope": self.scope,
            "stochastic_sampling": False,
            "search_rng_draws": 0,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlannerSearchPolicy":
        if not isinstance(data, Mapping) or set(data) != {
            "schema", "namespace", "version", "strategy", "max_depth",
            "node_limit", "max_plans", "branch_ordering", "dedup_mode",
            "scope", "stochastic_sampling", "search_rng_draws",
        }:
            raise PlannerPolicyError("search policy has missing or unknown fields")
        if data["schema"] != POLICY_SCHEMA or data["stochastic_sampling"] is not False:
            raise PlannerPolicyError("unknown or stochastic search policy")
        if type(data["search_rng_draws"]) is not int or data["search_rng_draws"] != 0:
            raise PlannerPolicyError("search must draw no RNG")
        return cls(**{key: data[key] for key in (
            "namespace", "version", "strategy", "max_depth", "node_limit",
            "max_plans", "branch_ordering", "dedup_mode", "scope",
        )})

    @property
    def identity(self) -> str:
        return identity(self.to_dict())
