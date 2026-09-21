# -*- coding: utf-8 -*-
"""One-way, fail-closed inspection of quarantined legacy state.

F02-009 deliberately does not convert legacy ``BattleState`` stores into
Terra stores.  The freeze certifies no such field-to-field correspondence.
This adapter copies only the legacy schema marker as a certified structural
fact and carries every payload-bearing (or absent) field as an unresolved
handle.  It is a compatibility diagnostic, never a live facade.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import UnknownHandle
from hsr_battle_agent.battle_sandbox.errors import (
    StructuredRejection,
    StructuredRejectionError,
)
from hsr_battle_agent.battle_sandbox.state import (
    BATTLE_STATE_SCHEMA_VERSION,
    BattleState,
    F01StateEnvelope,
)

__all__ = [
    "CERTIFIED_LEGACY_FIELDS",
    "LEGACY_PAYLOAD_FIELDS",
    "LEGACY_STATE_PROJECTION_SCHEMA",
    "LegacyProjectionError",
    "LegacyStateProjection",
    "project_certified_legacy_subset",
]

LEGACY_STATE_PROJECTION_SCHEMA = "legacy_state_projection/1"
CERTIFIED_LEGACY_FIELDS = ("schema_version",)
LEGACY_PAYLOAD_FIELDS = (
    "extensions",
    "modifier_state_by_entity",
    "entity_property_entries",
    "modifier_property_contributions",
    "component_lock_hp_records",
    "turn_timeline",
)
_SUPPORTED_LEGACY_SCHEMAS = (1, 2, 3, BATTLE_STATE_SCHEMA_VERSION)


class LegacyProjectionError(ValueError):
    """Raised when a caller requests an uncertified legacy projection."""


def _raw_document(source: BattleState | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, BattleState):
        return copy.deepcopy(source.to_dict())
    if not isinstance(source, Mapping):
        raise LegacyProjectionError(
            "legacy projection requires BattleState or a raw mapping"
        )
    for key in source:
        if not isinstance(key, str):
            raise LegacyProjectionError("legacy state keys must be strings")
    # The F01 carrier validates/copies the full lossless value model without
    # invoking BattleState.from_dict(), whose historical defaults are exactly
    # what this boundary must not apply.
    copied = F01StateEnvelope(dict(source)).value
    assert isinstance(copied, dict)
    return copied


def _unresolved_field(document: Mapping[str, Any], field: str) -> UnknownHandle:
    if field in document:
        payload = {"presence": "PRESENT", "value": copy.deepcopy(document[field])}
    else:
        payload = {"presence": "ABSENT"}
    return UnknownHandle(
        blocker_id=f"LEGACY_STATE_FIELD_UNCERTIFIED_{field.upper()}",
        owner_family="BATTLE_STATE_MIGRATION",
        payload=payload,
        provenance={
            "adapter": "battle_sandbox.legacy_state_adapter",
            "source_schema_version": document["schema_version"],
            "legacy_field": field,
        },
        required_evidence=(
            "certified one-way legacy-field to Terra-store projection contract",
        ),
    )


class LegacyStateProjection:
    """Immutable compatibility diagnostic; never authoritative Terra state."""

    __slots__ = (
        "_source_schema_version",
        "_certified_subset",
        "_unresolved_fields",
    )

    def __init__(
        self,
        *,
        source_schema_version: int,
        certified_subset: Mapping[str, Any],
        unresolved_fields: tuple[UnknownHandle, ...],
    ) -> None:
        if source_schema_version not in _SUPPORTED_LEGACY_SCHEMAS:
            raise LegacyProjectionError(
                f"unsupported legacy schema {source_schema_version!r}"
            )
        subset = F01StateEnvelope(dict(certified_subset)).value
        if not isinstance(subset, dict) or set(subset) != {"schema_version"}:
            raise LegacyProjectionError(
                "certified subset must contain only the legacy schema marker"
            )
        if subset["schema_version"] != source_schema_version:
            raise LegacyProjectionError(
                "certified schema marker does not match source schema"
            )
        if isinstance(unresolved_fields, (str, bytes)) or not isinstance(
            unresolved_fields, (tuple, list)
        ):
            raise LegacyProjectionError("unresolved_fields must be a sequence")
        if any(not isinstance(item, UnknownHandle) for item in unresolved_fields):
            raise LegacyProjectionError(
                "unresolved_fields entries must be UnknownHandle instances"
            )
        self._source_schema_version = source_schema_version
        self._certified_subset = subset
        self._unresolved_fields = tuple(
            UnknownHandle.from_dict(item.to_dict()) for item in unresolved_fields
        )

    @property
    def source_schema_version(self) -> int:
        return self._source_schema_version

    @property
    def certified_subset(self) -> dict[str, Any]:
        value = F01StateEnvelope(self._certified_subset).value
        assert isinstance(value, dict)
        return value

    @property
    def unresolved_fields(self) -> tuple[UnknownHandle, ...]:
        return tuple(
            UnknownHandle.from_dict(item.to_dict())
            for item in self._unresolved_fields
        )

    @property
    def boundary_kind(self) -> str:
        return "LEGACY_CERTIFIED_SUBSET_ONLY"

    def can_construct_terra_state(self) -> bool:
        return False

    def require_complete(self) -> NoReturn:
        rejection = StructuredRejection(
            reason_code="LEGACY_STATE_PROJECTION_UNRESOLVED",
            obligation_owner="BATTLE_STATE_MIGRATION",
            evidence_request=(
                "certified mappings for every legacy field before Terra state construction"
            ),
            unknown_handles=self._unresolved_fields,
            diagnostics={
                "boundary_kind": self.boundary_kind,
                "unresolved_count": len(self._unresolved_fields),
            },
        )
        raise StructuredRejectionError(rejection)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LEGACY_STATE_PROJECTION_SCHEMA,
            "boundary_kind": self.boundary_kind,
            "source_schema_version": self._source_schema_version,
            "certified_subset": F01StateEnvelope(self._certified_subset).to_dict(),
            "unresolved_fields": [item.to_dict() for item in self._unresolved_fields],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LegacyStateProjection":
        if not isinstance(data, Mapping):
            raise LegacyProjectionError("projection document must be a mapping")
        expected = {
            "schema",
            "boundary_kind",
            "source_schema_version",
            "certified_subset",
            "unresolved_fields",
        }
        if set(data) != expected:
            raise LegacyProjectionError(
                "projection document is missing fields or has unknown fields"
            )
        if data["schema"] != LEGACY_STATE_PROJECTION_SCHEMA:
            raise LegacyProjectionError("unknown legacy projection schema")
        if data["boundary_kind"] != "LEGACY_CERTIFIED_SUBSET_ONLY":
            raise LegacyProjectionError("unknown legacy projection boundary kind")
        raw_handles = data["unresolved_fields"]
        if isinstance(raw_handles, (str, bytes)) or not isinstance(
            raw_handles, (tuple, list)
        ):
            raise LegacyProjectionError("unresolved_fields must be a list")
        subset = F01StateEnvelope.from_dict(data["certified_subset"]).value
        if not isinstance(subset, Mapping):
            raise LegacyProjectionError("certified subset must decode to a mapping")
        return cls(
            source_schema_version=data["source_schema_version"],
            certified_subset=subset,
            unresolved_fields=tuple(
                UnknownHandle.from_dict(item) for item in raw_handles
            ),
        )


def project_certified_legacy_subset(
    source: BattleState | Mapping[str, Any],
    *,
    fields: tuple[str, ...] = CERTIFIED_LEGACY_FIELDS,
) -> LegacyStateProjection:
    """Copy only explicitly certified structural facts from legacy state.

    The projection never returns ``TerraBattleState`` and never maps a legacy
    JSON store onto a Terra owner.  Unsupported requested fields reject before
    a result is constructed.
    """
    if isinstance(fields, str) or not isinstance(fields, (tuple, list)):
        raise LegacyProjectionError("fields must be a tuple or list")
    if tuple(fields) != CERTIFIED_LEGACY_FIELDS:
        unsupported = tuple(field for field in fields if field not in CERTIFIED_LEGACY_FIELDS)
        raise LegacyProjectionError(
            f"uncertified legacy projection fields requested: {unsupported!r}"
        )
    document = _raw_document(source)
    if "schema_version" not in document:
        raise LegacyProjectionError(
            "legacy schema_version is absent; this boundary never defaults it"
        )
    schema_version = document["schema_version"]
    if isinstance(schema_version, bool) or schema_version not in _SUPPORTED_LEGACY_SCHEMAS:
        raise LegacyProjectionError(
            f"unsupported legacy schema {schema_version!r}"
        )
    unresolved_names = list(LEGACY_PAYLOAD_FIELDS)
    unresolved_names.extend(
        sorted(
            key
            for key in document
            if key not in {"schema_version", *LEGACY_PAYLOAD_FIELDS}
        )
    )
    return LegacyStateProjection(
        source_schema_version=schema_version,
        certified_subset={"schema_version": schema_version},
        unresolved_fields=tuple(
            _unresolved_field(document, field) for field in unresolved_names
        ),
    )
