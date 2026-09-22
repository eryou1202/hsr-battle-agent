# -*- coding: utf-8 -*-
"""Lossless, representation-only invocation descriptors."""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.descriptors.base import (
    DescriptorError,
    DescriptorOccurrence,
)
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["InvocationDescriptor", "InvocationKnowledge"]


class InvocationKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "caller",
    "context",
    "arguments",
    "is_skill_perform",
    "continuation_handles",
    "knowledge",
    "blocker",
}


class InvocationDescriptor(DescriptorOccurrence):
    """One invocation occurrence; never an invocation or await operation."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError(
                "invocation fields must explicitly contain caller, context, "
                "arguments, IsSkillPerform, continuation handles, knowledge and blocker"
            )
        arguments = self.fields["arguments"]
        if arguments.is_present() and not isinstance(arguments.require_present(), Mapping):
            raise DescriptorError("invocation arguments must be a mapping when present")
        flag = self.fields["is_skill_perform"]
        if flag.is_present() and not isinstance(flag.require_present(), bool):
            raise DescriptorError("IsSkillPerform must be a bool when present")
        handles = self.fields["continuation_handles"]
        if handles.is_present() and (
            isinstance(handles.require_present(), (str, bytes))
            or not isinstance(handles.require_present(), (list, tuple))
        ):
            raise DescriptorError(
                "continuation_handles must be a lossless list or tuple when present"
            )
        knowledge = self.fields["knowledge"]
        if not knowledge.is_present():
            raise DescriptorError("invocation knowledge must be explicit")
        try:
            parsed = InvocationKnowledge(knowledge.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown invocation knowledge value") from exc
        blocker = self.fields["blocker"]
        if parsed is InvocationKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("an unresolved invocation must carry a blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid invocation blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("a represented invocation must not carry a blocker")

    @property
    def knowledge(self) -> InvocationKnowledge:
        return InvocationKnowledge(self.fields["knowledge"].require_present())

    @property
    def is_skill_perform(self) -> Any:
        """Return the PresenceValue so omission never becomes false."""
        return self.fields["is_skill_perform"]

    def is_blocked(self) -> bool:
        return self.knowledge is InvocationKnowledge.UNRESOLVED
