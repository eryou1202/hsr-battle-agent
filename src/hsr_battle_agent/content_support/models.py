# -*- coding: utf-8 -*-
"""Closed-vocabulary typed model for the frozen M13 content-support registry.

This package is a **read-only descriptive query layer** over
``data/content_support/<content_version>/``.  It consumes the already-derived M13
registry and never re-derives support policy.

Authority boundary (invariant, enforced by construction):

* Registry data NEVER satisfies ``GateCertificate`` or ``NATIVE_EVIDENCED``.
* A record becoming "cleaner" grants no execution permission.
* :func:`~hsr_battle_agent.content_support.queries.real_content_execution_eligibility`
  can only ever return ``NOT_ELIGIBLE``.

The readiness and version vocabularies are **not** re-invented here: they are the
frozen ``ReadinessClass`` / ``VersionRelation`` / ``EvidenceMode`` types from
:mod:`hsr_battle_agent.battle_ir.evidence`, which is the sole home of those
vocabularies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence, Tuple, Union

from hsr_battle_agent.battle_ir.evidence import (  # noqa: F401  (re-exported)
    EvidenceMode,
    ReadinessClass,
    VersionRelation,
)

__all__ = [
    "REGISTRY_SCHEMA",
    "CONTRACT_SCHEMA",
    "SUMMARY_SCHEMA",
    "MASTER_SCHEMA",
    "CANONICAL_RECORD_COUNT",
    "EXPECTED_STATIC_SKILL_ROWS",
    "EXPECTED_TRIGGER_NAME_JOINED_ROWS",
    "EXPECTED_BEHAVIOR_ROOT_BOUND_ROWS",
    "EXPECTED_UNBOUND_ROWS",
    "EXPECTED_EMPTY_TRIGGER_ROWS",
    "EXPECTED_TRIGGER_MATCHED_WITHOUT_ENTRY_ABILITY",
    "EXPECTED_FULL_CLOSURE_SETTLEMENT_ROWS",
    "EXPECTED_SECOND_HOP_ROWS",
    "REGISTRY_SATISFIES_GATE_CERTIFICATE",
    "REGISTRY_SATISFIES_NATIVE_EVIDENCED",
    "ContentSupportError",
    "UnknownVocabularyError",
    "RegistryIntegrityError",
    "UnknownSkillError",
    "RegistryUnavailableError",
    "VersionRelationParseError",
    "M13_VERSION_RELATION_TOKEN",
    "UnknownVocabularyValue",
    "parse_closed",
    "BindingLevel",
    "SupportStatus",
    "Readiness",
    "BlockerClass",
    "ReentryHint",
    "UnboundReason",
    "SettlementKind",
    "ExecutionEligibilityOutcome",
    "PlannerVisibilityMode",
    "ContentSkillKey",
    "natural_sort_key",
    "freeze_json",
    "ClosureFacts",
    "MinimumFrontierPacketField",
    "SkillRecord",
    "SkillCapability",
    "ExecutionEligibility",
    "as_capability",
]

# --------------------------------------------------------------------------- #
# Schemas and frozen population invariants (M13 authority, do not reinterpret)
# --------------------------------------------------------------------------- #
REGISTRY_SCHEMA = "content_support_registry/1"
CONTRACT_SCHEMA = "content_support_registry_contract/1"
SUMMARY_SCHEMA = "content_support_summary/1"
MASTER_SCHEMA = "content_support_master/1"

CANONICAL_RECORD_COUNT = 620
EXPECTED_STATIC_SKILL_ROWS = 620
EXPECTED_TRIGGER_NAME_JOINED_ROWS = 528
EXPECTED_BEHAVIOR_ROOT_BOUND_ROWS = 524
EXPECTED_UNBOUND_ROWS = 96
EXPECTED_EMPTY_TRIGGER_ROWS = 92
EXPECTED_TRIGGER_MATCHED_WITHOUT_ENTRY_ABILITY = 4
EXPECTED_FULL_CLOSURE_SETTLEMENT_ROWS = 293
EXPECTED_ROOT_ONLY_SETTLEMENT_ROWS = 65
EXPECTED_BOUND_WITH_ANY_SETTLEMENT_ROWS = 358
EXPECTED_BOUND_WITHOUT_SETTLEMENT_ROWS = 166
EXPECTED_SECOND_HOP_ROWS = 20

#: The registry is descriptive data; it can never satisfy these gates.
REGISTRY_SATISFIES_GATE_CERTIFICATE = False
REGISTRY_SATISFIES_NATIVE_EVIDENCED = False

#: The single M13-to-frozen version-relation spelling mapping.
M13_VERSION_RELATION_TOKEN = "CLOSE_4.4.0_TO_4.4.54"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ContentSupportError(ValueError):
    """Base class for every content-support query-layer failure."""


class UnknownVocabularyError(ContentSupportError):
    """A registry value is outside the closed vocabulary this build knows.

    Raised (fail closed) unless the caller explicitly asks to preserve the raw
    value; a future or corrupted registry value is never silently mapped onto a
    supported value.
    """

    def __init__(self, vocabulary: str, raw: Any) -> None:
        self.vocabulary = vocabulary
        self.raw = raw
        super().__init__(f"{vocabulary} has no known member for {raw!r}")


class RegistryIntegrityError(ContentSupportError):
    """The registry on disk does not satisfy the M13 integrity invariants."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


