# -*- coding: utf-8 -*-
"""Explicit, diagnostic-only migration reader for legacy snapshot v1.

Reading is not semantic conversion.  The result preserves the complete raw
payload and every ambiguity, and it never invents a Terra store, identity,
allocator, revision sequence, policy identity or RNG stream contract.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.errors import (
    StructuredRejection,
    StructuredRejectionError,
)
from hsr_battle_agent.battle_sandbox.legacy_state_adapter import (
    LegacyProjectionError,
    LegacyStateProjection,
    project_certified_legacy_subset,
)
from hsr_battle_agent.battle_sandbox.state import F01StateEnvelope

__all__ = [
    "MIGRATION_RESULT_SCHEMA",
    "MigrationError",
    "MigrationResult",
    "migrate_legacy_snapshot",
]

MIGRATION_RESULT_SCHEMA = "legacy_snapshot_migration_result/1"
_LEGACY_SNAPSHOT_SCHEMA = 1
_LEGACY_FIELDS = ("schema_version", "battle_state", "rng_state", "trace")


class MigrationError(ValueError):
    """Raised for malformed migration input or result documents."""


def _presence(document: Mapping[str, Any], key: str) -> dict[str, Any]:
    if key not in document:
        return {"presence": "ABSENT"}
    if document[key] is None:
        return {"presence": "NULL"}
    return {"presence": "PRESENT", "value": copy.deepcopy(document[key])}


def _blocker(
    blocker_id: str,
    field: str,
    payload: Mapping[str, Any],
    evidence: str,
) -> UnknownHandle:
    return UnknownHandle(
        blocker_id=blocker_id,
        owner_family="LEGACY_SNAPSHOT_MIGRATION",
        payload=copy.deepcopy(dict(payload)),
        provenance={
            "reader": "battle_sandbox.snapshot_migration",
            "legacy_field": field,
        },
        required_evidence=(evidence,),
    )


class MigrationResult:
    """Preserved legacy input plus explicit unresolved migration obligations."""

    __slots__ = (
        "_raw_legacy_payload",
        "_legacy_snapshot_schema",
        "_certified_state_projection",
        "_unresolved_fields",
    )

    def __init__(
        self,
        *,
        raw_legacy_payload: Mapping[str, Any],
        legacy_snapshot_schema: PresenceValue,
        certified_state_projection: LegacyStateProjection | None,
        unresolved_fields: tuple[UnknownHandle, ...],
    ) -> None:
        raw = F01StateEnvelope(dict(raw_legacy_payload)).value
        if not isinstance(raw, dict):
            raise MigrationError("raw legacy payload must be a mapping")
        if not isinstance(legacy_snapshot_schema, PresenceValue):
            raise MigrationError(
                "legacy_snapshot_schema must be an explicit PresenceValue"
            )
        projection = certified_state_projection
        if projection is not None and not isinstance(
            projection, LegacyStateProjection
        ):
            raise MigrationError(
                "certified_state_projection must be LegacyStateProjection or None"
            )
        if isinstance(unresolved_fields, (str, bytes)) or not isinstance(
            unresolved_fields, (tuple, list)
        ):
            raise MigrationError("unresolved_fields must be a sequence")
        if any(not isinstance(item, UnknownHandle) for item in unresolved_fields):
            raise MigrationError("unresolved fields must be UnknownHandle values")
        self._raw_legacy_payload = raw
        self._legacy_snapshot_schema = PresenceValue.from_dict(
            legacy_snapshot_schema.to_dict()
        )
        self._certified_state_projection = (
            None
            if projection is None
            else LegacyStateProjection.from_dict(projection.to_dict())
        )
        self._unresolved_fields = tuple(
            UnknownHandle.from_dict(item.to_dict()) for item in unresolved_fields
        )

    @property
    def raw_legacy_payload(self) -> dict[str, Any]:
        value = F01StateEnvelope(self._raw_legacy_payload).value
        assert isinstance(value, dict)
        return value

    @property
    def legacy_snapshot_schema(self) -> PresenceValue:
        return PresenceValue.from_dict(self._legacy_snapshot_schema.to_dict())

    @property
    def certified_state_projection(self) -> LegacyStateProjection | None:
        if self._certified_state_projection is None:
            return None
        return LegacyStateProjection.from_dict(
            self._certified_state_projection.to_dict()
        )

    @property
    def unresolved_fields(self) -> tuple[UnknownHandle, ...]:
        return tuple(
            UnknownHandle.from_dict(item.to_dict())
            for item in self._unresolved_fields
        )

    @property
    def status(self) -> str:
        return "BLOCKED_UNRESOLVED"

    def can_construct_terra_snapshot(self) -> bool:
        return False

    def claims_semantic_equality(self) -> bool:
        return False

    def require_terra_snapshot(self) -> NoReturn:
        rejection = StructuredRejection(
            reason_code="LEGACY_SNAPSHOT_MIGRATION_UNRESOLVED",
            obligation_owner="LEGACY_SNAPSHOT_MIGRATION",
            evidence_request=(
                "complete certified legacy-to-Terra store, identity, policy and RNG contracts"
            ),
            unknown_handles=self._unresolved_fields,
            diagnostics={"status": self.status},
        )
        raise StructuredRejectionError(rejection)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MIGRATION_RESULT_SCHEMA,
            "status": self.status,
            "raw_legacy_payload": F01StateEnvelope(
                self._raw_legacy_payload
            ).to_dict(),
            "legacy_snapshot_schema": self._legacy_snapshot_schema.to_dict(),
            "certified_state_projection": (
                None
                if self._certified_state_projection is None
                else self._certified_state_projection.to_dict()
            ),
            "unresolved_fields": [item.to_dict() for item in self._unresolved_fields],
            "terra_snapshot": None,
            "semantic_equality_claimed": False,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MigrationResult":
        if not isinstance(data, Mapping):
            raise MigrationError("migration result document must be a mapping")
        expected = {
            "schema",
            "status",
            "raw_legacy_payload",
            "legacy_snapshot_schema",
            "certified_state_projection",
            "unresolved_fields",
            "terra_snapshot",
            "semantic_equality_claimed",
        }
        if set(data) != expected:
            raise MigrationError(
                "migration result must contain every field exactly"
            )
        if data["schema"] != MIGRATION_RESULT_SCHEMA:
            raise MigrationError("unknown migration result schema")
        if data["status"] != "BLOCKED_UNRESOLVED":
            raise MigrationError("migration result must remain blocked unresolved")
        if data["terra_snapshot"] is not None:
            raise MigrationError(
                "migration result cannot contain an invented Terra snapshot"
            )
        if data["semantic_equality_claimed"] is not False:
            raise MigrationError("legacy/Terra semantic equality is forbidden")
        raw = F01StateEnvelope.from_dict(data["raw_legacy_payload"]).value
        if not isinstance(raw, Mapping):
            raise MigrationError("raw legacy payload must decode to a mapping")
        projection_data = data["certified_state_projection"]
        projection = (
            None
            if projection_data is None
            else LegacyStateProjection.from_dict(projection_data)
        )
        handles = data["unresolved_fields"]
        if isinstance(handles, (str, bytes)) or not isinstance(
            handles, (tuple, list)
        ):
            raise MigrationError("unresolved_fields must be a list")
        return cls(
            raw_legacy_payload=raw,
            legacy_snapshot_schema=PresenceValue.from_dict(
                data["legacy_snapshot_schema"]
            ),
            certified_state_projection=projection,
            unresolved_fields=tuple(UnknownHandle.from_dict(item) for item in handles),
        )


def migrate_legacy_snapshot(payload: Mapping[str, Any]) -> MigrationResult:
    """Read a legacy snapshot into a deterministic, blocked migration result."""
    if not isinstance(payload, Mapping):
        raise MigrationError("legacy snapshot payload must be a mapping")
    if "schema" in payload and payload["schema"] == "terra_snapshot/2":
        raise MigrationError(
            "Terra snapshot v2 is not legacy input; no v2-to-v1 downgrade exists"
        )
    raw = F01StateEnvelope(dict(payload)).value
    assert isinstance(raw, dict)
    blockers: list[UnknownHandle] = []

    if "schema_version" not in raw:
        schema_presence = PresenceValue.absent()
        blockers.append(
            _blocker(
                "LEGACY_SNAPSHOT_SCHEMA_ABSENT",
                "schema_version",
                {"presence": "ABSENT"},
                "explicit supported legacy snapshot schema version",
            )
        )
    elif raw["schema_version"] is None:
        schema_presence = PresenceValue.null()
        blockers.append(
            _blocker(
                "LEGACY_SNAPSHOT_SCHEMA_NULL",
                "schema_version",
                {"presence": "NULL"},
                "explicit supported legacy snapshot schema version",
            )
        )
    else:
        schema_presence = PresenceValue.present(raw["schema_version"])
        if (
            isinstance(raw["schema_version"], bool)
            or raw["schema_version"] != _LEGACY_SNAPSHOT_SCHEMA
        ):
            blockers.append(
                _blocker(
                    "LEGACY_SNAPSHOT_SCHEMA_UNSUPPORTED",
                    "schema_version",
                    _presence(raw, "schema_version"),
                    "reader support for this exact legacy snapshot schema",
                )
            )

    projection: LegacyStateProjection | None = None
    if "battle_state" not in raw or raw["battle_state"] is None:
        blockers.append(
            _blocker(
                "LEGACY_SNAPSHOT_BATTLE_STATE_AMBIGUOUS",
                "battle_state",
                _presence(raw, "battle_state"),
                "explicit legacy battle state and certified Terra mappings",
            )
        )
    elif not isinstance(raw["battle_state"], Mapping):
        blockers.append(
            _blocker(
                "LEGACY_SNAPSHOT_BATTLE_STATE_MALFORMED",
                "battle_state",
                _presence(raw, "battle_state"),
                "well-formed legacy battle state mapping",
            )
        )
    else:
        try:
            projection = project_certified_legacy_subset(raw["battle_state"])
        except LegacyProjectionError as exc:
            blockers.append(
                _blocker(
                    "LEGACY_SNAPSHOT_BATTLE_STATE_UNSUPPORTED",
                    "battle_state",
                    {
                        "presence": "PRESENT",
                        "value": copy.deepcopy(raw["battle_state"]),
                        "diagnostic": str(exc),
                    },
                    "supported legacy BattleState schema and certified Terra mappings",
                )
            )
        else:
            blockers.extend(projection.unresolved_fields)

    for field in ("rng_state", "trace"):
        blockers.append(
            _blocker(
                f"LEGACY_SNAPSHOT_FIELD_UNCERTIFIED_{field.upper()}",
                field,
                _presence(raw, field),
                f"certified legacy {field} to Terra snapshot contract",
            )
        )

    for field in sorted(set(raw) - set(_LEGACY_FIELDS)):
        blockers.append(
            _blocker(
                f"LEGACY_SNAPSHOT_UNKNOWN_FIELD_{field.upper()}",
                field,
                _presence(raw, field),
                "version-qualified interpretation of the unknown legacy field",
            )
        )

    return MigrationResult(
        raw_legacy_payload=raw,
        legacy_snapshot_schema=schema_presence,
        certified_state_projection=projection,
        unresolved_fields=tuple(blockers),
    )
