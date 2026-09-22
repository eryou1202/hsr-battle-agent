# -*- coding: utf-8 -*-
"""Immutable representation-descriptor registry, separate from execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NoReturn

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorOccurrence
from hsr_battle_agent.battle_ir.descriptors.damage import DamageDescriptor
from hsr_battle_agent.battle_ir.descriptors.formation import FormationTopologyDescriptor
from hsr_battle_agent.battle_ir.descriptors.invocation import InvocationDescriptor
from hsr_battle_agent.battle_ir.descriptors.modifier import ModifierDescriptor
from hsr_battle_agent.battle_ir.descriptors.monster_ai import MonsterAIDescriptor
from hsr_battle_agent.battle_ir.descriptors.progression import ProgressionActivationDescriptor
from hsr_battle_agent.battle_ir.descriptors.scenario import ScenarioDescriptor
from hsr_battle_agent.battle_ir.descriptors.scheduler import SchedulerDescriptor
from hsr_battle_agent.battle_ir.descriptors.target import (
    ResolvedTargetSet,
    RetargetDescriptor,
    TargetIntent,
)

__all__ = [
    "DescriptorFamily",
    "DescriptorRegistration",
    "DescriptorRegistry",
    "DescriptorRegistryError",
]


class DescriptorRegistryError(ValueError):
    pass


class DescriptorFamily(Enum):
    INVOCATION = "INVOCATION"
    MODIFIER = "MODIFIER"
    FORMATION_TOPOLOGY = "FORMATION_TOPOLOGY"
    SCHEDULER = "SCHEDULER"
    MONSTER_AI = "MONSTER_AI"
    DAMAGE = "DAMAGE"
    TARGET_RETARGET = "TARGET_RETARGET"
    PROGRESSION_LOADOUT = "PROGRESSION_LOADOUT"
    SCENARIO_MODE_TERMINAL = "SCENARIO_MODE_TERMINAL"


_FAMILY_TYPES: dict[DescriptorFamily, tuple[type[DescriptorOccurrence], ...]] = {
    DescriptorFamily.INVOCATION: (InvocationDescriptor,),
    DescriptorFamily.MODIFIER: (ModifierDescriptor,),
    DescriptorFamily.FORMATION_TOPOLOGY: (FormationTopologyDescriptor,),
    DescriptorFamily.SCHEDULER: (SchedulerDescriptor,),
    DescriptorFamily.MONSTER_AI: (MonsterAIDescriptor,),
    DescriptorFamily.DAMAGE: (DamageDescriptor,),
    DescriptorFamily.TARGET_RETARGET: (TargetIntent, ResolvedTargetSet, RetargetDescriptor),
    DescriptorFamily.PROGRESSION_LOADOUT: (ProgressionActivationDescriptor,),
    DescriptorFamily.SCENARIO_MODE_TERMINAL: (ScenarioDescriptor,),
}


def _parse_family(value: DescriptorFamily | str) -> DescriptorFamily:
    if isinstance(value, DescriptorFamily):
        return value
    try:
        return DescriptorFamily(value)
    except (TypeError, ValueError) as exc:
        raise DescriptorRegistryError(f"unknown descriptor family {value!r}") from exc


@dataclass(frozen=True)
class DescriptorRegistration:
    family: DescriptorFamily
    static_entity_id: str
    descriptor: DescriptorOccurrence

    def __post_init__(self) -> None:
        family = _parse_family(self.family)
        if not isinstance(self.static_entity_id, str) or not self.static_entity_id:
            raise DescriptorRegistryError("static_entity_id must be a non-empty string")
        if type(self.descriptor) not in _FAMILY_TYPES[family]:
            raise DescriptorRegistryError(
                f"{type(self.descriptor).__name__} is not a {family.value} descriptor"
            )
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "descriptor", self.descriptor.detached_copy())


@dataclass(frozen=True)
class DescriptorRegistry:
    """Persistent registry of representations; never a primitive registry."""

    registrations: tuple[DescriptorRegistration, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.registrations, (str, bytes)) or not isinstance(
            self.registrations, (tuple, list)
        ):
            raise DescriptorRegistryError("registrations must be a tuple or list")
        supplied = tuple(self.registrations)
        if any(not isinstance(item, DescriptorRegistration) for item in supplied):
            raise DescriptorRegistryError("all registrations must be DescriptorRegistration values")
        normalized = tuple(
            DescriptorRegistration(item.family, item.static_entity_id, item.descriptor)
            for item in supplied
        )
        identities = [
            (item.family, item.static_entity_id, item.descriptor.occurrence_identity())
            for item in normalized
        ]
        if len(identities) != len(set(identities)):
            raise DescriptorRegistryError("duplicate descriptor registration")
        object.__setattr__(self, "registrations", normalized)

    def with_registration(self, registration: DescriptorRegistration) -> "DescriptorRegistry":
        if not isinstance(registration, DescriptorRegistration):
            raise DescriptorRegistryError("registration must be a DescriptorRegistration")
        return DescriptorRegistry(self.registrations + (registration,))

    def resolve_family(self, family: DescriptorFamily | str) -> tuple[DescriptorOccurrence, ...]:
        resolved = _parse_family(family)
        return tuple(
            x.descriptor.detached_copy()
            for x in self.registrations
            if x.family is resolved
        )

    def resolve_static(
        self, family: DescriptorFamily | str, static_entity_id: str
    ) -> tuple[DescriptorOccurrence, ...]:
        resolved = _parse_family(family)
        if not isinstance(static_entity_id, str) or not static_entity_id:
            raise DescriptorRegistryError("static_entity_id must be a non-empty string")
        return tuple(
            x.descriptor.detached_copy()
            for x in self.registrations
            if x.family is resolved and x.static_entity_id == static_entity_id
        )

    def families_present(self) -> tuple[DescriptorFamily, ...]:
        present = {x.family for x in self.registrations}
        return tuple(family for family in DescriptorFamily if family in present)

    def execution_permitted(self) -> NoReturn:
        raise DescriptorRegistryError(
            "the descriptor registry stores representation only and cannot permit execution"
        )
