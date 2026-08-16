# -*- coding: utf-8 -*-
"""Target Selector Runtime 05 sandbox integration tests.

Every execution in this module goes through
``PrimitiveCall -> PrimitiveExecutor -> PrimitiveRegistry -> PrimitiveResult``.
No test calls a battle_runtime implementation directly.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.model import PrimitiveCall
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry


class TargetSelectorExecutorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PrimitiveRegistry.create_default()
        self.executor = PrimitiveExecutor(self.registry)
        self.context = ExecutionContext()

    def execute(self, primitive_id: str, **inputs):
        call = PrimitiveCall.create(primitive_id, **inputs)
        return self.executor.execute(call, self.context)


class TestContextLeavesThroughExecutor(TargetSelectorExecutorTestCase):
    def test_task_action_target_normal_and_null(self):
        entity = EntityRef(runtime_id=21)
        self.context.task_action_target = entity
        result = self.execute("battle.ir.target.context_task_action_target")
        self.assertEqual(result.value, entity)
        self.assertEqual(result.semantic_result_type, "EntityRef")

        self.context.task_action_target = None
        result = self.execute("battle.ir.target.context_task_action_target")
        self.assertIsNone(result.value)

    def test_owner_entity_normal_and_null(self):
        entity = EntityRef(runtime_id=22)
        self.context.owner_entity = entity
        result = self.execute("battle.ir.target.context_owner_entity")
        self.assertEqual(result.value, entity)
        self.context.owner_entity = None
        self.assertIsNone(self.execute("battle.ir.target.context_owner_entity").value)


class TestSelectorsThroughExecutor(TargetSelectorExecutorTestCase):
    def test_task_action_target_selector_branches(self):
        entity = EntityRef(runtime_id=31)
        self.context.task_action_target = entity
        result = self.execute("battle.ir.target.select_task_action_target")
        self.assertEqual(result.value, TargetSet.of(entity))
        self.assertEqual(result.semantic_result_type, "TargetSet")

        self.context.task_action_target = None
        self.assertEqual(self.execute("battle.ir.target.select_task_action_target").value, TargetSet())

    def test_caster_selector_null_appends_null(self):
        self.context.caster_entity = None
        result = self.execute("battle.ir.target.select_caster")
        self.assertEqual(result.value, TargetSet.of(None))

    def test_none_selector_is_empty(self):
        result = self.execute("battle.ir.target.select_none")
        self.assertEqual(result.value, TargetSet())


class TestCollapseThroughExecutor(TargetSelectorExecutorTestCase):
    def test_collapse_single_or_null(self):
        entity = EntityRef(runtime_id=41)
        result = self.execute(
            "battle.ir.target.collapse_single_or_null", targets=TargetSet.of(entity)
        )
        self.assertEqual(result.value, entity)
        self.assertIsNone(
            self.execute("battle.ir.target.collapse_single_or_null", targets=TargetSet()).value
        )

    def test_collapse_required_single_or_null(self):
        entity = EntityRef(runtime_id=42)
        result = self.execute(
            "battle.ir.target.collapse_required_single_or_null",
            targets=TargetSet.of(entity),
        )
        self.assertEqual(result.value, entity)
        self.assertIsNone(
            self.execute(
                "battle.ir.target.collapse_required_single_or_null",
                targets=TargetSet.of(entity, EntityRef(runtime_id=43)),
            ).value
        )


class TestEntityIdentityThroughExecutor(TargetSelectorExecutorTestCase):
    def test_game_entity_runtime_id(self):
        result = self.execute(
            "battle.ir.entity.game_entity_runtime_id", entity=EntityRef(runtime_id=-5)
        )
        self.assertEqual(result.value, -5)
        self.assertEqual(result.semantic_result_type, "int32")


class TestCrossBatchComposition(TargetSelectorExecutorTestCase):
    def test_selector_to_collapse_composition_chain(self):
        self.context.caster_entity = EntityRef(runtime_id=77)
        selected = self.execute("battle.ir.target.select_caster")
        self.assertEqual(selected.value, TargetSet.of(EntityRef(runtime_id=77)))
        collapsed = self.execute(
            "battle.ir.target.collapse_required_single_or_null",
            targets=selected.value,
        )
        self.assertEqual(collapsed.value, EntityRef(runtime_id=77))
        # A second primitive in the same trace keeps deterministic event ids.
        self.assertEqual(len(self.context.trace), 4)

    def test_target_set_round_trips_through_executor_results(self):
        self.context.task_action_target = EntityRef(runtime_id=88)
        first = self.execute("battle.ir.target.select_task_action_target")
        second = self.execute(
            "battle.ir.target.collapse_required_single_or_null",
            targets=first.value,
        )
        self.assertEqual(second.value, EntityRef(runtime_id=88))


class TestTraceSummaries(TargetSelectorExecutorTestCase):
    def test_entity_ref_and_target_set_trace_summaries(self):
        self.context.caster_entity = EntityRef(runtime_id=99)
        self.execute("battle.ir.target.select_caster")
        events = self.context.trace.events
        started = events[0]
        finished = events[1]
        self.assertEqual(started.event, "PrimitiveStarted")
        self.assertEqual(started.input_tags, ())
        self.assertEqual(finished.event, "PrimitiveFinished")
        self.assertEqual(finished.result, "target_count:1")
        self.assertEqual(finished.result_type, "TargetSet")

        self.execute(
            "battle.ir.target.collapse_required_single_or_null",
            targets=TargetSet.of(EntityRef(runtime_id=99)),
        )
        finished = self.context.trace.events[-1]
        self.assertEqual(finished.result, "entity_ref:99")


class TestExecutionContextTransientFields(TargetSelectorExecutorTestCase):
    def test_clone_copies_transient_context_entities(self):
        self.context.caster_entity = EntityRef(runtime_id=1)
        self.context.task_action_target = EntityRef(runtime_id=2)
        branch = self.context.clone()
        self.assertEqual(branch.caster_entity, EntityRef(runtime_id=1))
        self.assertEqual(branch.task_action_target, EntityRef(runtime_id=2))
        branch.caster_entity = EntityRef(runtime_id=3)
        self.assertEqual(self.context.caster_entity, EntityRef(runtime_id=1))

    def test_transient_context_fields_do_not_change_state_hash(self):
        before = self.context.state_hash()
        self.context.caster_entity = EntityRef(runtime_id=1)
        self.context.task_action_target = EntityRef(runtime_id=2)
        self.context.owner_entity = EntityRef(runtime_id=3)
        self.assertEqual(self.context.state_hash(), before)


if __name__ == "__main__":
    unittest.main()
