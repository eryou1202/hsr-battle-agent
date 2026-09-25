"""Two committed REF02 settlements under explicitly local action admission."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario, CustomTerminalRule, EmptySidePolicy, ResultPolicy,
    ScenarioParticipant, SimultaneousExhaustionPolicy,
)
from hsr_battle_agent.battle_sandbox.identity import IdentityAllocator
from hsr_battle_agent.battle_sandbox.revision import RevisionAndTransactionSequence, StateRevision
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.game_data.reference_damage_adapters import ReferenceCombatState, ReferenceEntityState
from hsr_battle_agent.game_data.reference_operation_adapters import ReferenceAdapterGate
from hsr_battle_agent.game_data.scheduler_semantics_reference import OrdinaryTurnTimeline
from hsr_battle_agent.reference_sandbox import (
    COMPLETION_POLICY, ReferenceActionEnvelope, ReferenceBattleSession,
    ReferenceSandboxBlocked, ReferenceSessionSpec, make_replay_record, replay_session,
)
from tests.game_data.test_reference_damage_v2 import HASH, packet


def fixture() -> ReferenceSessionSpec:
    terra = TerraBattleState(
        revision_sequence=RevisionAndTransactionSequence(StateRevision.initial("m10-local", lineage="m10"), 0, 0),
        allocator=IdentityAllocator(), rng_state=SandboxRng(7),
    )
    scenario = CustomScenario(
        stage_id=None,
        participants=(ScenarioParticipant("actor-a", "left", 0), ScenarioParticipant("actor-b", "right", 0)),
        initial_state=terra,
        terminal_rule=CustomTerminalRule(
            "local.m10", "1", "two-actions", EmptySidePolicy.NON_TERMINAL,
            SimultaneousExhaustionPolicy.UNRESOLVED, ResultPolicy.REPORT_CUSTOM_OUTCOME,
        ),
    )
    combat = ReferenceCombatState((
        ReferenceEntityState("actor-a", Decimal("100"), Decimal("100"), Decimal("0"), Decimal("30")),
        ReferenceEntityState("actor-b", Decimal("100"), Decimal("100"), Decimal("0"), Decimal("30")),
    ), "team-local", Decimal("5"), "local-ordinary-timeline")
    gate = ReferenceAdapterGate("damage/1", "4.4.54", HASH, ("ordinary",), ("actor-a", "actor-b"))
    envelopes = []
    for actor, target in (("actor-a", "actor-b"), ("actor-b", "actor-a")):
        raw = packet()
        raw.update(source_id=actor, targets=[target], resource_owner="team-local")
        envelopes.append(ReferenceActionEnvelope(
            "local.m10", "1", f"{actor}:ordinary", actor, (target,), f"ordinary:{actor}",
            "tests/game_data/test_reference_damage_v2.py:packet", raw, gate, Decimal("2"),
        ))
    return ReferenceSessionSpec(
        scenario=scenario, combat_state=combat, envelopes=tuple(envelopes),
        timeline=OrdinaryTurnTimeline(
            ("actor-a", "actor-b"), {"actor-a": Decimal("0"), "actor-b": Decimal("1")}
        ),
        speeds={"actor-a": Decimal("100"), "actor-b": Decimal("100")}, max_actions=2,
    )


class LocalReferenceSessionTests(unittest.TestCase):
    def test_reset_two_turn_mutation_clone_and_replay(self) -> None:
        spec = fixture()
        initial = ReferenceBattleSession.create(spec)
        self.assertEqual(initial.acting_entity, "actor-a")
        self.assertEqual(initial.combat_state.entity("actor-b").hp, Decimal("100"))
        self.assertEqual(initial.state.revision.counter, 0)
        self.assertEqual([a.action_id for a in initial.legal_actions().actions], ["actor-a:ordinary"])
        self.assertEqual(initial.legal_actions().status.value, "COMPLETE_FOR_SUPPORTED_SCOPE")
        self.assertEqual(initial.clone().snapshot(), initial.snapshot())
        self.assertEqual(ReferenceBattleSession.create(spec).semantic_hash(), initial.semantic_hash())

        first = initial.step("actor-a:ordinary")
        one = first.session
        self.assertEqual(one.combat_state.entity("actor-b").hp, Decimal("90"))
        self.assertEqual(one.combat_state.entity("actor-b").toughness, Decimal("26"))
        self.assertEqual(one.combat_state.resource_current, Decimal("3"))
        self.assertEqual(one.acting_entity, "actor-b")
        self.assertEqual(one.state.revision.counter, 1)
        self.assertEqual(first.record["hp_delta"], "-10.0")
        self.assertEqual(first.record["settlement_evidence"], "REFERENCE_MODEL")
        self.assertEqual(first.record["action_evidence"], "SANDBOX_EXTENSION")
        self.assertEqual(first.record["completion_policy"], COMPLETION_POLICY)
        self.assertEqual(initial.combat_state.entity("actor-b").hp, Decimal("100"))
        self.assertEqual(initial.state.revision.counter, 0)

        second = one.step("actor-b:ordinary")
        two = second.session
        self.assertEqual(two.combat_state.entity("actor-a").hp, Decimal("90"))
        self.assertEqual(two.combat_state.resource_current, Decimal("1"))
        self.assertTrue(two.is_terminal())
        self.assertEqual(two.terminal_status(), "CUSTOM_TERMINAL")
        self.assertEqual(two.state.revision.counter, 2)
        self.assertEqual(two.legal_actions().status.value, "BLOCKED")
        self.assertEqual(two.clone().semantic_hash(), two.semantic_hash())
        self.assertEqual(two.snapshot().restore_state(), two.state)
        self.assertEqual(one.state.rng_state.to_dict(), initial.state.rng_state.to_dict())
        self.assertEqual(two.state.allocator.to_dict(), initial.state.allocator.to_dict())

        serialized = json.loads(json.dumps(make_replay_record(initial, (first, second))))
        self.assertEqual(replay_session(serialized).semantic_hash(), two.semantic_hash())
        repeated_initial = ReferenceBattleSession.create(spec)
        repeated_first = repeated_initial.step("actor-a:ordinary")
        repeated_second = repeated_first.session.step("actor-b:ordinary")
        self.assertEqual(
            json.dumps(make_replay_record(initial, (first, second)), sort_keys=True),
            json.dumps(make_replay_record(repeated_initial, (repeated_first, repeated_second)), sort_keys=True),
        )

    def test_rejection_is_byte_exact_and_late_packet_field_blocks(self) -> None:
        initial = ReferenceBattleSession.create(fixture())
        before = initial.snapshot().to_dict()
        for action, failure in (("missing", None), ("actor-a:ordinary", "after_preflight"),
                                ("actor-a:ordinary", "before_publication")):
            with self.subTest(action=action, failure=failure), self.assertRaises(ReferenceSandboxBlocked):
                initial.step(action, failure_point=failure)
            self.assertEqual(initial.snapshot().to_dict(), before)
        bad = fixture().envelopes[0].to_dict()
        bad["packet"]["SPHitRatio"] = "0.5"
        with self.assertRaises(ValueError):
            ReferenceActionEnvelope.from_dict(bad)
        wrong_cost = fixture().envelopes[0].to_dict()
        wrong_cost["local_resource_cost"] = "1"
        with self.assertRaisesRegex(ReferenceSandboxBlocked, "LOCAL_REFERENCE_COST_MISMATCH"):
            ReferenceActionEnvelope.from_dict(wrong_cost)
        wrong_identity = fixture().envelopes[0].to_dict()
        wrong_identity["reference_settlement_identity"] = "bad"
        with self.assertRaisesRegex(ReferenceSandboxBlocked, "SETTLEMENT_IDENTITY_MISMATCH"):
            ReferenceActionEnvelope.from_dict(wrong_identity)
        self.assertEqual(initial.snapshot().to_dict(), before)

        lethal_spec = fixture()
        lethal = lethal_spec.envelopes[0].to_dict()
        lethal["packet"]["base_value"] = "1000"
        original = lethal_spec.envelopes[0]
        lethal_envelope = ReferenceActionEnvelope(
            original.namespace, original.version, original.action_id, original.actor_id,
            original.target_ids, original.candidate_occurrence_id, original.fixture_id,
            lethal["packet"], original.gate, original.local_resource_cost,
        )
        lethal_spec = ReferenceSessionSpec(
            scenario=lethal_spec.scenario, combat_state=lethal_spec.combat_state,
            envelopes=(lethal_envelope, lethal_spec.envelopes[1]),
            timeline=lethal_spec.timeline, speeds=lethal_spec.speeds, max_actions=2,
        )
        lethal_session = ReferenceBattleSession.create(lethal_spec)
        lethal_before = lethal_session.snapshot().to_dict()
        self.assertEqual(lethal_session.legal_actions().status.value, "BLOCKED")
        self.assertEqual(lethal_session.legal_actions().blockers, ("UNRESOLVED_DEATH_CONTINUATION",))
        with self.assertRaisesRegex(ReferenceSandboxBlocked, "LEGAL_ACTIONS_BLOCKED"):
            lethal_session.step("actor-a:ordinary")
        self.assertEqual(lethal_session.snapshot().to_dict(), lethal_before)

    def test_initial_terra_families_cannot_be_ignored(self) -> None:
        spec = fixture()
        stores = dict(spec.scenario.initial_state.stores)
        stores["survival"] = stores["survival"].append("actor-a", {"hp": "1"})
        initial = spec.scenario.initial_state
        occupied = TerraBattleState(
            revision_sequence=initial.revision_sequence, allocator=initial.allocator,
            rng_state=initial.rng_state, stores=stores, opaque_stores=initial.opaque_stores,
        )
        scenario = CustomScenario(
            stage_id=None, participants=spec.scenario.participants, initial_state=occupied,
            terminal_rule=spec.scenario.terminal_rule,
        )
        blocked_spec = ReferenceSessionSpec(
            scenario=scenario, combat_state=spec.combat_state, envelopes=spec.envelopes,
            timeline=spec.timeline, speeds=spec.speeds, max_actions=2,
        )
        with self.assertRaisesRegex(ReferenceSandboxBlocked, "UNSUPPORTED_TERRA_INITIAL_FIELDS"):
            ReferenceBattleSession.create(blocked_spec)

    def test_insufficient_declared_reference_resource_blocks_complete_view(self) -> None:
        spec = fixture()
        combat = ReferenceCombatState(spec.combat_state.entities, "team-local", Decimal("1"),
                                      spec.combat_state.timeline_token)
        blocked_spec = ReferenceSessionSpec(
            scenario=spec.scenario, combat_state=combat, envelopes=spec.envelopes,
            timeline=spec.timeline, speeds=spec.speeds, max_actions=2,
        )
        session = ReferenceBattleSession.create(blocked_spec)
        before = session.snapshot().to_dict()
        view = session.legal_actions()
        self.assertEqual(view.status.value, "BLOCKED")
        self.assertEqual(view.actions, ())
        self.assertEqual(view.blockers, ("INSUFFICIENT_LOCAL_RESOURCE",))
        with self.assertRaisesRegex(ReferenceSandboxBlocked, "LEGAL_ACTIONS_BLOCKED"):
            session.step("actor-a:ordinary")
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_replay_rejects_every_recorded_decision_and_evidence_tamper(self) -> None:
        initial = ReferenceBattleSession.create(fixture())
        first = initial.step("actor-a:ordinary")
        second = first.session.step("actor-b:ordinary")
        record = make_replay_record(initial, (first, second))
        edits = (
            ("selected_action_id", "actor-b:ordinary"),
            ("target_ids", ["actor-a"]),
            ("hp_delta", "-9"),
            ("next_actor", "actor-a"),
            ("completion_policy", "OTHER"),
            ("schedule_policy", "OTHER"),
            ("settlement_evidence", "NATIVE_EVIDENCED"),
            ("action_envelope_identity", "bad"),
            ("reference_settlement_identity", "bad"),
            ("reference_after", {}),
        )
        for field, value in edits:
            with self.subTest(field=field):
                corrupted = copy.deepcopy(record)
                corrupted["steps"][0][field] = value
                with self.assertRaises(ReferenceSandboxBlocked):
                    replay_session(corrupted)
        corrupted = copy.deepcopy(record)
        corrupted["spec"]["envelopes"][0]["packet"]["base_value"] = "11"
        with self.assertRaises(ReferenceSandboxBlocked):
            replay_session(corrupted)


if __name__ == "__main__":
    unittest.main()
