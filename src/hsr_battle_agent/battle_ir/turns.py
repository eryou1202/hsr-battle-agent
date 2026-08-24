# -*- coding: utf-8 -*-
"""Minimal persistent Turn/AV values for semantic capability 29."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.targets import EntityRef

TURN_TIMELINE_SCHEMA = "battle_turn_timeline/1"
TURN_PHASE_READY = "ready"
TURN_PHASE_ACTIVE = "active"
TURN_PHASE_SETTLED = "settled"
TURN_PHASES = frozenset({TURN_PHASE_READY, TURN_PHASE_ACTIVE, TURN_PHASE_SETTLED})


@dataclass(frozen=True)
class ActionCompletionBoundary:
    """Explicit acknowledgement that native post-action gates have settled.

    ``next_action_delay_raw`` is intentionally supplied by the caller because
    Semantics 29 does not close the generic post-action recharge writer or its
    content-dependent ratio. ``provenance`` must identify that input's source.
    """

    actor: EntityRef
    next_action_delay_raw: int
    provenance: str

    def __post_init__(self) -> None:
        if not isinstance(self.actor, EntityRef):
            raise TypeError("actor must be EntityRef")
        if isinstance(self.next_action_delay_raw, bool) or not isinstance(
            self.next_action_delay_raw, int
        ):
            raise TypeError("next_action_delay_raw must be an int")
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError("provenance must be a non-empty string")


@dataclass(frozen=True)
class TurnAdvanceResult:
    actor: EntityRef
    selected_delay_raw: int
    elapsed_action_delay_raw: int
    ordered_entities: tuple[EntityRef, ...]
    turn_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.actor, EntityRef):
            raise TypeError("actor must be EntityRef")
        for name in ("selected_delay_raw", "elapsed_action_delay_raw", "turn_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if not isinstance(self.ordered_entities, tuple):
            raise TypeError("ordered_entities must be a tuple")
        if any(not isinstance(item, EntityRef) for item in self.ordered_entities):
            raise TypeError("ordered_entities must contain only EntityRef values")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TURN_TIMELINE_SCHEMA,
            "kind": "TurnAdvanceResult",
            "actor": self.actor.to_dict(),
            "selected_delay_raw": self.selected_delay_raw,
            "elapsed_action_delay_raw": self.elapsed_action_delay_raw,
            "ordered_entities": [item.to_dict() for item in self.ordered_entities],
            "turn_index": self.turn_index,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TurnAdvanceResult":
        if not isinstance(data, Mapping):
            raise TypeError("TurnAdvanceResult dict must be a mapping")
        if (
            data.get("schema") != TURN_TIMELINE_SCHEMA
            or data.get("kind") != "TurnAdvanceResult"
        ):
            raise ValueError("unsupported TurnAdvanceResult dict")
        return cls(
            actor=EntityRef.from_dict(data["actor"]),
            selected_delay_raw=int(data["selected_delay_raw"]),
            elapsed_action_delay_raw=int(data["elapsed_action_delay_raw"]),
            ordered_entities=tuple(
                EntityRef.from_dict(item) for item in data["ordered_entities"]
            ),
            turn_index=int(data["turn_index"]),
        )

    def trace_summary(self) -> str:
        order = ",".join(str(item.runtime_id) for item in self.ordered_entities)
        return (
            f"turn_advance:turn={self.turn_index}:actor={self.actor.runtime_id}:"
            f"delta=0x{self.selected_delay_raw & 0xFFFFFFFFFFFFFFFF:X}:"
            f"elapsed=0x{self.elapsed_action_delay_raw & 0xFFFFFFFFFFFFFFFF:X}:"
            f"order=[{order}]"
        )
