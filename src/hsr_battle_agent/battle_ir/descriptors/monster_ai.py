# -*- coding: utf-8 -*-
"""Lossless monster-AI policy/state descriptors without selection semantics."""
from __future__ import annotations

from enum import Enum

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["MonsterAIDescriptor", "MonsterAIKnowledge"]


class MonsterAIKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "policy_body", "state", "sequence", "use_skill", "variables",
    "sequence_occurrence", "admission_handoff", "target_handoff",
    "knowledge", "blocker",
}


class MonsterAIDescriptor(DescriptorOccurrence):
    """AI representation; never a winner, admitted action or state commit."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("monster AI fields are incomplete or unknown")
        sequence = self.fields["sequence"]
        if sequence.is_present() and (
            isinstance(sequence.require_present(), (str, bytes))
            or not isinstance(sequence.require_present(), (list, tuple))
        ):
            raise DescriptorError("AI sequence must preserve ordered list/tuple shape")
        occurrence = self.fields["sequence_occurrence"]
        if occurrence.is_present() and (
            isinstance(occurrence.require_present(), bool)
            or not isinstance(occurrence.require_present(), int)
            or occurrence.require_present() < 0
        ):
            raise DescriptorError("sequence occurrence must be a non-negative integer")
        knowledge_value = self.fields["knowledge"]
        if not knowledge_value.is_present():
            raise DescriptorError("AI knowledge must be explicit")
        try:
            knowledge = MonsterAIKnowledge(knowledge_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown AI knowledge") from exc
        blocker = self.fields["blocker"]
        if knowledge is MonsterAIKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("unresolved AI descriptor requires blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid AI blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("represented AI descriptor cannot carry blocker")

    def is_blocked(self) -> bool:
        return MonsterAIKnowledge(self.fields["knowledge"].require_present()) is MonsterAIKnowledge.UNRESOLVED
