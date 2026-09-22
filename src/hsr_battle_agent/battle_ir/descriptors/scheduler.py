# -*- coding: utf-8 -*-
"""Representation-only scheduler candidate descriptors."""
from __future__ import annotations

from enum import Enum

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["SchedulerDescriptor", "SchedulerFamily", "SchedulerKnowledge"]


class SchedulerFamily(Enum):
    ORDINARY = "ORDINARY"
    ULTRA_REQUEST = "ULTRA_REQUEST"
    TURN_INSERT_ABILITY = "TURN_INSERT_ABILITY"
    TURN_INSERT_ACTION = "TURN_INSERT_ACTION"
    ONE_MORE = "ONE_MORE"
    IMMEDIATE_ACTION = "IMMEDIATE_ACTION"
    ACTION_TASK = "ACTION_TASK"
    DAMAGE_TASK = "DAMAGE_TASK"


class SchedulerKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "family", "candidate", "partial_order", "source_sequence",
    "knowledge", "blocker",
}


class SchedulerDescriptor(DescriptorOccurrence):
    """One candidate in one scheduler family; it is not a legal action."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("scheduler fields are incomplete or unknown")
        family_value = self.fields["family"]
        if not family_value.is_present():
            raise DescriptorError("scheduler family must be explicit")
        try:
            SchedulerFamily(family_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown scheduler family") from exc
        for name in ("partial_order", "source_sequence"):
            value = self.fields[name]
            if value.is_present() and (
                isinstance(value.require_present(), (str, bytes))
                or not isinstance(value.require_present(), (list, tuple))
            ):
                raise DescriptorError(f"{name} must be an ordered list or tuple")
        knowledge_value = self.fields["knowledge"]
        if not knowledge_value.is_present():
            raise DescriptorError("scheduler knowledge must be explicit")
        try:
            knowledge = SchedulerKnowledge(knowledge_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown scheduler knowledge") from exc
        blocker = self.fields["blocker"]
        if knowledge is SchedulerKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("unresolved scheduler descriptor requires blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid scheduler blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("represented scheduler descriptor cannot carry blocker")

    @property
    def family(self) -> SchedulerFamily:
        return SchedulerFamily(self.fields["family"].require_present())

    def is_blocked(self) -> bool:
        return SchedulerKnowledge(self.fields["knowledge"].require_present()) is SchedulerKnowledge.UNRESOLVED
