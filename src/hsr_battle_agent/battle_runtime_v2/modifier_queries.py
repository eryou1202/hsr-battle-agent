"""Pure, frozen modifier lookup and stacking-decision primitives (G02-001).

The functions in this module inspect caller-supplied immutable records only.
They neither mutate a modifier collection nor grant execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ModifierQueryError(ValueError):
    """The query cannot be evaluated without guessing a frozen value."""


class LookupState(Enum):
    ADDED_OR_ALIVE = 0
    ALIVE = 1


class CasterFilterKind(Enum):
    NATIVE_ANY = "NATIVE_ANY"
    EXACT_EFFECTIVE = "EXACT_EFFECTIVE"


class StackingDecision(Enum):
    CREATE_DISTINCT = "CREATE_DISTINCT"
    PROCESS_EXISTING = "PROCESS_EXISTING"
    BLOCKED_REFRESH = "BLOCKED_REFRESH"
    BLOCKED_UNSUPPORTED = "BLOCKED_UNSUPPORTED"


@dataclass(frozen=True)
class ModifierCandidate:
    occurrence_id: str
    name: str
    state: LookupState
    stacking_flag: int
    direct_caster_id: str
    effective_caster_id: str
    provider_id: str | None

    def __post_init__(self) -> None:
        for label in ("occurrence_id", "name", "direct_caster_id", "effective_caster_id"):
            if not isinstance(getattr(self, label), str) or not getattr(self, label):
                raise ModifierQueryError(f"{label} must be a non-empty string")
        if isinstance(self.stacking_flag, bool) or not isinstance(self.stacking_flag, int):
            raise ModifierQueryError("stacking_flag must be an exact integer")
        if self.provider_id is not None and (not isinstance(self.provider_id, str) or not self.provider_id):
            raise ModifierQueryError("provider_id must be a non-empty string or native null")


@dataclass(frozen=True)
class ModifierLookupQuery:
    name: str
    state: LookupState
    stacking_flag: int
    caster_filter: CasterFilterKind
    effective_caster_id: str | None = None
    provider_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ModifierQueryError("name must be a non-empty exact string")
        if not isinstance(self.state, LookupState):
            raise ModifierQueryError("state must be a bound LookupState")
        if isinstance(self.stacking_flag, bool) or not isinstance(self.stacking_flag, int):
            raise ModifierQueryError("stacking_flag must be a bound exact integer")
        if not isinstance(self.caster_filter, CasterFilterKind):
            raise ModifierQueryError("caster_filter must be explicit")
        if self.caster_filter is CasterFilterKind.EXACT_EFFECTIVE:
            if not isinstance(self.effective_caster_id, str) or not self.effective_caster_id:
                raise ModifierQueryError("concrete caster lookup requires effective_caster_id")
        elif self.effective_caster_id is not None:
            raise ModifierQueryError("wildcard caster must not carry a concrete caster")
        if self.provider_id is not None and (not isinstance(self.provider_id, str) or not self.provider_id):
            raise ModifierQueryError("provider_id must be a non-empty opaque token or native null")


@dataclass(frozen=True)
class ModifierLookupResult:
    query: ModifierLookupQuery
    match: ModifierCandidate | None
    inspected_occurrences: tuple[str, ...]


@dataclass(frozen=True)
class StackingPlan:
    policy_ordinal: int | None
    decision: StackingDecision
    matched_occurrence_id: str | None
    reason: str

    @property
    def mutates_found_instance(self) -> bool:
        return self.decision is StackingDecision.PROCESS_EXISTING


def _matches(candidate: ModifierCandidate, query: ModifierLookupQuery) -> bool:
    # Preserve the recovered branch order: name -> state -> flag -> caster -> provider.
    if candidate.name != query.name:
        return False
    if candidate.state is not query.state:
        return False
    if query.stacking_flag != 100 and candidate.stacking_flag != query.stacking_flag:
        return False
    if query.caster_filter is CasterFilterKind.NATIVE_ANY:
        # Native -1/0 exits here.  A supplied provider is deliberately ignored.
        return True
    if candidate.effective_caster_id != query.effective_caster_id:
        return False
    # Native null is absence of this predicate, not equality to a null field.
    if query.provider_id is not None and candidate.provider_id != query.provider_id:
        return False
    return True


def first_matching_modifier(
    candidates: Iterable[ModifierCandidate], query: ModifierLookupQuery
) -> ModifierLookupResult:
    """Return the first local match in caller-supplied order, or none."""
    if not isinstance(query, ModifierLookupQuery):
        raise ModifierQueryError("query must be ModifierLookupQuery")
    inspected: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, ModifierCandidate):
            raise ModifierQueryError("collection contains an unbound candidate")
        inspected.append(candidate.occurrence_id)
        if _matches(candidate, query):
            return ModifierLookupResult(query, candidate, tuple(inspected))
    return ModifierLookupResult(query, None, tuple(inspected))


def plan_stacking(
    policy_ordinal: int | None, lookup: ModifierLookupResult
) -> StackingPlan:
    """Produce a bounded decision description; never apply it.

    Only Multiple's branch is directly safe as a create/add-style decision here.
    Refresh remains separately labelled and quarantined.  Other policies require
    lifecycle dependencies outside this pure primitive.
    """
    if not isinstance(lookup, ModifierLookupResult):
        raise ModifierQueryError("lookup must be a completed pure lookup result")
    if policy_ordinal is not None and (
        isinstance(policy_ordinal, bool) or not isinstance(policy_ordinal, int)
    ):
        raise ModifierQueryError("policy ordinal must be an integer or absent")
    matched = None if lookup.match is None else lookup.match.occurrence_id
    if policy_ordinal == 4:  # Multiple: FACT in the frozen policy table.
        return StackingPlan(4, StackingDecision.CREATE_DISTINCT, matched,
                            "Multiple appends a distinct instance; a found instance is not mutated")
    if policy_ordinal == 2:  # Refresh stays distinct from all Replace families.
        return StackingPlan(2, StackingDecision.BLOCKED_REFRESH, matched,
                            "Refresh lifecycle/commit remains quarantined")
    if policy_ordinal is None:
        return StackingPlan(None, StackingDecision.BLOCKED_UNSUPPORTED, matched,
                            "missing stacking policy is UNKNOWN")
    return StackingPlan(policy_ordinal, StackingDecision.BLOCKED_UNSUPPORTED, matched,
                        "policy requires a separately closed lifecycle contract")


__all__ = [
    "CasterFilterKind", "LookupState", "ModifierCandidate", "ModifierLookupQuery",
    "ModifierLookupResult", "ModifierQueryError", "StackingDecision", "StackingPlan",
    "first_matching_modifier", "plan_stacking",
]
