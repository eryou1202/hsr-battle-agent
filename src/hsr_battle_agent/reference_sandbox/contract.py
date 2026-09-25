"""Explicit local action envelopes; never a recovered HSR skill catalogue."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes
from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario, CustomTerminalRule, EmptySidePolicy, ResultPolicy,
    ScenarioParticipant, SimultaneousExhaustionPolicy,
)
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.game_data.reference_damage_adapters import (
    OrdinaryReferencePacket, PacketKind, ReferenceCombatState, ReferenceEntityState,
)
from hsr_battle_agent.game_data.reference_operation_adapters import ReferenceAdapterGate
from hsr_battle_agent.game_data.scheduler_semantics_reference import OrdinaryTurnTimeline

SCOPE = "REFERENCE_BATTLE_SANDBOX_V1_LOCAL_ACTION_ENVELOPE"
COMPLETION_POLICY = "LOCAL_ACTION_COMMIT_MEANS_COMPLETED_SUCCESS/1"
SCHEDULE_POLICY = "REFERENCE_ORDINARY_AFTER_LOCAL_SUCCESS/1"
TERMINAL_POLICY = "LOCAL_MAX_COMMITTED_ACTIONS/1"


class ReferenceSandboxBlocked(ValueError):
    """The declared local scope cannot be executed without guessing."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


def _token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReferenceSandboxBlocked("INVALID_CONTRACT", name)
    return value


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ReferenceSandboxBlocked("INVALID_JSON_PAYLOAD", str(exc)) from exc


def _digest(value: Any, domain: str) -> str:
    return hashlib.sha256(domain.encode("utf-8") + b"\0" + canonical_v2_bytes(value)).hexdigest()


def combat_to_dict(state: ReferenceCombatState) -> dict[str, Any]:
    return {
        "schema": "reference_combat_state/1",
        "entities": [
            {"entity_id": e.entity_id, "hp": str(e.hp), "max_hp": str(e.max_hp),
             "shield": str(e.shield), "toughness": str(e.toughness)}
            for e in state.entities
        ],
        "resource_owner": state.resource_owner,
        "resource_current": str(state.resource_current),
        "timeline_token": state.timeline_token,
    }


def combat_from_dict(data: Mapping[str, Any]) -> ReferenceCombatState:
    if not isinstance(data, Mapping) or set(data) != {
        "schema", "entities", "resource_owner", "resource_current", "timeline_token"
    } or data["schema"] != "reference_combat_state/1":
        raise ReferenceSandboxBlocked("INVALID_COMBAT_STATE")
    raw = data["entities"]
    if not isinstance(raw, list) or not raw:
        raise ReferenceSandboxBlocked("INVALID_COMBAT_STATE", "entities")
    entities = []
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != {
            "entity_id", "hp", "max_hp", "shield", "toughness"
        }:
            raise ReferenceSandboxBlocked("INVALID_COMBAT_STATE", "entity shape")
        numbers = tuple(Decimal(item[key]) for key in ("hp", "max_hp", "shield", "toughness"))
        if not all(value.is_finite() for value in numbers):
            raise ReferenceSandboxBlocked("INVALID_COMBAT_STATE", "nonfinite value")
        entities.append(ReferenceEntityState(_token(item["entity_id"], "entity_id"), *numbers))
    resource = Decimal(data["resource_current"])
    if not resource.is_finite():
        raise ReferenceSandboxBlocked("INVALID_COMBAT_STATE", "nonfinite resource")
    return ReferenceCombatState(tuple(entities), _token(data["resource_owner"], "resource_owner"),
                                resource, _token(data["timeline_token"], "timeline_token"))


def timeline_from_dict(data: Mapping[str, Any]) -> OrdinaryTurnTimeline:
    if not isinstance(data, Mapping) or set(data) != {
        "action_order", "remaining_delays", "current_actor_id", "elapsed_action_delay", "turn_index"
    }:
        raise ReferenceSandboxBlocked("INVALID_TIMELINE")
    if not isinstance(data["action_order"], list) or not isinstance(data["remaining_delays"], Mapping):
        raise ReferenceSandboxBlocked("INVALID_TIMELINE")
    delays = {key: Decimal(value) for key, value in data["remaining_delays"].items()}
    elapsed = Decimal(data["elapsed_action_delay"])
    if any(not value.is_finite() for value in delays.values()) or not elapsed.is_finite():
        raise ReferenceSandboxBlocked("INVALID_TIMELINE", "nonfinite delay")
    if isinstance(data["turn_index"], bool) or not isinstance(data["turn_index"], int):
        raise ReferenceSandboxBlocked("INVALID_TIMELINE", "turn index")
    return OrdinaryTurnTimeline(
        tuple(data["action_order"]),
        delays, data["current_actor_id"], elapsed, data["turn_index"],
    )


