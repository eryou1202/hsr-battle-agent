"""Atomic local-envelope battle sessions over REF02 reference settlement."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.legal_actions import (
    LegalActionProposal, LegalActionsStatus, LegalActionsView,
    query_player_legal_actions, settle_legal_action,
)
from hsr_battle_agent.battle_sandbox.revision import RevisionAndTransactionSequence
from hsr_battle_agent.battle_sandbox.snapshot_v2 import SnapshotPolicyIdentity, TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.game_data.damage_survival_reference import SurvivalState
from hsr_battle_agent.game_data.reference_damage_adapters import (
    ReferenceCombatState, ReferenceDamageResult, apply_reference_packet,
)
from hsr_battle_agent.game_data.reference_execution import (
    ExecutionContext, ReferenceBattleState, RuntimeEntity, SemanticExecutor,
)
from hsr_battle_agent.game_data.scheduler_semantics_reference import (
    OrdinaryTurnTimeline, TaskState, TaskStep, select_initial_ordinary_actor,
)

from .contract import (
    COMPLETION_POLICY, SCHEDULE_POLICY, TERMINAL_POLICY,
    ReferenceSandboxBlocked, ReferenceSessionSpec,
    _digest, combat_from_dict, combat_to_dict, timeline_from_dict,
)

_STORE = "scenario_runtime"
_KEY = "reference_sandbox/local_action_session/1"
_PAYLOAD_SCHEMA = "ReferenceBattleSessionState/1"
_STEP_SCHEMA = "ReferenceBattleStep/1"


def _policy(spec: ReferenceSessionSpec) -> SnapshotPolicyIdentity:
    rule = spec.scenario.terminal_rule
    return SnapshotPolicyIdentity(
        evidence_mode=EvidenceMode.SANDBOX_EXTENSION,
        evidence_vocabulary_version="1",
        profile_id="reference_sandbox.local_action_envelope",
        profile_version="1",
        profile_content_sha256=spec.identity,
        rule_set_id=f"{rule.namespace}:{rule.rule_id}:{TERMINAL_POLICY}",
        rule_set_version=rule.version,
        rule_set_content_sha256=_digest(
            {"custom_rule": rule.to_dict(), "local_max_actions": spec.max_actions},
            "reference-sandbox-terminal/1",
        ),
    )


def _payload(state: TerraBattleState, spec: ReferenceSessionSpec) -> dict[str, Any]:
    entries = [item for item in state.stores[_STORE].entries if item.key == _KEY]
    if not entries:
        raise ReferenceSandboxBlocked("MISSING_SESSION_STATE")
    for index, entry in enumerate(entries):
        if entry.occurrence != index:
            raise ReferenceSandboxBlocked("CORRUPT_SESSION_HISTORY")
    current = entries[-1].value.require_present()
    if not isinstance(current, dict) or set(current) != {
        "schema", "spec_identity", "step_index", "combat", "timeline", "terminal",
        "completed_actions", "action_evidence", "settlement_evidence", "orchestration_evidence"
    } or current["schema"] != _PAYLOAD_SCHEMA or current["spec_identity"] != spec.identity:
        raise ReferenceSandboxBlocked("CORRUPT_SESSION_STATE")
    if current["step_index"] != len(entries) - 1 or len(current["completed_actions"]) != current["step_index"]:
        raise ReferenceSandboxBlocked("CORRUPT_SESSION_HISTORY")
    known_envelopes = {item.identity for item in spec.envelopes}
    if any(identity not in known_envelopes for identity in current["completed_actions"]):
        raise ReferenceSandboxBlocked("CORRUPT_SESSION_HISTORY", "unknown completed action")
    if current["terminal"] != ("CUSTOM_TERMINAL" if current["step_index"] >= spec.max_actions else "CONTINUE"):
        raise ReferenceSandboxBlocked("CORRUPT_TERMINAL_STATE")
    if (current["action_evidence"], current["settlement_evidence"], current["orchestration_evidence"]) != (
        EvidenceMode.SANDBOX_EXTENSION.value, EvidenceMode.REFERENCE_MODEL.value,
        EvidenceMode.SANDBOX_EXTENSION.value,
    ):
        raise ReferenceSandboxBlocked("EVIDENCE_LABEL_MISMATCH")
    combat_from_dict(current["combat"])
    timeline_from_dict(current["timeline"])
    return copy.deepcopy(current)


def _initial_payload(spec: ReferenceSessionSpec, timeline: OrdinaryTurnTimeline) -> dict[str, Any]:
    return {"schema": _PAYLOAD_SCHEMA, "spec_identity": spec.identity,
            "step_index": 0, "combat": combat_to_dict(spec.combat_state),
            "timeline": timeline.as_json(), "terminal": "CONTINUE", "completed_actions": [],
            "action_evidence": EvidenceMode.SANDBOX_EXTENSION.value,
            "settlement_evidence": EvidenceMode.REFERENCE_MODEL.value,
            "orchestration_evidence": EvidenceMode.SANDBOX_EXTENSION.value}


def _candidate(source: TerraBattleState, payload: dict[str, Any], *, advance: bool) -> TerraBattleState:
    stores = dict(source.stores)
    stores[_STORE] = stores[_STORE].append(_KEY, payload)
    sequence = source.revision_sequence
    if advance:
        sequence = RevisionAndTransactionSequence(
            published_revision=sequence.published_revision.advance(contract="reference_sandbox.local_action_envelope/1"),
            replay_sequence=sequence.replay_sequence + 1,
            committed_effect_sequence=sequence.committed_effect_sequence + 1,
        )
    return TerraBattleState(stores=stores, opaque_stores=source.opaque_stores,
                            revision_sequence=sequence, allocator=source.allocator,
                            rng_state=source.rng_state)


def _legal_dict(view: LegalActionsView) -> dict[str, Any]:
    return {"status": view.status.value, "actions": [
        {"action_id": x.action_id, "candidate_occurrence_id": x.candidate_occurrence_id,
         "actor_id": x.actor_id, "target_ids": list(x.target_ids),
         "resource_cost": str(x.resource_cost), "evidence_mode": x.evidence_mode.value}
        for x in view.actions
    ], "blockers": list(view.blockers), "evidence_mode": view.evidence_mode.value,
            "completeness_scope": "CALLER_DECLARED_LOCAL_ENVELOPES_ONLY"}


def _schedule_after_success(spec: ReferenceSessionSpec, combat: ReferenceCombatState,
                            timeline: OrdinaryTurnTimeline, actor_id: str, index: int) -> tuple[OrdinaryTurnTimeline, dict[str, Any]]:
    # This SUCCESS is local orchestration. The reference scheduler only consumes
    # it as an explicit input; it does not establish native action completion.
    entities = {
        item.entity_id: RuntimeEntity(
            item.entity_id, "local", SurvivalState(item.hp, item.max_hp, item.shield,
                                                     alive=item.hp > 0),
            speed=spec.speeds[item.entity_id],
        )
        for item in combat.entities
    }
    task_id = f"local-action:{index}:{actor_id}"
    state = ReferenceBattleState(
        entities=entities, ordinary_turn_timeline=timeline,
        action_tasks={task_id: TaskStep(task_id, TaskState.SUCCESS, actor_id)},
    )
    result = SemanticExecutor().advance_ordinary_after_completed_action(
        state, ExecutionContext(action_task_id=task_id)
    )
    next_timeline = result.state.ordinary_turn_timeline
    if next_timeline is None:
        raise ReferenceSandboxBlocked("SCHEDULER_BLOCKED")
    return next_timeline, dict(result.trace[0])


@dataclass(frozen=True)
class ReferenceStepResult:
    session: "ReferenceBattleSession"
    record: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.record))


class ReferenceBattleSession:
    """Immutable publication boundary for a declared engineering battle."""

    __slots__ = ("_spec", "_initial", "_state")

    def __init__(self, spec: ReferenceSessionSpec, initial: TerraSnapshotV2,
                 state: TerraBattleState) -> None:
        self._spec = ReferenceSessionSpec.from_dict(spec.to_dict())
        self._initial = initial.clone()
        self._state = state.clone()
        _payload(self._state, self._spec)

    @classmethod
    def create(cls, spec: ReferenceSessionSpec) -> "ReferenceBattleSession":
        if not isinstance(spec, ReferenceSessionSpec):
            raise ReferenceSandboxBlocked("INVALID_SESSION_SPEC")
        initial = spec.scenario.initial_state
        if any(not store.is_empty() for store in initial.stores.values()):
            raise ReferenceSandboxBlocked("UNSUPPORTED_TERRA_INITIAL_FIELDS")
        if any(not store.is_empty() for store in initial.opaque_stores.values()):
            raise ReferenceSandboxBlocked("UNRESOLVED_TERRA_INITIAL_STATE")
        selected = select_initial_ordinary_actor(spec.timeline, spec.timeline.action_order)
        state = _candidate(initial, _initial_payload(spec, selected.timeline), advance=False)
        snapshot = TerraSnapshotV2(state=state, policy_identity=_policy(spec))
        return cls(spec, snapshot, state)

    @property
    def spec(self) -> ReferenceSessionSpec:
        return ReferenceSessionSpec.from_dict(self._spec.to_dict())

    @property
    def state(self) -> TerraBattleState:
        return self._state.clone()

    @property
    def initial_snapshot(self) -> TerraSnapshotV2:
        return self._initial.clone()

    def snapshot(self) -> TerraSnapshotV2:
        return TerraSnapshotV2(state=self._state, policy_identity=_policy(self._spec))

    def semantic_hash(self) -> str:
        return semantic_hash_v2(self.snapshot())

    def clone(self) -> "ReferenceBattleSession":
        return type(self)(self._spec, self._initial, self._state)

    @property
    def combat_state(self) -> ReferenceCombatState:
        return combat_from_dict(_payload(self._state, self._spec)["combat"])

    @property
    def acting_entity(self) -> str | None:
        data = _payload(self._state, self._spec)
        return None if data["terminal"] != "CONTINUE" else timeline_from_dict(data["timeline"]).current_actor_id

    def is_terminal(self) -> bool:
        return _payload(self._state, self._spec)["terminal"] == "CUSTOM_TERMINAL"

    def terminal_status(self) -> str:
        return _payload(self._state, self._spec)["terminal"]

    def legal_actions(self) -> LegalActionsView:
        data = _payload(self._state, self._spec)
        if data["terminal"] != "CONTINUE":
            return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("CUSTOM_TERMINAL",))
        actor = timeline_from_dict(data["timeline"]).current_actor_id
        if actor is None:
            return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("NO_ACTING_ENTITY",))
        available = f"ordinary:{actor}"
        combat = combat_from_dict(data["combat"])
        actor_envelopes = [x for x in self._spec.envelopes if x.actor_id == actor]
        if any(x.resource_cost > combat.resource_current for x in actor_envelopes):
            return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("INSUFFICIENT_LOCAL_RESOURCE",))
        timeline = timeline_from_dict(data["timeline"])
        if any(item.hp <= 0 for item in combat.entities):
            return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("UNRESOLVED_SURVIVAL",))
        for envelope in actor_envelopes:
            if envelope.target_ids[0] not in {item.entity_id for item in combat.entities}:
                return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("TARGET_NOT_PRESENT",))
            try:
                settlement = apply_reference_packet(
                    envelope.gate, combat, envelope.packet,
                    version=envelope.gate.source_version, sha256=envelope.gate.source_sha256,
                    scope=envelope.reference_scope,
                )
            except (ArithmeticError, ValueError, TypeError):
                return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("REFERENCE_SETTLEMENT_BLOCKED",))
            if not any(value != 0 for value in (
                settlement.hp_delta, settlement.shield_delta, settlement.toughness_delta,
                settlement.after.resource_current - combat.resource_current,
            )):
                return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("NO_COMBAT_MUTATION",))
            if any(item.hp <= 0 for item in settlement.after.entities):
                return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("UNRESOLVED_DEATH_CONTINUATION",))
            try:
                _schedule_after_success(self._spec, settlement.after, timeline,
                                        actor, data["step_index"] + 1)
            except (ArithmeticError, ValueError, TypeError):
                return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("SCHEDULER_BLOCKED",))
        proposals = [LegalActionProposal(
            x.action_id, x.candidate_occurrence_id, x.actor_id, tuple(x.target_ids),
            x.resource_cost, True, True,
        ) for x in actor_envelopes]
        if not proposals:
            return LegalActionsView(LegalActionsStatus.BLOCKED, (), ("NO_LOCAL_ENVELOPE",))
        return query_player_legal_actions((available,), proposals)

    def step(self, action_id: str, *, failure_point: str | None = None) -> ReferenceStepResult:
        before = self.snapshot()
        before_hash = semantic_hash_v2(before)
        data = _payload(self._state, self._spec)
        view = self.legal_actions()
        if view.status is not LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE:
            raise ReferenceSandboxBlocked("LEGAL_ACTIONS_BLOCKED", ",".join(view.blockers))
        matches = [x for x in self._spec.envelopes if x.action_id == action_id and x.actor_id == self.acting_entity]
        if len(matches) != 1 or len([x for x in view.actions if x.action_id == action_id]) != 1:
            raise ReferenceSandboxBlocked("ACTION_NOT_LEGAL", str(action_id))
        envelope = matches[0]
        combat = combat_from_dict(data["combat"])
        timeline = timeline_from_dict(data["timeline"])
        if envelope.target_ids[0] not in {x.entity_id for x in combat.entities}:
            raise ReferenceSandboxBlocked("TARGET_NOT_PRESENT")
        if any(x.hp <= 0 for x in combat.entities):
            raise ReferenceSandboxBlocked("UNRESOLVED_SURVIVAL")
        try:
            after_resource = settle_legal_action(view, action_id, combat.resource_current)
            settlement: ReferenceDamageResult = apply_reference_packet(
                envelope.gate, combat, envelope.packet,
                version=envelope.gate.source_version, sha256=envelope.gate.source_sha256,
                scope=envelope.reference_scope,
            )
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise ReferenceSandboxBlocked("REFERENCE_SETTLEMENT_BLOCKED", str(exc)) from exc
        if settlement.after.resource_current != after_resource or settlement.evidence_mode is not EvidenceMode.REFERENCE_MODEL:
            raise ReferenceSandboxBlocked("SETTLEMENT_INTEGRITY_BLOCKED")
        if not any(value != 0 for value in (
            settlement.hp_delta, settlement.shield_delta, settlement.toughness_delta,
            settlement.after.resource_current - combat.resource_current,
        )):
            raise ReferenceSandboxBlocked("NO_COMBAT_MUTATION")
        # No local death/revive or break callback model is declared. A lethal
        # result is a valid REF02 result but outside this session's next-turn scope.
        if any(x.hp <= 0 for x in settlement.after.entities):
            raise ReferenceSandboxBlocked("UNRESOLVED_DEATH_CONTINUATION")
        try:
            next_timeline, schedule_trace = _schedule_after_success(
                self._spec, settlement.after, timeline, envelope.actor_id, data["step_index"] + 1
            )
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise ReferenceSandboxBlocked("SCHEDULER_BLOCKED", str(exc)) from exc
        if failure_point == "after_preflight":
            raise ReferenceSandboxBlocked("INJECTED_FAILURE", failure_point)
        if failure_point not in (None, "after_preflight", "before_publication"):
            raise ReferenceSandboxBlocked("INVALID_FAILURE_POINT")
        next_index = data["step_index"] + 1
        next_payload = copy.deepcopy(data)
        next_payload.update({
            "step_index": next_index, "combat": combat_to_dict(settlement.after),
            "timeline": next_timeline.as_json(),
            "terminal": "CUSTOM_TERMINAL" if next_index >= self._spec.max_actions else "CONTINUE",
            "completed_actions": data["completed_actions"] + [envelope.identity],
        })
        candidate = _candidate(self._state, next_payload, advance=True)
        if failure_point == "before_publication":
            raise ReferenceSandboxBlocked("INJECTED_FAILURE", failure_point)
        next_session = type(self)(self._spec, self._initial, candidate)
        after = next_session.snapshot()
        after_hash = semantic_hash_v2(after)
        settlement_result_identity = _digest({
            "before": combat_to_dict(combat), "after": combat_to_dict(settlement.after),
            "amount": str(settlement.amount), "hp_delta": str(settlement.hp_delta),
            "shield_delta": str(settlement.shield_delta), "toughness_delta": str(settlement.toughness_delta),
        }, "reference-settlement-result/1")
        record = {
            "schema": _STEP_SCHEMA, "step_index": next_index,
            "before_snapshot": before.to_dict(), "after_snapshot": after.to_dict(),
            "before_hash": before_hash, "after_hash": after_hash,
            "before_revision": before.state.revision_sequence.to_dict(),
            "after_revision": after.state.revision_sequence.to_dict(),
            "before_rng": before.state.rng_state.to_dict(), "after_rng": after.state.rng_state.to_dict(),
            "before_allocator": before.state.allocator.to_dict(), "after_allocator": after.state.allocator.to_dict(),
            "acting_entity": envelope.actor_id, "legal_actions": _legal_dict(view),
            "selected_action_id": action_id, "target_ids": list(envelope.target_ids),
            "action_envelope_identity": envelope.identity,
            "reference_settlement_identity": envelope.settlement_identity,
            "reference_result_identity": settlement_result_identity,
            "reference_before": combat_to_dict(combat), "reference_after": combat_to_dict(settlement.after),
            "reference_amount": str(settlement.amount),
            "hp_delta": str(settlement.hp_delta), "shield_delta": str(settlement.shield_delta),
            "toughness_delta": str(settlement.toughness_delta),
            "resource_delta": str(settlement.after.resource_current - combat.resource_current),
            "timeline_before": timeline.as_json(), "timeline_after": next_timeline.as_json(),
            "schedule_trace": schedule_trace, "next_actor": next_session.acting_entity,
            "completion_policy": COMPLETION_POLICY, "schedule_policy": SCHEDULE_POLICY,
            "terminal_policy": TERMINAL_POLICY, "terminal_status": next_session.terminal_status(),
            "declared_reads": ["scenario_runtime", "reference_combat", "ordinary_timeline", "local_action_envelopes"],
            "declared_writes": ["scenario_runtime", "revision_and_transaction_sequence"],
            "action_evidence": EvidenceMode.SANDBOX_EXTENSION.value,
            "settlement_evidence": EvidenceMode.REFERENCE_MODEL.value,
            "orchestration_evidence": EvidenceMode.SANDBOX_EXTENSION.value,
            "validation": "DETERMINISTIC_REPLAY_ONLY",
        }
        record["identity"] = _digest(record, "reference-battle-step/1")
        return ReferenceStepResult(next_session, record)
