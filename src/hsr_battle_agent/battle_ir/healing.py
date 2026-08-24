# -*- coding: utf-8 -*-
"""Canonical real-skill heal boundary values for capability 30.

The representations keep recovered content separate from caller-supplied
runtime resolutions.  In particular, serialized DynamicFloat operands are
opaque keys, not literal heal values, and a Heal request is not an HP write.
"""
from __future__ import annotations

from dataclasses import dataclass

from hsr_battle_agent.battle_ir.targets import EntityRef

_QWORD_MIN = -(2**63)
_QWORD_MAX = 0xFFFFFFFFFFFFFFFF


def _require_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")


def _require_raw(value: int, name: str) -> None:
    _require_int(value, name)
    if not (_QWORD_MIN <= value <= _QWORD_MAX):
        raise ValueError(f"{name} is outside the qword raw range")


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class SerializedDynamicFloatFormula:
    """Structurally decoded DynamicFloat formula; evaluation is external."""

    opcodes: tuple[int, ...]
    qword_operands: tuple[int, ...]
    int32_operands: tuple[int, ...]
    source_start: str
    source_end_exclusive: str

    def __post_init__(self) -> None:
        if not isinstance(self.opcodes, tuple) or not self.opcodes:
            raise ValueError("opcodes must be a non-empty tuple")
        if any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 255 for item in self.opcodes):
            raise ValueError("opcodes must contain byte integers")
        if not isinstance(self.qword_operands, tuple):
            raise TypeError("qword_operands must be a tuple")
        if not isinstance(self.int32_operands, tuple):
            raise TypeError("int32_operands must be a tuple")
        for item in self.qword_operands:
            _require_raw(item, "qword operand")
        for item in self.int32_operands:
            _require_int(item, "int32 operand")
            if not (-(2**31) <= item <= 2**31 - 1):
                raise ValueError("int32 operand is out of range")
        _require_text(self.source_start, "source_start")
        _require_text(self.source_end_exclusive, "source_end_exclusive")

    @property
    def sole_int32_operand(self) -> int:
        if self.qword_operands or len(self.int32_operands) != 1:
            raise ValueError("formula does not have exactly one int32 operand")
        return self.int32_operands[0]


@dataclass(frozen=True)
class NatashaSkill02HealConfig:
    """Validated projection of the committed real Natasha content artifact."""

    ability_name: str
    content_artifact_ref: str
    content_artifact_sha256: str
    archive_sha256: str
    parent_discriminator: int
    predicate_discriminator: int
    predicate_trigger_key: int
    target_discriminator: int
    target_name: str
    dispel_discriminator: int
    dispel_order: int
    dispel_numbers: SerializedDynamicFloatFormula
    heal_discriminator: int
    heal_formula_type: int
    heal_percentage: SerializedDynamicFloatFormula
    modify_value: SerializedDynamicFloatFormula

    def __post_init__(self) -> None:
        for name in (
            "ability_name",
            "content_artifact_ref",
            "content_artifact_sha256",
            "archive_sha256",
            "target_name",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "parent_discriminator",
            "predicate_discriminator",
            "predicate_trigger_key",
            "target_discriminator",
            "dispel_discriminator",
            "dispel_order",
            "heal_discriminator",
            "heal_formula_type",
        ):
            _require_int(getattr(self, name), name)
        for name in ("dispel_numbers", "heal_percentage", "modify_value"):
            if not isinstance(getattr(self, name), SerializedDynamicFloatFormula):
                raise TypeError(f"{name} must be SerializedDynamicFloatFormula")


@dataclass(frozen=True)
class ResolvedDynamicFloat:
    """One external DynamicFloat evaluation with mandatory provenance."""

    formula_operand: int
    value_raw: int
    provenance: str

    def __post_init__(self) -> None:
        _require_int(self.formula_operand, "formula_operand")
        _require_raw(self.value_raw, "value_raw")
        _require_text(self.provenance, "provenance")


