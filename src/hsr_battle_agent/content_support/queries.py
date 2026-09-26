# -*- coding: utf-8 -*-
"""Deterministic read-only queries over a loaded content-support registry.

Every query is a pure function of the registry argument.  All bulk results are
returned in the documented stable order (``AvatarID`` then ``SkillID``) and as
immutable tuples of frozen values, so repeated calls cannot differ.

This module deliberately re-derives **nothing** about support policy: it reads
``binding_level`` / ``support_status`` / ``readiness`` / blocker classes /
reentry hints straight out of M13 output (see the M14 "no duplicate policy"
rule).  The only computed values are the execution-denial reason and the
planner visibility buckets, both of which are *denials or descriptions* and
never permissions.
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple, Union

from .models import (
    REGISTRY_SATISFIES_GATE_CERTIFICATE,
    REGISTRY_SATISFIES_NATIVE_EVIDENCED,
    BindingLevel,
    BlockerClass,
    ContentSkillKey,
    ContentSupportError,
    EvidenceMode,
    ExecutionEligibility,
    ExecutionEligibilityOutcome,
    PlannerVisibilityMode,
    ReentryHint,
    SkillCapability,
    SkillRecord,
    SupportStatus,
    UnknownSkillError,
    as_capability,
    parse_closed,
)
from .registry import ContentSupportRegistry

__all__ = [
    "get_skill",
    "require_skill",
    "get_avatar_skills",
    "get_by_binding_level",
    "get_by_support_status",
    "get_by_blocker_class",
    "get_by_reentry_hint",
    "get_unbound_skills",
    "get_bound_skills",
    "get_settlement_skills",
    "get_second_hop_skills",
    "get_all_skills",
    "real_content_execution_eligibility",
    "planner_content_visibility",
    "describe_registry",
]

Capability = SkillCapability
_Token = Union[str, ContentSkillKey, Tuple[str, str]]


# --------------------------------------------------------------------------- #
# internal helpers
# --------------------------------------------------------------------------- #
def _cap(record: SkillRecord) -> SkillCapability:
    return as_capability(record)


def _sorted_caps(records: Iterable[SkillRecord]) -> Tuple[SkillCapability, ...]:
    ordered = sorted(records, key=lambda r: r.key.sort_key)
    return tuple(_cap(record) for record in ordered)


def _member_value(value: object) -> object:
    return getattr(value, "value", value)


def _coerce_enum(enum_cls: type, value: object) -> object:
    """Accept a member or a raw string, failing closed on unknown spellings."""
    if value is None:
        raise ContentSupportError(f"{enum_cls.__name__} filter must not be None")
    if isinstance(value, enum_cls):
        return value
    return parse_closed(enum_cls, value)


# --------------------------------------------------------------------------- #
# single-skill queries
# --------------------------------------------------------------------------- #
def get_skill(
    registry: ContentSupportRegistry,
    avatar_id: _Token,
    skill_id: Optional[str] = None,
) -> Optional[SkillCapability]:
    """Return the capability view, or ``None`` when the skill is absent.

    The explicit-absent form is the documented behaviour for unknown skills; use
    :func:`require_skill` when absence should raise.
    """
    token = avatar_id if skill_id is None else f"{avatar_id}:{skill_id}"
    record = registry.record(token)
    return None if record is None else _cap(record)


def require_skill(
    registry: ContentSupportRegistry,
    avatar_id: _Token,
    skill_id: Optional[str] = None,
) -> SkillCapability:
    """Return the capability view or raise :class:`UnknownSkillError`."""
    capability = get_skill(registry, avatar_id, skill_id)
    if capability is None:
        token = avatar_id if skill_id is None else f"{avatar_id}:{skill_id}"
        raise UnknownSkillError(token)
    return capability


# --------------------------------------------------------------------------- #
# bulk queries
# --------------------------------------------------------------------------- #
def get_all_skills(registry: ContentSupportRegistry) -> Tuple[SkillCapability, ...]:
    """Every canonical skill, ordered by ``AvatarID`` then ``SkillID``."""
    return _sorted_caps(registry.records)


def get_avatar_skills(
    registry: ContentSupportRegistry, avatar_id: str
) -> Tuple[SkillCapability, ...]:
    """All skills for one ``AvatarID`` (empty tuple when the avatar is absent)."""
    wanted = str(avatar_id)
    return _sorted_caps(r for r in registry.records if r.key.avatar_id == wanted)


def get_by_binding_level(
    registry: ContentSupportRegistry, level: Union[BindingLevel, str]
) -> Tuple[SkillCapability, ...]:
    wanted = _coerce_enum(BindingLevel, level)
    return _sorted_caps(r for r in registry.records if r.binding_level == wanted)


def get_by_support_status(
    registry: ContentSupportRegistry, status: Union[SupportStatus, str]
) -> Tuple[SkillCapability, ...]:
    wanted = _coerce_enum(SupportStatus, status)
    return _sorted_caps(r for r in registry.records if r.support_status == wanted)


def get_by_blocker_class(
    registry: ContentSupportRegistry, blocker: Union[BlockerClass, str]
) -> Tuple[SkillCapability, ...]:
    wanted = _coerce_enum(BlockerClass, blocker)
    return _sorted_caps(r for r in registry.records if wanted in r.blocker_classes)


def get_by_reentry_hint(
    registry: ContentSupportRegistry, hint: Union[ReentryHint, str]
) -> Tuple[SkillCapability, ...]:
    wanted = _coerce_enum(ReentryHint, hint)
    return _sorted_caps(r for r in registry.records if wanted in r.reentry_hints)


def get_unbound_skills(registry: ContentSupportRegistry) -> Tuple[SkillCapability, ...]:
    """Skills with no behavior root (``binding_level == STATIC_ONLY``)."""
    return _sorted_caps(r for r in registry.records if r.is_unbound)


def get_bound_skills(registry: ContentSupportRegistry) -> Tuple[SkillCapability, ...]:
    """Skills that reach a behavior root (non-null EntryAbility)."""
    return _sorted_caps(r for r in registry.records if r.is_bound)


def get_settlement_skills(registry: ContentSupportRegistry) -> Tuple[SkillCapability, ...]:
    """Skills whose represented closure records any settlement operation."""
    return _sorted_caps(r for r in registry.records if r.closure.settlement_present)


def get_second_hop_skills(registry: ContentSupportRegistry) -> Tuple[SkillCapability, ...]:
    """Skills whose first-hop targets contain a further TriggerAbility."""
    return _sorted_caps(r for r in registry.records if r.closure.second_hop_continuation_present)


# --------------------------------------------------------------------------- #
# execution denial boundary
# --------------------------------------------------------------------------- #
def _denial_reason(record: SkillRecord) -> Tuple[str, str]:
    """Derive the denial reason strictly from registry evidence."""
    status_value = _member_value(record.support_status)
    if record.is_unbound:
        reason = _member_value(record.unbound_reason) or "NO_ENTRY_ABILITY"
        return (
            "NO_BEHAVIOR_ROOT",
            f"binding_level={_member_value(record.binding_level)} "
            f"unbound_reason={reason}; there is no EntryAbility to reference",
        )
    if not record.closure.settlement_present:
        return (
            "NO_SETTLEMENT_OBSERVED",
            f"closure records no settlement operation "
            f"(scope={record.closure.settlement_scope}); nothing to settle",
        )
    if status_value == "BLOCKED_BY_CONTINUATION":
        return (
            "SECOND_HOP_CONTINUATION_UNRESOLVED",
            "a first-hop target contains a further TriggerAbility whose continuation is unresolved",
        )
    blockers = ", ".join(str(_member_value(b)) for b in record.blocker_classes) or "none recorded"
    return (
        f"BLOCKED_STATUS_{status_value}",
        f"registry support_status={status_value}; blocker classes: {blockers}",
    )


def real_content_execution_eligibility(
    registry: ContentSupportRegistry,
    avatar_id: _Token,
    skill_id: Optional[str] = None,
) -> ExecutionEligibility:
    """Execution-eligibility denial for one skill.

    The registry is descriptive data.  It cannot satisfy ``GateCertificate`` or
    ``NATIVE_EVIDENCED``, so this query has exactly one possible outcome:
    ``NOT_ELIGIBLE``.  It returns no certificate, constructs no transaction plan
    and never converts ``SAFE_REFERENCE_MODEL_ONLY`` into execution permission.
    """
    record = registry.record(avatar_id if skill_id is None else f"{avatar_id}:{skill_id}")
    if record is None:
        token = avatar_id if skill_id is None else f"{avatar_id}:{skill_id}"
        raise UnknownSkillError(token)

    reason_code, detail = _denial_reason(record)
    return ExecutionEligibility(
        key=record.key,
        outcome=ExecutionEligibilityOutcome.NOT_ELIGIBLE,
        reason_code=reason_code,
        reason_detail=detail,
        execution_evidence_mode=EvidenceMode.UNSUPPORTED,
        representation_evidence_mode=EvidenceMode.REFERENCE_MODEL,
        satisfies_gate_certificate=REGISTRY_SATISFIES_GATE_CERTIFICATE,
        satisfies_native_evidenced=REGISTRY_SATISFIES_NATIVE_EVIDENCED,
    )


# --------------------------------------------------------------------------- #
# planner visibility (descriptive only)
# --------------------------------------------------------------------------- #
def planner_content_visibility(
    registry: ContentSupportRegistry,
    mode: Union[PlannerVisibilityMode, str],
) -> Tuple[SkillCapability, ...]:
    """Descriptive filter for future planners.

    Modes are deliberately limited to ``REPRESENTABLE`` / ``HAS_SETTLEMENT`` /
    ``BLOCKED_WITH_REASON``.  This never yields a playable/legal/executable
    action: a registry skill is not a ``PlayerLegalAction``.
    """
    wanted = _coerce_enum(PlannerVisibilityMode, mode)
    if wanted is PlannerVisibilityMode.REPRESENTABLE:
        return _sorted_caps(
            r for r in registry.records
            if r.closure.closure_census_available or r.closure.closure_metadata_scope
        )
    if wanted is PlannerVisibilityMode.HAS_SETTLEMENT:
        return _sorted_caps(r for r in registry.records if r.closure.settlement_present)
    # BLOCKED_WITH_REASON: selection is the recorded presence of blocker classes,
    # read straight from M13 output rather than recomputed here.
    return _sorted_caps(r for r in registry.records if r.blocker_classes)


def describe_registry(registry: ContentSupportRegistry) -> dict:
    """Small diagnostic snapshot.  Not an authority and not a cache key."""
    counts = dict(registry.counts())
    counts["content_version"] = registry.content_version
    counts["schema"] = registry.summary.get("schema")
    counts["registry_path"] = str(registry.registry_path)
    counts["registry_satisfies_gate_certificate"] = REGISTRY_SATISFIES_GATE_CERTIFICATE
    counts["registry_satisfies_native_evidenced"] = REGISTRY_SATISFIES_NATIVE_EVIDENCED
    return counts
