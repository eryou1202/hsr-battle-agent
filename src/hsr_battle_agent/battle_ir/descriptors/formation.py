# -*- coding: utf-8 -*-
"""Lossless formation and topology descriptors."""
from __future__ import annotations

from enum import Enum
from typing import Mapping

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["FormationTopologyDescriptor", "TopologyKnowledge"]


class TopologyKnowledge(Enum):
    REPRESENTED = "REPRESENTED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "team_identity", "formation_index", "row_index", "spatial_order",
    "entity_identity", "lineup_index", "relations", "knowledge", "blocker",
}


class FormationTopologyDescriptor(DescriptorOccurrence):
    """Formation/topology occurrence without inferred adjacency or targetability."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("formation/topology fields are incomplete or unknown")
        relations = self.fields["relations"]
        if relations.is_present() and (
            isinstance(relations.require_present(), (str, bytes))
            or not isinstance(relations.require_present(), (list, tuple))
        ):
            raise DescriptorError("topology relations must be an ordered list or tuple")
        for name in ("formation_index", "row_index", "lineup_index"):
            value = self.fields[name]
            if value.is_present() and (
                isinstance(value.require_present(), bool)
                or not isinstance(value.require_present(), int)
            ):
                raise DescriptorError(f"{name} must be an exact integer when present")
        knowledge_value = self.fields["knowledge"]
        if not knowledge_value.is_present():
            raise DescriptorError("topology knowledge must be explicit")
        try:
            knowledge = TopologyKnowledge(knowledge_value.require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown topology knowledge value") from exc
        blocker = self.fields["blocker"]
        if knowledge is TopologyKnowledge.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("unresolved topology requires a blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid topology blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("represented topology cannot carry blocker")

    def is_blocked(self) -> bool:
        return TopologyKnowledge(self.fields["knowledge"].require_present()) is TopologyKnowledge.UNRESOLVED
