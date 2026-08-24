# -*- coding: utf-8 -*-
"""Deterministic ordinary-scope Turn/AV runtime tests (Semantics 29)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import (  # noqa: E402
    TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID,
)
from hsr_battle_agent.battle_ir.property import (  # noqa: E402
    MaterializationKind,
    PropertyEntry,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_ir.turns import (  # noqa: E402
    TURN_PHASE_ACTIVE,
    TURN_PHASE_SETTLED,
    ActionCompletionBoundary,
    TurnAdvanceResult,
)
from hsr_battle_agent.battle_runtime import property as property_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime import turns as turn_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def install_delay(state: BattleState, entity: EntityRef, value: int) -> None:
    entry = PropertyEntry(
        source_generation=[1],
        source_active=[True],
        source_value=[fp(value)],
        materialization_kind=int(MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION),
        generation_counter=1,
        active_source_extent=1,
        last_changed_source=0,
        base_or_fallback=0,
        materialized=fp(value),
    )
    property_runtime.set_property_entry(
        state,
        entity,
        turn_runtime.REMAINING_ACTION_DELAY_PROPERTY_ID,
        entry,
    )


class TestTurnAVRuntime29(unittest.TestCase):
    def populated(self, delays: tuple[int, ...]) -> tuple[BattleState, tuple[EntityRef, ...]]:
        state = BattleState()
        entities = tuple(EntityRef(index + 1) for index in range(len(delays)))
        for entity, delay in zip(entities, delays):
            install_delay(state, entity, delay)
        turn_runtime.initialize_turn_timeline(state, TargetSet.from_iterable(entities))
        return state, entities

    def test_sort_select_and_advance_remaining_and_elapsed_delay(self):
        state, (first, second, third) = self.populated((30, 10, 20))
        result = turn_runtime.advance_to_next_actor(state)

        self.assertEqual(result.actor, second)
        self.assertEqual(result.ordered_entities, (second, third, first))
        self.assertTrue(fixpoint_equal(result.selected_delay_raw, fp(10)))
        self.assertTrue(fixpoint_equal(result.elapsed_action_delay_raw, fp(10)))
        self.assertTrue(
            fixpoint_equal(turn_runtime.remaining_action_delay(state, first), fp(20))
        )
        self.assertTrue(
            fixpoint_equal(turn_runtime.remaining_action_delay(state, second), fp(0))
        )
        self.assertTrue(
            fixpoint_equal(turn_runtime.remaining_action_delay(state, third), fp(10))
        )
        self.assertEqual(state.turn_timeline["phase"], TURN_PHASE_ACTIVE)

    def test_multiple_sequential_turns_require_explicit_recharge_boundary(self):
        state, (first, second, third) = self.populated((30, 10, 20))
        turn_one = turn_runtime.advance_to_next_actor(state)
        with self.assertRaises(turn_runtime.TurnCompletionRequiredError):
            turn_runtime.advance_to_next_actor(state)

        turn_runtime.acknowledge_action_completion(
            state,
            ActionCompletionBoundary(
                actor=turn_one.actor,
                next_action_delay_raw=fp(40),
                provenance="test:explicit-recharge:actor-2",
            ),
        )
        self.assertEqual(state.turn_timeline["phase"], TURN_PHASE_SETTLED)
        turn_two = turn_runtime.advance_to_next_actor(state)
        self.assertEqual(turn_two.actor, third)
        self.assertTrue(fixpoint_equal(turn_two.elapsed_action_delay_raw, fp(20)))

        turn_runtime.acknowledge_action_completion(
            state,
            ActionCompletionBoundary(
                actor=third,
                next_action_delay_raw=fp(30),
                provenance="test:explicit-recharge:actor-3",
            ),
        )
        turn_three = turn_runtime.advance_to_next_actor(state)
        self.assertEqual(turn_three.actor, first)
        self.assertEqual(turn_three.turn_index, 3)
        self.assertTrue(fixpoint_equal(turn_three.elapsed_action_delay_raw, fp(30)))

    def test_equal_delay_tie_preserves_prior_action_list_order(self):
        state, entities = self.populated((10, 10, 10))
        state.turn_timeline["action_entity_runtime_ids"] = [3, 1, 2]
        result = turn_runtime.advance_to_next_actor(state)
        self.assertEqual(result.actor, entities[2])
        self.assertEqual(
            tuple(entity.runtime_id for entity in result.ordered_entities),
            (3, 1, 2),
        )

    def test_completion_actor_and_provenance_are_validated(self):
        state, entities = self.populated((10, 20))
        turn_runtime.advance_to_next_actor(state)
        with self.assertRaises(turn_runtime.TurnSemanticError):
            turn_runtime.acknowledge_action_completion(
                state,
                ActionCompletionBoundary(
                    actor=entities[1],
                    next_action_delay_raw=fp(10),
                    provenance="wrong actor",
                ),
            )
        with self.assertRaises(ValueError):
            ActionCompletionBoundary(
                actor=entities[0], next_action_delay_raw=fp(10), provenance=""
            )

    def test_snapshot_roundtrip_and_clone_divergence_are_hash_stable(self):
        sandbox = Sandbox(seed=29)
        entities = (EntityRef(1), EntityRef(2))
        install_delay(sandbox.context.state, entities[0], 20)
        install_delay(sandbox.context.state, entities[1], 10)
        turn_runtime.initialize_turn_timeline(
            sandbox.context.state, TargetSet.from_iterable(entities)
        )
        snapshot = sandbox.snapshot()
        restored = type(snapshot).from_dict(snapshot.to_dict())
        self.assertEqual(restored.state_hash(), snapshot.state_hash())

        branch = sandbox.clone()
        self.assertEqual(branch.state_hash(), sandbox.state_hash())
        branch.execute(TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID)
        self.assertNotEqual(branch.state_hash(), sandbox.state_hash())
        self.assertEqual(sandbox.context.state.turn_timeline["turn_index"], 0)

    def test_formal_sandbox_primitive_uses_catalog_provenance_and_trace(self):
        sandbox = Sandbox(seed=29)
        entities = (EntityRef(1), EntityRef(2))
        install_delay(sandbox.context.state, entities[0], 20)
        install_delay(sandbox.context.state, entities[1], 10)
        turn_runtime.initialize_turn_timeline(
            sandbox.context.state, TargetSet.from_iterable(entities)
        )

        registered = sandbox.registry.resolve(TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID)
        self.assertIn(":499799", registered.provenance_ref)
        result = sandbox.execute(TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID)
        self.assertIsInstance(result.value, TurnAdvanceResult)
        self.assertEqual(result.value.actor, entities[1])
        self.assertEqual(result.semantic_result_type, "turn_advance_result")
        self.assertEqual(
            sandbox.context.trace.events[-1].result_type,
            "TurnAdvanceResult",
        )

    def test_missing_delay_entry_and_negative_delay_are_rejected(self):
        state = BattleState()
        with self.assertRaises(turn_runtime.UnsupportedTurnParticipantError):
            turn_runtime.initialize_turn_timeline(state, TargetSet.of(EntityRef(1)))

        install_delay(state, EntityRef(1), -1)
        with self.assertRaises(ValueError):
            turn_runtime.initialize_turn_timeline(state, TargetSet.of(EntityRef(1)))


if __name__ == "__main__":
    unittest.main()