def scenario_from_dict(data: Mapping[str, Any]) -> CustomScenario:
    if not isinstance(data, Mapping) or data.get("schema") != "terra_custom_scenario/1" or data.get("evidence_mode") != EvidenceMode.SANDBOX_EXTENSION.value:
        raise ReferenceSandboxBlocked("INVALID_SCENARIO")
    if set(data) not in ({"schema", "evidence_mode", "participants", "initial_state", "terminal_rule"},
                         {"schema", "evidence_mode", "participants", "initial_state", "terminal_rule", "stage_id"}):
        raise ReferenceSandboxBlocked("INVALID_SCENARIO", "shape")
    rule = data["terminal_rule"]
    if not isinstance(rule, Mapping) or set(rule) != {
        "namespace", "version", "rule_id", "empty_side_policy",
        "simultaneous_exhaustion_policy", "result_policy"
    }:
        raise ReferenceSandboxBlocked("INVALID_SCENARIO", "terminal rule")
    return CustomScenario(
        stage_id=data.get("stage_id"),
        participants=tuple(ScenarioParticipant(**item) for item in data["participants"]),
        initial_state=TerraBattleState.from_dict(data["initial_state"]),
        terminal_rule=CustomTerminalRule(
            rule["namespace"], rule["version"], rule["rule_id"],
            EmptySidePolicy(rule["empty_side_policy"]),
            SimultaneousExhaustionPolicy(rule["simultaneous_exhaustion_policy"]),
            ResultPolicy(rule["result_policy"]),
        ),
    )


