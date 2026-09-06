"""Canonical Modifier definition catalog for executable-reference lowering.

Definitions come from structural keys inside ``GlobalModifiers``,
``ModifierMap``, or an Ability's embedded ``Modifiers`` map. Filenames and
display names are never used as identity authority. Equivalent repetitions
are deterministically deduplicated with every provenance retained; conflicting
payloads are excluded rather than silently selecting one.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping


SUPPORTED_STACKING_NAMES = frozenset({"ReplaceByCaster", "Replace", "Merge", "Multiple"})


@dataclass(frozen=True)
class ModifierDefinition:
    name: str
    stacking: str
    source_behavior_id: str
    life_step_moment: str | None = None
    source_lifetime: Mapping[str, Any] | None = None
    source_count: Mapping[str, Any] | None = None
    definition_sha256: str | None = None
    source_behavior_ids: tuple[str, ...] = ()
    source_provenance: tuple[Mapping[str, Any], ...] = ()

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "stacking": self.stacking,
            "source_behavior_id": self.source_behavior_id,
            "source_behavior_ids": list(self.source_behavior_ids or (self.source_behavior_id,)),
            "source_provenance": list(self.source_provenance),
            "life_step_moment": self.life_step_moment,
            "source_lifetime": self.source_lifetime,
            "source_count": self.source_count,
            "definition_sha256": self.definition_sha256,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _source_refs(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(value) for value in record.get("source_refs", []) if isinstance(value, Mapping)]


def _definition_candidates(corpus: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for record in corpus.get("records", []):
        if not isinstance(record, Mapping):
            continue
        behavior_id = str(record.get("behavior_id") or "")
        owner_kind = str(record.get("owner_kind") or "UNKNOWN")
        owner_ref = str(record.get("owner_ref") or "")
        refs = _source_refs(record)
        if owner_kind == "Modifier" and owner_ref:
            payload = record.get("modifier_definition_payload")
            if not isinstance(payload, Mapping):
                payload = record.get("raw_unknown")
            if isinstance(payload, Mapping):
                container = refs[0].get("source_container") if refs else None
                yield {
                    "name": owner_ref,
                    "payload": dict(payload),
                    "semantic_sha256": _payload_sha256(payload),
                    "provenance": {
                        "source_behavior_id": behavior_id,
                        "source_owner_kind": owner_kind,
                        "source_owner_ref": owner_ref,
                        "source_field_path": f"{container}.{owner_ref}" if container else owner_ref,
                        "identity_method": "STRUCTURED_MODIFIER_CONTAINER_KEY",
                        "source_refs": refs,
                    },
                }
        for nested in record.get("modifier_definitions", []):
            if not isinstance(nested, Mapping):
                continue
            name = str(nested.get("name") or "")
            payload = nested.get("payload")
            if not name or not isinstance(payload, Mapping):
                continue
            yield {
                "name": name,
                "payload": dict(payload),
                "semantic_sha256": _payload_sha256(payload),
                "provenance": {
                    "source_behavior_id": behavior_id,
                    "source_owner_kind": owner_kind,
                    "source_owner_ref": owner_ref,
                    "source_field_path": str(nested.get("source_field_path") or f"Modifiers.{name}"),
                    "identity_method": "STRUCTURED_ABILITY_MODIFIERS_KEY",
                    "source_refs": refs,
                },
            }


def _catalog_and_report(corpus: Mapping[str, Any]) -> tuple[dict[str, ModifierDefinition], dict[str, Any]]:
    candidates = list(_definition_candidates(corpus))
    by_name: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for candidate in candidates:
        by_name[str(candidate["name"])][str(candidate["semantic_sha256"])].append(candidate)

    catalog: dict[str, ModifierDefinition] = {}
    conflicts: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    equivalent_duplicate_count = 0
    stacking_counts: Counter[str] = Counter()
    for name in sorted(by_name):
        variants = by_name[name]
        equivalent_duplicate_count += sum(max(0, len(items) - 1) for items in variants.values())
        if len(variants) != 1:
            conflicts.append({
                "name": name,
                "variant_count": len(variants),
                "variants": [
                    {
                        "semantic_sha256": semantic_sha256,
                        "candidate_count": len(items),
                        "stacking": items[0]["payload"].get("Stacking"),
                        "source_provenance": sorted(
                            (item["provenance"] for item in items), key=_canonical_json
                        ),
                    }
                    for semantic_sha256, items in sorted(variants.items())
                ],
            })
            continue
        semantic_sha256, items = next(iter(variants.items()))
        payload = items[0]["payload"]
        stacking = payload.get("Stacking")
        stacking_counts[str(stacking) if stacking is not None else "MISSING"] += 1
        provenances = tuple(sorted((item["provenance"] for item in items), key=_canonical_json))
        source_behavior_ids = tuple(sorted({str(value["source_behavior_id"]) for value in provenances}))
        if not isinstance(stacking, str) or stacking not in SUPPORTED_STACKING_NAMES:
            unsupported.append({
                "name": name,
                "semantic_sha256": semantic_sha256,
                "stacking": stacking,
                "candidate_count": len(items),
                "source_behavior_ids": list(source_behavior_ids),
            })
            continue
        catalog[name] = ModifierDefinition(
            name=name,
            stacking=stacking,
            source_behavior_id=source_behavior_ids[0],
            life_step_moment=str(payload["LifeStepMoment"]) if payload.get("LifeStepMoment") is not None else None,
            source_lifetime=payload.get("LifeTime") if isinstance(payload.get("LifeTime"), Mapping) else None,
            source_count=payload.get("Count") if isinstance(payload.get("Count"), Mapping) else None,
            definition_sha256=semantic_sha256,
            source_behavior_ids=source_behavior_ids,
            source_provenance=provenances,
        )

    report = {
        "schema": "hsr_battle_agent.modifier_definition_catalog/1",
        "identity_policy": "STRUCTURED_MODIFIER_MAP_KEY_ONLY",
        "duplicate_policy": "FULL_SOURCE_PAYLOAD_EQUALITY_WITH_ALL_PROVENANCE_RETAINED",
        "conflict_policy": "EXCLUDE_ALL_NON_EQUIVALENT_SAME_NAME_VARIANTS",
        "definition_candidate_count": len(candidates),
        "unique_definition_name_count": len(by_name),
        "equivalent_duplicate_count": equivalent_duplicate_count,
        "true_conflict_count": len(conflicts),
        "supported_catalog_definition_count": len(catalog),
        "unsupported_definition_count": len(unsupported),
        "definitions_by_stacking": dict(sorted(stacking_counts.items())),
        "definitions": [definition.as_json() for definition in catalog.values()],
        "unsupported_definitions": unsupported,
        "conflict_clusters": conflicts,
    }
    report["catalog_sha256"] = sha256(_canonical_json(report).encode("utf-8")).hexdigest()
    return dict(sorted(catalog.items())), report


def modifier_catalog_from_corpus(corpus: Mapping[str, Any]) -> dict[str, ModifierDefinition]:
    """Return only conflict-free definitions with an implemented stacking policy."""
    catalog, _ = _catalog_and_report(corpus)
    return catalog


def modifier_catalog_report_from_corpus(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Return auditable definition, duplicate, provenance, and conflict counts."""
    _, report = _catalog_and_report(corpus)
    return report
