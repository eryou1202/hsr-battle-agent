# -*- coding: utf-8 -*-
"""Sandbox kernel error types.

F01-007 adds :class:`StructuredRejection` and
:class:`StructuredRejectionError`.  Rejection is modelled as data first: a
stable machine reason code, the obligation owner, the evidence request, the
contract references involved and the unknown handles it links.  Exceptions are
adapters around that data, never the source of truth.

The pre-existing error classes below are unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    ContractRef,
    EvidenceVocabularyError,
    UnknownHandle,
)

__all__ = [
    "BattleSandboxError",
    "DuplicatePrimitiveError",
    "FrozenRegistryError",
    "InvalidPrimitiveInputError",
    "StructuredRejection",
    "StructuredRejectionError",
    "RejectionDataError",
    "StubNotImplementedError",
    "UnsupportedPrimitiveError",
    "UnsupportedStateVersionError",
]

REJECTION_SCHEMA = "structured_rejection/1"


class BattleSandboxError(Exception):
    """Base class for all sandbox kernel errors."""


class UnsupportedPrimitiveError(BattleSandboxError):
    def __init__(self, primitive_id: str) -> None:
        super().__init__(
            f"unsupported battle IR primitive: {primitive_id!r} "
            "(no silent no-op; register the primitive or fail)"
        )
        self.primitive_id = primitive_id


class InvalidPrimitiveInputError(BattleSandboxError):
    pass


class DuplicatePrimitiveError(BattleSandboxError):
    def __init__(self, primitive_id: str) -> None:
        super().__init__(f"primitive already registered: {primitive_id!r}")
        self.primitive_id = primitive_id


class FrozenRegistryError(BattleSandboxError):
    def __init__(self) -> None:
        super().__init__("primitive registry is frozen")


class UnsupportedStateVersionError(BattleSandboxError):
    def __init__(self, schema_version: object) -> None:
        super().__init__(
            f"unsupported BattleState schema_version: {schema_version!r}"
        )
        self.schema_version = schema_version


class StubNotImplementedError(BattleSandboxError):
    """Explicit NOT_IMPLEMENTED guard for future sandbox surface."""


# ---------------------------------------------------------------------------
# Structured rejection (F01-007)
# ---------------------------------------------------------------------------


class RejectionDataError(BattleSandboxError):
    """Raised for malformed structured-rejection data."""


def _copy_diagnostic_value(value: Any, where: str = "diagnostics") -> Any:
    """Copy JSON-like diagnostic data without key or sequence coercion."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RejectionDataError(f"{where} contains a non-finite float")
        return value
    if isinstance(value, list):
        return [
            _copy_diagnostic_value(item, f"{where}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return tuple(
            _copy_diagnostic_value(item, f"{where}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, Mapping):
        copied: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RejectionDataError(
                    f"{where} keys must be strings, got {type(key).__name__}"
                )
            copied[key] = _copy_diagnostic_value(item, f"{where}.{key}")
        return copied
    raise RejectionDataError(
        f"{where} contains unsupported {type(value).__name__}"
    )


@dataclass(frozen=True)
class StructuredRejection:
    """Machine-readable rejection data.

    The stable *reason kind* is :attr:`reason_code`.  Object identity also
    includes obligation owner, evidence request and ordered links; otherwise
    distinct unresolved obligations would collapse merely because they share a
    reason code.  ``diagnostics`` is excluded from identity and equality, so
    reworded human-readable detail does not change the rejection.

    ``contract_refs`` and ``unknown_handles`` link the rejection to the exact
    contracts and unresolved blockers involved, and both survive a round trip.
    There is no success, default or fallback value: a rejection states a
    refusal, and :meth:`resolve` refuses to pretend otherwise.
    """

    reason_code: str
    obligation_owner: str
    evidence_request: str
    contract_refs: tuple[ContractRef, ...] = field(default_factory=tuple)
    unknown_handles: tuple[UnknownHandle, ...] = field(default_factory=tuple)
    diagnostics: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reason_code",
            self._require_code(self.reason_code, "reason_code"),
        )
        object.__setattr__(
            self,
            "obligation_owner",
            self._require_code(self.obligation_owner, "obligation_owner"),
        )
        if not isinstance(self.evidence_request, str) or not self.evidence_request:
            raise RejectionDataError(
                "evidence_request must be a non-empty string"
            )
        for name, expected in (
            ("contract_refs", ContractRef),
            ("unknown_handles", UnknownHandle),
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(
                value, (tuple, list)
            ):
                raise RejectionDataError(
                    f"{name} must be a tuple or list of {expected.__name__}"
                )
            for item in value:
                if not isinstance(item, expected):
                    raise RejectionDataError(
                        f"{name} entries must be {expected.__name__} instances, "
                        f"got {type(item).__name__}"
                    )
            object.__setattr__(self, name, tuple(value))
        if not isinstance(self.diagnostics, Mapping):
            raise RejectionDataError(
                "diagnostics must be a mapping of diagnostic detail"
            )
        object.__setattr__(
            self, "diagnostics", _copy_diagnostic_value(self.diagnostics)
        )

    @staticmethod
    def _require_code(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise RejectionDataError(f"{label} must be a non-empty string")
        if value != value.strip():
            raise RejectionDataError(
                f"{label} {value!r} must not carry surrounding whitespace"
            )
        if value.upper() != value:
            raise RejectionDataError(
                f"{label} {value!r} must be an uppercase stable machine code"
            )
        return value

    # -- identity --------------------------------------------------------

    def identity(self) -> str:
        """Stable structural identity, excluding human diagnostics."""
        document = {
            "reason_code": self.reason_code,
            "obligation_owner": self.obligation_owner,
            "evidence_request": self.evidence_request,
            "contract_refs": [ref.to_dict() for ref in self.contract_refs],
            "unknown_handle_hashes": [
                handle.identity_hash() for handle in self.unknown_handles
            ],
        }
        encoded = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def reason(self) -> str:
        """Return the stable reason-code identity, independent of messages."""
        return self.reason_code

    def __hash__(self) -> int:
        """Hash consistently with structural equality (diagnostics excluded)."""
        return int(self.identity()[:16], 16)

    def describe(self) -> str:
        """Human-readable summary.  Never used for identity."""
        return (
            f"{self.reason_code}: owned by {self.obligation_owner}; "
            f"requires {self.evidence_request}"
        )

    # -- refusal ---------------------------------------------------------

    def resolve(self) -> NoReturn:
        """Refuse: a rejection has no success value."""
        raise RejectionDataError(
            f"rejection {self.reason_code} cannot be resolved into a value; "
            "supply the requested evidence and rebuild"
        )

    def __bool__(self) -> NoReturn:
        raise RejectionDataError(
            "StructuredRejection has no truthiness; it is neither success nor "
            "failure by conversion -- handle it explicitly"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REJECTION_SCHEMA,
            "reason_code": self.reason_code,
            "obligation_owner": self.obligation_owner,
            "evidence_request": self.evidence_request,
            "contract_refs": [ref.to_dict() for ref in self.contract_refs],
            "unknown_handles": [
                handle.to_dict() for handle in self.unknown_handles
            ],
            "diagnostics": copy.deepcopy(dict(self.diagnostics)),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StructuredRejection":
        if not isinstance(data, Mapping):
            raise RejectionDataError(
                f"rejection document must be a mapping, got {type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else REJECTION_SCHEMA
        if schema != REJECTION_SCHEMA:
            raise RejectionDataError(
                f"unknown rejection schema {schema!r}; expected "
                f"{REJECTION_SCHEMA!r}"
            )
        for name in (
            "reason_code",
            "obligation_owner",
            "evidence_request",
        ):
            if name not in data:
                raise RejectionDataError(
                    f"rejection document is missing required field {name!r}"
                )
        raw_refs = data["contract_refs"] if "contract_refs" in data else []
        raw_handles = data["unknown_handles"] if "unknown_handles" in data else []
        if isinstance(raw_refs, (str, bytes)) or not isinstance(
            raw_refs, (tuple, list)
        ):
            raise RejectionDataError("contract_refs must be a list")
        if isinstance(raw_handles, (str, bytes)) or not isinstance(
            raw_handles, (tuple, list)
        ):
            raise RejectionDataError("unknown_handles must be a list")
        try:
            contract_refs = tuple(
                ContractRef.from_dict(item) for item in raw_refs
            )
            unknown_handles = tuple(
                UnknownHandle.from_dict(item) for item in raw_handles
            )
        except EvidenceVocabularyError as exc:
            raise RejectionDataError(
                f"invalid linked rejection data: {exc}"
            ) from exc
        return cls(
            reason_code=data["reason_code"],
            obligation_owner=data["obligation_owner"],
            evidence_request=data["evidence_request"],
            contract_refs=contract_refs,
            unknown_handles=unknown_handles,
            diagnostics=copy.deepcopy(
                data["diagnostics"] if "diagnostics" in data else {}
            ),
        )

    # -- exception adapter ------------------------------------------------

    def to_exception(self) -> "StructuredRejectionError":
        """Wrap this data in an exception.  The data remains the truth."""
        return StructuredRejectionError(self)


class StructuredRejectionError(BattleSandboxError):
    """Exception adapter carrying :class:`StructuredRejection` data.

    Existing code may keep raising and catching exceptions; the structured
    rejection attached here is the machine-readable source of truth.
    """

    def __init__(self, rejection: StructuredRejection) -> None:
        if not isinstance(rejection, StructuredRejection):
            raise RejectionDataError(
                "StructuredRejectionError requires a StructuredRejection, got "
                f"{type(rejection).__name__}"
            )
        super().__init__(rejection.describe())
        self.rejection = rejection
        # Human-readable text is never the identity; expose code separately.
        self.reason_code = rejection.reason_code
