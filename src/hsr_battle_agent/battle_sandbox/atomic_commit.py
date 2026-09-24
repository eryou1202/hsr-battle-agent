# -*- coding: utf-8 -*-
"""Build-and-publish-once local atomic commit for Terra transactions.

Atomicity here is a local architecture guarantee, not a claim about recovered
client rollback behavior.  Validation and candidate construction happen before
the sole publication boundary: returning an :class:`AtomicCommitResult`.
"""
from __future__ import annotations

from typing import Any

from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.revision import RevisionAndTransactionSequence
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.staged_trace import StagedRecord, StagedTrace
from hsr_battle_agent.battle_sandbox.state import F01StateEnvelope
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.transaction import (
    StagedDelta, TransactionError, TransactionPlan, transaction_plan_identity,
)
from hsr_battle_agent.battle_sandbox.transaction_rng import TransactionRng

__all__ = [
    "ATOMIC_COMMIT_FAILURE_POINTS", "AtomicCommit", "AtomicCommitError",
    "AtomicCommitInjectedFailure", "AtomicCommitResult",
]


class AtomicCommitError(TransactionError):
    """Raised when validation refuses a local atomic commit."""


class AtomicCommitInjectedFailure(AtomicCommitError):
    """Test-only deterministic failure before the publication boundary."""


ATOMIC_COMMIT_FAILURE_POINTS = (
    "before_validation",
    "after_binding_validation",
    "after_delta_validation",
    "after_rng_validation",
    "after_trace_validation",
    "before_publication",
    "publication",
)


class AtomicCommitResult:
    """The single published aggregate: state and ordered transaction outputs."""

    __slots__ = ("_state", "_records", "_certificate_identity", "_plan_identity")

    def __init__(self, state: TerraBattleState, records: tuple[StagedRecord, ...],
                 certificate_identity: str, plan_identity: str) -> None:
        if not isinstance(state, TerraBattleState):
            raise AtomicCommitError("commit result requires TerraBattleState")
        self._state = state.clone()
        self._records = tuple(StagedRecord.from_dict(x.to_dict()) for x in records)
        self._certificate_identity = certificate_identity
        self._plan_identity = plan_identity

    @property
    def state(self) -> TerraBattleState:
        return self._state.clone()

    @property
    def records(self) -> tuple[StagedRecord, ...]:
        return tuple(StagedRecord.from_dict(x.to_dict()) for x in self._records)

    @property
    def trace(self) -> tuple[StagedRecord, ...]:
        return tuple(x for x in self.records if x.channel == "TRACE")

    @property
    def events(self) -> tuple[StagedRecord, ...]:
        return tuple(x for x in self.records if x.channel == "EVENT")

    @property
    def queue_writes(self) -> tuple[StagedRecord, ...]:
        return tuple(x for x in self.records if x.channel == "QUEUE")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_atomic_commit_result/1",
            "state": self._state.to_dict(),
            "records": [x.to_dict() for x in self._records],
            "certificate_identity": self._certificate_identity,
            "plan_identity": self._plan_identity,
        }

    def identity(self) -> str:
        return F01StateEnvelope(self.to_dict()).state_hash()


