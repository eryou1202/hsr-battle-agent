# -*- coding: utf-8 -*-
"""Explicit SANDBOX_EXTENSION scenario initialization.

This module deliberately does not model official Stage initialization, wave
progression, loadout activation, or native victory semantics.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.snapshot_v2 import (
    SnapshotPolicyIdentity,
    TerraSnapshotV2,
)
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState

__all__ = [
    "CustomScenario",
    "CustomScenarioError",
    "CustomTerminalResult",
    "CustomTerminalRule",
    "EmptySidePolicy",
    "ResultPolicy",
    "ScenarioParticipant",
    "SimultaneousExhaustionPolicy",
]


class CustomScenarioError(ValueError):
    pass


class EmptySidePolicy(Enum):
    TERMINAL = "TERMINAL"
    NON_TERMINAL = "NON_TERMINAL"


class SimultaneousExhaustionPolicy(Enum):
    DRAW = "DRAW"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UNRESOLVED = "UNRESOLVED"


class ResultPolicy(Enum):
    REPORT_CUSTOM_OUTCOME = "REPORT_CUSTOM_OUTCOME"
    REPORT_EXHAUSTED_SIDES = "REPORT_EXHAUSTED_SIDES"


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CustomScenarioError(f"{label} must be a non-empty trimmed string")
    return value


@dataclass(frozen=True)
class ScenarioParticipant:
    participant_id: str
    side_id: str
    formation_slot: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "participant_id", _token(self.participant_id, "participant_id"))
        object.__setattr__(self, "side_id", _token(self.side_id, "side_id"))
        if isinstance(self.formation_slot, bool) or not isinstance(self.formation_slot, int):
            raise CustomScenarioError("formation_slot must be an explicit integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "participant_id": self.participant_id,
            "side_id": self.side_id,
            "formation_slot": self.formation_slot,
        }


@dataclass(frozen=True)
class CustomTerminalRule:
    namespace: str
    version: str
    rule_id: str
    empty_side_policy: EmptySidePolicy
    simultaneous_exhaustion_policy: SimultaneousExhaustionPolicy
    result_policy: ResultPolicy

    def __post_init__(self) -> None:
        for name in ("namespace", "version", "rule_id"):
            object.__setattr__(self, name, _token(getattr(self, name), name))
        if not isinstance(self.empty_side_policy, EmptySidePolicy):
            raise CustomScenarioError("empty_side_policy must be explicit")
        if not isinstance(self.simultaneous_exhaustion_policy, SimultaneousExhaustionPolicy):
            raise CustomScenarioError("simultaneous_exhaustion_policy must be explicit")
        if not isinstance(self.result_policy, ResultPolicy):
            raise CustomScenarioError("result_policy must be explicit")

    def to_dict(self) -> dict[str, str]:
        return {
            "namespace": self.namespace,
            "version": self.version,
            "rule_id": self.rule_id,
            "empty_side_policy": self.empty_side_policy.value,
            "simultaneous_exhaustion_policy": self.simultaneous_exhaustion_policy.value,
            "result_policy": self.result_policy.value,
        }

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(canonical_v2_bytes(self.to_dict())).hexdigest()


@dataclass(frozen=True)
class CustomTerminalResult:
    rule_namespace: str
    rule_version: str
    rule_id: str
    terminal: bool
    custom_outcome: str
    exhausted_sides: tuple[str, ...]
    result_policy: ResultPolicy
    evidence_mode: EvidenceMode = EvidenceMode.SANDBOX_EXTENSION


class CustomScenario:
    """Complete custom initial state plus explicitly named terminal policy."""

    __slots__ = ("_stage_id", "_participants", "_initial_state", "_terminal_rule")

    def __init__(
        self,
        *,
        stage_id: str | None,
        participants: Iterable[ScenarioParticipant],
        initial_state: TerraBattleState,
        terminal_rule: CustomTerminalRule,
    ) -> None:
        if stage_id is not None:
            stage_id = _token(stage_id, "stage_id")
        items = tuple(participants)
        if not items or any(not isinstance(item, ScenarioParticipant) for item in items):
            raise CustomScenarioError("participants must be an explicit non-empty participant sequence")
        occurrences = {(item.side_id, item.formation_slot) for item in items}
        if len(occurrences) != len(items):
            raise CustomScenarioError("participant side/slot occurrences must be unique")
        if not isinstance(initial_state, TerraBattleState):
            raise CustomScenarioError("initial_state must be a complete TerraBattleState")
        if not isinstance(terminal_rule, CustomTerminalRule):
            raise CustomScenarioError("terminal_rule must be explicit")
        self._stage_id = stage_id
        self._participants = tuple(ScenarioParticipant(**item.to_dict()) for item in items)
        self._initial_state = initial_state.clone()
        self._terminal_rule = CustomTerminalRule(**{
            "namespace": terminal_rule.namespace,
            "version": terminal_rule.version,
            "rule_id": terminal_rule.rule_id,
            "empty_side_policy": terminal_rule.empty_side_policy,
            "simultaneous_exhaustion_policy": terminal_rule.simultaneous_exhaustion_policy,
            "result_policy": terminal_rule.result_policy,
        })

    @property
    def stage_id(self) -> str | None:
        return self._stage_id

    @property
    def participants(self) -> tuple[ScenarioParticipant, ...]:
        return tuple(ScenarioParticipant(**item.to_dict()) for item in self._participants)

    @property
    def initial_state(self) -> TerraBattleState:
        return self._initial_state.clone()

    @property
    def terminal_rule(self) -> CustomTerminalRule:
        return CustomTerminalRule(
            self._terminal_rule.namespace,
            self._terminal_rule.version,
            self._terminal_rule.rule_id,
            self._terminal_rule.empty_side_policy,
            self._terminal_rule.simultaneous_exhaustion_policy,
            self._terminal_rule.result_policy,
        )

    def policy_identity(self) -> SnapshotPolicyIdentity:
        rule = self._terminal_rule
        return SnapshotPolicyIdentity(
            evidence_mode=EvidenceMode.SANDBOX_EXTENSION,
            evidence_vocabulary_version="1",
            profile_id="terra.custom-scenario",
            profile_version="1",
            profile_content_sha256=hashlib.sha256(
                canonical_v2_bytes([item.to_dict() for item in self._participants])
            ).hexdigest(),
            rule_set_id=f"{rule.namespace}:{rule.rule_id}",
            rule_set_version=rule.version,
            rule_set_content_sha256=rule.content_sha256,
        )

    def snapshot(self) -> TerraSnapshotV2:
        return TerraSnapshotV2(state=self._initial_state, policy_identity=self.policy_identity())

    def semantic_hash(self) -> str:
        return semantic_hash_v2(self.snapshot())

    def evaluate_terminal(self, *, left_alive: int, right_alive: int) -> CustomTerminalResult:
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (left_alive, right_alive)):
            raise CustomScenarioError("alive counts must be explicit non-negative integers")
        exhausted = tuple(side for side, alive in (("left", left_alive), ("right", right_alive)) if alive == 0)
        rule = self._terminal_rule
        terminal = bool(exhausted) and rule.empty_side_policy is EmptySidePolicy.TERMINAL
        if not terminal:
            outcome = "CUSTOM_CONTINUE"
        elif len(exhausted) == 2:
            outcome = f"CUSTOM_SIMULTANEOUS_{rule.simultaneous_exhaustion_policy.value}"
        else:
            outcome = f"CUSTOM_{exhausted[0].upper()}_EXHAUSTED"
        return CustomTerminalResult(
            rule.namespace, rule.version, rule.rule_id, terminal, outcome,
            exhausted, rule.result_policy,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": "terra_custom_scenario/1",
            "evidence_mode": EvidenceMode.SANDBOX_EXTENSION.value,
            "participants": [item.to_dict() for item in self._participants],
            "initial_state": self._initial_state.to_dict(),
            "terminal_rule": self._terminal_rule.to_dict(),
        }
        if self._stage_id is not None:
            result["stage_id"] = self._stage_id
        return result
