# -*- coding: utf-8 -*-
"""Representation-only descriptor base with explicit occurrence identity.

A descriptor binds a contract, evidence classification and provenance to one
source occurrence. It grants no execution capability and is not a gate
certificate or native contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    ContractRef,
    EvidenceMode,
    EvidenceVocabularyError,
    parse_evidence_mode,
)
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue, PresenceValueError
from hsr_battle_agent.battle_ir.provenance import (
    SourceProvenance,
    SourceProvenanceError,
)

__all__ = [
    "DESCRIPTOR_BATCH_SCHEMA",
    "DESCRIPTOR_OCCURRENCE_SCHEMA",
    "DescriptorBatch",
    "DescriptorError",
    "DescriptorOccurrence",
]

DESCRIPTOR_OCCURRENCE_SCHEMA = "descriptor_occurrence/1"
DESCRIPTOR_BATCH_SCHEMA = "descriptor_batch/1"


class DescriptorError(ValueError):
    """Raised for a lossy or inconsistent descriptor representation."""


def _normalize_path(value: Any) -> tuple[str | int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise DescriptorError("occurrence_path must be a tuple or list")
    path: list[str | int] = []
    for segment in value:
        if isinstance(segment, bool) or not isinstance(segment, (str, int)):
            raise DescriptorError(
                "occurrence_path segments must be strings or non-negative ints"
            )
        if isinstance(segment, str) and not segment:
            raise DescriptorError("occurrence_path string segments must be non-empty")
        if isinstance(segment, int) and segment < 0:
            raise DescriptorError("occurrence_path integer segments must be >= 0")
        path.append(segment)
    if not path:
        raise DescriptorError("occurrence_path must identify at least one segment")
    return tuple(path)


def _normalize_presence_mapping(
    value: Mapping[str, PresenceValue], label: str
) -> dict[str, PresenceValue]:
    if not isinstance(value, Mapping):
        raise DescriptorError(f"{label} must be a mapping")
    normalized: dict[str, PresenceValue] = {}
    for name, presence in value.items():
        if not isinstance(name, str) or not name:
            raise DescriptorError(f"{label} names must be non-empty strings")
        if not isinstance(presence, PresenceValue):
            raise DescriptorError(
                f"{label}[{name!r}] must be a PresenceValue; presence may not "
                "be inferred or defaulted"
            )
        normalized[name] = PresenceValue.from_dict(presence.to_dict())
    return normalized


def _presence_items_to_dict(
    values: Mapping[str, PresenceValue]
) -> list[dict[str, Any]]:
    return [
        {"name": name, "value": presence.to_dict()}
        for name, presence in values.items()
    ]


def _presence_items_from_dict(value: Any, label: str) -> dict[str, PresenceValue]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise DescriptorError(f"{label} must be a list")
    restored: dict[str, PresenceValue] = {}
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"name", "value"}:
            raise DescriptorError(f"{label} items must contain exactly name and value")
        name = item["name"]
        if not isinstance(name, str) or not name:
            raise DescriptorError(f"{label} names must be non-empty strings")
        if name in restored:
            raise DescriptorError(f"duplicate {label} name {name!r}")
        try:
            restored[name] = PresenceValue.from_dict(item["value"])
        except PresenceValueError as exc:
            raise DescriptorError(f"invalid {label} value: {exc}") from exc
    return restored


@dataclass(frozen=True, eq=False)
class DescriptorOccurrence:
    """One lossless occurrence of a representation-only descriptor."""

    contract_ref: ContractRef
    evidence_mode: EvidenceMode
    provenance: SourceProvenance
    occurrence_path: tuple[str | int, ...]
    source_order: int
    payload: PresenceValue = field(default_factory=PresenceValue.absent)
    fields: Mapping[str, PresenceValue] = field(default_factory=dict)
    unknown_fields: Mapping[str, PresenceValue] = field(default_factory=dict)

    # Equality is the complete serialized representation; occurrence identity
    # is exposed separately.  The object is intentionally unhashable because
    # nested lossless payloads may contain mappings/lists and an object-identity
    # hash would contradict representation equality.
    __hash__ = None

    def __post_init__(self) -> None:
        if not isinstance(self.contract_ref, ContractRef):
            raise DescriptorError("contract_ref must be a ContractRef")
        try:
            mode = parse_evidence_mode(self.evidence_mode)
        except EvidenceVocabularyError as exc:
            raise DescriptorError(str(exc)) from exc
        if mode is not self.contract_ref.evidence_mode:
            raise DescriptorError(
                "descriptor EvidenceMode must be the exact mode carried by its "
                "ContractRef"
            )
        if not isinstance(self.provenance, SourceProvenance):
            raise DescriptorError("provenance must be a SourceProvenance")
        if isinstance(self.source_order, bool) or not isinstance(self.source_order, int):
            raise DescriptorError("source_order must be an int")
        if self.source_order < 0:
            raise DescriptorError("source_order must be >= 0")
        if not isinstance(self.payload, PresenceValue):
            raise DescriptorError(
                "payload must be a PresenceValue; absence and null may not be inferred"
            )
        object.__setattr__(self, "evidence_mode", mode)
        object.__setattr__(self, "occurrence_path", _normalize_path(self.occurrence_path))
        object.__setattr__(self, "payload", PresenceValue.from_dict(self.payload.to_dict()))
        normalized_fields = _normalize_presence_mapping(self.fields, "fields")
        normalized_unknown = _normalize_presence_mapping(
            self.unknown_fields, "unknown_fields"
        )
        overlap = set(normalized_fields) & set(normalized_unknown)
        if overlap:
            raise DescriptorError(
                f"known and unknown descriptor fields overlap: {tuple(sorted(overlap))}"
            )
        object.__setattr__(self, "fields", MappingProxyType(normalized_fields))
        object.__setattr__(self, "unknown_fields", MappingProxyType(normalized_unknown))

    def occurrence_identity(self) -> tuple[Any, ...]:
        """Identity of the source occurrence, independent of payload equality."""
        return (
            self.contract_ref.namespace,
            self.contract_ref.contract_id,
            self.contract_ref.schema_version,
            self.occurrence_path,
            self.source_order,
        )

    def execution_permitted(self) -> NoReturn:
        raise DescriptorError(
            "a descriptor is representation only and cannot permit execution"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DESCRIPTOR_OCCURRENCE_SCHEMA,
            "contract_ref": self.contract_ref.to_dict(),
            "evidence_mode": self.evidence_mode.serialize(),
            "provenance": self.provenance.to_dict(),
            "occurrence_path": list(self.occurrence_path),
            "source_order": self.source_order,
            "payload": self.payload.to_dict(),
            "fields": _presence_items_to_dict(self.fields),
            "unknown_fields": _presence_items_to_dict(self.unknown_fields),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DescriptorOccurrence":
        if not isinstance(data, Mapping):
            raise DescriptorError("descriptor document must be a mapping")
        required = {
            "schema", "contract_ref", "evidence_mode", "provenance",
            "occurrence_path", "source_order", "payload", "fields",
            "unknown_fields",
        }
        if set(data) != required:
            raise DescriptorError(
                "descriptor document must contain exactly the declared schema fields"
            )
        if data["schema"] != DESCRIPTOR_OCCURRENCE_SCHEMA:
            raise DescriptorError(f"unknown descriptor schema {data['schema']!r}")
        try:
            return cls(
                contract_ref=ContractRef.from_dict(data["contract_ref"]),
                evidence_mode=parse_evidence_mode(data["evidence_mode"]),
                provenance=SourceProvenance.from_dict(data["provenance"]),
                occurrence_path=_normalize_path(data["occurrence_path"]),
                source_order=data["source_order"],
                payload=PresenceValue.from_dict(data["payload"]),
                fields=_presence_items_from_dict(data["fields"], "fields"),
                unknown_fields=_presence_items_from_dict(
                    data["unknown_fields"], "unknown_fields"
                ),
            )
        except DescriptorError:
            raise
        except (EvidenceVocabularyError, PresenceValueError, SourceProvenanceError) as exc:
            raise DescriptorError(f"invalid descriptor document: {exc}") from exc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DescriptorOccurrence):
            return NotImplemented
        return self.to_dict() == other.to_dict()


@dataclass(frozen=True, eq=False)
class DescriptorBatch:
    """Ordered occurrences; equal payloads are never deduplicated."""

    occurrences: tuple[DescriptorOccurrence, ...]

    __hash__ = None

    def __post_init__(self) -> None:
        if isinstance(self.occurrences, (str, bytes)) or not isinstance(
            self.occurrences, (tuple, list)
        ):
            raise DescriptorError("occurrences must be a tuple or list")
        normalized = tuple(self.occurrences)
        if any(not isinstance(item, DescriptorOccurrence) for item in normalized):
            raise DescriptorError("all batch items must be DescriptorOccurrence values")
        identities = [item.occurrence_identity() for item in normalized]
        if len(set(identities)) != len(identities):
            raise DescriptorError(
                "two descriptors claim the same source occurrence identity"
            )
        object.__setattr__(self, "occurrences", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DESCRIPTOR_BATCH_SCHEMA,
            "occurrences": [item.to_dict() for item in self.occurrences],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DescriptorBatch":
        if not isinstance(data, Mapping) or set(data) != {"schema", "occurrences"}:
            raise DescriptorError(
                "descriptor batch must contain exactly schema and occurrences"
            )
        if data["schema"] != DESCRIPTOR_BATCH_SCHEMA:
            raise DescriptorError(f"unknown descriptor batch schema {data['schema']!r}")
        raw = data["occurrences"]
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
            raise DescriptorError("descriptor batch occurrences must be a list")
        return cls(tuple(DescriptorOccurrence.from_dict(item) for item in raw))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DescriptorBatch):
            return NotImplemented
        return self.to_dict() == other.to_dict()
