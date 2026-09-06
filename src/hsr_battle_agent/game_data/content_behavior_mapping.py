"""Auditable coverage mapping between static content and canonical behavior.

This module intentionally does *not* infer native IDs from close-version
TurnBasedGameData filenames.  It publishes the difference between an exact
4.4.54 static denominator and the much smaller captured behavior slice, while
retaining narrowly-scoped representation-transform candidates for inspection.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable, Mapping

from .nanoka_content import stable_hash


STATIC_FAMILIES: Mapping[str, str] = {
    "Avatar": "avatars",
    "Skill": "skills",
    "Trace": "traces",
    "Eidolon": "eidolons",
    "LightCone": "lightcones",
    "RelicSet": "relic_sets",
    "Monster": "monsters",
    "MonsterSkill": "monster_skills",
    "StageBuff": "stage_buffs",
}

OWNER_STATIC_FAMILY: Mapping[str, str] = {
    "Avatar": "Avatar",
    "LightCone": "LightCone",
    "RelicSet": "RelicSet",
    "Monster": "Monster",
    "StageBuff": "StageBuff",
}


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def normalized_token(value: str) -> str:
    """Normalize only for an explicitly non-native representation candidate."""
    return "".join(character.lower() for character in value if character.isalnum())


def character_tag_index(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    """Return normalized StarRailRes tags to deterministic avatar-ID candidates."""
    result: dict[str, list[str]] = defaultdict(list)
    for entity_id, value in payload.items():
        if not isinstance(value, Mapping):
            continue
        tag = value.get("tag")
        if isinstance(tag, str) and tag:
            result[normalized_token(tag)].append(str(entity_id))
    return {key: sorted(values) for key, values in sorted(result.items())}


def static_family_ids(database_path: Path, game_version: str) -> dict[str, list[str]]:
    """Read only ID-preserved static entity keys from the local SQLite database."""
    database = sqlite3.connect(database_path)
    try:
        return {
            family: [
                str(row[0])
                for row in database.execute(
                    f"SELECT entity_id FROM {table} WHERE game_version=? ORDER BY entity_id",
                    (game_version,),
                )
            ]
            for family, table in STATIC_FAMILIES.items()
        }
    finally:
        database.close()


def _operation_counts(entrypoints: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    total = 0
    executable = 0

    def visit(operations: Iterable[Mapping[str, Any]]) -> None:
        nonlocal total, executable
        for operation in operations:
            if not isinstance(operation, Mapping):
                continue
            total += 1
            executable += operation.get("disposition") == "EXECUTABLE_REFERENCE"
            for child in operation.get("children", []):
                if isinstance(child, Mapping):
                    visit(child.get("operations", []))

    for entrypoint in entrypoints:
        if isinstance(entrypoint, Mapping):
            visit(entrypoint.get("operations", []))
    return total, executable


def _entrypoint_counts(entrypoints: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    listed = [entrypoint for entrypoint in entrypoints if isinstance(entrypoint, Mapping)]
    return len(listed), sum(entrypoint.get("executable_reference") is True for entrypoint in listed)


def _avatar_candidate(
    owner_ref: str,
    *,
    tags: Mapping[str, list[str]],
    static_avatar_ids: set[str],
) -> tuple[str, list[str], str | None]:
    """Return a candidate only for the explicit ``Avatar_<tag>`` filename form."""
    owner = normalized_token(owner_ref)
    matches = [
        (tag, ids)
        for tag, ids in tags.items()
        if owner.startswith("avatar" + tag)
    ]
    if len(matches) != 1:
        return "UNMAPPED", [], None
    tag, external_ids = matches[0]
    local_ids = [entity_id for entity_id in external_ids if entity_id in static_avatar_ids]
    if len(local_ids) != 1:
        return "UNMAPPED", [], tag
    return "REPRESENTATION_TRANSFORM_CANDIDATE", local_ids, tag


def _exact_config_id_candidate(
    owner_ref: str,
    *,
    static_ids: set[str],
) -> list[str]:
    """Accept only an unambiguous numeric config token already in static IDs.

    Equipment source records use forms such as ``Ability20000`` and
    ``RelicAbility101``.  This is more precise than a filename/name match but
    deliberately remains a separate classification from a literal native ID.
    Numbers embedded in arbitrary text do not count unless exactly one token
    equals a known static entity ID.
    """
    values = re.findall(r"(?<!\d)(\d{3,})(?!\d)", owner_ref)
    candidates = sorted({value for value in values if value in static_ids})
    return candidates if len(candidates) == 1 else []


def _record_link(
    record: Mapping[str, Any],
    compiled: Mapping[str, Any] | None,
    *,
    tags: Mapping[str, list[str]],
    static_ids: Mapping[str, list[str]],
) -> dict[str, Any]:
    owner_kind = str(record.get("owner_kind", "UNKNOWN"))
    owner_ref = str(record.get("owner_ref", ""))
    linked_family = OWNER_STATIC_FAMILY.get(owner_kind)
    link_type = "OUT_OF_STATIC_FAMILY_SCOPE"
    candidate_ids: list[str] = []
    representation_tag: str | None = None
    if owner_kind == "Avatar":
        link_type, candidate_ids, representation_tag = _avatar_candidate(
            owner_ref,
            tags=tags,
            static_avatar_ids=set(static_ids["Avatar"]),
        )
    elif linked_family and owner_ref in set(static_ids[linked_family]):
        # This deliberately only accepts a literal ID equality.  Current
        # close-version owner refs do not satisfy it, but the rule is retained
        # for future exact-version sources.
        link_type = "EXACT_ID"
        candidate_ids = [owner_ref]
    elif linked_family:
        candidate_ids = _exact_config_id_candidate(
            owner_ref,
            static_ids=set(static_ids[linked_family]),
        )
        link_type = "EXACT_CONFIG_ID" if candidate_ids else "UNMAPPED"

    report_entrypoints = compiled.get("entrypoints", []) if compiled else []
    entrypoints, executable_entrypoints = _entrypoint_counts(report_entrypoints)
    operations, executable_operations = _operation_counts(report_entrypoints)
    source_refs = record.get("source_refs", [])
    first_source = source_refs[0] if source_refs and isinstance(source_refs[0], Mapping) else {}
    return {
        "behavior_id": record.get("behavior_id"),
        "owner_kind": owner_kind,
        "owner_ref": owner_ref,
        "behavior_bearing": bool(compiled.get("behavior_bearing")) if compiled else bool(record.get("entrypoints")),
        "compile_status": compiled.get("compile_status", "NOT_IN_COMPILER_REPORT") if compiled else "NOT_IN_COMPILER_REPORT",
        "whole_record_executable_reference": bool(compiled.get("executable")) if compiled else False,
        "entrypoint_counts": {"total": entrypoints, "executable_reference": executable_entrypoints},
        "operation_counts": {"total": operations, "executable_bound": executable_operations},
        "static_link": {
            "static_family": linked_family,
            "classification": link_type,
            "mapping_method": link_type,
            "candidate_entity_ids": candidate_ids,
            "representation_tag": representation_tag,
            "evidence": (
                "literal owner_ref equals an exact 4.4.54 entity_id"
                if link_type == "EXACT_ID"
                else "an unambiguous numeric config token in the source owner equals one exact 4.4.54 entity_id"
                if link_type == "EXACT_CONFIG_ID"
                else "normalized Avatar_<tag> owner filename matches cached StarRailRes character tag; not native-ID proof"
                if link_type == "REPRESENTATION_TRANSFORM_CANDIDATE"
                else "captured source path/owner only; no exact static-ID relation is asserted"
            ),
        },
        "source_ref": {
            key: first_source.get(key)
            for key in ("repository", "commit", "path", "raw_sha256", "version_relation")
        },
    }


def _named_source_counts(record_links: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counters: Counter[str] = Counter()
    for link in record_links:
        if link.get("owner_kind") != "Avatar":
            continue
        owner_ref = str(link.get("owner_ref", ""))
        if re.search(r"_Rank\d+", owner_ref):
            counters["Eidolon"] += 1
        elif "SkillTree" in owner_ref:
            counters["Trace"] += 1
        elif "Skill" in owner_ref:
            counters["Skill"] += 1
    return dict(counters)


def build_content_behavior_mapping(
    corpus: Mapping[str, Any],
    compiler_report: Mapping[str, Any],
    static_ids: Mapping[str, list[str]],
    character_tags: Mapping[str, list[str]],
    *,
    source_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build deterministic, intentionally conservative content/behavior coverage."""
    compiled_by_behavior = {
        str(record.get("behavior_id")): record
        for record in compiler_report.get("records", [])
        if isinstance(record, Mapping)
    }
    record_links = [
        _record_link(
            record,
            compiled_by_behavior.get(str(record.get("behavior_id"))),
            tags=character_tags,
            static_ids=static_ids,
        )
        for record in corpus.get("records", [])
        if isinstance(record, Mapping)
    ]
    record_links.sort(key=lambda row: str(row["behavior_id"]))
    named_counts = _named_source_counts(record_links)

    families: dict[str, dict[str, Any]] = {}
    for family, ids in STATIC_FAMILIES.items():
        links = [link for link in record_links if link["static_link"]["static_family"] == family]
        direct = [
            link for link in links
            if link["static_link"]["classification"] in {"EXACT_ID", "EXACT_CONFIG_ID"}
        ]
        transformed = [
            link for link in links
            if link["static_link"]["classification"] == "REPRESENTATION_TRANSFORM_CANDIDATE"
        ]
        source_only = [link for link in links if link["static_link"]["classification"] == "UNMAPPED"]
        directly_linked = {
            entity_id for link in direct for entity_id in link["static_link"]["candidate_entity_ids"]
        }
        transform_linked = {
            entity_id for link in transformed for entity_id in link["static_link"]["candidate_entity_ids"]
        }
        families[family] = {
            "static_entity_denominator": len(static_ids[family]),
            "static_entities_directly_linked": len(directly_linked),
            "static_entities_representation_transform_candidates": len(transform_linked),
            "static_entities_unmapped": len(set(static_ids[family]) - directly_linked - transform_linked),
            "behavior_records_direct_id_link": len(direct),
            "behavior_records_exact_config_id_link": sum(
                link["static_link"]["classification"] == "EXACT_CONFIG_ID" for link in links
            ),
            "behavior_records_representation_transform_candidate": len(transformed),
            "behavior_records_source_path_only": len(source_only),
            "behavior_records_captured_for_family": len(links),
            "behavior_bearing_records_captured_for_family": sum(link["behavior_bearing"] for link in links),
            "whole_record_executable_reference": sum(link["whole_record_executable_reference"] for link in links),
            "entrypoints_executable_reference": sum(
                link["entrypoint_counts"]["executable_reference"] for link in links
            ),
            "operation_executable_bound": sum(
                link["operation_counts"]["executable_bound"] for link in links
            ),
            "source_named_parent_only_records": named_counts.get(family, 0),
            "full_4_4_54_behavior_denominator": "UNKNOWN",
            "interpretation": (
                "The exact static entity denominator comes from local Nanoka 4.4.54 SQLite. "
                "No filename/name-only mapping is counted as a direct native-ID relation."
            ),
        }

    out_of_scope = Counter(
        str(link["owner_kind"])
        for link in record_links
        if link["static_link"]["static_family"] is None
    )
    payload = {
        "report_id": "FULL-CONTENT-BEHAVIOR-MAPPING-001",
        "game_version": str(corpus.get("game_version")),
        "status": "EXACT_STATIC_DENOMINATOR_WITH_PROVENANCE_AWARE_BEHAVIOR_LINKS",
        "counting_rule": (
            "Static denominators are ID-preserved local Nanoka 4.4.54 entities. "
            "EXACT_ID requires literal exact entity-id equality; EXACT_CONFIG_ID requires an unambiguous numeric config token equal to one static entity ID. "
            "REPRESENTATION_TRANSFORM_CANDIDATE is a cached StarRailRes tag/filename relation only, "
            "never native-ID proof. SOURCE_PATH_ONLY and parent-only names do not count as static links."
        ),
        "inputs": dict(sorted(source_metadata.items())),
        "link_classifications": {
            "EXACT_ID": "literal source owner reference equals an exact local 4.4.54 static entity ID",
            "EXACT_CONFIG_ID": "a tokenized numeric source config owner reference equals exactly one local 4.4.54 static entity ID",
            "STRUCTURED_MAPPING": "a separately recorded source relationship joins a behavior record to an exact local static entity",
            "REPRESENTATION_TRANSFORM_CANDIDATE": "normalized Avatar_<tag> filename matches a cached StarRailRes tag and one local Avatar ID; not native-ID proof",
            "UNMAPPED": "source path/name identifies a behavior family but has no exact static entity relation",
            "OUT_OF_STATIC_FAMILY_SCOPE": "captured global Modifier behavior has no corresponding requested static-content family",
            "PARENT_AVATAR_ONLY": "source name indicates Skill/Trace/Eidolon shape but does not identify its static entity ID",
        },
        "static_family_coverage": dict(sorted(families.items())),
        "captured_behavior_owner_summary": dict(sorted(Counter(link["owner_kind"] for link in record_links).items())),
        "family_coverage_table": [
            {
                "family": family,
                "static_total": details["static_entity_denominator"],
                "behavior_mapped": details["behavior_records_direct_id_link"] + details["behavior_records_representation_transform_candidate"],
                "canonicalized": details["behavior_records_captured_for_family"],
                "executable": details["whole_record_executable_reference"],
                "golden": 0,
                "unmapped": details["static_entities_unmapped"],
            }
            for family, details in sorted(families.items())
        ],
        "out_of_static_family_scope": dict(sorted(out_of_scope.items())),
        "record_links": record_links,
    }
    payload["report_sha256"] = stable_hash(payload)
    return payload
