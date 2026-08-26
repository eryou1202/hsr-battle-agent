"""Canonical Modifier definition catalog for executable-reference lowering.

The catalog is derived only from already canonicalized BehaviorRecords.  It
does not invent a stacking policy when the reviewed source record did not
preserve one; callers must keep those AddModifier operations structural.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SUPPORTED_STACKING_NAMES = frozenset({"ReplaceByCaster", "Replace", "Merge", "Multiple"})


@dataclass(frozen=True)
class ModifierDefinition:
    name: str
    stacking: str
    source_behavior_id: str
    life_step_moment: str | None = None
    source_lifetime: Mapping[str, Any] | None = None
    source_count: Mapping[str, Any] | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "stacking": self.stacking,
            "source_behavior_id": self.source_behavior_id,
            "life_step_moment": self.life_step_moment,
            "source_lifetime": self.source_lifetime,
            "source_count": self.source_count,
        }


def modifier_catalog_from_corpus(corpus: Mapping[str, Any]) -> dict[str, ModifierDefinition]:
    """Return only definitions with an explicitly supported source Stacking.

    Multiple reviewed behavior records may define the same Modifier name.  A
    conflicting definition is deliberately omitted rather than arbitrarily
    picking one representation.
    """
    candidates: dict[str, ModifierDefinition] = {}
    conflicts: set[str] = set()
    for record in corpus.get("records", []):
        if not isinstance(record, Mapping) or record.get("owner_kind") != "Modifier":
            continue
        name = str(record.get("owner_ref") or "")
        raw_unknown = record.get("raw_unknown")
        if not name or not isinstance(raw_unknown, Mapping):
            continue
        stacking = raw_unknown.get("Stacking")
        if not isinstance(stacking, str) or stacking not in SUPPORTED_STACKING_NAMES:
            continue
        definition = ModifierDefinition(
            name=name,
            stacking=stacking,
            source_behavior_id=str(record.get("behavior_id") or ""),
            life_step_moment=str(raw_unknown["LifeStepMoment"]) if raw_unknown.get("LifeStepMoment") is not None else None,
            source_lifetime=raw_unknown.get("LifeTime") if isinstance(raw_unknown.get("LifeTime"), Mapping) else None,
            source_count=raw_unknown.get("Count") if isinstance(raw_unknown.get("Count"), Mapping) else None,
        )
        existing = candidates.get(name)
        if existing is None:
            candidates[name] = definition
        elif existing != definition:
            conflicts.add(name)
    for name in conflicts:
        candidates.pop(name, None)
    return dict(sorted(candidates.items()))