class UnknownSkillError(ContentSupportError):
    """A required skill is absent from the loaded registry."""

    def __init__(self, key: Any) -> None:
        self.key = key
        super().__init__(f"skill not present in registry: {key}")


class RegistryUnavailableError(ContentSupportError):
    """The requested content version has no readable registry."""


class VersionRelationParseError(ContentSupportError):
    """A version relation cannot be represented by the frozen vocabulary."""


# --------------------------------------------------------------------------- #
# Closed vocabularies
# --------------------------------------------------------------------------- #
class _ClosedVocabulary(str, Enum):
    """String enum whose ``__str__`` is the bare member value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class BindingLevel(_ClosedVocabulary):
    """M13 ``binding_level`` vocabulary."""

    STATIC_ONLY = "STATIC_ONLY"
    BEHAVIOR_ROOT_BOUND = "BEHAVIOR_ROOT_BOUND"
    FULL_ACTION_REPRESENTED = "FULL_ACTION_REPRESENTED"
    REFERENCE_SETTLEMENT_BOUND = "REFERENCE_SETTLEMENT_BOUND"
    CONTENT_ACTION_EXECUTABLE_REFERENCE = "CONTENT_ACTION_EXECUTABLE_REFERENCE"


class SupportStatus(_ClosedVocabulary):
    """M13 ``support_status`` vocabulary."""

    REPRESENTABLE_BLOCKED = "REPRESENTABLE_BLOCKED"
    BLOCKED_BY_EVIDENCE = "BLOCKED_BY_EVIDENCE"
    BLOCKED_BY_REFERENCE_SUPPORT = "BLOCKED_BY_REFERENCE_SUPPORT"
    BLOCKED_BY_CONTINUATION = "BLOCKED_BY_CONTINUATION"
    NO_SETTLEMENT = "NO_SETTLEMENT"
    UNBOUND_STATIC_SKILL = "UNBOUND_STATIC_SKILL"


#: M13 readiness is the frozen ``ReadinessClass``; this alias avoids a second,
#: identity-unequal copy of the same vocabulary.
Readiness = ReadinessClass


class BlockerClass(_ClosedVocabulary):
    """M13 blocker-class vocabulary."""

    WAIT_ANIM_STATE = "WAIT_ANIM_STATE"
    DAMAGE_PACKET = "DAMAGE_PACKET"
    HEAL_PACKET = "HEAL_PACKET"
    MODIFIER = "MODIFIER"
    RANDOM_TARGET = "RANDOM_TARGET"
    PREDICATE_CALLBACK = "PREDICATE_CALLBACK"
    SECOND_HOP_CONTINUATION = "SECOND_HOP_CONTINUATION"
    RESOURCE = "RESOURCE"
    REFERENCE_PACKET_OTHER = "REFERENCE_PACKET_OTHER"
    BEHAVIOR_AFFECTING_NODE_NOT_COMPILED = "BEHAVIOR_AFFECTING_NODE_NOT_COMPILED"
    UNKNOWN_OR_UNSUPPORTED = "UNKNOWN_OR_UNSUPPORTED"


class ReentryHint(_ClosedVocabulary):
    """M13 reentry-hint vocabulary (routing hints only, never approvals)."""

    NEW_NATIVE_SPHITRATIO_EVIDENCE = "NEW_NATIVE_SPHITRATIO_EVIDENCE"
    WAITANIMSTATE_LOCAL_POLICY_REVIEW = "WAITANIMSTATE_LOCAL_POLICY_REVIEW"
    MODIFIER_STACKING_EVIDENCE = "MODIFIER_STACKING_EVIDENCE"
    TARGET_RANDOM_CONTRACT = "TARGET_RANDOM_CONTRACT"
    PREDICATE_CALLBACK_SUPPORT = "PREDICATE_CALLBACK_SUPPORT"
    SECOND_HOP_ORCHESTRATION = "SECOND_HOP_ORCHESTRATION"
    DAMAGE_PACKET_FIELD_SUPPORT = "DAMAGE_PACKET_FIELD_SUPPORT"
    HEAL_PACKET_SUPPORT = "HEAL_PACKET_SUPPORT"


class UnboundReason(_ClosedVocabulary):
    """M13 ``unbound_reason`` vocabulary."""

    EMPTY_TRIGGER_KEY = "EMPTY_TRIGGER_KEY"
    TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY = "TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY"


class SettlementKind(_ClosedVocabulary):
    """Settlement operation kinds permitted by the M13 closure census."""

    DAMAGE_REQUEST = "DAMAGE_REQUEST"
    HEAL_REQUEST = "HEAL_REQUEST"
    MODIFY_TEAM_SP = "MODIFY_TEAM_SP"
    MODIFY_WEAKNESS = "MODIFY_WEAKNESS"


class ExecutionEligibilityOutcome(_ClosedVocabulary):
    """Result of :func:`real_content_execution_eligibility`.

    M14 defines exactly one outcome.  There is deliberately no ``ELIGIBLE``
    member: the query layer has no authority to grant execution, so an eligible
    result is not merely unreachable, it is unrepresentable.
    """

    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class PlannerVisibilityMode(_ClosedVocabulary):
    """Descriptive planner-facing filter modes.

    ``PLAYABLE`` / ``LEGAL_ACTION`` / ``EXECUTABLE_ACTION`` are deliberately
    absent: a registry skill is not a ``PlayerLegalAction``.
    """

    REPRESENTABLE = "REPRESENTABLE"
    HAS_SETTLEMENT = "HAS_SETTLEMENT"
    BLOCKED_WITH_REASON = "BLOCKED_WITH_REASON"


class UnknownVocabularyValue:
    """Explicit preservation of a vocabulary value this build does not know.

    Produced only when a caller opts in via ``preserve_unknown=True``.  The
    value keeps the raw spelling and can never compare equal to a real member,
    so unknown data cannot masquerade as supported data.
    """

    __slots__ = ("vocabulary", "raw")

    def __init__(self, vocabulary: str, raw: Any) -> None:
        object.__setattr__(self, "vocabulary", str(vocabulary))
        object.__setattr__(self, "raw", raw)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, UnknownVocabularyValue)
            and other.vocabulary == self.vocabulary
            and other.raw == self.raw
        )

    def __hash__(self) -> int:
        return hash((self.vocabulary, repr(self.raw)))

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"UnknownVocabularyValue({self.vocabulary!r}, {self.raw!r})"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"UNKNOWN:{self.vocabulary}:{self.raw!r}"


def parse_closed(
    vocabulary: type,
    raw: Any,
    *,
    preserve_unknown: bool = False,
) -> Union[Enum, UnknownVocabularyValue, None]:
    """Map ``raw`` onto a closed vocabulary member, failing closed by default.

    ``None`` in maps to ``None`` out (M13 uses ``null`` for "not applicable").
    """
    if raw is None:
        return None
    try:
        return vocabulary(raw)
    except ValueError:
        if preserve_unknown:
            return UnknownVocabularyValue(vocabulary.__name__, raw)
        raise UnknownVocabularyError(vocabulary.__name__, raw) from None


# --------------------------------------------------------------------------- #
# Keys and ordering
# --------------------------------------------------------------------------- #
def natural_sort_key(token: str) -> Tuple[int, int, str]:
    """Deterministic ordering token.

    Digits-only identities sort numerically first; anything else sorts
    lexicographically after them.  This keeps ``AvatarID`` then ``SkillID``
    ordering stable even if a future version changes identity width.
    """
    text = str(token)
    if text.isdigit():
        return (0, int(text), "")
    return (1, 0, text)


@dataclass(frozen=True, order=True)
class ContentSkillKey:
    """Immutable typed identity for one static ``AvatarID:SkillID`` row."""

    content_version: str
    avatar_id: str
    skill_id: str

    def __post_init__(self) -> None:
        for name in ("content_version", "avatar_id", "skill_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ContentSupportError(f"{name} must be a non-empty trimmed string")

    @property
    def canonical(self) -> str:
        """Registry index form: ``"AvatarID:SkillID"`` (no version)."""
        return f"{self.avatar_id}:{self.skill_id}"

    @property
    def qualified(self) -> str:
        """Version-qualified form: ``"version/AvatarID:SkillID"``."""
        return f"{self.content_version}/{self.canonical}"

    @property
    def sort_key(self) -> Tuple[int, int, str, int, int, str]:
        return natural_sort_key(self.avatar_id) + natural_sort_key(self.skill_id)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.canonical


def freeze_json(value: Any) -> Any:
    """Recursively freeze a JSON value into an immutable equivalent."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): freeze_json(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(v) for v in value)
    return value


