# -*- coding: utf-8 -*-
"""Read-only observation context for independent Terra state.

This is not an execution context and exposes no draw, write or commit method.
It captures a private state clone and returns either immutable scalar/tuple
views or fresh validated copies.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.revision import (
    RevisionAndTransactionSequence,
)
from hsr_battle_agent.battle_sandbox.rng import (
    CLIENT_RNG_ALGORITHM,
    SANDBOX_RNG_ALGORITHM,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import (
    SnapshotPolicyIdentity,
    TerraSnapshotV2,
)
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState

__all__ = [
    "ReadOnlyRngState",
    "TerraReadContext",
    "TerraReadContextError",
]


class TerraReadContextError(ValueError):
    """Raised for invalid access to the read-only Terra context."""


@dataclass(frozen=True)
class ReadOnlyRngState:
    """Immutable observation of the complete selected generator state."""

    schema_version: int
    algorithm: str
    state_version: int
    internal_state: tuple[int, ...]
    gauss_next: float | None

    @classmethod
    def from_state(cls, state: TerraBattleState) -> "ReadOnlyRngState":
        if not isinstance(state, TerraBattleState):
            raise TerraReadContextError("state must be a TerraBattleState")
        document = state.to_dict()["rng_state"]
        payload = document["state"]
        return cls(
            schema_version=document["schema_version"],
            algorithm=document["algorithm"],
            state_version=payload["version"],
            internal_state=tuple(payload["internal_state"]),
            gauss_next=payload["gauss_next"],
        )

    @property
    def client_algorithm(self) -> str:
        return CLIENT_RNG_ALGORITHM

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm": self.algorithm,
            "state": {
                "version": self.state_version,
                "internal_state": list(self.internal_state),
                "gauss_next": self.gauss_next,
            },
        }


class TerraReadContext:
    """Private-clone context exposing observation but no execution surface."""

    __slots__ = ("_state", "_rng_view")

    def __init__(self, state: TerraBattleState) -> None:
        if not isinstance(state, TerraBattleState):
            raise TerraReadContextError("state must be a TerraBattleState")
        self._state = state.clone()
        self._rng_view = ReadOnlyRngState.from_state(self._state)

    @property
    def revision_sequence(self) -> RevisionAndTransactionSequence:
        return self._state.revision_sequence

    @property
    def rng_state(self) -> ReadOnlyRngState:
        return self._rng_view

    @property
    def store_names(self) -> tuple[str, ...]:
        return tuple(self._state.stores)

    @property
    def opaque_store_names(self) -> tuple[str, ...]:
        return tuple(self._state.opaque_stores)

    def state_copy(self) -> TerraBattleState:
        """Return a detached state copy, never the context's private state."""
        return self._state.clone()

    def capture_snapshot(
        self, policy_identity: SnapshotPolicyIdentity
    ) -> TerraSnapshotV2:
        return TerraSnapshotV2(
            state=self._state,
            policy_identity=policy_identity,
        )

    def __repr__(self) -> str:
        return (
            f"TerraReadContext(revision={self._state.revision.identity()!r}, "
            f"rng={SANDBOX_RNG_ALGORITHM!r}, client_rng={CLIENT_RNG_ALGORITHM!r})"
        )
