# -*- coding: utf-8 -*-
"""Lossless damage request topology descriptors."""
from __future__ import annotations

from enum import Enum

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["DamageDescriptor", "DamageKnowledge"]


class DamageKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "damage_root", "damage_hit", "damage_component", "context",
    "survival_dependencies", "resource_dependencies",
    "special_channel_references", "knowledge", "blocker",
}


class DamageDescriptor(DescriptorOccurrence):
    """Damage root/hit/component representation without formula execution."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("damage fields are incomplete or unknown")
        for name in (
            "survival_dependencies", "resource_dependencies", "special_channel_references"
        ):
            value = self.fields[name]
            if value.is_present() and (
                isinstance(value.require_present(), (str, bytes))
                or not isinstance(value.require_present(), (list, tuple))
            ):
                raise DescriptorError(f"{name} must preserve ordered list/tuple shape")
        knowledge_value = self.fields["knowledge"]
        if not knowledge_value.is_present():
            raise DescriptorError("damage knowledge must be explicit")
        try:
            knowledge = DamageKnowledge(knowledge_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown damage knowledge") from exc
        blocker = self.fields["blocker"]
        if knowledge is DamageKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("unresolved damage descriptor requires blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid damage blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("represented damage descriptor cannot carry blocker")

    def is_blocked(self) -> bool:
        return DamageKnowledge(self.fields["knowledge"].require_present()) is DamageKnowledge.UNRESOLVED
