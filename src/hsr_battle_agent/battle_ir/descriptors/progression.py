# -*- coding: utf-8 -*-
"""Progression/loadout activation descriptors."""
from __future__ import annotations

from enum import Enum

from hsr_battle_agent.battle_ir.descriptors.base import DescriptorError, DescriptorOccurrence
from hsr_battle_agent.battle_ir.evidence import UnknownHandle

__all__ = ["ActivationState", "ProgressionActivationDescriptor"]


class ActivationState(Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    UNRESOLVED = "UNRESOLVED"


_FIELDS = {
    "source_family", "source_identity", "activation_state",
    "activation_provenance", "candidate_mapping", "blocker",
}


class ProgressionActivationDescriptor(DescriptorOccurrence):
    """Per-source activation classification; linkage never implies activation."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if set(self.fields) != _FIELDS:
            raise DescriptorError("progression fields are incomplete or unknown")
        for name in ("source_family", "source_identity", "activation_state"):
            if not self.fields[name].is_present():
                raise DescriptorError(f"{name} must be explicit")
        try:
            state = ActivationState(self.fields["activation_state"].require_present())
        except (TypeError, ValueError) as exc:
            raise DescriptorError("unknown progression activation state") from exc
        blocker = self.fields["blocker"]
        if state is ActivationState.UNRESOLVED:
            if not blocker.is_present():
                raise DescriptorError("UNRESOLVED activation must carry a blocker")
            try:
                UnknownHandle.from_dict(blocker.require_present())
            except (TypeError, ValueError) as exc:
                raise DescriptorError("invalid progression blocker") from exc
        elif not blocker.is_absent():
            raise DescriptorError("resolved activation cannot carry blocker")

    @property
    def activation_state(self) -> ActivationState:
        return ActivationState(self.fields["activation_state"].require_present())

    def is_blocked(self) -> bool:
        return self.activation_state is ActivationState.UNRESOLVED