# --------------------------------------------------------------------------- #
# Records and views
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClosureFacts:
    """Closure metadata as recorded by M13 (descriptive only)."""

    closure_census_available: bool
    closure_metadata_scope: str
    settlement_scope: str
    settlement_present: bool
    settlement_operation_count: int
    settlement_kinds: Tuple[SettlementKind, ...]
    first_hop_edge_count: int
    first_hop_target_count: int
    nonsettlement_sibling_count: int
    second_hop_continuation_present: bool
    second_hop_occurrence_count: int
    operation_count: Union[int, None]
    blocker_occurrence_count: int
    waitanimstate_present: bool
    distinct_settlement_target_aliases: Tuple[str, ...]
    conditional_settlement_operation_count: int
    m12_full_closure_status: Union[str, None]


@dataclass(frozen=True)
class MinimumFrontierPacketField:
    """Minimum-frontier packet-field metadata recorded by M13.

    Descriptive only.  ``deterministic_transition`` being ``False`` means the
    field's runtime effect is *not* established, so it is a blocker, never an
    input contract.
    """

    field: str
    extra_attack_fields: Tuple[str, ...]
    deterministic_transition: Union[bool, None]
    reference_contract_status: Union[str, None]
    evidence_ref: Union[str, None]


@dataclass(frozen=True)
class SkillRecord:
    """One canonical M13 registry record, typed and frozen."""

    key: ContentSkillKey
    avatar_name: Union[str, None]
    skill_trigger_key: str
    entry_ability: Union[str, None]
    prepare_ability: Union[str, None]
    unbound_reason: Any
    trigger_key_matched_owner_skill_name: bool
    owner_config_path: str
    binding_level: Any
    support_status: Any
    readiness: Any
    representation_readiness: Union[str, None]
    execution_readiness: str
    primary_blocker: Any
    blocker_classes: Tuple[Any, ...]
    raw_blocker_reasons: Tuple[str, ...]
    reentry_hints: Tuple[Any, ...]
    version_relation: Any
    version_provenance_qualified: bool
    closure: ClosureFacts
    minimum_frontier_packet_field: Union[MinimumFrontierPacketField, None] = None
    #: Deep-frozen copy of the original M13 record body, for provenance lookups.
    #: Excluded from equality/hash so a record's identity is its typed content.
    raw_record: Any = field(default=None, compare=False, hash=False, repr=False)

    @property
    def is_bound(self) -> bool:
        """True when an EntryAbility names a behavior root."""
        return self.entry_ability is not None

    @property
    def is_unbound(self) -> bool:
        return not self.is_bound


