# -*- coding: utf-8 -*-
"""Read-only content-capability query layer over the frozen M13 support registry.

Public surface
--------------

* :func:`load_registry` — load one **explicit** content version.
* :func:`get_skill` / :func:`require_skill` and the bulk ``get_by_*`` queries.
* :func:`real_content_execution_eligibility` — always ``NOT_ELIGIBLE``.
* :func:`planner_content_visibility` — descriptive planner filter.

Authority boundary
------------------

Registry data NEVER satisfies ``GateCertificate`` or ``NATIVE_EVIDENCED``.  A
record becoming cleaner does not grant execution permission.  Runtime still
requires its own evidence-mode, readiness and gate checks.

Still true after M14:

``FIRST_REAL_CONTENT_BOUND_ACTION = NO``,
``CONTENT_BOUND_BATTLE_SANDBOX = NOT_ESTABLISHED``,
``FULL_SOURCE_BACKED_HSR_ACTION_BINDING = NO``,
``NATIVE_SKILL_EXECUTION = NO``, ``Golden = 0``, ``NATIVE_TRACE = empty``.
"""
from __future__ import annotations

from .models import (
    EXPECTED_BEHAVIOR_ROOT_BOUND_ROWS,
    EXPECTED_EMPTY_TRIGGER_ROWS,
    EXPECTED_FULL_CLOSURE_SETTLEMENT_ROWS,
    EXPECTED_SECOND_HOP_ROWS,
    EXPECTED_STATIC_SKILL_ROWS,
    EXPECTED_TRIGGER_MATCHED_WITHOUT_ENTRY_ABILITY,
    EXPECTED_TRIGGER_NAME_JOINED_ROWS,
    EXPECTED_UNBOUND_ROWS,
    REGISTRY_SATISFIES_GATE_CERTIFICATE,
    REGISTRY_SATISFIES_NATIVE_EVIDENCED,
    BindingLevel,
    BlockerClass,
    ClosureFacts,
    ContentSkillKey,
    ContentSupportError,
    EvidenceMode,
    ExecutionEligibility,
    ExecutionEligibilityOutcome,
    PlannerVisibilityMode,
    Readiness,
    ReadinessClass,
    ReentryHint,
    RegistryIntegrityError,
    RegistryUnavailableError,
    SettlementKind,
    SkillCapability,
    SkillRecord,
    SupportStatus,
    UnboundReason,
    UnknownSkillError,
    UnknownVocabularyError,
    UnknownVocabularyValue,
    VersionRelation,
    VersionRelationParseError,
    as_capability,
    natural_sort_key,
    parse_closed,
)
from .queries import (
    describe_registry,
    get_all_skills,
    get_avatar_skills,
    get_bound_skills,
    get_by_binding_level,
    get_by_blocker_class,
    get_by_reentry_hint,
    get_by_support_status,
    get_second_hop_skills,
    get_settlement_skills,
    get_skill,
    get_unbound_skills,
    planner_content_visibility,
    real_content_execution_eligibility,
    require_skill,
)
from .registry import (
    CONTRACT_FILENAME,
    CONTENT_SUPPORT_ROOT_RELATIVE,
    MASTER_FILENAME,
    REGISTRY_FILENAME,
    SUPPORTED_CONTENT_VERSIONS,
    SUMMARY_FILENAME,
    ContentSupportRegistry,
    available_content_versions,
    content_support_dir,
    default_repository_root,
    load_registry,
)

__all__ = [
    # loader
    "load_registry",
    "ContentSupportRegistry",
    "available_content_versions",
    "content_support_dir",
    "default_repository_root",
    "SUPPORTED_CONTENT_VERSIONS",
    "CONTENT_SUPPORT_ROOT_RELATIVE",
    "REGISTRY_FILENAME",
    "CONTRACT_FILENAME",
    "SUMMARY_FILENAME",
    "MASTER_FILENAME",
    # queries
    "get_skill",
    "require_skill",
    "get_all_skills",
    "get_avatar_skills",
    "get_by_binding_level",
    "get_by_support_status",
    "get_by_blocker_class",
    "get_by_reentry_hint",
    "get_unbound_skills",
    "get_bound_skills",
    "get_settlement_skills",
    "get_second_hop_skills",
    "real_content_execution_eligibility",
    "planner_content_visibility",
    "describe_registry",
    # model
    "ContentSkillKey",
    "SkillRecord",
    "SkillCapability",
    "ClosureFacts",
    "ExecutionEligibility",
    "BindingLevel",
    "SupportStatus",
    "Readiness",
    "ReadinessClass",
    "BlockerClass",
    "ReentryHint",
    "UnboundReason",
    "SettlementKind",
    "ExecutionEligibilityOutcome",
    "PlannerVisibilityMode",
    "EvidenceMode",
    "VersionRelation",
    "UnknownVocabularyValue",
    "parse_closed",
    "natural_sort_key",
    "as_capability",
    # errors
    "ContentSupportError",
    "UnknownVocabularyError",
    "RegistryIntegrityError",
    "RegistryUnavailableError",
    "UnknownSkillError",
    "VersionRelationParseError",
    # invariants
    "REGISTRY_SATISFIES_GATE_CERTIFICATE",
    "REGISTRY_SATISFIES_NATIVE_EVIDENCED",
    "EXPECTED_STATIC_SKILL_ROWS",
    "EXPECTED_TRIGGER_NAME_JOINED_ROWS",
    "EXPECTED_BEHAVIOR_ROOT_BOUND_ROWS",
    "EXPECTED_UNBOUND_ROWS",
    "EXPECTED_EMPTY_TRIGGER_ROWS",
    "EXPECTED_TRIGGER_MATCHED_WITHOUT_ENTRY_ABILITY",
    "EXPECTED_FULL_CLOSURE_SETTLEMENT_ROWS",
    "EXPECTED_SECOND_HOP_ROWS",
]
