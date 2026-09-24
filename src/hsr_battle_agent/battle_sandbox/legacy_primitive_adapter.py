# -*- coding: utf-8 -*-
"""Explicit one-way adapter for one certified, pure legacy primitive.

The adapter is intentionally not a compatibility facade.  It accepts one
allowlisted leaf whose published semantic specification has no context reads
or writes, executes it against private legacy state/RNG/trace objects, and
returns an empty private Terra delta only after proving that execution changed
none of those private state inputs.  It never publishes or commits anything.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, NoReturn

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_ir.model import (
    PrimitiveCall,
    PrimitiveResult,
    TARGET_SELECT_NONE_PRIMITIVE_ID,
)
from hsr_battle_agent.battle_ir.targets import TargetSet
from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry
from hsr_battle_agent.battle_sandbox.state import BattleState
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.trace import ExecutionTrace
from hsr_battle_agent.battle_sandbox.transaction import (
    StagedDelta,
    TransactionPlan,
    transaction_plan_identity,
)

__all__ = [
    "LEGACY_PRIMITIVE_ALLOWLIST",
    "LegacyAdapterError",
    "LegacyAdapterOutcome",
    "LegacyAdapterResult",
    "LegacyPrimitiveAdapter",
]

LEGACY_PRIMITIVE_ALLOWLIST = (TARGET_SELECT_NONE_PRIMITIVE_ID,)


class LegacyAdapterError(ValueError):
    pass


class LegacyAdapterOutcome(Enum):
    STAGED = "STAGED"
    REJECTED = "REJECTED"
    UNSUPPORTED = "UNSUPPORTED"

    def __bool__(self) -> NoReturn:
        raise LegacyAdapterError("LegacyAdapterOutcome has no truthiness")


class LegacyAdapterResult:
    """Detached adapter result; STAGED is still not publication permission."""

    __slots__ = ("_outcome", "_delta", "_primitive_id", "_result_summary", "_reason")

    def __init__(
        self,
        outcome: LegacyAdapterOutcome,
        *,
        delta: StagedDelta | None = None,
        primitive_id: str | None = None,
        result_summary: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        if not isinstance(outcome, LegacyAdapterOutcome):
            raise LegacyAdapterError("outcome must be LegacyAdapterOutcome")
        if outcome is LegacyAdapterOutcome.STAGED:
            if not isinstance(delta, StagedDelta) or not primitive_id or reason is not None:
                raise LegacyAdapterError("STAGED requires a delta and primitive identity")
            self._delta = delta.detached_copy()
            self._primitive_id = primitive_id
            self._result_summary = dict(result_summary or {})
            self._reason = None
        else:
            if delta is not None or primitive_id is not None or result_summary is not None or not reason:
                raise LegacyAdapterError("non-staged result requires only a reason")
            self._delta = None
            self._primitive_id = None
            self._result_summary = None
            self._reason = reason
        self._outcome = outcome

    def __bool__(self) -> NoReturn:
        raise LegacyAdapterError("LegacyAdapterResult has no truthiness or permission")

    @property
    def outcome(self) -> LegacyAdapterOutcome:
        return self._outcome

    @property
    def staged_delta(self) -> StagedDelta | None:
        return None if self._delta is None else self._delta.detached_copy()

    @property
    def primitive_id(self) -> str | None:
        return self._primitive_id

    @property
    def result_summary(self) -> dict[str, Any] | None:
        return None if self._result_summary is None else dict(self._result_summary)

    @property
    def reason(self) -> str | None:
        return self._reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_legacy_primitive_adapter_result/1",
            "outcome": self._outcome.value,
            "primitive_id": self._primitive_id,
            "result_summary": self.result_summary,
            "reason": self._reason,
            "staged_writes": None if self._delta is None else [x.to_dict() for x in self._delta.writes],
        }


class LegacyPrimitiveAdapter:
    """Run exactly one allowlisted pure leaf in a private legacy branch."""

    __slots__ = ()

    def stage(
        self,
        state: TerraBattleState,
        plan: TransactionPlan,
        primitive: PrimitiveCall,
    ) -> LegacyAdapterResult:
        if not isinstance(state, TerraBattleState) or not isinstance(plan, TransactionPlan):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="STRICT_INPUT_REQUIRED")
        if plan.certificate.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="NATIVE_CERTIFICATE_REQUIRED")
        if not isinstance(primitive, PrimitiveCall):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="PRIMITIVE_CALL_REQUIRED")
        if primitive.primitive_id not in LEGACY_PRIMITIVE_ALLOWLIST:
            return LegacyAdapterResult(LegacyAdapterOutcome.UNSUPPORTED, reason="PRIMITIVE_NOT_ALLOWLISTED")
        operations = plan.operations
        if (
            len(operations) != 1
            or operations[0].operation_id != primitive.primitive_id
            or operations[0].payload != {}
            or primitive.arguments
            or plan.allowed_reads
            or plan.allowed_writes
        ):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="PLAN_BINDING_MISMATCH")
        if (
            plan.certificate_identity != plan.certificate.identity()
            or transaction_plan_identity(operations) != plan.certificate.plan_identity
        ):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="PLAN_BINDING_MISMATCH")
        try:
            delta = StagedDelta(plan, state)
        except (TypeError, ValueError):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="STAGED_DELTA_REJECTED")

        live_before = state.to_dict()
        registry = PrimitiveRegistry.create_default()
        registered = registry.resolve(primitive.primitive_id)
        if registered.spec.context_reads or registered.spec.context_writes:
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="NON_PURE_PRIMITIVE_SPEC")

        private_state = BattleState()
        private_rng = state.rng_state
        private_trace = ExecutionTrace()
        context = ExecutionContext(state=private_state, rng=private_rng, trace=private_trace)
        state_before = private_state.to_dict()
        rng_before = private_rng.to_dict()
        try:
            result = PrimitiveExecutor(registry).execute(primitive, context)
        except Exception:
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="LEGACY_EXECUTION_REJECTED")

        if state.to_dict() != live_before:
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="LIVE_STATE_CHANGED")
        if private_state.to_dict() != state_before:
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="UNEXPECTED_LEGACY_STATE_DIFF")
        if private_rng.to_dict() != rng_before:
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="UNEXPECTED_LEGACY_RNG_DIFF")
        trace_document = private_trace.to_dict()
        trace_events = trace_document["events"]
        if (
            len(trace_events) != 2
            or [event["event"] for event in trace_events]
            != ["PrimitiveStarted", "PrimitiveFinished"]
            or any(event["primitive_id"] != primitive.primitive_id for event in trace_events)
        ):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="UNEXPECTED_LEGACY_TRACE_DIFF")
        if (
            not isinstance(result, PrimitiveResult)
            or result.primitive_id != primitive.primitive_id
            or result.semantic_result_type != registered.spec.result
            or not isinstance(result.value, TargetSet)
            or result.value.items != ()
        ):
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="UNEXPECTED_LEGACY_RESULT")

        if delta.writes or delta.allocator.to_dict() != state.allocator.to_dict():
            return LegacyAdapterResult(LegacyAdapterOutcome.REJECTED, reason="UNEXPECTED_TERRA_DIFF")
        return LegacyAdapterResult(
            LegacyAdapterOutcome.STAGED,
            delta=delta,
            primitive_id=result.primitive_id,
            result_summary={
                "semantic_result_type": result.semantic_result_type,
                "runtime_result_type": result.runtime_result_type,
                "private_trace_event_count": len(trace_events),
            },
        )
