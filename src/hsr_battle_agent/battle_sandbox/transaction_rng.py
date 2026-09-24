# -*- coding: utf-8 -*-
"""Private, state-derived transaction RNG (G01-007).

The algorithm is the existing sandbox MT19937 abstraction.  It is explicitly
not a recovered client RNG.  Draws and their ledger remain private until an
atomic commit consumes the material.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state import F01StateEnvelope
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.transaction import TransactionError, TransactionPlan

__all__ = ["RngDraw", "TransactionRng", "TransactionRngMaterial"]


@dataclass(frozen=True, init=False, eq=False)
class RngDraw:
    _method: str
    _arguments: F01StateEnvelope
    _result: F01StateEnvelope

    def __init__(self, method: str, arguments: Any, result: Any) -> None:
        if method not in {"next_u64", "randint", "uniform"}:
            raise TransactionError(f"unsupported transaction RNG method {method!r}")
        object.__setattr__(self, "_method", method)
        object.__setattr__(self, "_arguments", F01StateEnvelope(arguments))
        object.__setattr__(self, "_result", F01StateEnvelope(result))

    @property
    def method(self) -> str:
        return self._method

    @property
    def arguments(self) -> Any:
        return self._arguments.value

    @property
    def result(self) -> Any:
        return self._result.value

    def to_dict(self) -> dict[str, Any]:
        return {"method": self._method, "arguments": self._arguments.to_dict(), "result": self._result.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RngDraw":
        return cls(
            data["method"], F01StateEnvelope.from_dict(data["arguments"]).value,
            F01StateEnvelope.from_dict(data["result"]).value,
        )


class TransactionRngMaterial:
    """Detached RNG replacement and ordered draw ledger for AtomicCommit."""

    __slots__ = ("_rng", "_ledger")

    def __init__(self, rng: SandboxRng, ledger: tuple[RngDraw, ...]) -> None:
        self._rng = rng.clone()
        self._ledger = tuple(RngDraw.from_dict(x.to_dict()) for x in ledger)

    @property
    def rng(self) -> SandboxRng:
        return self._rng.clone()

    @property
    def ledger(self) -> tuple[RngDraw, ...]:
        return tuple(RngDraw.from_dict(x.to_dict()) for x in self._ledger)

    def to_dict(self) -> dict[str, Any]:
        return {"rng": self._rng.to_dict(), "ledger": [x.to_dict() for x in self._ledger]}


class TransactionRng:
    """A private RNG clone, bound to one valid transaction plan."""

    __slots__ = (
        "_rng", "_ledger", "_plan_identity", "_certificate_identity",
        "_source_revision", "_source_state_hash", "_consumed",
    )

    def __init__(self, plan: TransactionPlan, state: TerraBattleState) -> None:
        if not isinstance(plan, TransactionPlan) or not isinstance(state, TerraBattleState):
            raise TransactionError("TransactionRng requires a valid plan and TerraBattleState")
        if state.revision.to_dict() != plan.source_revision.to_dict():
            raise TransactionError("transaction RNG source revision is stale")
        actual_hash = semantic_hash_v2(
            TerraSnapshotV2(
                state=state, policy_identity=plan.certificate.policy_identity
            )
        )
        if actual_hash != plan.source_state_hash:
            raise TransactionError(
                "transaction RNG source state does not match the plan"
            )
        self._rng = state.rng_state
        self._ledger: tuple[RngDraw, ...] = ()
        self._plan_identity = plan.certificate.plan_identity
        self._certificate_identity = plan.certificate_identity
        self._source_revision = plan.source_revision
        self._source_state_hash = plan.source_state_hash
        self._consumed = False

    def _ready(self) -> None:
        if self._consumed:
            raise TransactionError("transaction RNG commit material has already been consumed")

    def next_u64(self) -> int:
        self._ready()
        result = self._rng.next_u64()
        self._ledger += (RngDraw("next_u64", (), result),)
        return result

    def randint(self, low: int, high: int) -> int:
        self._ready()
        result = self._rng.randint(low, high)
        self._ledger += (RngDraw("randint", (low, high), result),)
        return result

    def uniform(self, low: float, high: float) -> float:
        self._ready()
        result = self._rng.uniform(low, high)
        self._ledger += (RngDraw("uniform", (low, high), result),)
        return result

    @property
    def ledger(self) -> tuple[RngDraw, ...]:
        return tuple(RngDraw.from_dict(x.to_dict()) for x in self._ledger)

    @property
    def draw_count(self) -> int:
        return len(self._ledger)

    @property
    def source_state_hash(self) -> str:
        return self._source_state_hash

    @property
    def certificate_identity(self) -> str:
        return self._certificate_identity

    @property
    def plan_identity(self) -> str:
        return self._plan_identity

    @property
    def source_revision(self):
        return type(self._source_revision).from_dict(self._source_revision.to_dict())

    def peek_material(self) -> TransactionRngMaterial:
        self._ready()
        return TransactionRngMaterial(self._rng, self._ledger)

    def consume_commit_material(self) -> TransactionRngMaterial:
        self._ready()
        material = TransactionRngMaterial(self._rng, self._ledger)
        self._consumed = True
        return material

    def detached_copy(self) -> "TransactionRng":
        self._ready()
        result = object.__new__(type(self))
        result._rng = self._rng.clone()
        result._ledger = tuple(RngDraw.from_dict(x.to_dict()) for x in self._ledger)
        result._plan_identity = self._plan_identity
        result._certificate_identity = self._certificate_identity
        result._source_revision = type(self._source_revision).from_dict(self._source_revision.to_dict())
        result._source_state_hash = self._source_state_hash
        result._consumed = False
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_transaction_rng/1",
            "plan_identity": self._plan_identity,
            "certificate_identity": self._certificate_identity,
            "source_revision": self._source_revision.to_dict(),
            "source_state_hash": self._source_state_hash,
            "rng": self._rng.to_dict(),
            "ledger": [x.to_dict() for x in self._ledger],
            "consumed": self._consumed,
        }