@dataclass(frozen=True)
class ReferenceActionEnvelope:
    namespace: str
    version: str
    action_id: str
    actor_id: str
    target_ids: tuple[str, ...]
    candidate_occurrence_id: str
    fixture_id: str
    packet: Mapping[str, Any]
    gate: ReferenceAdapterGate
    local_resource_cost: Decimal
    reference_scope: str = "ordinary"
    completion_policy: str = COMPLETION_POLICY
    schedule_policy: str = SCHEDULE_POLICY

    def __post_init__(self) -> None:
        for key in ("namespace", "version", "action_id", "actor_id", "candidate_occurrence_id", "fixture_id"):
            _token(getattr(self, key), key)
        if self.completion_policy != COMPLETION_POLICY or self.schedule_policy != SCHEDULE_POLICY:
            raise ReferenceSandboxBlocked("UNSUPPORTED_LOCAL_POLICY")
        if self.reference_scope != "ordinary" or not isinstance(self.gate, ReferenceAdapterGate):
            raise ReferenceSandboxBlocked("UNSUPPORTED_REFERENCE_SCOPE")
        targets = tuple(self.target_ids)
        if len(targets) != 1 or not all(isinstance(x, str) and x for x in targets):
            raise ReferenceSandboxBlocked("UNSUPPORTED_TARGETS")
        object.__setattr__(self, "target_ids", targets)
        raw = _json_copy(self.packet)
        parsed = OrdinaryReferencePacket.from_dict(raw)
        if parsed.kind not in (PacketKind.ORDINARY_DAMAGE, PacketKind.EXPLICIT_HEAL):
            raise ReferenceSandboxBlocked("UNSUPPORTED_SETTLEMENT_KIND")
        if parsed.source_id != self.actor_id or parsed.targets != targets:
            raise ReferenceSandboxBlocked("ENVELOPE_PACKET_MISMATCH", "actor or targets")
        try:
            cost = Decimal(self.local_resource_cost)
        except (TypeError, ValueError) as exc:
            raise ReferenceSandboxBlocked("INVALID_LOCAL_RESOURCE_COST") from exc
        if not cost.is_finite() or cost < 0 or cost != parsed.resource_cost:
            raise ReferenceSandboxBlocked("LOCAL_REFERENCE_COST_MISMATCH")
        object.__setattr__(self, "local_resource_cost", cost)
        self.gate.require(version=self.gate.source_version, sha256=self.gate.source_sha256,
                          scope=self.reference_scope, owner=self.actor_id)
        object.__setattr__(self, "packet", raw)

    @property
    def resource_cost(self) -> Decimal:
        return self.local_resource_cost

    @property
    def settlement_identity(self) -> str:
        return _digest({"fixture_id": self.fixture_id, "gate": self._gate_dict(),
                        "scope": self.reference_scope, "packet": self.packet}, "reference-settlement/1")

    def _gate_dict(self) -> dict[str, Any]:
        return {"adapter_id": self.gate.adapter_id, "source_version": self.gate.source_version,
                "source_sha256": self.gate.source_sha256, "allowed_scopes": list(self.gate.allowed_scopes),
                "allowed_owners": list(self.gate.allowed_owners), "evidence_mode": self.gate.evidence_mode.value}

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "ReferenceActionEnvelope/1", "namespace": self.namespace,
                "version": self.version, "action_id": self.action_id, "actor_id": self.actor_id,
                "target_ids": list(self.target_ids), "candidate_occurrence_id": self.candidate_occurrence_id,
                "fixture_id": self.fixture_id, "reference_scope": self.reference_scope,
                "packet": _json_copy(self.packet), "gate": self._gate_dict(),
                "local_resource_cost": str(self.local_resource_cost),
                "reference_settlement_identity": self.settlement_identity,
                "completion_policy": self.completion_policy, "schedule_policy": self.schedule_policy,
                "action_evidence": EvidenceMode.SANDBOX_EXTENSION.value,
                "settlement_evidence": EvidenceMode.REFERENCE_MODEL.value,
                "orchestration_evidence": EvidenceMode.SANDBOX_EXTENSION.value}

    @property
    def identity(self) -> str:
        return _digest(self.to_dict(), "reference-action-envelope/1")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReferenceActionEnvelope":
        if not isinstance(data, Mapping) or set(data) != set(cls._fields()) or data.get("schema") != "ReferenceActionEnvelope/1":
            raise ReferenceSandboxBlocked("INVALID_ENVELOPE")
        if (data["action_evidence"], data["settlement_evidence"], data["orchestration_evidence"]) != (
            EvidenceMode.SANDBOX_EXTENSION.value, EvidenceMode.REFERENCE_MODEL.value,
            EvidenceMode.SANDBOX_EXTENSION.value
        ):
            raise ReferenceSandboxBlocked("EVIDENCE_LABEL_MISMATCH")
        gate = data["gate"]
        if not isinstance(gate, Mapping) or set(gate) != {
            "adapter_id", "source_version", "source_sha256", "allowed_scopes", "allowed_owners", "evidence_mode"
        } or gate["evidence_mode"] != EvidenceMode.REFERENCE_MODEL.value:
            raise ReferenceSandboxBlocked("INVALID_REFERENCE_GATE")
        result = cls(data["namespace"], data["version"], data["action_id"], data["actor_id"],
                   tuple(data["target_ids"]), data["candidate_occurrence_id"], data["fixture_id"],
                   data["packet"], ReferenceAdapterGate(gate["adapter_id"], gate["source_version"],
                   gate["source_sha256"], tuple(gate["allowed_scopes"]), tuple(gate["allowed_owners"])),
                   Decimal(data["local_resource_cost"]), data["reference_scope"],
                   data["completion_policy"], data["schedule_policy"])
        if data["reference_settlement_identity"] != result.settlement_identity:
            raise ReferenceSandboxBlocked("SETTLEMENT_IDENTITY_MISMATCH")
        return result

    @staticmethod
    def _fields() -> tuple[str, ...]:
        return ("schema", "namespace", "version", "action_id", "actor_id", "target_ids",
                "candidate_occurrence_id", "fixture_id", "reference_scope", "packet", "gate",
                "local_resource_cost", "reference_settlement_identity",
                "completion_policy", "schedule_policy", "action_evidence", "settlement_evidence",
                "orchestration_evidence")


