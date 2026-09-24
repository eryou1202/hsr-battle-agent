"""Separate supported-scope player legality view for REF03-001.

Scheduler candidates and AI opportunities are deliberately not accepted as
player actions.  The caller must supply explicit action proposals and all
required target/terminal gates must close before any complete view is returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Iterable

from hsr_battle_agent.battle_ir.evidence import EvidenceMode


class LegalActionError(ValueError):
    pass


def _d(value: object) -> Decimal:
    if isinstance(value, bool):
        raise LegalActionError("boolean is not a resource amount")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise LegalActionError("invalid resource amount") from error
    if not result.is_finite() or result < 0:
        raise LegalActionError("resource amount must be finite and non-negative")
    return result


class LegalActionsStatus(Enum):
    COMPLETE_FOR_SUPPORTED_SCOPE = "COMPLETE_FOR_SUPPORTED_SCOPE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class LegalActionProposal:
    action_id: str
    candidate_occurrence_id: str
    actor_id: str
    target_ids: tuple[str | None, ...]
    resource_cost: Decimal
    target_supported: bool
    terminal_supported: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_ids", tuple(self.target_ids))
        if not self.action_id or not self.candidate_occurrence_id or not self.actor_id:
            raise LegalActionError("proposal identities are required")
        if not all(item is None or isinstance(item, str) for item in self.target_ids):
            raise LegalActionError("target identities must be strings or explicit null")
        object.__setattr__(self, "resource_cost", _d(self.resource_cost))
        if not isinstance(self.target_supported, bool) or not isinstance(self.terminal_supported, bool):
            raise LegalActionError("target and terminal gates must be explicit")


@dataclass(frozen=True)
class PlayerLegalAction:
    action_id: str
    candidate_occurrence_id: str
    actor_id: str
    target_ids: tuple[str | None, ...]
    resource_cost: Decimal
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL


@dataclass(frozen=True)
class LegalActionsView:
    status: LegalActionsStatus
    actions: tuple[PlayerLegalAction, ...]
    blockers: tuple[str, ...]
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL

    def __post_init__(self) -> None:
        if self.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
            raise LegalActionError("legal-actions view is REFERENCE_MODEL only")
        if self.status is LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
            if self.blockers:
                raise LegalActionError("complete view cannot contain blockers")
        elif self.actions:
            raise LegalActionError("blocked view cannot expose partial actions")


def query_player_legal_actions(
    candidate_occurrence_ids: Iterable[str],
    proposals: Iterable[LegalActionProposal],
) -> LegalActionsView:
    available = tuple(candidate_occurrence_ids)
    proposal_list = tuple(proposals)
    blockers: list[str] = []
    for proposal in proposal_list:
        if not isinstance(proposal, LegalActionProposal):
            raise LegalActionError("only explicit LegalActionProposal values are accepted")
        if proposal.candidate_occurrence_id not in available:
            blockers.append(f"MISSING_CANDIDATE:{proposal.candidate_occurrence_id}")
        if not proposal.target_supported:
            blockers.append(f"UNSUPPORTED_TARGET:{proposal.action_id}")
        if not proposal.terminal_supported:
            blockers.append(f"UNSUPPORTED_TERMINAL:{proposal.action_id}")
    if blockers:
        return LegalActionsView(LegalActionsStatus.BLOCKED, (), tuple(blockers))
    actions = tuple(PlayerLegalAction(
        proposal.action_id, proposal.candidate_occurrence_id, proposal.actor_id,
        tuple(proposal.target_ids), proposal.resource_cost,
    ) for proposal in proposal_list)
    return LegalActionsView(LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE, actions, ())


def settle_legal_action(
    view: LegalActionsView, action_id: str, resource_before: object
) -> Decimal:
    """Return post-settlement reference resource; never mutate caller state."""
    before = _d(resource_before)
    if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
        raise LegalActionError("blocked legal-actions view cannot settle")
    matches = [action for action in view.actions if action.action_id == action_id]
    if len(matches) != 1:
        raise LegalActionError("action is missing or ambiguous")
    if matches[0].resource_cost > before:
        raise LegalActionError("insufficient explicit resource")
    return before - matches[0].resource_cost


__all__ = [
    "LegalActionError", "LegalActionProposal", "LegalActionsStatus", "LegalActionsView",
    "PlayerLegalAction", "query_player_legal_actions", "settle_legal_action",
]
