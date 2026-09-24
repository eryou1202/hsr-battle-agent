"""Version/hash-gated REFERENCE_MODEL value and resource adapters (REF01-001)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from enum import Enum
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.evidence import EvidenceMode


class ReferenceOperationError(ValueError):
    pass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ReferenceOperationError("boolean is not a reference numeric value")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ReferenceOperationError(f"non-numeric value {value!r}") from error
    if not result.is_finite():
        raise ReferenceOperationError("non-finite reference arithmetic is unsupported")
    return result


@dataclass(frozen=True)
class ReferenceAdapterGate:
    adapter_id: str
    source_version: str
    source_sha256: str
    allowed_scopes: tuple[str, ...]
    allowed_owners: tuple[str, ...]
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_scopes", tuple(self.allowed_scopes))
        object.__setattr__(self, "allowed_owners", tuple(self.allowed_owners))
        if self.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
            raise ReferenceOperationError("reference adapters require REFERENCE_MODEL")
        if not self.adapter_id or not self.source_version or not _SHA256.fullmatch(self.source_sha256):
            raise ReferenceOperationError("adapter requires id, version, and lowercase sha256")
        if not self.allowed_scopes or not self.allowed_owners:
            raise ReferenceOperationError("adapter requires bounded scope and owner gates")
        if not all(isinstance(value, str) and value for value in self.allowed_scopes + self.allowed_owners):
            raise ReferenceOperationError("scope and owner gates require non-empty tokens")
        if len(set(self.allowed_scopes)) != len(self.allowed_scopes):
            raise ReferenceOperationError("duplicate scope declaration")
        if len(set(self.allowed_owners)) != len(self.allowed_owners):
            raise ReferenceOperationError("duplicate owner declaration")

    def require(self, *, version: str, sha256: str, scope: str, owner: str) -> None:
        if version != self.source_version or sha256 != self.source_sha256:
            raise ReferenceOperationError("reference version/hash gate mismatch")
        if scope not in self.allowed_scopes or owner not in self.allowed_owners:
            raise ReferenceOperationError("reference scope/owner gate mismatch")


class ArithmeticOperator(Enum):
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"


@dataclass(frozen=True)
class ReferenceValueResult:
    adapter_id: str
    owner: str
    scope: str
    value: Decimal
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL


def evaluate_arithmetic(
    gate: ReferenceAdapterGate,
    *,
    version: str,
    sha256: str,
    scope: str,
    owner: str,
    operator: ArithmeticOperator,
    left: Any,
    right: Any,
) -> ReferenceValueResult:
    gate.require(version=version, sha256=sha256, scope=scope, owner=owner)
    if not isinstance(operator, ArithmeticOperator):
        raise ReferenceOperationError("unsupported arithmetic operator")
    lhs, rhs = _decimal(left), _decimal(right)
    with localcontext() as context:
        context.prec = 38
        try:
            value = {
                ArithmeticOperator.ADD: lambda: lhs + rhs,
                ArithmeticOperator.SUBTRACT: lambda: lhs - rhs,
                ArithmeticOperator.MULTIPLY: lambda: lhs * rhs,
                ArithmeticOperator.DIVIDE: lambda: lhs / rhs,
            }[operator]()
        except (DivisionByZero, ZeroDivisionError) as error:
            raise ReferenceOperationError("division by zero is rejected") from error
    return ReferenceValueResult(gate.adapter_id, owner, scope, value)


@dataclass(frozen=True)
class OwnedValueStore:
    """Detached owner-scoped reference values; a key belongs to one store only."""

    owner: str
    values: tuple[tuple[str, Decimal], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        if not self.owner or any(
            not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str) or not item[0]
            or not isinstance(item[1], Decimal) for item in self.values
        ):
            raise ReferenceOperationError("owned value store requires canonical key/Decimal pairs")

    @classmethod
    def from_mapping(cls, owner: str, values: Mapping[str, Any]) -> "OwnedValueStore":
        if not owner:
            raise ReferenceOperationError("store owner is required")
        return cls(owner, tuple((str(key), _decimal(value)) for key, value in values.items()))

    def as_mapping(self) -> dict[str, Decimal]:
        return dict(self.values)

    def with_value(self, *, owner: str, key: str, value: Any) -> "OwnedValueStore":
        if owner != self.owner:
            raise ReferenceOperationError("cross-owner write rejected")
        if not key:
            raise ReferenceOperationError("value key is required")
        changed = self.as_mapping()
        changed[key] = _decimal(value)
        return OwnedValueStore.from_mapping(self.owner, changed)


@dataclass(frozen=True)
class TeamResourceState:
    owner: str
    current: Decimal
    maximum: Decimal

    def __post_init__(self) -> None:
        if not self.owner or self.maximum < 0 or self.current < 0 or self.current > self.maximum:
            raise ReferenceOperationError("invalid bounded team resource holder")


@dataclass(frozen=True)
class ResourceResult:
    before: TeamResourceState
    after: TeamResourceState
    evaluated_contribution: Decimal
    applied_contribution: Decimal
    source_name: str
    evidence_mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL


_ADD_RATIO_SOURCES = frozenset({
    "Avatar_Natasha_00_Skill02_Phase02", "Avatar_Natasha_00_Skill03_Phase02",
})
_ADD_VALUE_SOURCES = frozenset({
    "MCommon_HOT_SP", "M_BlackSwan_00_DOT_Rank04_AddSP", "MAvatar_Natasha_00_Rank04_Check",
})


def apply_named_team_sp_contribution(
    gate: ReferenceAdapterGate,
    state: TeamResourceState,
    *,
    version: str,
    sha256: str,
    scope: str,
    target_owner: str,
    source_name: str,
    argument_name: str,
    evaluated_contribution: Any,
) -> ResourceResult:
    """Apply only the named ModifySPNew post-commit contribution packet.

    Non-positive evaluated contributions are discarded; they are never treated
    as a cost.  A new state is returned, leaving the supplied holder untouched.
    """
    gate.require(version=version, sha256=sha256, scope=scope, owner=target_owner)
    if target_owner != state.owner:
        raise ReferenceOperationError("target does not own the supplied team holder")
    allowed = _ADD_RATIO_SOURCES if argument_name == "AddRatio" else (
        _ADD_VALUE_SOURCES if argument_name == "AddValue" else frozenset()
    )
    if source_name not in allowed:
        raise ReferenceOperationError("source/argument pair is outside the named packet")
    contribution = _decimal(evaluated_contribution)
    applied = max(Decimal("0"), contribution)
    new_current = min(state.maximum, state.current + applied)
    after = TeamResourceState(state.owner, new_current, state.maximum)
    return ResourceResult(state, after, contribution, new_current - state.current, source_name)


__all__ = [
    "ArithmeticOperator", "OwnedValueStore", "ReferenceAdapterGate",
    "ReferenceOperationError", "ReferenceValueResult", "ResourceResult",
    "TeamResourceState", "apply_named_team_sp_contribution", "evaluate_arithmetic",
]
