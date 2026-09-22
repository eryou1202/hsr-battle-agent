# -*- coding: utf-8 -*-
"""Lossless modifier request, lookup, transition and lifecycle descriptors."""
from __future__ import annotations

from enum import Enum
from typing import Mapping

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["ModifierDescriptor", "ModifierDescriptorKind", "ModifierKnowledge"]


class ModifierDescriptorKind(Enum):
    REQUEST = "REQUEST"
    LOOKUP_QUERY = "LOOKUP_QUERY"
    STACKING_TRANSITION = "STACKING_TRANSITION"
    LIFECYCLE_CALLBACK = "LIFECYCLE_CALLBACK"


class ModifierKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "kind", "request", "lookup_query", "stacking_transition",
    "lifecycle_callback", "provider", "caster", "stacking_policy",
    "knowledge", "blocker",
}


class ModifierDescriptor(DescriptorOccurrence):
    """Modifier representation with four non-interchangeable descriptor kinds."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("modifier descriptor fields are incomplete or unknown")
        kind_value = self.fields["kind"]
        if not kind_value.is_present():
            raise DescriptorError("modifier kind must be explicit")
        try:
            kind = ModifierDescriptorKind(kind_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown modifier descriptor kind") from exc
        active = {
            ModifierDescriptorKind.REQUEST: "request",
            ModifierDescriptorKind.LOOKUP_QUERY: "lookup_query",
            ModifierDescriptorKind.STACKING_TRANSITION: "stacking_transition",
            ModifierDescriptorKind.LIFECYCLE_CALLBACK: "lifecycle_callback",
        }[kind]
        for name in ("request", "lookup_query", "stacking_transition", "lifecycle_callback"):
            value = self.fields[name]
            if name == active:
                if not value.is_present() or not isinstance(value.require_present(), Mapping):
                    raise DescriptorError(f"{name} must be a present mapping for {kind.value}")
            elif not value.is_absent():
                raise DescriptorError(f"{name} must be ABSENT for {kind.value}")
        transition = self.fields["stacking_transition"]
        if transition.is_present():
            operation = transition.require_present().get("operation")
            if operation not in {"Refresh", "Replace", "Multiple", "Unknown"}:
                raise DescriptorError("stacking transition operation must remain explicit")
        knowledge_value = self.fields["knowledge"]
        if not knowledge_value.is_present():
            raise DescriptorError("modifier knowledge must be explicit")
        try:
            knowledge = ModifierKnowledge(knowledge_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown modifier knowledge value") from exc
        blocker = self.fields["blocker"]
        if knowledge is ModifierKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("unresolved modifier descriptor requires blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid modifier blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("represented modifier descriptor cannot carry blocker")

    @property
    def kind(self) -> ModifierDescriptorKind:
        return ModifierDescriptorKind(self.fields["kind"].require_present())

    def is_blocked(self) -> bool:
        return ModifierKnowledge(self.fields["knowledge"].require_present()) is ModifierKnowledge.UNRESOLVED