@dataclass(frozen=True)
class SkillCapability:
    """Compact derived view over M13 data.  Not a new authority."""

    key: ContentSkillKey
    binding_level: Any
    support_status: Any
    representation_readiness: Union[str, None]
    execution_readiness: str
    settlement_present: bool
    settlement_kinds: Tuple[SettlementKind, ...]
    blocker_classes: Tuple[Any, ...]
    primary_blocker: Any
    reentry_hints: Tuple[Any, ...]
    entry_ability: Union[str, None]
    prepare_ability: Union[str, None]
    version_relation: Any


def as_capability(record: SkillRecord) -> SkillCapability:
    """Project a record onto the compact capability view."""
    return SkillCapability(
        key=record.key,
        binding_level=record.binding_level,
        support_status=record.support_status,
        representation_readiness=record.representation_readiness,
        execution_readiness=record.execution_readiness,
        settlement_present=record.closure.settlement_present,
        settlement_kinds=record.closure.settlement_kinds,
        blocker_classes=record.blocker_classes,
        primary_blocker=record.primary_blocker,
        reentry_hints=record.reentry_hints,
        entry_ability=record.entry_ability,
        prepare_ability=record.prepare_ability,
        version_relation=record.version_relation,
    )


@dataclass(frozen=True)
class ExecutionEligibility:
    """Denial result.  Never a certificate, plan or permission."""

    key: ContentSkillKey
    outcome: ExecutionEligibilityOutcome
    reason_code: str
    reason_detail: str
    execution_evidence_mode: EvidenceMode
    representation_evidence_mode: EvidenceMode
    satisfies_gate_certificate: bool = REGISTRY_SATISFIES_GATE_CERTIFICATE
    satisfies_native_evidenced: bool = REGISTRY_SATISFIES_NATIVE_EVIDENCED

    @property
    def eligible(self) -> bool:
        """Always ``False``: ``NOT_ELIGIBLE`` is the only defined outcome."""
        return self.outcome is not ExecutionEligibilityOutcome.NOT_ELIGIBLE
