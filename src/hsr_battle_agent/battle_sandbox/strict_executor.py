# -*- coding: utf-8 -*-
"""Strict Terra step seam (G01-012).

This module deliberately imports no legacy primitive executor or registry.  It
supports one structural operation only: an already-certified empty/no-op
transaction.  Everything else is an explicit local rejection or unsupported
result.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.atomic_commit import AtomicCommit, AtomicCommitResult
from hsr_battle_agent.battle_sandbox.errors import StructuredRejection
from hsr_battle_agent.battle_sandbox.staged_trace import StagedTrace
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.transaction import (
    StagedDelta, TransactionError, TransactionPlan, transaction_plan_identity,
)
from hsr_battle_agent.battle_sandbox.transaction_rng import TransactionRng

__all__ = [
    "STRICT_NO_OP_ACTION", "StrictExecutor", "StrictStepError",
    "StrictStepOutcome", "StrictStepResult",
]

STRICT_NO_OP_ACTION = "terra.strict.no_op/1"


class StrictStepError(ValueError):
    pass


class StrictStepOutcome(Enum):
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    UNSUPPORTED = "UNSUPPORTED"

    def __bool__(self) -> NoReturn:
        raise StrictStepError("StrictStepOutcome has no truthiness")


def _rejection(reason: str, request: str, *, plan: Any = None, detail: str = "") -> StructuredRejection:
    refs = ()
    if isinstance(plan, TransactionPlan):
        refs = (plan.certificate.contract_ref,)
    return StructuredRejection(
        reason_code=reason,
        obligation_owner="STRICT_STEP",
        evidence_request=request,
        contract_refs=refs,
        diagnostics={"detail": detail},
    )


class StrictStepResult:
    __slots__ = ("_outcome", "_state", "_revision", "_transaction_identity", "_rejections")

    def __init__(self, *, outcome: StrictStepOutcome, state: TerraBattleState | None = None,
                 transaction_identity: str | None = None,
                 rejections: tuple[StructuredRejection, ...] = ()) -> None:
        if not isinstance(outcome, StrictStepOutcome):
            raise StrictStepError("outcome must be StrictStepOutcome")
        owned_rejections = tuple(StructuredRejection.from_dict(x.to_dict()) for x in rejections)
        if outcome is StrictStepOutcome.COMMITTED:
            if not isinstance(state, TerraBattleState) or not transaction_identity or owned_rejections:
                raise StrictStepError("COMMITTED requires state and identity with no rejection")
            self._state = state.clone()
            self._revision = state.revision
            self._transaction_identity = transaction_identity
        else:
            if state is not None or transaction_identity is not None or not owned_rejections:
                raise StrictStepError("non-committed result requires rejection only")
            self._state = None
            self._revision = None
            self._transaction_identity = None
        self._outcome = outcome
        self._rejections = owned_rejections

    def __bool__(self) -> NoReturn:
        raise StrictStepError("StrictStepResult has no truthiness")

    @property
    def outcome(self) -> StrictStepOutcome:
        return self._outcome

    @property
    def committed_state(self) -> TerraBattleState | None:
        return None if self._state is None else self._state.clone()

    @property
    def resulting_revision(self):
        return None if self._revision is None else type(self._revision).from_dict(self._revision.to_dict())

    @property
    def transaction_identity(self) -> str | None:
        return self._transaction_identity

    @property
    def rejections(self) -> tuple[StructuredRejection, ...]:
        return tuple(StructuredRejection.from_dict(x.to_dict()) for x in self._rejections)

    def is_committed(self) -> bool:
        return self._outcome is StrictStepOutcome.COMMITTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_strict_step_result/1",
            "outcome": self._outcome.value,
            "resulting_revision": None if self._revision is None else self._revision.to_dict(),
            "transaction_identity": self._transaction_identity,
            "rejections": [x.to_dict() for x in self._rejections],
        }


class StrictExecutor:
    """New Terra-only step path; never dispatches a legacy primitive."""

    __slots__ = ()

    def step(self, state: TerraBattleState, plan: TransactionPlan, action: str) -> StrictStepResult:
        if not isinstance(state, TerraBattleState):
            return StrictStepResult(
                outcome=StrictStepOutcome.REJECTED,
                rejections=(_rejection("STRICT_INVALID_STATE", "TerraBattleState input"),),
            )
        if not isinstance(plan, TransactionPlan):
            return StrictStepResult(
                outcome=StrictStepOutcome.REJECTED,
                rejections=(_rejection("STRICT_INVALID_CERTIFICATE", "valid GateCertificate-derived TransactionPlan"),),
            )
        if (
            plan.certificate.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED
            or plan.certificate_identity != plan.certificate.identity()
            or transaction_plan_identity(plan.operations) != plan.certificate.plan_identity
        ):
            return StrictStepResult(
                outcome=StrictStepOutcome.REJECTED,
                rejections=(_rejection("STRICT_CERTIFICATE_MISMATCH", "exact sealed native certificate bindings", plan=plan),),
            )
        if action != STRICT_NO_OP_ACTION or plan.operations:
            return StrictStepResult(
                outcome=StrictStepOutcome.UNSUPPORTED,
                rejections=(_rejection("STRICT_ACTION_UNSUPPORTED", "explicitly qualified strict operation", plan=plan, detail=repr(action)),),
            )
        try:
            commit: AtomicCommitResult = AtomicCommit(
                plan,
                StagedDelta(plan, state),
                TransactionRng(plan, state),
                StagedTrace(plan, state),
            ).commit(state)
        except (TransactionError, ValueError, TypeError) as exc:
            return StrictStepResult(
                outcome=StrictStepOutcome.REJECTED,
                rejections=(_rejection("STRICT_TRANSACTION_REJECTED", "unchanged certified source state", plan=plan, detail=str(exc)),),
            )
        return StrictStepResult(
            outcome=StrictStepOutcome.COMMITTED,
            state=commit.state,
            transaction_identity=commit.identity(),
        )
