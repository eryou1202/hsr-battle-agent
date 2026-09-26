# -*- coding: utf-8 -*-
"""Read-only loader for one explicit content version's M13 support registry.

The loader never regenerates M13, never reads the 342 MB compiler report and
never re-derives support policy.  It only:

1. parses the four M13 artifacts,
2. types them against the closed vocabularies, and
3. validates simple *integrity* invariants (schema, count, uniqueness, index
   consistency).

It deliberately does **not** recompute ``binding_level`` / ``support_status`` /
``readiness``; those are consumed as already-derived M13 output so that future
registry revisions flow through unchanged.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .models import (
    CANONICAL_RECORD_COUNT,
    CONTRACT_SCHEMA,
    EXPECTED_EMPTY_TRIGGER_ROWS,
    EXPECTED_SECOND_HOP_ROWS,
    EXPECTED_STATIC_SKILL_ROWS,
    EXPECTED_TRIGGER_MATCHED_WITHOUT_ENTRY_ABILITY,
    EXPECTED_TRIGGER_NAME_JOINED_ROWS,
    EXPECTED_UNBOUND_ROWS,
    MASTER_SCHEMA,
    MinimumFrontierPacketField,
    M13_VERSION_RELATION_TOKEN,
    REGISTRY_SCHEMA,
    SUMMARY_SCHEMA,
)
from .models import (
    BindingLevel,
    BlockerClass,
    ClosureFacts,
    ContentSkillKey,
    ContentSupportError,
    ReentryHint,
    Readiness,
    RegistryIntegrityError,
    RegistryUnavailableError,
    SettlementKind,
    SkillRecord,
    SupportStatus,
    UnboundReason,
    VersionRelation,
    VersionRelationParseError,
    freeze_json,
    parse_closed,
)

__all__ = [
    "CONTENT_SUPPORT_ROOT_RELATIVE",
    "REGISTRY_FILENAME",
    "CONTRACT_FILENAME",
    "SUMMARY_FILENAME",
    "MASTER_FILENAME",
    "SUPPORTED_CONTENT_VERSIONS",
    "default_repository_root",
    "content_support_dir",
    "available_content_versions",
    "load_registry",
    "ContentSupportRegistry",
]

#: Relative location of the M13/M14 data plane inside the repository.
CONTENT_SUPPORT_ROOT_RELATIVE = Path("data") / "content_support"

REGISTRY_FILENAME = "content_support_registry_v1.json"
CONTRACT_FILENAME = "content_support_registry_contract_v1.json"
SUMMARY_FILENAME = "content_support_summary_v1.json"
MASTER_FILENAME = "content_support_master_v1.json"

#: Versions this build knows how to read.  Explicit on purpose: there is no
#: "latest" resolution and no ``4.4.54 -> 4.5.54`` fallback.
SUPPORTED_CONTENT_VERSIONS: Tuple[str, ...] = ("4.4.54",)


def default_repository_root() -> Path:
    """Repository root inferred from this file's location (``<root>/src/...``)."""
    return Path(__file__).resolve().parents[3]


def content_support_dir(content_version: str, root: Optional[Path] = None) -> Path:
    """Directory holding one content version's support artifacts."""
    base = Path(root) if root is not None else default_repository_root()
    return base / CONTENT_SUPPORT_ROOT_RELATIVE / content_version


