# -*- coding: utf-8 -*-
"""One-way seam from published mapping-ledger output to descriptor lookup.

This module does not inspect source payloads, candidate names or compiler
dispositions.  The resolution ledger remains the sole owner of mapping-state
classification and static joins.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.descriptor_registry import (
    DescriptorFamily,
    DescriptorRegistry,
)
from hsr_battle_agent.battle_ir.descriptors.base import DescriptorOccurrence
from hsr_battle_agent.battle_ir.resolution_ledger import (
    ResolutionLedgerEntry,
    ResolutionState,
)

__all__ = [
    "BehaviorDescriptorResult",
    "BehaviorDescriptorStatus",
    "BindingTableDiagnostics",
    "adapt_mapping_entry",
    "diagnose_binding_tables",
]


class BehaviorDescriptorStatus(Enum):
    EXACT_DESCRIPTOR = "EXACT_DESCRIPTOR"
    EXACT_MAPPING_DESCRIPTOR_MISSING = "EXACT_MAPPING_DESCRIPTOR_MISSING"
    LEDGER_MISSING = "LEDGER_MISSING"
    LEDGER_AMBIGUOUS = "LEDGER_AMBIGUOUS"
    LEDGER_BLOCKED = "LEDGER_BLOCKED"


@dataclass(frozen=True)
class BehaviorDescriptorResult:
    family: DescriptorFamily
    ledger_entry: ResolutionLedgerEntry
    status: BehaviorDescriptorStatus
    descriptors: tuple[DescriptorOccurrence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.family, DescriptorFamily):
            raise TypeError("family must be a DescriptorFamily")
        if not isinstance(self.ledger_entry, ResolutionLedgerEntry):
            raise TypeError("ledger_entry must be a ResolutionLedgerEntry")
        if not isinstance(self.status, BehaviorDescriptorStatus):
            raise TypeError("status must be a BehaviorDescriptorStatus")
        if any(not isinstance(item, DescriptorOccurrence) for item in self.descriptors):
            raise TypeError("descriptors must contain descriptor occurrences")
        if self.status is BehaviorDescriptorStatus.EXACT_DESCRIPTOR:
            if self.ledger_entry.state is not ResolutionState.EXACT or not self.descriptors:
                raise ValueError("EXACT_DESCRIPTOR requires exact ledger state and descriptors")
        elif self.descriptors:
            raise ValueError("non-exact descriptor result cannot expose descriptors")
        object.__setattr__(
            self,
            "descriptors",
            tuple(item.detached_copy() for item in self.descriptors),
        )

    def execution_permitted(self) -> NoReturn:
        raise ValueError(
            "descriptor mapping is representation evidence and cannot permit execution"
        )


def adapt_mapping_entry(
    entry: ResolutionLedgerEntry,
    family: DescriptorFamily,
    registry: DescriptorRegistry,
) -> BehaviorDescriptorResult:
    """Adapt the ledger's already-published answer; never recompute its join."""
    if not isinstance(entry, ResolutionLedgerEntry):
        raise TypeError("entry must be a ResolutionLedgerEntry")
    if not isinstance(family, DescriptorFamily):
        raise TypeError("family must be a DescriptorFamily")
    if not isinstance(registry, DescriptorRegistry):
        raise TypeError("registry must be a DescriptorRegistry")
    if entry.state is ResolutionState.MISSING:
        return BehaviorDescriptorResult(family, entry, BehaviorDescriptorStatus.LEDGER_MISSING)
    if entry.state is ResolutionState.AMBIGUOUS:
        return BehaviorDescriptorResult(family, entry, BehaviorDescriptorStatus.LEDGER_AMBIGUOUS)
    if entry.state is ResolutionState.BLOCKED:
        return BehaviorDescriptorResult(family, entry, BehaviorDescriptorStatus.LEDGER_BLOCKED)
    static_entity_id = entry.require_resolved()
    matches = registry.resolve_static(family, static_entity_id)
    if not matches:
        return BehaviorDescriptorResult(
            family, entry, BehaviorDescriptorStatus.EXACT_MAPPING_DESCRIPTOR_MISSING
        )
    return BehaviorDescriptorResult(
        family, entry, BehaviorDescriptorStatus.EXACT_DESCRIPTOR, matches
    )


@dataclass(frozen=True)
class BindingTableDiagnostics:
    """Informational key cross-check; deliberately absent from resolution flow."""

    table_key_counts: Mapping[str, int]
    overlapping_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_key_counts", MappingProxyType(dict(self.table_key_counts)))
        object.__setattr__(self, "overlapping_labels", tuple(self.overlapping_labels))


def diagnose_binding_tables(
    primitive_bindings: Mapping[str, Any],
    static_families: Mapping[str, Any],
    owner_static_family: Mapping[str, Any],
) -> BindingTableDiagnostics:
    """Cross-check the three legacy tables without changing any registry result."""
    tables = {
        "PRIMITIVE_BINDINGS": primitive_bindings,
        "STATIC_FAMILIES": static_families,
        "OWNER_STATIC_FAMILY": owner_static_family,
    }
    for name, table in tables.items():
        if not isinstance(table, Mapping):
            raise TypeError(f"{name} must be a mapping")
    key_sets = [{str(key) for key in table} for table in tables.values()]
    overlap = set().union(
        key_sets[0] & key_sets[1], key_sets[0] & key_sets[2], key_sets[1] & key_sets[2]
    )
    return BindingTableDiagnostics(
        {name: len(table) for name, table in tables.items()}, tuple(sorted(overlap))
    )
