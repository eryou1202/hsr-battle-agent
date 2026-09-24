"""REFERENCE_MODEL-only ordinary scheduling primitives (REF03-001)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Iterable

from hsr_battle_agent.battle_ir.evidence import EvidenceMode


class ReferenceScheduleError(ValueError):
    pass


def _d(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ReferenceScheduleError("boolean is not a scheduler number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ReferenceScheduleError("invalid scheduler number") from error
    if not result.is_finite() or result < 0:
        raise ReferenceScheduleError("scheduler number must be finite and non-negative")
    return result


class SchedulerFamily(Enum):
    ORDINARY = "ORDINARY"
    ULTRA_REQUEST = "ULTRA_REQUEST"
    TURN_INSERT_ABILITY = "TURN_INSERT_ABILITY"
    TURN_INSERT_ACTION = "TURN_INSERT_ACTION"
    ONE_MORE = "ONE_MORE"
    IMMEDIATE = "IMMEDIATE"


@dataclass(frozen=True)
class SchedulerCandidate:
    occurrence_id: str
    actor_id: str
    family: SchedulerFamily
    remaining_delay: Decimal
    comparator_tail: tuple[int, ...]
    evidence_mode: EvidenceMode

    def __post_init__(self) -> None:
        object.__setattr__(self, "comparator_tail", tuple(self.comparator_tail))
        if not self.occurrence_id or not self.actor_id or not isinstance(self.family, SchedulerFamily):
            raise ReferenceScheduleError("candidate identities and family are required")
        object.__setattr__(self, "remaining_delay", _d(self.remaining_delay))
        if not isinstance(self.evidence_mode, EvidenceMode):
            raise ReferenceScheduleError("candidate evidence mode required")
        if not all(isinstance(item, int) and not isinstance(item, bool) for item in self.comparator_tail):
            raise ReferenceScheduleError("comparator tail must be explicit integers")

    @property
    def comparator_key(self) -> tuple[Decimal, tuple[int, ...]]:
        return self.remaining_delay, self.comparator_tail


@dataclass(frozen=True)
class AIDecisionOpportunity:
    opportunity_id: str
    actor_id: str
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL


@dataclass(frozen=True)
class SchedulerSelection:
    selected: SchedulerCandidate
    ordered_candidates: tuple[SchedulerCandidate, ...]
    advanced_candidates: tuple[SchedulerCandidate, ...]
    elapsed: Decimal
    evidence_mode: EvidenceMode


@dataclass(frozen=True)
class BehaviorDelayView:
    actor_id: str
    normalized_behavior_delay: Decimal
    property38_unchanged: Decimal
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL


def select_ordinary_candidate(
    candidates: Iterable[SchedulerCandidate], *, evidence_mode: EvidenceMode
) -> SchedulerSelection:
    """Select/advance a bounded ordinary list without mutating its inputs."""
    items = tuple(candidates)
    if not items or any(item.family is not SchedulerFamily.ORDINARY for item in items):
        raise ReferenceScheduleError("ordinary reference selection cannot merge scheduler families")
    if any(item.evidence_mode is not evidence_mode for item in items):
        raise ReferenceScheduleError("candidate/mode mismatch")
    # Python's stable sort implements the explicitly accepted reference fallback.
    ordered = tuple(sorted(items, key=lambda item: item.comparator_key))
    best_key = ordered[0].comparator_key
    tied = tuple(item for item in ordered if item.comparator_key == best_key)
    if evidence_mode is EvidenceMode.NATIVE_EVIDENCED and len(tied) > 1:
        raise ReferenceScheduleError("native all-key tie is unresolved")
    if evidence_mode is not EvidenceMode.REFERENCE_MODEL:
        raise ReferenceScheduleError("this adapter supports REFERENCE_MODEL scheduling only")
    selected = ordered[0]
    elapsed = selected.remaining_delay
    advanced = tuple(SchedulerCandidate(
        item.occurrence_id, item.actor_id, item.family,
        max(Decimal("0"), item.remaining_delay-elapsed), item.comparator_tail,
        item.evidence_mode,
    ) for item in ordered)
    return SchedulerSelection(selected, ordered, advanced, elapsed, evidence_mode)


def apply_behavior_delay_separately(
    candidate: SchedulerCandidate, normalized_behavior_delay: object
) -> BehaviorDelayView:
    """Represent behavior delay without rewriting ordinary property38."""
    if candidate.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
        raise ReferenceScheduleError("behavior delay adapter is reference-only")
    return BehaviorDelayView(candidate.actor_id, _d(normalized_behavior_delay),
                             candidate.remaining_delay)


__all__ = [
    "AIDecisionOpportunity", "BehaviorDelayView", "ReferenceScheduleError",
    "SchedulerCandidate", "SchedulerFamily", "SchedulerSelection",
    "apply_behavior_delay_separately", "select_ordinary_candidate",
]
