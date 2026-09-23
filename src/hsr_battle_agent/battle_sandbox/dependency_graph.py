# -*- coding: utf-8 -*-
"""Local conservative dependency closure for strict preflight (G01-002).

This module traverses only the explicit :mod:`preflight` representation.  It
does not execute an effect, inspect battle state, draw RNG, allocate an ID, or
issue permission.  Child references match *every* candidate with the same
owner and ContractRef.  Traversal uses candidate occurrence indexes solely for
path-local cycle detection; those indexes never deduplicate semantic
occurrences.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    ContractRef,
    EvidenceVocabularyError,
    UnknownHandle,
)
from hsr_battle_agent.battle_sandbox.errors import BattleSandboxError
from hsr_battle_agent.battle_sandbox.preflight import (
    ChildObligationRef,
    DependencyObligation,
    ObligationAccess,
    ObligationResolution,
    require_owner_code,
)

__all__ = [
    "CLOSURE_BLOCKER_SCHEMA",
    "DEPENDENCY_CLOSURE_SCHEMA",
    "ClosureBlocker",
    "ClosureStatus",
    "DependencyClosure",
    "DependencyClosureError",
    "DependencyGraph",
]

CLOSURE_BLOCKER_SCHEMA = "dependency_closure_blocker/1"
DEPENDENCY_CLOSURE_SCHEMA = "dependency_closure/1"


class DependencyClosureError(BattleSandboxError):
    """Raised for malformed closure input or representation."""


class ClosureStatus(Enum):
    """Local conservative-closure outcomes, never native status names."""

    CLOSED = "CLOSED"
    BLOCKED_MISSING = "BLOCKED_MISSING"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
    BLOCKED_UNSUPPORTED = "BLOCKED_UNSUPPORTED"
    BLOCKED_CYCLE = "BLOCKED_CYCLE"
    BLOCKED_UNBOUNDED = "BLOCKED_UNBOUNDED"

    def __bool__(self) -> NoReturn:
        raise DependencyClosureError(
            "ClosureStatus has no truthiness; inspect is_closed() explicitly"
        )

    def is_closed(self) -> bool:
        return self is ClosureStatus.CLOSED

    @classmethod
    def parse(cls, value: Any) -> "ClosureStatus":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise DependencyClosureError("closure status must be a string")
        try:
            return cls(value)
        except ValueError:
            raise DependencyClosureError(
                f"unknown local closure status {value!r}"
            ) from None


def _contract_copy(value: ContractRef) -> ContractRef:
    if not isinstance(value, ContractRef):
        raise DependencyClosureError("contract_ref must be a ContractRef")
    return ContractRef.from_dict(value.to_dict())


def _handle_copy(value: UnknownHandle) -> UnknownHandle:
    if not isinstance(value, UnknownHandle):
        raise DependencyClosureError("unknown handle must be an UnknownHandle")
    return UnknownHandle.from_dict(value.to_dict())


def _obligation_copy(value: DependencyObligation) -> DependencyObligation:
    if not isinstance(value, DependencyObligation):
        raise DependencyClosureError(
            "dependency candidates must be DependencyObligation values"
        )
    return DependencyObligation.from_dict(value.to_dict())


def _access_copy(value: ObligationAccess) -> ObligationAccess:
    if not isinstance(value, ObligationAccess):
        raise DependencyClosureError("closure access must be ObligationAccess")
    return ObligationAccess.from_dict(value.to_dict())


def _blocker_copy(value: "ClosureBlocker") -> "ClosureBlocker":
    if not isinstance(value, ClosureBlocker):
        raise DependencyClosureError("blockers must be ClosureBlocker values")
    return ClosureBlocker.from_dict(value.to_dict())


def _path(value: Any) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise DependencyClosureError("occurrence_path must be a tuple or list")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise DependencyClosureError(
                "occurrence_path entries must be non-negative integers"
            )
        result.append(item)
    return tuple(result)


@dataclass(frozen=True, init=False, eq=False, repr=False)
class ClosureBlocker:
    """One blocker in deterministic source/traversal discovery order."""

    _status: ClosureStatus
    _owner: str
    _contract_ref: ContractRef
    _unknown_handles: tuple[UnknownHandle, ...]
    _occurrence_path: tuple[int, ...]
    _evidence_request: str

    def __init__(
        self,
        *,
        status: ClosureStatus | str,
        owner: str,
        contract_ref: ContractRef,
        unknown_handles: tuple[UnknownHandle, ...] | list[UnknownHandle] = (),
        occurrence_path: tuple[int, ...] | list[int] = (),
        evidence_request: str,
    ) -> None:
        resolved_status = ClosureStatus.parse(status)
        if resolved_status is ClosureStatus.CLOSED:
            raise DependencyClosureError("a blocker cannot have CLOSED status")
        if not isinstance(evidence_request, str) or not evidence_request:
            raise DependencyClosureError(
                "blocker evidence_request must be a non-empty string"
            )
        if isinstance(unknown_handles, (str, bytes)) or not isinstance(
            unknown_handles, (tuple, list)
        ):
            raise DependencyClosureError("unknown_handles must be ordered values")
        object.__setattr__(self, "_status", resolved_status)
        object.__setattr__(self, "_owner", require_owner_code(owner))
        object.__setattr__(self, "_contract_ref", _contract_copy(contract_ref))
        object.__setattr__(
            self,
            "_unknown_handles",
            tuple(_handle_copy(item) for item in unknown_handles),
        )
        object.__setattr__(self, "_occurrence_path", _path(occurrence_path))
        object.__setattr__(self, "_evidence_request", evidence_request)

    @property
    def status(self) -> ClosureStatus:
        return self._status

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def contract_ref(self) -> ContractRef:
        return _contract_copy(self._contract_ref)

    @property
    def unknown_handles(self) -> tuple[UnknownHandle, ...]:
        return tuple(_handle_copy(item) for item in self._unknown_handles)

    @property
    def occurrence_path(self) -> tuple[int, ...]:
        return self._occurrence_path

    @property
    def evidence_request(self) -> str:
        return self._evidence_request

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CLOSURE_BLOCKER_SCHEMA,
            "status": self._status.value,
            "owner": self._owner,
            "contract_ref": self._contract_ref.to_dict(),
            "unknown_handles": [item.to_dict() for item in self._unknown_handles],
            "occurrence_path": list(self._occurrence_path),
            "evidence_request": self._evidence_request,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ClosureBlocker":
        expected = {
            "schema",
            "status",
            "owner",
            "contract_ref",
            "unknown_handles",
            "occurrence_path",
            "evidence_request",
        }
        if not isinstance(data, Mapping) or set(data) != expected:
            raise DependencyClosureError(
                "closure blocker must contain every declared field exactly"
            )
        if data["schema"] != CLOSURE_BLOCKER_SCHEMA:
            raise DependencyClosureError("unknown closure blocker schema")
        try:
            contract = ContractRef.from_dict(data["contract_ref"])
            handles = tuple(
                UnknownHandle.from_dict(item) for item in data["unknown_handles"]
            )
        except (EvidenceVocabularyError, TypeError) as exc:
            raise DependencyClosureError(f"invalid closure blocker: {exc}") from exc
        return cls(
            status=data["status"],
            owner=data["owner"],
            contract_ref=contract,
            unknown_handles=handles,
            occurrence_path=data["occurrence_path"],
            evidence_request=data["evidence_request"],
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClosureBlocker):
            return NotImplemented
        return self.to_dict() == other.to_dict()


@dataclass(frozen=True, init=False, eq=False, repr=False)
class DependencyClosure:
    """Complete conservative traversal result; never execution permission."""

    _status: ClosureStatus
    _obligations: tuple[DependencyObligation, ...]
    _blockers: tuple[ClosureBlocker, ...]
    _allowed_reads: tuple[ObligationAccess, ...]
    _allowed_writes: tuple[ObligationAccess, ...]

    def __init__(
        self,
        *,
        status: ClosureStatus | str,
        obligations: tuple[DependencyObligation, ...] | list[DependencyObligation],
        blockers: tuple[ClosureBlocker, ...] | list[ClosureBlocker],
        allowed_reads: tuple[ObligationAccess, ...] | list[ObligationAccess],
        allowed_writes: tuple[ObligationAccess, ...] | list[ObligationAccess],
    ) -> None:
        resolved_status = ClosureStatus.parse(status)
        sequences = (obligations, blockers, allowed_reads, allowed_writes)
        if any(
            isinstance(value, (str, bytes))
            or not isinstance(value, (tuple, list))
            for value in sequences
        ):
            raise DependencyClosureError("closure sequences must be tuple/list values")
        detached_obligations = tuple(_obligation_copy(item) for item in obligations)
        detached_blockers = tuple(_blocker_copy(item) for item in blockers)
        if resolved_status is ClosureStatus.CLOSED and detached_blockers:
            raise DependencyClosureError("CLOSED closure cannot contain a blocker")
        if resolved_status is not ClosureStatus.CLOSED:
            if not detached_blockers:
                raise DependencyClosureError("blocked closure must retain blockers")
            if detached_blockers[0].status is not resolved_status:
                raise DependencyClosureError(
                    "blocked closure status must equal its first traversal blocker"
                )
        object.__setattr__(self, "_status", resolved_status)
        object.__setattr__(self, "_obligations", detached_obligations)
        object.__setattr__(self, "_blockers", detached_blockers)
        object.__setattr__(
            self, "_allowed_reads", tuple(_access_copy(item) for item in allowed_reads)
        )
        object.__setattr__(
            self,
            "_allowed_writes",
            tuple(_access_copy(item) for item in allowed_writes),
        )

    def __bool__(self) -> NoReturn:
        raise DependencyClosureError(
            "DependencyClosure has no truthiness; call is_closed() explicitly"
        )

    def is_closed(self) -> bool:
        return self._status is ClosureStatus.CLOSED

    @property
    def status(self) -> ClosureStatus:
        return self._status

    @property
    def obligations(self) -> tuple[DependencyObligation, ...]:
        return tuple(_obligation_copy(item) for item in self._obligations)

    @property
    def blockers(self) -> tuple[ClosureBlocker, ...]:
        return tuple(ClosureBlocker.from_dict(item.to_dict()) for item in self._blockers)

    @property
    def allowed_reads(self) -> tuple[ObligationAccess, ...]:
        return tuple(_access_copy(item) for item in self._allowed_reads)

    @property
    def allowed_writes(self) -> tuple[ObligationAccess, ...]:
        return tuple(_access_copy(item) for item in self._allowed_writes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DEPENDENCY_CLOSURE_SCHEMA,
            "status": self._status.value,
            "obligations": [item.to_dict() for item in self._obligations],
            "blockers": [item.to_dict() for item in self._blockers],
            "allowed_reads": [item.to_dict() for item in self._allowed_reads],
            "allowed_writes": [item.to_dict() for item in self._allowed_writes],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DependencyClosure":
        expected = {
            "schema",
            "status",
            "obligations",
            "blockers",
            "allowed_reads",
            "allowed_writes",
        }
        if not isinstance(data, Mapping) or set(data) != expected:
            raise DependencyClosureError(
                "dependency closure must contain every declared field exactly"
            )
        if data["schema"] != DEPENDENCY_CLOSURE_SCHEMA:
            raise DependencyClosureError("unknown dependency closure schema")
        try:
            return cls(
                status=data["status"],
                obligations=tuple(
                    DependencyObligation.from_dict(item)
                    for item in data["obligations"]
                ),
                blockers=tuple(
                    ClosureBlocker.from_dict(item) for item in data["blockers"]
                ),
                allowed_reads=tuple(
                    ObligationAccess.from_dict(item) for item in data["allowed_reads"]
                ),
                allowed_writes=tuple(
                    ObligationAccess.from_dict(item)
                    for item in data["allowed_writes"]
                ),
            )
        except (TypeError, EvidenceVocabularyError) as exc:
            raise DependencyClosureError(f"invalid dependency closure: {exc}") from exc

    def detached_copy(self) -> "DependencyClosure":
        return DependencyClosure.from_dict(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DependencyClosure):
            return NotImplemented
        return self.to_dict() == other.to_dict()


class DependencyGraph:
    """Ordered candidate registry with conservative all-match traversal."""

    __slots__ = ("_candidates",)

    def __init__(
        self,
        candidates: tuple[DependencyObligation, ...] | list[DependencyObligation],
    ) -> None:
        if isinstance(candidates, (str, bytes)) or not isinstance(
            candidates, (tuple, list)
        ):
            raise DependencyClosureError("candidates must be a tuple or list")
        self._candidates = tuple(_obligation_copy(item) for item in candidates)

    @property
    def candidates(self) -> tuple[DependencyObligation, ...]:
        return tuple(_obligation_copy(item) for item in self._candidates)

    @staticmethod
    def _matches(obligation: DependencyObligation, ref: ChildObligationRef) -> bool:
        return (
            obligation.owner == ref.owner
            and obligation.contract_ref == ref.contract_ref
        )

    def close(
        self,
        roots: tuple[ChildObligationRef, ...] | list[ChildObligationRef],
        *,
        expansion_budget: int,
    ) -> DependencyClosure:
        """Expand every matching occurrence before any execution can exist.

        ``expansion_budget`` is a caller-declared local safety bound.  Exhaustion
        is an explicit ``BLOCKED_UNBOUNDED`` result; it never truncates into
        success.  Cycles are detected path-locally so a shared descendant or a
        repeated root remains an observable repeated occurrence.
        """
        if isinstance(roots, (str, bytes)) or not isinstance(roots, (tuple, list)):
            raise DependencyClosureError("roots must be a tuple or list")
        if isinstance(expansion_budget, bool) or not isinstance(
            expansion_budget, int
        ) or expansion_budget <= 0:
            raise DependencyClosureError("expansion_budget must be a positive int")
        detached_roots: list[ChildObligationRef] = []
        for item in roots:
            if not isinstance(item, ChildObligationRef):
                raise DependencyClosureError("roots must be ChildObligationRef values")
            detached_roots.append(ChildObligationRef.from_dict(item.to_dict()))

        obligations: list[DependencyObligation] = []
        blockers: list[ClosureBlocker] = []
        reads: list[ObligationAccess] = []
        writes: list[ObligationAccess] = []
        expansion_count = 0

        def add_blocker(
            status: ClosureStatus,
            ref: ChildObligationRef,
            path: tuple[int, ...],
            *,
            handles: tuple[UnknownHandle, ...] = (),
            request: str,
        ) -> None:
            blockers.append(
                ClosureBlocker(
                    status=status,
                    owner=ref.owner,
                    contract_ref=ref.contract_ref,
                    unknown_handles=handles,
                    occurrence_path=path,
                    evidence_request=request,
                )
            )

        def expand_ref(
            ref: ChildObligationRef,
            path: tuple[int, ...],
            active: frozenset[int],
        ) -> None:
            nonlocal expansion_count
            matches = [
                (index, candidate)
                for index, candidate in enumerate(self._candidates)
                if self._matches(candidate, ref)
            ]
            if not matches:
                add_blocker(
                    ClosureStatus.BLOCKED_MISSING,
                    ref,
                    path,
                    request="matching dependency obligation",
                )
                return

            for candidate_index, candidate in matches:
                occurrence_path = path + (candidate_index,)
                if candidate_index in active:
                    add_blocker(
                        ClosureStatus.BLOCKED_CYCLE,
                        ref,
                        occurrence_path,
                        request="finite acyclic dependency expansion",
                    )
                    continue
                if expansion_count >= expansion_budget:
                    add_blocker(
                        ClosureStatus.BLOCKED_UNBOUNDED,
                        ref,
                        occurrence_path,
                        request="declared finite dependency footprint",
                    )
                    continue

                expansion_count += 1
                owned = _obligation_copy(candidate)
                obligations.append(owned)
                reads.extend(owned.reads)
                writes.extend(owned.writes)

                if owned.resolution is ObligationResolution.UNKNOWN:
                    add_blocker(
                        ClosureStatus.BLOCKED_UNKNOWN,
                        ref,
                        occurrence_path,
                        handles=owned.unknown_handles,
                        request="evidence resolving every UnknownHandle",
                    )
                elif owned.resolution is ObligationResolution.UNSUPPORTED:
                    add_blocker(
                        ClosureStatus.BLOCKED_UNSUPPORTED,
                        ref,
                        occurrence_path,
                        handles=owned.unknown_handles,
                        request="supported dependency contract",
                    )

                next_active = active | {candidate_index}
                for child in owned.children:
                    expand_ref(child, occurrence_path, next_active)

        for root_index, root in enumerate(detached_roots):
            expand_ref(root, (root_index,), frozenset())

        status = ClosureStatus.CLOSED if not blockers else blockers[0].status
        return DependencyClosure(
            status=status,
            obligations=obligations,
            blockers=blockers,
            allowed_reads=reads,
            allowed_writes=writes,
        )