def available_content_versions(root: Optional[Path] = None) -> Tuple[str, ...]:
    """Content versions that have a registry directory on disk.

    Read-only discovery.  Callers must still pass an explicit version to
    :func:`load_registry`; this helper exists for diagnostics and tests.
    """
    base = (Path(root) if root is not None else default_repository_root()) / CONTENT_SUPPORT_ROOT_RELATIVE
    if not base.is_dir():
        return ()
    found = [
        child.name
        for child in sorted(base.iterdir())
        if child.is_dir() and (child / REGISTRY_FILENAME).is_file()
    ]
    return tuple(found)


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise RegistryUnavailableError(f"missing artifact: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise RegistryIntegrityError("MALFORMED_JSON", f"{path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegistryIntegrityError("NOT_AN_OBJECT", path.name)
    return payload


def _require_str(payload: Mapping[str, Any], field: str, where: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise RegistryIntegrityError("MISSING_FIELD", f"{where}.{field}")
    return value


def _version_relation(raw: Any) -> Any:
    """Map the single M13 spelling onto the frozen ``VersionRelation``."""
    if raw is None:
        return None
    if raw == M13_VERSION_RELATION_TOKEN:
        return VersionRelation.CLOSE_VERSION
    try:
        return VersionRelation(raw)
    except ValueError:
        raise VersionRelationParseError(
            f"version relation {raw!r} is not representable by the frozen vocabulary"
        ) from None


def _closure(record: Mapping[str, Any], where: str) -> ClosureFacts:
    raw = record.get("closure")
    if not isinstance(raw, Mapping):
        raise RegistryIntegrityError("MISSING_FIELD", f"{where}.closure")

    def _flag(name: str) -> bool:
        return bool(raw.get(name))

    def _int(name: str) -> int:
        value = raw.get(name)
        return value if isinstance(value, int) else 0

    kinds: Iterable[Any] = raw.get("settlement_kinds") or ()
    aliases: Iterable[Any] = raw.get("distinct_settlement_target_aliases") or ()
    return ClosureFacts(
        closure_census_available=_flag("closure_census_available"),
        closure_metadata_scope=str(raw.get("closure_metadata_scope") or ""),
        settlement_scope=str(raw.get("settlement_scope") or ""),
        settlement_present=_flag("settlement_present"),
        settlement_operation_count=_int("settlement_operation_count"),
        settlement_kinds=tuple(
            parse_closed(SettlementKind, kind, preserve_unknown=True) for kind in kinds
        ),
        first_hop_edge_count=_int("first_hop_edge_count"),
        first_hop_target_count=_int("first_hop_target_count"),
        nonsettlement_sibling_count=_int("nonsettlement_sibling_count"),
        second_hop_continuation_present=_flag("second_hop_continuation_present"),
        second_hop_occurrence_count=_int("second_hop_occurrence_count"),
        operation_count=raw.get("operation_count") if isinstance(raw.get("operation_count"), int) else None,
        blocker_occurrence_count=_int("blocker_occurrence_count"),
        waitanimstate_present=_flag("waitanimstate_present"),
        distinct_settlement_target_aliases=tuple(str(a) for a in aliases),
        conditional_settlement_operation_count=_int("conditional_settlement_operation_count"),
        m12_full_closure_status=raw.get("m12_full_closure_status"),
    )


def _packet_field(raw: Mapping[str, Any]) -> Optional[MinimumFrontierPacketField]:
    payload = raw.get("minimum_frontier_packet_field")
    if not isinstance(payload, Mapping):
        return None
    declared = payload.get("field")
    if not isinstance(declared, str) or not declared:
        return None
    return MinimumFrontierPacketField(
        field=declared,
        extra_attack_fields=tuple(str(v) for v in (payload.get("extra_attack_fields") or ())),
        deterministic_transition=payload.get("deterministic_transition"),
        reference_contract_status=payload.get("reference_contract_status"),
        evidence_ref=payload.get("evidence_ref"),
    )


def _record(raw: Mapping[str, Any], content_version: str, index: int) -> SkillRecord:
    where = f"records[{index}]"
    key = ContentSkillKey(
        content_version=content_version,
        avatar_id=_require_str(raw, "avatar_id", where),
        skill_id=_require_str(raw, "skill_id", where),
    )
    declared = raw.get("skill_key")
    if declared != key.canonical:
        raise RegistryIntegrityError(
            "SKILL_KEY_MISMATCH", f"{where}: declared {declared!r} != derived {key.canonical!r}"
        )
    return SkillRecord(
        key=key,
        avatar_name=raw.get("avatar_name"),
        skill_trigger_key=str(raw.get("skill_trigger_key") or ""),
        entry_ability=raw.get("entry_ability"),
        prepare_ability=raw.get("prepare_ability"),
        unbound_reason=parse_closed(UnboundReason, raw.get("unbound_reason")),
        trigger_key_matched_owner_skill_name=bool(raw.get("trigger_key_matched_owner_skill_name")),
        owner_config_path=str(raw.get("owner_config_path") or ""),
        binding_level=parse_closed(BindingLevel, raw.get("binding_level")),
        support_status=parse_closed(SupportStatus, raw.get("support_status")),
        readiness=parse_closed(Readiness, raw.get("readiness")),
        representation_readiness=raw.get("representation_readiness"),
        execution_readiness=str(raw.get("execution_readiness") or ""),
        primary_blocker=parse_closed(BlockerClass, raw.get("primary_blocker")),
        blocker_classes=tuple(
            parse_closed(BlockerClass, value) for value in (raw.get("blocker_classes") or ())
        ),
        raw_blocker_reasons=tuple(str(v) for v in (raw.get("raw_blocker_reasons") or ())),
        reentry_hints=tuple(
            parse_closed(ReentryHint, value) for value in (raw.get("reentry_hints") or ())
        ),
        version_relation=_version_relation(raw.get("version_relation")),
        version_provenance_qualified=bool(raw.get("version_provenance_qualified")),
        closure=_closure(raw, where),
        minimum_frontier_packet_field=_packet_field(raw),
        raw_record=freeze_json(raw),
    )


@dataclass(frozen=True)
class ContentSupportRegistry:
    """Immutable, deterministically ordered view of one content version.

    ``raw_records`` keeps the original M13 record bodies (deep-frozen) for
    provenance.  Queries never mutate it, and the registry exposes no setter.
    """

    content_version: str
    registry_path: Path
    contract: Mapping[str, Any]
    summary: Mapping[str, Any]
    master: Mapping[str, Any]
    records: Tuple[SkillRecord, ...]
    indexes: Mapping[str, Any]
    population: Mapping[str, Any]
    validation_summary: Mapping[str, Any]
    _by_key: Mapping[str, SkillRecord]

    def __post_init__(self) -> None:
        if self.content_version not in SUPPORTED_CONTENT_VERSIONS:
            raise RegistryIntegrityError(
                "UNSUPPORTED_CONTENT_VERSION",
                f"{self.content_version} not in {SUPPORTED_CONTENT_VERSIONS}",
            )

    # -- primitive lookups -------------------------------------------------
    @property
    def keys(self) -> Tuple[ContentSkillKey, ...]:
        return tuple(record.key for record in self.records)

    def record(self, key: Any) -> Optional[SkillRecord]:
        """Explicit-absent lookup by key, canonical string or ``(avatar, skill)``."""
        token = _coerce_index_token(key)
        return self._by_key.get(token)

    def counts(self) -> Mapping[str, int]:
        """Small derived counts.  Integrity only; not a policy re-derivation."""
        binding: Dict[str, int] = {}
        status: Dict[str, int] = {}
        for record in self.records:
            binding_key = getattr(record.binding_level, "value", None) or str(record.binding_level)
            status_key = getattr(record.support_status, "value", None) or str(record.support_status)
            binding[binding_key] = binding.get(binding_key, 0) + 1
            status[status_key] = status.get(status_key, 0) + 1
        return {
            "canonical_records": len(self.records),
            "bound": sum(1 for r in self.records if r.is_bound),
            "unbound": sum(1 for r in self.records if r.is_unbound),
            "with_any_observed_settlement": sum(
                1 for r in self.records if r.closure.settlement_present
            ),
            "second_hop_affected": sum(
                1 for r in self.records if r.closure.second_hop_continuation_present
            ),
            "binding_STATIC_ONLY": binding.get("STATIC_ONLY", 0),
            "status_UNBOUND_STATIC_SKILL": status.get("UNBOUND_STATIC_SKILL", 0),
        }


def _coerce_index_token(key: Any) -> str:
    if isinstance(key, ContentSkillKey):
        return key.canonical
    if isinstance(key, (tuple, list)) and len(key) == 2:
        return f"{key[0]}:{key[1]}"
    return str(key)


def _validate_registry_payload(
    payload: Mapping[str, Any],
    content_version: str,
    *,
    strict_counts: bool,
) -> Tuple[Tuple[SkillRecord, ...], Mapping[str, Any], Mapping[str, Any]]:
    schema = payload.get("schema")
    if schema != REGISTRY_SCHEMA:
        raise RegistryIntegrityError("UNEXPECTED_SCHEMA", f"registry schema {schema!r}")
    declared_version = payload.get("content_version")
    if declared_version != content_version:
        raise RegistryIntegrityError(
            "CONTENT_VERSION_MISMATCH",
            f"requested {content_version!r} but registry declares {declared_version!r}",
        )

    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        raise RegistryIntegrityError("MISSING_FIELD", "records")

    records = tuple(_record(raw, content_version, i) for i, raw in enumerate(raw_records))

    keys = [record.key.canonical for record in records]
    duplicates = sorted({k for k in keys if keys.count(k) > 1}) if len(set(keys)) != len(keys) else []
    if duplicates:
        raise RegistryIntegrityError("DUPLICATE_SKILL_KEY", ", ".join(duplicates[:5]))

    population = payload.get("population") or {}
    declared_count = population.get("canonical_records")
    if declared_count is not None and declared_count != len(records):
        raise RegistryIntegrityError(
            "RECORD_COUNT_MISMATCH",
            f"population declares {declared_count} but records has {len(records)}",
        )

    if strict_counts:
        _assert_population(records, population)

    indexes = payload.get("indexes") or {}
    _validate_indexes(indexes, set(keys))
    return records, population, indexes


def _assert_population(records: Tuple[SkillRecord, ...], population: Mapping[str, Any]) -> None:
    """Integrity checks against the frozen M13 population invariants."""
    total = len(records)
    if total != CANONICAL_RECORD_COUNT or population.get("static_skill_rows") != EXPECTED_STATIC_SKILL_ROWS:
        raise RegistryIntegrityError(
            "POPULATION_MISMATCH",
            f"expected {EXPECTED_STATIC_SKILL_ROWS} static rows, found {total}",
        )
    joined = sum(1 for r in records if r.skill_trigger_key)
    if joined != EXPECTED_TRIGGER_NAME_JOINED_ROWS:
        raise RegistryIntegrityError(
            "POPULATION_MISMATCH", f"trigger-name-joined {joined} != {EXPECTED_TRIGGER_NAME_JOINED_ROWS}"
        )
    bound = sum(1 for r in records if r.is_bound)
    if bound != CANONICAL_RECORD_COUNT - EXPECTED_UNBOUND_ROWS:
        raise RegistryIntegrityError(
            "POPULATION_MISMATCH", f"bound {bound} != {CANONICAL_RECORD_COUNT - EXPECTED_UNBOUND_ROWS}"
        )
    unbound = sum(1 for r in records if r.is_unbound)
    if unbound != EXPECTED_UNBOUND_ROWS:
        raise RegistryIntegrityError("POPULATION_MISMATCH", f"unbound {unbound} != {EXPECTED_UNBOUND_ROWS}")
    empty = sum(1 for r in records if _is_unbound_reason(r, "EMPTY_TRIGGER_KEY"))
    if empty != EXPECTED_EMPTY_TRIGGER_ROWS:
        raise RegistryIntegrityError("POPULATION_MISMATCH", f"empty trigger {empty}")
    no_entry = sum(
        1 for r in records if _is_unbound_reason(r, "TRIGGER_MATCHED_BUT_NO_ENTRY_ABILITY")
    )
    if no_entry != EXPECTED_TRIGGER_MATCHED_WITHOUT_ENTRY_ABILITY:
        raise RegistryIntegrityError("POPULATION_MISMATCH", f"trigger-matched-no-entry {no_entry}")
    second_hop = sum(1 for r in records if r.closure.second_hop_continuation_present)
    if second_hop != EXPECTED_SECOND_HOP_ROWS:
        raise RegistryIntegrityError("POPULATION_MISMATCH", f"second hop {second_hop}")
    # An EntryAbility must be present on every non-STATIC_ONLY row.
    broken = [
        r.key.canonical
        for r in records
        if r.binding_level is not BindingLevel.STATIC_ONLY and r.entry_ability is None
    ]
    if broken:
        raise RegistryIntegrityError("BINDING_WITHOUT_ENTRY_ABILITY", ", ".join(broken[:5]))


def _is_unbound_reason(record: SkillRecord, value: str) -> bool:
    reason = record.unbound_reason
    return getattr(reason, "value", reason) == value


def _validate_indexes(indexes: Mapping[str, Any], keys: set) -> None:
    by_skill = indexes.get("by_skill")
    if not isinstance(by_skill, Mapping):
        raise RegistryIntegrityError("MISSING_FIELD", "indexes.by_skill")
    if set(by_skill) != keys:
        missing = sorted(keys - set(by_skill))[:5]
        extra = sorted(set(by_skill) - keys)[:5]
        raise RegistryIntegrityError(
            "INDEX_INCONSISTENT", f"by_skill missing={missing} extra={extra}"
        )
    for name in ("by_avatar", "by_blocker_class", "by_support_status", "by_binding_level",
                 "by_reentry_hint", "by_unbound_reason"):
        index = indexes.get(name)
        if index is None:
            continue
        if not isinstance(index, Mapping):
            raise RegistryIntegrityError("INDEX_NOT_A_MAP", name)
        for bucket, members in index.items():
            if not isinstance(members, (list, tuple)):
                raise RegistryIntegrityError("INDEX_BUCKET_NOT_A_LIST", f"{name}.{bucket}")
            for member in members:
                if member not in keys:
                    raise RegistryIntegrityError(
                        "INDEX_DANGLING_KEY", f"{name}.{bucket} -> {member!r}"
                    )


def load_registry(
    content_version: str,
    *,
    root: Optional[Path] = None,
    strict_counts: bool = True,
) -> ContentSupportRegistry:
    """Load one explicit content version's registry.

    There is no implicit "latest" resolution and no cross-version fallback: an
    unknown or absent version raises :class:`RegistryUnavailableError`.
    """
    if not isinstance(content_version, str) or not content_version:
        raise ContentUnavailableVersion(content_version)
    directory = content_support_dir(content_version, root)
    if not directory.is_dir():
        raise RegistryUnavailableError(f"no content support directory: {directory}")

    registry_payload = _read_json(directory / REGISTRY_FILENAME)
    contract_payload = _read_json(directory / CONTRACT_FILENAME)
    summary_payload = _read_json(directory / SUMMARY_FILENAME)
    master_payload = _read_json(directory / MASTER_FILENAME)

    if contract_payload.get("schema") != CONTRACT_SCHEMA:
        raise RegistryIntegrityError("UNEXPECTED_SCHEMA", "contract")
    if summary_payload.get("schema") != SUMMARY_SCHEMA:
        raise RegistryIntegrityError("UNEXPECTED_SCHEMA", "summary")
    if master_payload.get("schema") != MASTER_SCHEMA:
        raise RegistryIntegrityError("UNEXPECTED_SCHEMA", "master")

    records, population, indexes = _validate_registry_payload(
        registry_payload, content_version, strict_counts=strict_counts
    )

    ordered = tuple(sorted(records, key=lambda r: r.key.sort_key))
    by_key = {record.key.canonical: record for record in ordered}

    return ContentSupportRegistry(
        content_version=content_version,
        registry_path=directory / REGISTRY_FILENAME,
        contract=freeze_json(contract_payload),
        summary=freeze_json(summary_payload),
        master=freeze_json(master_payload),
        records=ordered,
        indexes=freeze_json(indexes),
        population=freeze_json(population),
        validation_summary=freeze_json(registry_payload.get("validation") or {}),
        _by_key=MappingProxyType(by_key),
    )


class ContentUnavailableVersion(RegistryUnavailableError):
    """Raised for a missing/blank content-version argument."""
