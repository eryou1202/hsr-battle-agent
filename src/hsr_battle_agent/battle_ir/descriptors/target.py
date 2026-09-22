# -*- coding: utf-8 -*-
"""Lossless target-intent, resolved-target-set and retarget descriptors."""
from __future__ import annotations

from enum import Enum

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = [
    "ResolvedTargetSet",
    "RetargetDescriptor",
    "TargetDescriptorKnowledge",
    "TargetIntent",
]


class TargetDescriptorKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


def _validate_knowledge(item: DescriptorOccurrence) -> None:
    knowledge_value = item.fields["knowledge"]
    if not knowledge_value.is_present():
        raise DescriptorError("target knowledge must be explicit")
    try:
        knowledge = TargetDescriptorKnowledge(knowledge_value.require_present())
    except (TypeError, ValueError) as exc:
        raise DescriptorError("unknown target knowledge") from exc
    blocker = item.fields["blocker"]
    if knowledge is TargetDescriptorKnowledge.UNRESOLVED:
        if not blocker.is_present():
            raise DescriptorError("unresolved target descriptor requires blocker")
        try:
            UnknownHandle.from_dict(blocker.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("invalid target blocker") from exc
    elif not blocker.is_absent():
        raise DescriptorError("represented target descriptor cannot carry blocker")


class TargetIntent(DescriptorOccurrence):
    """Selected primary reference or symbolic selector; not a resolved hit list."""

    _FIELDS = {"intent_kind", "intent", "knowledge", "blocker"}

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != self._FIELDS:
            raise DescriptorError("TargetIntent fields are incomplete or unknown")
        if not self.fields["intent_kind"].is_present():
            raise DescriptorError("TargetIntent kind must be explicit")
        _validate_knowledge(self)

    def is_blocked(self) -> bool:
        return TargetDescriptorKnowledge(self.fields["knowledge"].require_present()) is TargetDescriptorKnowledge.UNRESOLVED


class ResolvedTargetSet(DescriptorOccurrence):
    """Ordered nullable target list preserving emptiness, nulls and duplicates."""

    _FIELDS = {
        "targets", "resolution_stage", "duplicate_policy", "rng_provenance",
        "knowledge", "blocker",
    }

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != self._FIELDS:
            raise DescriptorError("ResolvedTargetSet fields are incomplete or unknown")
        targets = self.fields["targets"]
        if not targets.is_present() or not isinstance(targets.require_present(), list):
            raise DescriptorError(
                "resolved targets must be a present list; tuples may not flatten to lists"
            )
        _validate_knowledge(self)

    @property
    def targets(self) -> list[object]:
        return self.fields["targets"].require_present()

    def is_blocked(self) -> bool:
        return TargetDescriptorKnowledge(self.fields["knowledge"].require_present()) is TargetDescriptorKnowledge.UNRESOLVED


class RetargetDescriptor(DescriptorOccurrence):
    """Retarget request representation; no mutation or lifetime is inferred."""

    _FIELDS = {
        "input_intent", "predicate", "random_request", "include_limbo",
        "maximum", "nested_tasks", "affected_context", "lifetime",
        "knowledge", "blocker",
    }

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != self._FIELDS:
            raise DescriptorError("Retarget fields are incomplete or unknown")
        nested = self.fields["nested_tasks"]
        if nested.is_present() and (
            isinstance(nested.require_present(), (str, bytes))
            or not isinstance(nested.require_present(), (list, tuple))
        ):
            raise DescriptorError("retarget nested tasks must retain ordered shape")
        _validate_knowledge(self)

    def is_blocked(self) -> bool:
        return TargetDescriptorKnowledge(self.fields["knowledge"].require_present()) is TargetDescriptorKnowledge.UNRESOLVED