@dataclass(frozen=True)
class RealSkillExternalBindings:
    """Explicit inputs at unresolved real-client semantic boundaries."""

    predicate_satisfied: bool
    predicate_provenance: str
    ability_target: EntityRef
    target_provenance: str
    dynamic_values: tuple[ResolvedDynamicFloat, ...]
    ordinary_healer_branch: bool
    healer_branch_provenance: str

    def __post_init__(self) -> None:
        if not isinstance(self.predicate_satisfied, bool):
            raise TypeError("predicate_satisfied must be bool")
        _require_text(self.predicate_provenance, "predicate_provenance")
        if not isinstance(self.ability_target, EntityRef):
            raise TypeError("ability_target must be EntityRef")
        _require_text(self.target_provenance, "target_provenance")
        if not isinstance(self.dynamic_values, tuple):
            raise TypeError("dynamic_values must be a tuple")
        if any(not isinstance(item, ResolvedDynamicFloat) for item in self.dynamic_values):
            raise TypeError("dynamic_values must contain ResolvedDynamicFloat")
        keys = [item.formula_operand for item in self.dynamic_values]
        if len(keys) != len(set(keys)):
            raise ValueError("dynamic_values formula operands must be unique")
        if not isinstance(self.ordinary_healer_branch, bool):
            raise TypeError("ordinary_healer_branch must be bool")
        _require_text(self.healer_branch_provenance, "healer_branch_provenance")

    def resolve(self, formula: SerializedDynamicFloatFormula) -> ResolvedDynamicFloat:
        key = formula.sole_int32_operand
        matches = [item for item in self.dynamic_values if item.formula_operand == key]
        if len(matches) != 1:
            raise KeyError(f"no unique external DynamicFloat resolution for operand {key}")
        return matches[0]


@dataclass(frozen=True)
class DispelStatusRequestBoundary:
    caster: EntityRef
    target: EntityRef
    numbers_raw: int
    order: int
    config_ref: str
    resolution_provenance: str

    def __post_init__(self) -> None:
        if not isinstance(self.caster, EntityRef) or not isinstance(self.target, EntityRef):
            raise TypeError("caster and target must be EntityRef")
        _require_raw(self.numbers_raw, "numbers_raw")
        _require_int(self.order, "order")
        _require_text(self.config_ref, "config_ref")
        _require_text(self.resolution_provenance, "resolution_provenance")

    def trace_summary(self) -> str:
        return (
            f"dispel_request:caster={self.caster.runtime_id}:"
            f"target={self.target.runtime_id}:order={self.order}:"
            f"numbers=0x{self.numbers_raw & _QWORD_MAX:X}"
        )


@dataclass(frozen=True)
class HealRequestBoundary:
    healer: EntityRef
    target: EntityRef
    amount_raw: int
    observed_current_hp_raw: int
    formula_type: int
    config_ref: str
    dynamic_resolution_provenance: tuple[str, ...]
    consumer_status: str = "POSITIVE_HEAL_EVENT_CONSUMER_NOT_RECOVERED"

    def __post_init__(self) -> None:
        if not isinstance(self.healer, EntityRef) or not isinstance(self.target, EntityRef):
            raise TypeError("healer and target must be EntityRef")
        _require_raw(self.amount_raw, "amount_raw")
        _require_raw(self.observed_current_hp_raw, "observed_current_hp_raw")
        _require_int(self.formula_type, "formula_type")
        _require_text(self.config_ref, "config_ref")
        if not isinstance(self.dynamic_resolution_provenance, tuple) or not all(
            isinstance(item, str) and item.strip()
            for item in self.dynamic_resolution_provenance
        ):
            raise ValueError("dynamic_resolution_provenance must be non-empty strings")
        _require_text(self.consumer_status, "consumer_status")

    def trace_summary(self) -> str:
        return (
            f"heal_request:healer={self.healer.runtime_id}:"
            f"target={self.target.runtime_id}:formula={self.formula_type}:"
            f"amount=0x{self.amount_raw & _QWORD_MAX:X}:consumer=pending"
        )


@dataclass(frozen=True)
class RealSkillExecutionBoundaryResult:
    ability_name: str
    caster: EntityRef
    target: EntityRef
    predicate_satisfied: bool
    predicate_provenance: str
    dispel_request: DispelStatusRequestBoundary | None
    heal_request: HealRequestBoundary | None
    status: str
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.ability_name, "ability_name")
        if not isinstance(self.caster, EntityRef) or not isinstance(self.target, EntityRef):
            raise TypeError("caster and target must be EntityRef")
        if not isinstance(self.predicate_satisfied, bool):
            raise TypeError("predicate_satisfied must be bool")
        _require_text(self.predicate_provenance, "predicate_provenance")
        if self.dispel_request is not None and not isinstance(
            self.dispel_request, DispelStatusRequestBoundary
        ):
            raise TypeError("dispel_request has wrong type")
        if self.heal_request is not None and not isinstance(
            self.heal_request, HealRequestBoundary
        ):
            raise TypeError("heal_request has wrong type")
        _require_text(self.status, "status")
        if not isinstance(self.blockers, tuple) or not all(
            isinstance(item, str) and item.strip() for item in self.blockers
        ):
            raise ValueError("blockers must contain non-empty strings")

    def trace_summary(self) -> str:
        return (
            f"real_skill_boundary:{self.ability_name}:caster={self.caster.runtime_id}:"
            f"target={self.target.runtime_id}:predicate={self.predicate_satisfied}:"
            f"status={self.status}:blockers={len(self.blockers)}"
        )