class AtomicCommit:
    """Validate components, build a replacement aggregate, publish once."""

    __slots__ = ("_plan", "_delta", "_rng", "_trace", "_committed")

    def __init__(self, plan: TransactionPlan, delta: StagedDelta,
                 rng: TransactionRng, trace: StagedTrace) -> None:
        if not isinstance(plan, TransactionPlan):
            raise AtomicCommitError("AtomicCommit requires TransactionPlan")
        if not isinstance(delta, StagedDelta):
            raise AtomicCommitError("AtomicCommit requires StagedDelta")
        if not isinstance(rng, TransactionRng):
            raise AtomicCommitError("AtomicCommit requires TransactionRng")
        if not isinstance(trace, StagedTrace):
            raise AtomicCommitError("AtomicCommit requires StagedTrace")
        # Delta and trace are functional; detach them.  RNG is detached so
        # subsequent caller draws cannot rewrite this commit's material.
        self._plan = plan
        self._delta = delta.detached_copy()
        self._rng = rng.detached_copy()
        self._trace = trace.detached_copy()
        self._committed = False

    @staticmethod
    def _inject(requested: str | None, point: str) -> None:
        if requested is not None and requested not in ATOMIC_COMMIT_FAILURE_POINTS:
            raise AtomicCommitError(f"unknown failure injection point {requested!r}")
        if requested == point:
            raise AtomicCommitInjectedFailure(f"injected atomic commit failure at {point}")

    def commit(self, live_state: TerraBattleState, *, failure_point: str | None = None) -> AtomicCommitResult:
        if self._committed:
            raise AtomicCommitError("an atomic commit cannot be replayed")
        if not isinstance(live_state, TerraBattleState):
            raise AtomicCommitError("AtomicCommit requires live TerraBattleState")
        self._inject(failure_point, "before_validation")

        plan_id = transaction_plan_identity(self._plan.operations)
        certificate_id = self._plan.certificate_identity
        if plan_id != self._plan.certificate.plan_identity:
            raise AtomicCommitError("plan identity no longer matches certificate")
        if live_state.revision.to_dict() != self._plan.source_revision.to_dict():
            raise AtomicCommitError("source revision is stale; automatic retry is forbidden")
        live_hash = semantic_hash_v2(
            TerraSnapshotV2(state=live_state, policy_identity=self._plan.certificate.policy_identity)
        )
        if live_hash != self._plan.source_state_hash:
            raise AtomicCommitError("live semantic state no longer matches the planned input")
        self._inject(failure_point, "after_binding_validation")

        if (
            self._delta.plan_identity != plan_id
            or self._delta.certificate_identity != certificate_id
            or self._delta.source_state_hash != live_hash
            or self._delta.source_revision.to_dict() != live_state.revision.to_dict()
        ):
            raise AtomicCommitError("staged delta bindings do not match the plan")
        if self._delta.to_dict()["allowed_writes"] != [x.to_dict() for x in self._plan.allowed_writes]:
            raise AtomicCommitError("staged delta write footprint differs from certificate")
        self._inject(failure_point, "after_delta_validation")

        if (
            self._rng.plan_identity != plan_id
            or self._rng.certificate_identity != certificate_id
            or self._rng.source_state_hash != live_hash
            or self._rng.source_revision.to_dict() != live_state.revision.to_dict()
        ):
            raise AtomicCommitError("staged RNG bindings do not match the plan")
        rng_material = self._rng.peek_material()
        self._inject(failure_point, "after_rng_validation")

        if self._trace.discarded:
            raise AtomicCommitError("discarded staged output cannot be committed")
        if (
            self._trace.plan_identity != plan_id
            or self._trace.certificate_identity != certificate_id
            or self._trace.source_state_hash != live_hash
        ):
            raise AtomicCommitError("staged output bindings do not match the plan")
        if [x.to_dict() for x in self._trace.allowed_writes] != [
            x.to_dict() for x in self._plan.allowed_writes
        ]:
            raise AtomicCommitError("staged output write footprint differs from certificate")
        self._inject(failure_point, "after_trace_validation")

        prior = live_state.revision_sequence
        next_sequence = RevisionAndTransactionSequence(
            published_revision=prior.published_revision.advance(contract="terra-atomic-commit/1"),
            replay_sequence=prior.replay_sequence + 1,
            committed_effect_sequence=prior.committed_effect_sequence + 1,
        )
        candidate = TerraBattleState(
            stores=self._delta.stores,
            opaque_stores=self._delta.opaque_stores,
            revision_sequence=next_sequence,
            allocator=self._delta.allocator,
            rng_state=rng_material.rng,
        )
        records = self._trace.records
        self._inject(failure_point, "before_publication")
        self._inject(failure_point, "publication")

        # The only irreversible local action is consuming private material;
        # the caller observes publication solely through the one result below.
        consumed = self._rng.consume_commit_material()
        if consumed.to_dict() != rng_material.to_dict():
            raise AtomicCommitError("staged RNG changed after validation")
        result = AtomicCommitResult(candidate, records, certificate_id, plan_id)
        self._committed = True
        return result
