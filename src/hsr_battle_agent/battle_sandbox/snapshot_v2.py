# -*- coding: utf-8 -*-
"""Complete lossless snapshot boundary for independent Terra state."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.evidence import EvidenceMode, parse_evidence_mode
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState

__all__ = [
    "TERRA_SNAPSHOT_SCHEMA",
    "SNAPSHOT_POLICY_IDENTITY_SCHEMA",
    "SnapshotPolicyIdentity",
    "SnapshotV2Error",
    "TerraSnapshotV2",
    "capture_snapshot_v2",
]

TERRA_SNAPSHOT_SCHEMA = "terra_snapshot/2"
SNAPSHOT_POLICY_IDENTITY_SCHEMA = "snapshot_policy_identity/1"
_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


class SnapshotV2Error(ValueError):
    """Raised for incomplete or malformed Terra snapshots."""


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise SnapshotV2Error(f"{label} must be a non-empty trimmed string")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise SnapshotV2Error(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class SnapshotPolicyIdentity:
    """Versioned evidence/profile/rule identity included in state identity.

    These fields identify the selected local contracts.  They do not assert
    executability, and a reference evidence mode remains reference evidence.
    Definitions needed by state restoration remain embedded in the state's
    immutable-input stores; this object is not a hash-only definition stub.
    """

    evidence_mode: EvidenceMode
    evidence_vocabulary_version: str
    profile_id: str
    profile_version: str
    profile_content_sha256: str
    rule_set_id: str
    rule_set_version: str
    rule_set_content_sha256: str

    def __post_init__(self) -> None:
        try:
            mode = parse_evidence_mode(self.evidence_mode)
        except (TypeError, ValueError) as exc:
            raise SnapshotV2Error(f"invalid evidence mode: {exc}") from exc
        object.__setattr__(self, "evidence_mode", mode)
        for name in (
            "evidence_vocabulary_version",
            "profile_id",
            "profile_version",
            "rule_set_id",
            "rule_set_version",
        ):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        for name in ("profile_content_sha256", "rule_set_content_sha256"):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SNAPSHOT_POLICY_IDENTITY_SCHEMA,
            "evidence_mode": self.evidence_mode.value,
            "evidence_vocabulary_version": self.evidence_vocabulary_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_content_sha256": self.profile_content_sha256,
            "rule_set_id": self.rule_set_id,
            "rule_set_version": self.rule_set_version,
            "rule_set_content_sha256": self.rule_set_content_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SnapshotPolicyIdentity":
        if not isinstance(data, Mapping):
            raise SnapshotV2Error("snapshot policy identity must be a mapping")
        expected = {
            "schema",
            "evidence_mode",
            "evidence_vocabulary_version",
            "profile_id",
            "profile_version",
            "profile_content_sha256",
            "rule_set_id",
            "rule_set_version",
            "rule_set_content_sha256",
        }
        if set(data) != expected:
            raise SnapshotV2Error(
                "snapshot policy identity must contain every identity/version field exactly"
            )
        if data["schema"] != SNAPSHOT_POLICY_IDENTITY_SCHEMA:
            raise SnapshotV2Error("unknown snapshot policy identity schema")
        return cls(
            evidence_mode=data["evidence_mode"],
            evidence_vocabulary_version=data["evidence_vocabulary_version"],
            profile_id=data["profile_id"],
            profile_version=data["profile_version"],
            profile_content_sha256=data["profile_content_sha256"],
            rule_set_id=data["rule_set_id"],
            rule_set_version=data["rule_set_version"],
            rule_set_content_sha256=data["rule_set_content_sha256"],
        )


class TerraSnapshotV2:
    """Immutable snapshot of complete Terra state plus selected policy identity."""

    __slots__ = ("_state", "_policy_identity")

    def __init__(
        self,
        *,
        state: TerraBattleState,
        policy_identity: SnapshotPolicyIdentity,
    ) -> None:
        if not isinstance(state, TerraBattleState):
            raise SnapshotV2Error("state must be a TerraBattleState")
        if not isinstance(policy_identity, SnapshotPolicyIdentity):
            raise SnapshotV2Error(
                "policy_identity must be a SnapshotPolicyIdentity"
            )
        self._state = state.clone()
        self._policy_identity = SnapshotPolicyIdentity.from_dict(
            policy_identity.to_dict()
        )

    @property
    def state(self) -> TerraBattleState:
        return self._state.clone()

    @property
    def policy_identity(self) -> SnapshotPolicyIdentity:
        return SnapshotPolicyIdentity.from_dict(self._policy_identity.to_dict())

    def restore_state(self) -> TerraBattleState:
        return self._state.clone()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TERRA_SNAPSHOT_SCHEMA,
            "state": self._state.to_dict(),
            "policy_identity": self._policy_identity.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerraSnapshotV2":
        if not isinstance(data, Mapping):
            raise SnapshotV2Error("Terra snapshot document must be a mapping")
        if set(data) != {"schema", "state", "policy_identity"}:
            raise SnapshotV2Error(
                "Terra snapshot must contain exactly schema, state and policy_identity; absent components are never defaulted"
            )
        if data["schema"] != TERRA_SNAPSHOT_SCHEMA:
            raise SnapshotV2Error(
                f"unknown Terra snapshot schema {data['schema']!r}"
            )
        try:
            return cls(
                state=TerraBattleState.from_dict(data["state"]),
                policy_identity=SnapshotPolicyIdentity.from_dict(
                    data["policy_identity"]
                ),
            )
        except SnapshotV2Error:
            raise
        except (TypeError, ValueError) as exc:
            raise SnapshotV2Error(f"invalid Terra snapshot: {exc}") from exc

    def clone(self) -> "TerraSnapshotV2":
        return type(self).from_dict(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TerraSnapshotV2):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"TerraSnapshotV2(profile={self._policy_identity.profile_id!r}, "
            f"rules={self._policy_identity.rule_set_id!r}, "
            f"mode={self._policy_identity.evidence_mode.value!r})"
        )


def capture_snapshot_v2(
    state: TerraBattleState,
    policy_identity: SnapshotPolicyIdentity,
) -> TerraSnapshotV2:
    return TerraSnapshotV2(state=state, policy_identity=policy_identity)