class ReferenceSessionSpec:
    """Complete caller declaration for one bounded local battle session."""

    def __init__(self, *, scenario: CustomScenario, combat_state: ReferenceCombatState,
                 envelopes: tuple[ReferenceActionEnvelope, ...], timeline: OrdinaryTurnTimeline,
                 speeds: Mapping[str, Decimal], max_actions: int) -> None:
        if not isinstance(scenario, CustomScenario) or not isinstance(combat_state, ReferenceCombatState):
            raise ReferenceSandboxBlocked("INVALID_INITIAL_SPEC")
        if scenario.terminal_rule.empty_side_policy is not EmptySidePolicy.NON_TERMINAL:
            raise ReferenceSandboxBlocked("UNSUPPORTED_CUSTOM_TERMINAL_POLICY")
        if not isinstance(timeline, OrdinaryTurnTimeline) or timeline.current_actor_id is not None or timeline.turn_index != 0:
            raise ReferenceSandboxBlocked("INVALID_INITIAL_TIMELINE")
        if isinstance(max_actions, bool) or not isinstance(max_actions, int) or max_actions < 1:
            raise ReferenceSandboxBlocked("INVALID_TERMINAL_BOUND")
        actors = tuple(item.participant_id for item in scenario.participants)
        if len(set(actors)) != len(actors) or set(actors) != {x.entity_id for x in combat_state.entities} or set(actors) != set(timeline.action_order):
            raise ReferenceSandboxBlocked("PARTICIPANT_MISMATCH")
        if not isinstance(speeds, Mapping) or set(speeds) != set(actors):
            raise ReferenceSandboxBlocked("SPEED_SCOPE_MISMATCH")
        speed_map = {key: Decimal(value) for key, value in speeds.items()}
        if any(not value.is_finite() or value <= 0 for value in speed_map.values()):
            raise ReferenceSandboxBlocked("INVALID_SPEED")
        items = tuple(envelopes)
        if not items or any(not isinstance(x, ReferenceActionEnvelope) for x in items):
            raise ReferenceSandboxBlocked("INCOMPLETE_LOCAL_ACTION_SCOPE")
        if len({x.action_id for x in items}) != len(items) or {x.actor_id for x in items} != set(actors):
            raise ReferenceSandboxBlocked("INCOMPLETE_LOCAL_ACTION_SCOPE")
        if any(x.candidate_occurrence_id != f"ordinary:{x.actor_id}" for x in items):
            raise ReferenceSandboxBlocked("CANDIDATE_MISMATCH")
        if any(x.packet["resource_owner"] != combat_state.resource_owner for x in items):
            raise ReferenceSandboxBlocked("RESOURCE_OWNER_MISMATCH")
        if any(x.entity_id == "" or x.hp <= 0 for x in combat_state.entities):
            raise ReferenceSandboxBlocked("UNSUPPORTED_INITIAL_SURVIVAL")
        self.scenario = scenario_from_dict(scenario.to_dict())
        self.combat_state = combat_from_dict(combat_to_dict(combat_state))
        self.envelopes = tuple(ReferenceActionEnvelope.from_dict(x.to_dict()) for x in items)
        self.timeline = timeline_from_dict(timeline.as_json())
        self.speeds = dict(speed_map)
        self.max_actions = max_actions

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "ReferenceSessionSpec/1", "scenario": self.scenario.to_dict(),
                "combat_state": combat_to_dict(self.combat_state),
                "envelopes": [x.to_dict() for x in self.envelopes],
                "timeline": self.timeline.as_json(),
                "speeds": {key: str(value) for key, value in sorted(self.speeds.items())},
                "max_actions": self.max_actions, "terminal_policy": TERMINAL_POLICY,
                "validation": "DETERMINISTIC_REPLAY_ONLY"}

    @property
    def identity(self) -> str:
        return _digest(self.to_dict(), "reference-session-spec/1")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReferenceSessionSpec":
        if not isinstance(data, Mapping) or set(data) != {
            "schema", "scenario", "combat_state", "envelopes", "timeline", "speeds",
            "max_actions", "terminal_policy", "validation"
        } or data["schema"] != "ReferenceSessionSpec/1" or data["terminal_policy"] != TERMINAL_POLICY or data["validation"] != "DETERMINISTIC_REPLAY_ONLY":
            raise ReferenceSandboxBlocked("INVALID_SESSION_SPEC")
        return cls(scenario=scenario_from_dict(data["scenario"]), combat_state=combat_from_dict(data["combat_state"]),
                   envelopes=tuple(ReferenceActionEnvelope.from_dict(x) for x in data["envelopes"]),
                   timeline=timeline_from_dict(data["timeline"]),
                   speeds={key: Decimal(value) for key, value in data["speeds"].items()},
                   max_actions=data["max_actions"])
