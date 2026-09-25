# -*- coding: utf-8 -*-
"""Independent-oracle metadata registry and Golden promotion gate.

The gate is deliberately stricter than deterministic replay.  Reference,
custom, same-code-path and executor-generated expectations cannot qualify as
native Golden oracles.  It validates required metadata and declared source
classification; it does not authenticate the truthfulness of caller-supplied
provenance.  External authority review remains required before registration.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes

__all__ = [
    "OracleAssessment", "OracleError", "OracleExpectation", "OracleKind",
    "OracleRegistry", "OracleValidation", "OracleValidationStatus",
]

_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")


class OracleError(ValueError):
    pass


class OracleKind(Enum):
    INDEPENDENT_NATIVE = "INDEPENDENT_NATIVE"
    EXECUTOR_GENERATED = "EXECUTOR_GENERATED"
    SAME_CODE_PATH = "SAME_CODE_PATH"
    REFERENCE_MODEL = "REFERENCE_MODEL"
    SANDBOX_EXTENSION = "SANDBOX_EXTENSION"


class OracleAssessment(Enum):
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"


class OracleValidationStatus(Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OracleError(f"{label} must be a non-empty trimmed string")
    return value


@dataclass(frozen=True)
class OracleExpectation:
    oracle_id: str
    game_version: str
    expectation_identity: str
    source_identity: str
    source_sha256: str
    independent_provenance: tuple[str, ...]
    expected_payload_sha256: str
    kind: OracleKind
    evidence_mode: EvidenceMode

    def __post_init__(self) -> None:
        for name in ("oracle_id", "game_version", "expectation_identity", "source_identity"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        for name in ("source_sha256", "expected_payload_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise OracleError(f"{name} must be a lowercase SHA-256 digest")
        provenance = tuple(self.independent_provenance)
        if any(not isinstance(item, str) or not item.strip() for item in provenance):
            raise OracleError("independent_provenance entries must be non-empty strings")
        object.__setattr__(self, "independent_provenance", provenance)
        if not isinstance(self.kind, OracleKind) or not isinstance(self.evidence_mode, EvidenceMode):
            raise OracleError("kind and evidence_mode must use canonical vocabularies")

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "game_version": self.game_version,
            "expectation_identity": self.expectation_identity,
            "source_identity": self.source_identity,
            "source_sha256": self.source_sha256,
            "independent_provenance": list(self.independent_provenance),
            "expected_payload_sha256": self.expected_payload_sha256,
            "kind": self.kind.value,
            "evidence_mode": self.evidence_mode.value,
        }


@dataclass(frozen=True)
class OracleValidation:
    oracle_id: str
    status: OracleValidationStatus
    expected_sha256: str
    actual_sha256: str


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_v2_bytes(payload)).hexdigest()


class OracleRegistry:
    __slots__ = ("_game_version", "_records", "_expectation_identities")

    def __init__(self, game_version: str, records: Iterable[OracleExpectation] = ()) -> None:
        self._game_version = _token(game_version, "game_version")
        self._records: dict[str, OracleExpectation] = {}
        self._expectation_identities: set[str] = set()
        for record in records:
            self.register(record)

    def assess(self, record: OracleExpectation) -> tuple[OracleAssessment, tuple[str, ...]]:
        if not isinstance(record, OracleExpectation):
            return OracleAssessment.REJECTED, ("not an OracleExpectation",)
        reasons = []
        if record.kind is not OracleKind.INDEPENDENT_NATIVE:
            reasons.append("oracle source is not independent native observation")
        if record.evidence_mode is not EvidenceMode.NATIVE_EVIDENCED:
            reasons.append("oracle evidence mode is not NATIVE_EVIDENCED")
        if record.game_version != self._game_version:
            reasons.append("oracle is not qualified for the registry game version")
        if not record.independent_provenance:
            reasons.append("independent provenance is missing")
        return (OracleAssessment.REJECTED, tuple(reasons)) if reasons else (OracleAssessment.QUALIFIED, ())

    def register(self, record: OracleExpectation) -> None:
        assessment, reasons = self.assess(record)
        if assessment is not OracleAssessment.QUALIFIED:
            raise OracleError("oracle rejected: " + "; ".join(reasons))
        if record.oracle_id in self._records:
            raise OracleError(f"duplicate oracle_id {record.oracle_id!r}")
        if record.expectation_identity in self._expectation_identities:
            raise OracleError(
                "duplicate expectation_identity "
                f"{record.expectation_identity!r} cannot increment Golden twice"
            )
        # Reconstruct scalar/tuple values so registry ownership is explicit.
        owned = OracleExpectation(**{
            "oracle_id": record.oracle_id, "game_version": record.game_version,
            "expectation_identity": record.expectation_identity,
            "source_identity": record.source_identity, "source_sha256": record.source_sha256,
            "independent_provenance": tuple(record.independent_provenance),
            "expected_payload_sha256": record.expected_payload_sha256,
            "kind": record.kind, "evidence_mode": record.evidence_mode,
        })
        self._records[owned.oracle_id] = owned
        self._expectation_identities.add(owned.expectation_identity)

    @property
    def golden_count(self) -> int:
        return len(self._records)

    def validate(self, oracle_id: str, actual_payload: Any) -> OracleValidation:
        try:
            record = self._records[oracle_id]
        except KeyError as exc:
            raise OracleError(f"unknown qualified oracle {oracle_id!r}") from exc
        actual = payload_sha256(actual_payload)
        status = (OracleValidationStatus.MATCH if actual == record.expected_payload_sha256
                  else OracleValidationStatus.MISMATCH)
        return OracleValidation(record.oracle_id, status, record.expected_payload_sha256, actual)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "terra_oracle_registry/1",
            "game_version": self._game_version,
            "qualified_oracles": [record.to_dict() for record in self._records.values()],
            "golden": self.golden_count,
        }
