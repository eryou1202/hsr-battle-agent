# -*- coding: utf-8 -*-
"""Closed typed model for the content-to-planner admission boundary.

This module owns the *only* vocabulary for "may this concrete real content
skill become an action candidate for the reference battle planner?".

For every current 4.4.54 real content skill the answer is ``REJECTED``.  The
outcome enum deliberately has no positive member: a future executable content
action cannot be expressed here, it must be introduced together with a real
runtime execution authority (see the M15 contract artifact).

Nothing in this module is a gameplay legality conclusion.  These are
engineering admission conclusions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from hsr_battle_agent.content_support import (
    BindingLevel,
    BlockerClass,
    ReentryHint,
    SupportStatus,
)

__all__ = [
    "ADMISSION_SCHEMA",
    "ADMISSION_OUTCOMES",
    "ADMISSION_REASON_CODES",
    "M14_REASON_TO_ADMISSION_REASON",
    "ContentPlannerAdmissionError",
    "PositiveContentAdmissionNotImplementedError",
    "POSITIVE_CONTENT_ADMISSION_MEANING",
    "FACADE_POSITIVE_PATH",
    "ContentPlannerAdmissionOutcome",
    "AdmissionReasonCode",
    "NonEffects",
    "ContentPlannerAdmissionRequest",
    "ContentPlannerAdmissionResult",
    "ContentPlanPreparation",
]

ADMISSION_SCHEMA = "content_planner_admission/1"

#: The complete outcome vocabulary.  There is intentionally no positive member.
ADMISSION_OUTCOMES = ("REJECTED",)

#: Reason codes an admission result may carry.
ADMISSION_REASON_CODES = (
    "CONTENT_VERSION_UNAVAILABLE",
    "SKILL_NOT_IN_REGISTRY",
    "NO_BEHAVIOR_ROOT",
    "NO_SETTLEMENT_OBSERVED",
    "SECOND_HOP_CONTINUATION_UNRESOLVED",
    "BLOCKED_BY_EVIDENCE",
    "BLOCKED_BY_REFERENCE_SUPPORT",
    "REPRESENTABLE_BUT_NOT_EXECUTABLE",
    # Visible fallback: an M14 reason this build does not recognise is surfaced
    # explicitly rather than silently mapped onto a known reason.
    "UNMAPPED_M14_REASON",
)

#: Deterministic M14-reason -> admission-reason mapping.  M14 stays the single
#: interpretation layer; this table only renames, it never re-derives.
M14_REASON_TO_ADMISSION_REASON = {
    "NO_BEHAVIOR_ROOT": "NO_BEHAVIOR_ROOT",
    "NO_SETTLEMENT_OBSERVED": "NO_SETTLEMENT_OBSERVED",
    "SECOND_HOP_CONTINUATION_UNRESOLVED": "SECOND_HOP_CONTINUATION_UNRESOLVED",
    "BLOCKED_STATUS_BLOCKED_BY_EVIDENCE": "BLOCKED_BY_EVIDENCE",
    "BLOCKED_STATUS_BLOCKED_BY_REFERENCE_SUPPORT": "BLOCKED_BY_REFERENCE_SUPPORT",
    "BLOCKED_STATUS_BLOCKED_BY_CONTINUATION": "SECOND_HOP_CONTINUATION_UNRESOLVED",
    "BLOCKED_STATUS_REPRESENTABLE_BLOCKED": "REPRESENTABLE_BUT_NOT_EXECUTABLE",
    "BLOCKED_STATUS_NO_SETTLEMENT": "NO_SETTLEMENT_OBSERVED",
    "BLOCKED_STATUS_UNBOUND_STATIC_SKILL": "NO_BEHAVIOR_ROOT",
}

#: The typed decisions this boundary makes.
ENGINEERING_CONCLUSIONS = (
    "may_create_reference_action_envelope",
    "may_enter_player_legal_actions",
    "may_expand_planner_successor",
    "may_mutate_state",
)

#: The concrete artifacts a rejection must never produce.
NON_EFFECT_FIELDS = (
    "reference_action_envelopes",
    "player_legal_actions",
    "planner_successors",
    "state_mutations",
    "rng_draws",
    "allocator_tickets",
    "scheduler_entries",
    "execution_traces",
    "gate_certificates",
    "transaction_plans",
    "staged_deltas",
)


class ContentPlannerAdmissionError(ValueError):
    """The admission *request* itself is malformed."""


#: Machine-readable meaning of the facade's positive path.
POSITIVE_CONTENT_ADMISSION_MEANING = "POSITIVE_CONTENT_ADMISSION_NOT_IMPLEMENTED"

#: The facade's positive path is not implemented and fails closed.  A future
#: positive admission must arrive together with a runtime execution authority,
#: never by widening the outcome enum or relaxing this facade.
FACADE_POSITIVE_PATH = "NOT_IMPLEMENTED_FAIL_CLOSED"


class PositiveContentAdmissionNotImplementedError(ContentPlannerAdmissionError):
    """Raised if the facade ever observes a non-rejected admission.

    M15 implements no positive planner handoff.  Reaching this error means the
    ``REJECTED``-only invariant was broken somewhere upstream; the facade fails
    closed instead of entering a planner.  A future positive path requires, at
    minimum: content capability/identity, an authorized content binder, runtime
    evidence/readiness, and ``GateCertificate`` / preflight closure.
    """

    meaning = POSITIVE_CONTENT_ADMISSION_MEANING

    def __init__(self, detail: str = "") -> None:
        self.reason_code = POSITIVE_CONTENT_ADMISSION_MEANING
        super().__init__(
            f"{POSITIVE_CONTENT_ADMISSION_MEANING}: {detail}" if detail
            else POSITIVE_CONTENT_ADMISSION_MEANING
        )


class ContentPlannerAdmissionOutcome(str, Enum):
    """Closed admission outcome vocabulary.

    ``REJECTED`` is the only member.  An eligible content action is
    unrepresentable here, not merely unreachable, until a runtime execution
    authority exists that can satisfy the strict execution prerequisites.
    """

    REJECTED = "REJECTED"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class AdmissionReasonCode(str, Enum):
    """Closed reason vocabulary for a content-planner rejection."""

    CONTENT_VERSION_UNAVAILABLE = "CONTENT_VERSION_UNAVAILABLE"
    SKILL_NOT_IN_REGISTRY = "SKILL_NOT_IN_REGISTRY"
    NO_BEHAVIOR_ROOT = "NO_BEHAVIOR_ROOT"
    NO_SETTLEMENT_OBSERVED = "NO_SETTLEMENT_OBSERVED"
    SECOND_HOP_CONTINUATION_UNRESOLVED = "SECOND_HOP_CONTINUATION_UNRESOLVED"
    BLOCKED_BY_EVIDENCE = "BLOCKED_BY_EVIDENCE"
    BLOCKED_BY_REFERENCE_SUPPORT = "BLOCKED_BY_REFERENCE_SUPPORT"
    REPRESENTABLE_BUT_NOT_EXECUTABLE = "REPRESENTABLE_BUT_NOT_EXECUTABLE"
    UNMAPPED_M14_REASON = "UNMAPPED_M14_REASON"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


@dataclass(frozen=True)
class NonEffects:
    """Counters for what an admission decision did *not* produce.

    Every field is structurally zero for the current M15 boundary; the type
    exists so tests and callers can assert the pre-planner invariant by
    comparing the whole record instead of trusting prose.
    """

    reference_action_envelopes: int = 0
    player_legal_actions: int = 0
    planner_successors: int = 0
    state_mutations: int = 0
    rng_draws: int = 0
    allocator_tickets: int = 0
    scheduler_entries: int = 0
    execution_traces: int = 0
    gate_certificates: int = 0
    transaction_plans: int = 0
    staged_deltas: int = 0

    def is_neutral(self) -> bool:
        return all(getattr(self, name) == 0 for name in NON_EFFECT_FIELDS)


@dataclass(frozen=True)
class ContentPlannerAdmissionRequest:
    """Immutable request naming one concrete real content skill.

    ``actor_id`` and ``target_ids`` are explicitly **non-authoritative**
    descriptive context only.  They take no part in the decision, AvatarID is
    never derived from ``actor_id``, and SkillID is never derived from a
    behavior name.
    """

    content_version: str
    avatar_id: str
    skill_id: str
    actor_id: Optional[str] = None
    target_ids: Tuple[str, ...] = ()
    note: Optional[str] = None

    #: Declares the only fields the decision may consult.
    AUTHORITATIVE_FIELDS = ("content_version", "avatar_id", "skill_id")

    def __post_init__(self) -> None:
        for name in ("content_version", "avatar_id", "skill_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ContentPlannerAdmissionError(
                    f"{name} must be a non-empty trimmed string"
                )
        targets = tuple(self.target_ids or ())
        if not all(isinstance(t, str) and t for t in targets):
            raise ContentPlannerAdmissionError("target_ids must be non-empty strings")
        object.__setattr__(self, "target_ids", targets)

    @property
    def skill_key(self) -> str:
        return f"{self.avatar_id}:{self.skill_id}"

    def to_dict(self) -> dict:
        return {
            "schema": ADMISSION_SCHEMA,
            "content_version": self.content_version,
            "avatar_id": self.avatar_id,
            "skill_id": self.skill_id,
            "skill_key": self.skill_key,
            "non_authoritative_context": {
                "actor_id": self.actor_id,
                "target_ids": list(self.target_ids),
                "note": self.note,
                "used_for_decision": False,
            },
        }


@dataclass(frozen=True)
class ContentPlannerAdmissionResult:
    """Structured, deterministic rejection of one content skill."""

    content_version: str
    skill_key: Optional[str]
    outcome: ContentPlannerAdmissionOutcome
    reason_code: AdmissionReasonCode
    reason_detail: str
    binding_level: Optional[BindingLevel]
    support_status: Optional[SupportStatus]
    blocker_classes: Tuple[BlockerClass, ...]
    reentry_hints: Tuple[ReentryHint, ...]
    frontier_packet_field: Optional[str]
    m14_reason_code: Optional[str]
    non_effects: NonEffects
    may_create_reference_action_envelope: bool = False
    may_enter_player_legal_actions: bool = False
    may_expand_planner_successor: bool = False
    may_mutate_state: bool = False

    @property
    def rejected(self) -> bool:
        return self.outcome is ContentPlannerAdmissionOutcome.REJECTED

    @property
    def admitted(self) -> bool:
        return not self.rejected

    def to_dict(self) -> dict:
        return {
            "schema": ADMISSION_SCHEMA,
            "content_version": self.content_version,
            "skill_key": self.skill_key,
            "outcome": self.outcome.value,
            "reason_code": self.reason_code.value,
            "reason_detail": self.reason_detail,
            "m14_reason_code": self.m14_reason_code,
            "binding_level": getattr(self.binding_level, "value", None),
            "support_status": getattr(self.support_status, "value", None),
            "blocker_classes": [getattr(b, "value", b) for b in self.blocker_classes],
            "reentry_hints": [getattr(h, "value", h) for h in self.reentry_hints],
            "frontier_packet_field": self.frontier_packet_field,
            "may_create_reference_action_envelope": self.may_create_reference_action_envelope,
            "may_enter_player_legal_actions": self.may_enter_player_legal_actions,
            "may_expand_planner_successor": self.may_expand_planner_successor,
            "may_mutate_state": self.may_mutate_state,
            "non_effects": {name: getattr(self.non_effects, name) for name in NON_EFFECT_FIELDS},
        }


@dataclass(frozen=True)
class ContentPlanPreparation:
    """Result of the optional planner facade.

    On rejection the facade returns this record and stops.  ``plan_request``
    stays ``None`` and ``planner_invocations`` stays ``0``; the planner is never
    entered.
    """

    admission: ContentPlannerAdmissionResult
    admitted: bool
    planner_invocations: int
    plan_request: Any

    @property
    def stopped_before_planner(self) -> bool:
        return not self.admitted and self.planner_invocations == 0 and self.plan_request is None
