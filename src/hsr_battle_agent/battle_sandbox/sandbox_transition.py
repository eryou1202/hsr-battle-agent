# -*- coding: utf-8 -*-
"""Explicit state-bearing SANDBOX_EXTENSION resource transitions.

This module is the narrow local capability used to establish meaningful
planner branching.  It does not model a client-native resource rule.  The
caller declares the complete supported action set and an initial resource
value; planning validates a complete REFERENCE_MODEL legal-action view, and a
private transaction publishes one replacement :class:`TerraBattleState`.

The native strict gate remains separate.  No object in this module is a
``GateCertificate`` and none can satisfy a NATIVE_EVIDENCED gate.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.legal_actions import (
    LegalActionProposal,
    LegalActionsStatus,
    LegalActionsView,
    PlayerLegalAction,
    query_player_legal_actions,
)
from hsr_battle_agent.battle_sandbox.revision import (
    RevisionAndTransactionSequence,
    StateRevision,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import (
    SnapshotPolicyIdentity,
    TerraSnapshotV2,
)
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState

__all__ = [
    "SANDBOX_RESOURCE_RECORD_SCHEMA",
    "SANDBOX_RESOURCE_TRANSITION_SCHEMA",
    "SandboxActionRule",
    "SandboxResourceContract",
    "SandboxResourcePlan",
    "SandboxResourceState",
    "SandboxResourceTransaction",
    "SandboxTransitionError",
    "SandboxTransitionOutcome",
    "SandboxTransitionResult",
    "initialize_sandbox_resource_state",
    "plan_sandbox_resource_transition",
    "query_sandbox_legal_actions",
    "read_sandbox_resource_state",
]

SANDBOX_RESOURCE_RECORD_SCHEMA = "sandbox_resource_state/1"
SANDBOX_RESOURCE_TRANSITION_SCHEMA = "sandbox_resource_transition/1"
_RESOURCE_STORE = "resources"


class SandboxTransitionError(ValueError):
    """Raised when a local transition contract or plan is malformed."""


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise SandboxTransitionError(f"{label} must be a non-empty trimmed string")
    return value


def _amount(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise SandboxTransitionError(f"{label} must not be boolean")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SandboxTransitionError(f"{label} must be a decimal value") from exc
    if not result.is_finite() or result < 0:
        raise SandboxTransitionError(f"{label} must be finite and non-negative")
    return result


def _amount_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _policy_copy(policy: SnapshotPolicyIdentity) -> SnapshotPolicyIdentity:
    if not isinstance(policy, SnapshotPolicyIdentity):
        raise SandboxTransitionError("policy_identity must be explicit")
    if policy.evidence_mode is not EvidenceMode.SANDBOX_EXTENSION:
        raise SandboxTransitionError(
            "state-bearing local transition requires SANDBOX_EXTENSION policy"
        )
    return SnapshotPolicyIdentity.from_dict(policy.to_dict())


@dataclass(frozen=True)
class SandboxActionRule:
    """One caller-declared action in a complete local supported scope."""

    action_id: str
    candidate_occurrence_id: str
    actor_id: str
    target_ids: tuple[str | None, ...]
    resource_cost: Decimal
    target_supported: bool = True
    terminal_supported: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", _token(self.action_id, "action_id"))
        object.__setattr__(
            self,
            "candidate_occurrence_id",
            _token(self.candidate_occurrence_id, "candidate_occurrence_id"),
        )
        object.__setattr__(self, "actor_id", _token(self.actor_id, "actor_id"))
        if isinstance(self.target_ids, (str, bytes)) or not isinstance(
            self.target_ids, (tuple, list)
        ):
            raise SandboxTransitionError("target_ids must be an ordered sequence")
        targets = tuple(self.target_ids)
        if any(item is not None and not isinstance(item, str) for item in targets):
            raise SandboxTransitionError("target_ids accept only string or explicit null")
        object.__setattr__(self, "target_ids", targets)
        object.__setattr__(
            self, "resource_cost", _amount(self.resource_cost, "resource_cost")
        )
        if not isinstance(self.target_supported, bool) or not isinstance(
            self.terminal_supported, bool
        ):
            raise SandboxTransitionError(
                "target_supported and terminal_supported must be explicit booleans"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "candidate_occurrence_id": self.candidate_occurrence_id,
            "actor_id": self.actor_id,
            "target_ids": list(self.target_ids),
            "resource_cost": _amount_text(self.resource_cost),
            "target_supported": self.target_supported,
            "terminal_supported": self.terminal_supported,
        }

    def proposal(self) -> LegalActionProposal:
        return LegalActionProposal(
            self.action_id,
            self.candidate_occurrence_id,
            self.actor_id,
            self.target_ids,
            self.resource_cost,
            self.target_supported,
            self.terminal_supported,
        )


@dataclass(frozen=True)
class SandboxResourceContract:
    """Versioned caller declaration for one local resource and action scope."""

    namespace: str
    version: str
    contract_id: str
    owner_id: str
    resource_id: str
    actions: tuple[SandboxActionRule, ...]
    evidence_mode: EvidenceMode = EvidenceMode.SANDBOX_EXTENSION

    def __post_init__(self) -> None:
        for name in ("namespace", "version", "contract_id", "owner_id", "resource_id"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        if self.evidence_mode is not EvidenceMode.SANDBOX_EXTENSION:
            raise SandboxTransitionError("resource contract is SANDBOX_EXTENSION only")
        if isinstance(self.actions, (str, bytes)) or not isinstance(
            self.actions, (tuple, list)
        ):
            raise SandboxTransitionError("actions must be an ordered sequence")
        actions = tuple(self.actions)
        if not actions or any(not isinstance(item, SandboxActionRule) for item in actions):
            raise SandboxTransitionError("actions must contain explicit SandboxActionRule values")
        action_ids = tuple(item.action_id for item in actions)
        if len(set(action_ids)) != len(action_ids):
            raise SandboxTransitionError("action_id values must be unique in the local scope")
        object.__setattr__(self, "actions", actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SANDBOX_RESOURCE_TRANSITION_SCHEMA,
            "namespace": self.namespace,
            "version": self.version,
            "contract_id": self.contract_id,
            "owner_id": self.owner_id,
            "resource_id": self.resource_id,
            "evidence_mode": self.evidence_mode.value,
            "actions": [item.to_dict() for item in self.actions],
        }

    @property
    def identity(self) -> str:
        return hashlib.sha256(canonical_v2_bytes(self.to_dict())).hexdigest()

    @property
    def resource_key(self) -> str:
        return f"{self.namespace}:{self.owner_id}:{self.resource_id}"


@dataclass(frozen=True)
class SandboxResourceState:
    contract_identity: str
    owner_id: str
    resource_id: str
    amount: Decimal
    maximum: Decimal
    transition_ordinal: int
    evidence_mode: EvidenceMode = EvidenceMode.SANDBOX_EXTENSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_identity", _token(self.contract_identity, "contract_identity")
        )
        object.__setattr__(self, "owner_id", _token(self.owner_id, "owner_id"))
        object.__setattr__(self, "resource_id", _token(self.resource_id, "resource_id"))
        object.__setattr__(self, "amount", _amount(self.amount, "amount"))
        object.__setattr__(self, "maximum", _amount(self.maximum, "maximum"))
        if self.amount > self.maximum:
            raise SandboxTransitionError("amount cannot exceed the declared maximum")
        if isinstance(self.transition_ordinal, bool) or not isinstance(
            self.transition_ordinal, int
        ) or self.transition_ordinal < 0:
            raise SandboxTransitionError("transition_ordinal must be an explicit non-negative int")
        if self.evidence_mode is not EvidenceMode.SANDBOX_EXTENSION:
            raise SandboxTransitionError("resource state is SANDBOX_EXTENSION only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SANDBOX_RESOURCE_RECORD_SCHEMA,
            "contract_identity": self.contract_identity,
            "owner_id": self.owner_id,
            "resource_id": self.resource_id,
            "amount": _amount_text(self.amount),
            "maximum": _amount_text(self.maximum),
            "transition_ordinal": self.transition_ordinal,
            "evidence_mode": self.evidence_mode.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SandboxResourceState":
        if not isinstance(data, Mapping):
            raise SandboxTransitionError("resource record must be a mapping")
        expected = {
            "schema", "contract_identity", "owner_id", "resource_id", "amount",
            "maximum", "transition_ordinal", "evidence_mode",
        }
        if set(data) != expected or data["schema"] != SANDBOX_RESOURCE_RECORD_SCHEMA:
            raise SandboxTransitionError("resource record has an unknown or incomplete schema")
        if data["evidence_mode"] != EvidenceMode.SANDBOX_EXTENSION.value:
            raise SandboxTransitionError("resource record evidence mode changed")
        return cls(
            contract_identity=data["contract_identity"],
            owner_id=data["owner_id"],
            resource_id=data["resource_id"],
            amount=data["amount"],
            maximum=data["maximum"],
            transition_ordinal=data["transition_ordinal"],
        )


def _snapshot_hash(state: TerraBattleState, policy: SnapshotPolicyIdentity) -> str:
    return semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=policy))


def _new_state(
    source: TerraBattleState,
    *,
    stores: Mapping[str, Any],
    advance: bool,
) -> TerraBattleState:
    prior = source.revision_sequence
    sequence = prior
    if advance:
        sequence = RevisionAndTransactionSequence(
            published_revision=prior.published_revision.advance(
                contract=SANDBOX_RESOURCE_TRANSITION_SCHEMA
            ),
            replay_sequence=prior.replay_sequence + 1,
            committed_effect_sequence=prior.committed_effect_sequence + 1,
        )
    return TerraBattleState(
        revision_sequence=sequence,
        allocator=source.allocator,
        rng_state=source.rng_state,
        stores=stores,
        opaque_stores=source.opaque_stores,
    )


def initialize_sandbox_resource_state(
    state: TerraBattleState,
    contract: SandboxResourceContract,
    *,
    amount: Any,
    maximum: Any,
) -> TerraBattleState:
    """Build explicit initial local resource state without transition effects."""
    if not isinstance(state, TerraBattleState):
        raise SandboxTransitionError("state must be TerraBattleState")
    if not isinstance(contract, SandboxResourceContract):
        raise SandboxTransitionError("contract must be SandboxResourceContract")
    initial = SandboxResourceState(
        contract.identity,
        contract.owner_id,
        contract.resource_id,
        amount,
        maximum,
        0,
    )
    stores = dict(state.stores)
    resource_store = stores[_RESOURCE_STORE]
    if any(entry.key == contract.resource_key for entry in resource_store.entries):
        raise SandboxTransitionError("resource is already initialized for this contract")
    stores[_RESOURCE_STORE] = resource_store.append(
        contract.resource_key, initial.to_dict()
    )
    return _new_state(state, stores=stores, advance=False)


def read_sandbox_resource_state(
    state: TerraBattleState, contract: SandboxResourceContract
) -> SandboxResourceState:
    if not isinstance(state, TerraBattleState) or not isinstance(
        contract, SandboxResourceContract
    ):
        raise SandboxTransitionError("state and contract are required")
    matching = [
        entry for entry in state.stores[_RESOURCE_STORE].entries
        if entry.key == contract.resource_key
    ]
    if not matching:
        raise SandboxTransitionError("declared resource is absent from Terra state")
    decoded_records: list[SandboxResourceState] = []
    for index, entry in enumerate(matching):
        decoded = SandboxResourceState.from_dict(entry.value.require_present())
        if (
            decoded.contract_identity != contract.identity
            or decoded.owner_id != contract.owner_id
            or decoded.resource_id != contract.resource_id
        ):
            raise SandboxTransitionError(
                "resource record does not match its declared contract"
            )
        if decoded.transition_ordinal != index:
            raise SandboxTransitionError(
                "resource history has a missing, duplicate or reordered transition ordinal"
            )
        if decoded_records and decoded.maximum != decoded_records[0].maximum:
            raise SandboxTransitionError(
                "resource history changed the caller-declared maximum"
            )
        decoded_records.append(decoded)
    return decoded_records[-1]


def query_sandbox_legal_actions(
    contract: SandboxResourceContract,
    candidate_occurrence_ids: Iterable[str],
) -> LegalActionsView:
    """Return the complete REFERENCE_MODEL view declared by the local contract."""
    if not isinstance(contract, SandboxResourceContract):
        raise SandboxTransitionError("contract must be SandboxResourceContract")
    available = tuple(candidate_occurrence_ids)
    expected = tuple(item.candidate_occurrence_id for item in contract.actions)
    if available != expected:
        return LegalActionsView(
            LegalActionsStatus.BLOCKED,
            (),
            ("CANDIDATE_SCOPE_MISMATCH",),
        )
    return query_player_legal_actions(
        available,
        tuple(item.proposal() for item in contract.actions),
    )


def _action_document(action: PlayerLegalAction) -> dict[str, Any]:
    if not isinstance(action, PlayerLegalAction):
        raise SandboxTransitionError("action must be PlayerLegalAction")
    if action.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
        raise SandboxTransitionError("player legal action must remain REFERENCE_MODEL")
    action_id = _token(action.action_id, "action.action_id")
    candidate_id = _token(
        action.candidate_occurrence_id, "action.candidate_occurrence_id"
    )
    actor_id = _token(action.actor_id, "action.actor_id")
    if not isinstance(action.target_ids, tuple) or any(
        item is not None and not isinstance(item, str) for item in action.target_ids
    ):
        raise SandboxTransitionError(
            "player legal action target_ids must be the canonical tuple of strings/nulls"
        )
    return {
        "action_id": action_id,
        "candidate_occurrence_id": candidate_id,
        "actor_id": actor_id,
        "target_ids": list(action.target_ids),
        "resource_cost": _amount_text(_amount(action.resource_cost, "resource_cost")),
        "evidence_mode": action.evidence_mode.value,
    }


@dataclass(frozen=True)
class SandboxResourcePlan:
    """Pure immutable plan bound to an exact source and complete local scope."""

    contract_identity: str
    policy_identity: SnapshotPolicyIdentity
    source_revision: StateRevision
    source_state_hash: str
    action: PlayerLegalAction
    amount_before: Decimal
    amount_after: Decimal
    transition_ordinal: int
    declared_reads: tuple[str, ...]
    declared_writes: tuple[str, ...]
    evidence_mode: EvidenceMode = EvidenceMode.SANDBOX_EXTENSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_identity", _token(self.contract_identity, "contract_identity")
        )
        object.__setattr__(self, "policy_identity", _policy_copy(self.policy_identity))
        if not isinstance(self.source_revision, StateRevision):
            raise SandboxTransitionError("source_revision must be explicit")
        object.__setattr__(self, "source_state_hash", _token(self.source_state_hash, "source_state_hash"))
        _action_document(self.action)
        object.__setattr__(self, "amount_before", _amount(self.amount_before, "amount_before"))
        object.__setattr__(self, "amount_after", _amount(self.amount_after, "amount_after"))
        if self.amount_after > self.amount_before:
            raise SandboxTransitionError("resource action cannot increase local resource")
        if isinstance(self.transition_ordinal, bool) or not isinstance(
            self.transition_ordinal, int
        ) or self.transition_ordinal <= 0:
            raise SandboxTransitionError("transition_ordinal must be a positive int")
        reads = tuple(self.declared_reads)
        writes = tuple(self.declared_writes)
        if reads != (_RESOURCE_STORE,) or writes != (_RESOURCE_STORE,):
            raise SandboxTransitionError("resource plan footprint must be exactly resources")
        object.__setattr__(self, "declared_reads", reads)
        object.__setattr__(self, "declared_writes", writes)
        if self.evidence_mode is not EvidenceMode.SANDBOX_EXTENSION:
            raise SandboxTransitionError("resource plan is SANDBOX_EXTENSION only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "sandbox_resource_plan/1",
            "contract_identity": self.contract_identity,
            "policy_identity": self.policy_identity.to_dict(),
            "source_revision": self.source_revision.to_dict(),
            "source_state_hash": self.source_state_hash,
            "action": _action_document(self.action),
            "amount_before": _amount_text(self.amount_before),
            "amount_after": _amount_text(self.amount_after),
            "transition_ordinal": self.transition_ordinal,
            "declared_reads": list(self.declared_reads),
            "declared_writes": list(self.declared_writes),
            "evidence_mode": self.evidence_mode.value,
        }

    @property
    def identity(self) -> str:
        return hashlib.sha256(canonical_v2_bytes(self.to_dict())).hexdigest()


def plan_sandbox_resource_transition(
    state: TerraBattleState,
    policy_identity: SnapshotPolicyIdentity,
    contract: SandboxResourceContract,
    view: LegalActionsView,
    action_id: str,
) -> SandboxResourcePlan:
    """Plan one exact action without mutating state or consuming RNG/allocator."""
    if not isinstance(state, TerraBattleState):
        raise SandboxTransitionError("state must be TerraBattleState")
    policy = _policy_copy(policy_identity)
    if not isinstance(contract, SandboxResourceContract):
        raise SandboxTransitionError("contract must be SandboxResourceContract")
    if not isinstance(view, LegalActionsView):
        raise SandboxTransitionError("view must be LegalActionsView")
    if view.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
        raise SandboxTransitionError("legal-actions view must remain REFERENCE_MODEL")
    if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE or view.blockers:
        raise SandboxTransitionError("blocked or partial legal-actions view cannot plan")
    expected = tuple(
        {
            "action_id": rule.action_id,
            "candidate_occurrence_id": rule.candidate_occurrence_id,
            "actor_id": rule.actor_id,
            "target_ids": list(rule.target_ids),
            "resource_cost": _amount_text(rule.resource_cost),
            "evidence_mode": EvidenceMode.REFERENCE_MODEL.value,
        }
        for rule in contract.actions
    )
    actual = tuple(_action_document(item) for item in view.actions)
    if actual != expected:
        raise SandboxTransitionError(
            "legal-actions view is not the complete ordered action set declared by the contract"
        )
    action_id = _token(action_id, "action_id")
    selected = tuple(item for item in view.actions if item.action_id == action_id)
    if len(selected) != 1:
        raise SandboxTransitionError("selected action is missing or ambiguous")
    current = read_sandbox_resource_state(state, contract)
    cost = _amount(selected[0].resource_cost, "resource_cost")
    if cost > current.amount:
        raise SandboxTransitionError("insufficient explicit local resource")
    return SandboxResourcePlan(
        contract_identity=contract.identity,
        policy_identity=policy,
        source_revision=state.revision,
        source_state_hash=_snapshot_hash(state, policy),
        action=selected[0],
        amount_before=current.amount,
        amount_after=current.amount - cost,
        transition_ordinal=current.transition_ordinal + 1,
        declared_reads=(_RESOURCE_STORE,),
        declared_writes=(_RESOURCE_STORE,),
    )


class SandboxTransitionOutcome(Enum):
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


class SandboxTransitionResult:
    __slots__ = ("_outcome", "_state", "_reason", "_plan_identity")

    def __init__(
        self,
        outcome: SandboxTransitionOutcome,
        state: TerraBattleState | None,
        reason: str | None,
        plan_identity: str,
    ) -> None:
        self._outcome = outcome
        self._state = None if state is None else state.clone()
        self._reason = reason
        self._plan_identity = plan_identity

    @property
    def outcome(self) -> SandboxTransitionOutcome:
        return self._outcome

    @property
    def committed_state(self) -> TerraBattleState | None:
        return None if self._state is None else self._state.clone()

    @property
    def reason(self) -> str | None:
        return self._reason

    @property
    def plan_identity(self) -> str:
        return self._plan_identity


class SandboxResourceTransaction:
    """One-use local transaction using validate/build/return publication."""

    __slots__ = ("_contract", "_plan", "_committed")

    def __init__(
        self, contract: SandboxResourceContract, plan: SandboxResourcePlan
    ) -> None:
        if not isinstance(contract, SandboxResourceContract) or not isinstance(
            plan, SandboxResourcePlan
        ):
            raise SandboxTransitionError("contract and plan are required")
        if contract.identity != plan.contract_identity:
            raise SandboxTransitionError("plan does not bind the supplied contract")
        self._contract = contract
        self._plan = plan
        self._committed = False

    def commit(self, live_state: TerraBattleState) -> SandboxTransitionResult:
        plan_id = self._plan.identity
        if self._committed:
            return SandboxTransitionResult(
                SandboxTransitionOutcome.REJECTED, None, "ALREADY_COMMITTED", plan_id
            )
        if not isinstance(live_state, TerraBattleState):
            return SandboxTransitionResult(
                SandboxTransitionOutcome.REJECTED, None, "INVALID_LIVE_STATE", plan_id
            )
        # All validation happens before the candidate is constructed.  None of
        # these reads can mutate live state because TerraBattleState exports
        # detached components.
        if live_state.revision.to_dict() != self._plan.source_revision.to_dict():
            return SandboxTransitionResult(
                SandboxTransitionOutcome.REJECTED, None, "STALE_REVISION", plan_id
            )
        if _snapshot_hash(live_state, self._plan.policy_identity) != self._plan.source_state_hash:
            return SandboxTransitionResult(
                SandboxTransitionOutcome.REJECTED, None, "STALE_STATE", plan_id
            )
        try:
            current = read_sandbox_resource_state(live_state, self._contract)
        except SandboxTransitionError:
            return SandboxTransitionResult(
                SandboxTransitionOutcome.REJECTED, None, "RESOURCE_INVALID", plan_id
            )
        if (
            current.amount != self._plan.amount_before
            or current.transition_ordinal + 1 != self._plan.transition_ordinal
        ):
            return SandboxTransitionResult(
                SandboxTransitionOutcome.REJECTED, None, "RESOURCE_STALE", plan_id
            )

        next_resource = SandboxResourceState(
            self._contract.identity,
            self._contract.owner_id,
            self._contract.resource_id,
            self._plan.amount_after,
            current.maximum,
            self._plan.transition_ordinal,
        )
        stores = dict(live_state.stores)
        stores[_RESOURCE_STORE] = stores[_RESOURCE_STORE].append(
            self._contract.resource_key, next_resource.to_dict()
        )
        candidate = _new_state(live_state, stores=stores, advance=True)
        self._committed = True
        return SandboxTransitionResult(
            SandboxTransitionOutcome.COMMITTED, candidate, None, plan_id
        )
