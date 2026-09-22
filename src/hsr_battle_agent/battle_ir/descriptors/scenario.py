# -*- coding: utf-8 -*-
"""Lossless scenario, mode, environment and terminal descriptors."""
from __future__ import annotations

from enum import Enum

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import EvidenceMode, UnknownHandle

__all__ = ["ScenarioDescriptor", "ScenarioDescriptorKind", "ScenarioKnowledge"]


class ScenarioDescriptorKind(Enum):
    SCENARIO = "SCENARIO"
    WAVE_GROUP = "WAVE_GROUP"
    SLOT = "SLOT"
    OCCURRENCE = "OCCURRENCE"
    ENVIRONMENT = "ENVIRONMENT"
    MODE = "MODE"
    TERMINAL = "TERMINAL"


class ScenarioKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "kind", "scenario_identity", "source_items", "environment",
    "mode", "terminal_rule", "terminal_rule_class", "knowledge", "blocker",
}


class ScenarioDescriptor(DescriptorOccurrence):
    """Nested scenario representation; never a flattened executable wave list."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("scenario fields are incomplete or unknown")
        if not self.fields["kind"].is_present():
            raise DescriptorError("scenario descriptor kind must be explicit")
        try:
            kind = ScenarioDescriptorKind(self.fields["kind"].require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown scenario descriptor kind") from exc
        items = self.fields["source_items"]
        if items.is_present() and not isinstance(items.require_present(), list):
            raise DescriptorError(
                "scenario source_items must be a list; source order cannot be flattened"
            )
        rule_class = self.fields["terminal_rule_class"]
        if kind is ScenarioDescriptorKind.TERMINAL:
            if not rule_class.is_present():
                raise DescriptorError("terminal rule class must be explicit")
            if rule_class.require_present() not in {
                EvidenceMode.NATIVE_EVIDENCED.value,
                EvidenceMode.REFERENCE_MODEL.value,
                EvidenceMode.SANDBOX_EXTENSION.value,
                EvidenceMode.UNSUPPORTED.value,
            }:
                raise DescriptorError("unknown terminal rule evidence class")
        elif not rule_class.is_absent():
            raise DescriptorError("non-terminal descriptor cannot carry terminal rule class")
        knowledge_value = self.fields["knowledge"]
        if not knowledge_value.is_present():
            raise DescriptorError("scenario knowledge must be explicit")
        try:
            knowledge = ScenarioKnowledge(knowledge_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown scenario knowledge") from exc
        blocker = self.fields["blocker"]
        if knowledge is ScenarioKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("unresolved scenario descriptor requires blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid scenario blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("represented scenario descriptor cannot carry blocker")

    @property
    def kind(self) -> ScenarioDescriptorKind:
        return ScenarioDescriptorKind(self.fields["kind"].require_present())

    def is_blocked(self) -> bool:
        return ScenarioKnowledge(self.fields["knowledge"].require_present()) is ScenarioKnowledge.UNRESOLVED
