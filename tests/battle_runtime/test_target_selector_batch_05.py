# -*- coding: utf-8 -*-
"""Target Selector Batch 05 runtime leaf tests (direct runtime module)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet
from hsr_battle_agent.battle_runtime import targets
from hsr_battle_agent.battle_sandbox.context import ExecutionContext


class TestTaskContextLeaves(unittest.TestCase):
    def test_task_action_target_and_owner_entity_field_reads(self):
        task_target = EntityRef(runtime_id=11)
        owner = EntityRef(runtime_id=12)
        context = ExecutionContext(task_action_target=task_target, owner_entity=owner)
        self.assertEqual(targets.context_task_action_target(context), task_target)
        self.assertEqual(targets.context_owner_entity(context), owner)

    def test_missing_context_fields_return_null(self):
        context = ExecutionContext()
        self.assertIsNone(targets.context_task_action_target(context))
        self.assertIsNone(targets.context_owner_entity(context))


class TestSingleEntitySelectors(unittest.TestCase):
    def test_task_action_target_selector_normal(self):
        entity = EntityRef(runtime_id=1)
        context = ExecutionContext(task_action_target=entity)
        self.assertEqual(targets.select_task_action_target(context), TargetSet.of(entity))

    def test_task_action_target_selector_null_field_is_empty(self):
        context = ExecutionContext(task_action_target=None)
        self.assertEqual(targets.select_task_action_target(context), TargetSet())

    def test_caster_selector_normal(self):
        entity = EntityRef(runtime_id=5)
        context = ExecutionContext(caster_entity=entity)
        self.assertEqual(targets.select_caster(context), TargetSet.of(entity))

    def test_caster_selector_null_appends_null_element(self):
        context = ExecutionContext(caster_entity=None)
        result = targets.select_caster(context)
        self.assertEqual(result, TargetSet.of(None))
        self.assertEqual(result.count, 1)
        self.assertIsNone(result.items[0])

    def test_none_selector_always_empty(self):
        context = ExecutionContext(
            task_action_target=EntityRef(runtime_id=1),
            owner_entity=EntityRef(runtime_id=2),
            caster_entity=EntityRef(runtime_id=3),
        )
        self.assertEqual(targets.select_none(context), TargetSet())


class TestSingleTargetCollapse(unittest.TestCase):
    def test_collapse_single_or_null(self):
        entity = EntityRef(runtime_id=9)
        self.assertEqual(targets.collapse_single_or_null(TargetSet.of(entity)), entity)
        self.assertEqual(
            targets.collapse_single_or_null(TargetSet.of(entity, EntityRef(runtime_id=2))),
            entity,
        )
        self.assertIsNone(targets.collapse_single_or_null(TargetSet()))
        self.assertIsNone(targets.collapse_single_or_null(TargetSet.of(None)))

    def test_collapse_required_single_or_null(self):
        entity = EntityRef(runtime_id=9)
        self.assertEqual(
            targets.collapse_required_single_or_null(TargetSet.of(entity)), entity
        )
        self.assertIsNone(targets.collapse_required_single_or_null(TargetSet()))
        self.assertIsNone(
            targets.collapse_required_single_or_null(
                TargetSet.of(entity, EntityRef(runtime_id=2))
            )
        )


class TestEntityIdentity(unittest.TestCase):
    def test_game_entity_runtime_id_returns_stable_id(self):
        entity = EntityRef(runtime_id=-17)
        self.assertEqual(targets.game_entity_runtime_id(entity), -17)


if __name__ == "__main__":
    unittest.main()
