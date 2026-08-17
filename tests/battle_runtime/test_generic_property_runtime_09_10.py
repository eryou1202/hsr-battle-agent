# -*- coding: utf-8 -*-
"""Battle runtime tests for Handoff 09 contribution lifecycle + Handoff 10
generic property source-slot and materialization framework.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.modifiers import (  # noqa: E402
    ModifierState,
    ModifierStateValue,
)
from hsr_battle_agent.battle_ir.property import (  # noqa: E402
    MaterializationKind,
    PropertyEntry,
    StackPropertyTaskConfig,
    StackPropertyTaskContext,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_runtime import property as runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def make_entry(
    kind: int,
    *,
    base: int = 0,
    post_hook_context=None,
    post_transform_a=None,
    post_transform_b=None,
) -> PropertyEntry:
    return PropertyEntry(
        source_generation=[0],
        source_active=[False],
        source_value=[0],
        materialization_kind=kind,
        base_or_fallback=fp(base),
        materialized=fp(base),
        post_hook_context=post_hook_context,
        post_transform_a=post_transform_a,
        post_transform_b=post_transform_b,
    )


def make_modifier(
    *,
    name: str = "StackModifier",
    owner: EntityRef = EntityRef(1),
    ordinal: int = 0,
    state: int = 1,
) -> ModifierState:
    return ModifierState(
        name=name,
        owner_entity=owner,
        instance_ordinal=ordinal,
        state_raw=state,
    )


class TestSourceSlotLifecycle(unittest.TestCase):
    def test_allocate_one_source_returns_stable_index(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        index = runtime.allocate_source_slot(entry, fp(100))
        self.assertEqual(index, 1)
        self.assertTrue(entry.source_active[1])
        self.assertEqual(entry.source_generation[1], 1)
        self.assertEqual(entry.generation_counter, 1)
        self.assertEqual(entry.last_changed_source, 1)
        self.assertTrue(fixpoint_equal(entry.materialized, fp(100)))

    def test_allocate_never_claims_source_zero(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        runtime.allocate_source_slot(entry, fp(5))
        runtime.allocate_source_slot(entry, fp(6))
        self.assertEqual(entry.source_generation[0], 0)
        self.assertFalse(entry.source_active[0])
        self.assertEqual(entry.source_value[0], 0)

    def test_refresh_updates_same_index_and_does_not_append(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        first = runtime.allocate_source_slot(entry, fp(4))
        capacity_before = len(entry.source_value)
        runtime.update_source_slot(entry, first, fp(9))
        self.assertEqual(len(entry.source_value), capacity_before)
        self.assertEqual(entry.generation_counter, 2)
        self.assertEqual(entry.source_generation[first], 2)
        self.assertTrue(entry.source_active[first])
        self.assertTrue(fixpoint_equal(entry.materialized, fp(9)))

    def test_remove_disables_exact_index_without_shift(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        first = runtime.allocate_source_slot(entry, fp(10))
        second = runtime.allocate_source_slot(entry, fp(20))
        stale = entry.source_value[first]
        runtime.remove_source_slot(entry, first)
        self.assertFalse(entry.source_active[first])
        self.assertEqual(entry.source_generation[first], 0)
        self.assertEqual(entry.source_value[first], stale)
        self.assertEqual(second, 2)
        self.assertTrue(entry.source_active[second])
        self.assertTrue(fixpoint_equal(entry.materialized, fp(20)))

    def test_add_two_remove_first_refresh_second(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        first = runtime.allocate_source_slot(entry, fp(1))
        second = runtime.allocate_source_slot(entry, fp(2))
        runtime.remove_source_slot(entry, first)
        runtime.update_source_slot(entry, second, fp(7))
        self.assertEqual((first, second), (1, 2))
        self.assertTrue(fixpoint_equal(entry.materialized, fp(7)))
        self.assertEqual(entry.source_generation, [0, 0, 3])

    def test_remove_with_no_active_sources_is_noop(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        before = entry.to_dict()
        runtime.remove_source_slot(entry, 0)
        self.assertEqual(entry.to_dict(), before)

    def test_unknown_kind_raises_and_never_falls_back_to_add(self):
        entry = make_entry(8, base=1)
        with self.assertRaises(runtime.UnsupportedMaterializationKind):
            runtime.allocate_source_slot(entry, fp(5))

    def test_update_never_allocates_missing_slot(self):
        entry = make_entry(int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE))
        with self.assertRaises(runtime.PropertySourceSlotError):
            runtime.update_source_slot(entry, 5, fp(1))


class TestMaterializationKinds(unittest.TestCase):
    def _active_entry(self, kind: int, values: list[int], base: int = 0) -> PropertyEntry:
        generations = [0]
        active = [False]
        source_values = [0]
        for value in values:
            generations.append(1)
            active.append(True)
            source_values.append(fp(value))
        return PropertyEntry(
            source_generation=generations,
            source_active=active,
            source_value=source_values,
            materialization_kind=kind,
            generation_counter=len(values),
            active_source_extent=len(values),
            last_changed_source=len(values),
            base_or_fallback=fp(base),
            materialized=0,
        )

    def test_kind1_selects_source_zero(self):
        entry = PropertyEntry(
            source_generation=[1],
            source_active=[True],
            source_value=[fp(42)],
            materialization_kind=int(
                MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
            ),
            generation_counter=1,
            active_source_extent=1,
            last_changed_source=0,
            base_or_fallback=0,
            materialized=0,
        )
        value = runtime.rebuild_materialized(entry)
        self.assertTrue(fixpoint_equal(value, fp(42)))
        self.assertTrue(fixpoint_equal(entry.materialized, fp(42)))

    def test_kind2_selects_last_changed_source(self):
        entry = self._active_entry(
            int(MaterializationKind.KIND_2_LAST_CHANGED_SOURCE_SELECTION),
            [1, 9],
        )
        entry.last_changed_source = 2
        value = runtime.rebuild_materialized(entry)
        self.assertTrue(fixpoint_equal(value, fp(9)))

    def test_kind3_active_add_fold(self):
        entry = self._active_entry(
            int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE),
            [2, 3],
            base=10,
        )
        value = runtime.rebuild_materialized(entry)
        self.assertTrue(fixpoint_equal(value, fp(15)))

    def test_kind4_active_multiply_fold_and_no_active_fallback(self):
        entry = self._active_entry(
            int(MaterializationKind.KIND_4_ACTIVE_FOLD_MULTIPLY_CALLEE),
            [2, 3],
            base=10,
        )
        value = runtime.rebuild_materialized(entry)
        self.assertTrue(fixpoint_equal(value, fp(60)))

        empty = self._active_entry(
            int(MaterializationKind.KIND_4_ACTIVE_FOLD_MULTIPLY_CALLEE),
            [],
            base=7,
        )
        self.assertTrue(fixpoint_equal(runtime.rebuild_materialized(empty), fp(7)))

    def test_kind5_is_explicitly_unsupported(self):
        entry = self._active_entry(
            int(MaterializationKind.KIND_5_ACTIVE_FOLD_SUBTRACT_MULTIPLY_CALLEES),
            [2, 3],
            base=10,
        )
        with self.assertRaises(runtime.UnsupportedMaterializationKind) as raised:
            runtime.rebuild_materialized(entry)
        self.assertIn("subtract", str(raised.exception).lower())

    def test_kind6_and_kind7_are_complementary_extrema(self):
        entry6 = self._active_entry(
            int(MaterializationKind.KIND_6_ACTIVE_EXTREMUM_DIRECTION_A),
            [5, 3, 9],
        )
        entry7 = self._active_entry(
            int(MaterializationKind.KIND_7_ACTIVE_EXTREMUM_DIRECTION_B),
            [5, 3, 9],
        )
        lower = runtime.rebuild_materialized(entry6)
        upper = runtime.rebuild_materialized(entry7)
        self.assertTrue(fixpoint_equal(lower, fp(3)))
        self.assertTrue(fixpoint_equal(upper, fp(9)))

    def test_non_null_post_stages_are_explicitly_unsupported(self):
        for field, value in (
            ("post_hook_context", {"opaque": 1}),
            ("post_transform_a", "opaque_a"),
            ("post_transform_b", "opaque_b"),
        ):
            with self.subTest(field=field):
                kwargs = {field: value}
                entry = make_entry(
                    int(MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE),
                    **kwargs,
                )
                with self.assertRaises(runtime.UnsupportedPropertyPostStageError):
                    runtime.rebuild_materialized(entry)


class TestComponentChangeBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.state = BattleState()
        self.entity = EntityRef(1)
        self.property_id = 5
        runtime.ensure_property_entry(
            self.state,
            self.entity,
            self.property_id,
            materialization_kind=int(
                MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
            ),
            base_or_fallback=0,
        )

    def test_each_component_mutation_records_one_boundary(self):
        boundaries: list = []
        index = runtime.component_stack_source(
            self.state,
            self.entity,
            self.property_id,
            fp(10),
            boundary_sink=boundaries.append,
        )
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0].operation, "source_allocated")
        self.assertEqual(boundaries[0].source_index, index)
        self.assertTrue(fixpoint_equal(boundaries[0].old_materialized, fp(0)))
        self.assertTrue(fixpoint_equal(boundaries[0].new_materialized, fp(10)))

        boundaries.clear()
        runtime.update_contribution_source(
            self.state,
            self.entity,
            self.property_id,
            index,
            fp(15),
            boundary_sink=boundaries.append,
        )
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0].operation, "source_updated")
        self.assertTrue(fixpoint_equal(boundaries[0].old_materialized, fp(10)))
        self.assertTrue(fixpoint_equal(boundaries[0].new_materialized, fp(15)))

        boundaries.clear()
        runtime.remove_contribution_source(
            self.state,
            self.entity,
            self.property_id,
            index,
            boundary_sink=boundaries.append,
        )
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0].operation, "source_removed")
        self.assertTrue(fixpoint_equal(boundaries[0].old_materialized, fp(15)))
        self.assertTrue(fixpoint_equal(boundaries[0].new_materialized, fp(0)))


class TestModifierContributionLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.state = BattleState()
        self.entity = EntityRef(2)
        self.property_id = 5
        runtime.ensure_property_entry(
            self.state,
            self.entity,
            self.property_id,
            materialization_kind=int(
                MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
            ),
            base_or_fallback=0,
        )

    def test_removed_modifier_cannot_create_contribution(self):
        modifier = make_modifier(state=2)
        index = runtime.stack_property_contribution(
            self.state,
            modifier,
            self.property_id,
            fp(10),
            self.entity,
            is_refresh=False,
        )
        self.assertIsNone(index)
        self.assertEqual(self.state.modifier_property_contributions, {})

    def test_refresh_keeps_one_record_and_stable_index(self):
        modifier = make_modifier()
        first = runtime.stack_property_contribution(
            self.state, modifier, self.property_id, fp(10), self.entity
        )
        second = runtime.stack_property_contribution(
            self.state,
            modifier,
            self.property_id,
            fp(25),
            self.entity,
            is_refresh=True,
        )
        self.assertEqual(first, second)
        key = "modifier_property:1:0:StackModifier"
        records = self.state.modifier_property_contributions[key]
        self.assertEqual(len(records), 1)
        entry = runtime.get_property_entry(self.state, self.entity, self.property_id)
        self.assertTrue(fixpoint_equal(entry.materialized, fp(25)))

    def test_pop_removes_only_owner_records_and_keeps_other_modifier(self):
        modifier_a = make_modifier(name="A", ordinal=0)
        modifier_b = make_modifier(name="B", ordinal=1)
        index_a = runtime.stack_property_contribution(
            self.state, modifier_a, self.property_id, fp(100), self.entity
        )
        index_b = runtime.stack_property_contribution(
            self.state, modifier_b, self.property_id, fp(25), self.entity
        )
        self.assertEqual((index_a, index_b), (1, 2))

        runtime.pop_property_contributions(self.state, modifier_a)

        entry = runtime.get_property_entry(self.state, self.entity, self.property_id)
        self.assertFalse(entry.source_active[1])
        self.assertEqual(entry.source_generation[1], 0)
        self.assertTrue(entry.source_active[2])
        self.assertEqual(entry.source_generation[2], 2)
        self.assertTrue(fixpoint_equal(entry.materialized, fp(25)))
        self.assertNotIn(
            "modifier_property:1:0:A",
            self.state.modifier_property_contributions,
        )
        self.assertIn(
            "modifier_property:1:1:B",
            self.state.modifier_property_contributions,
        )

    def test_pop_iterates_records_in_forward_order(self):
        modifier = make_modifier()
        entities = [EntityRef(10), EntityRef(11)]
        for entity in entities:
            runtime.ensure_property_entry(
                self.state,
                entity,
                self.property_id,
                materialization_kind=int(
                    MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
                ),
            )
        boundaries = []
        runtime.stack_property_contribution(
            self.state,
            modifier,
            self.property_id,
            fp(1),
            entities[0],
            boundary_sink=boundaries.append,
        )
        runtime.stack_property_contribution(
            self.state,
            modifier,
            self.property_id,
            fp(2),
            entities[1],
            boundary_sink=boundaries.append,
        )
        runtime.pop_property_contributions(
            self.state, modifier, boundary_sink=boundaries.append
        )
        self.assertEqual(
            [b.entity.runtime_id for b in boundaries[-2:]],
            [10, 11],
        )
        self.assertNotIn(
            "modifier_property:1:0:StackModifier",
            self.state.modifier_property_contributions,
        )


class TestStackPropertyTaskBoundary(unittest.TestCase):
    def test_init_accepts_minimal_opaque_context_and_config_projections(self):
        modifier = make_modifier()
        executor = runtime.stack_property_executor_init(
            {"modifier": modifier},
            {"property_id": 6},
        )
        self.assertEqual(executor.kind_marker, 0x7777)
        self.assertEqual(executor.task_context.modifier, modifier)
        self.assertEqual(executor.task_config.property_id, 6)

    def test_two_targets_receive_two_ordered_owner_records(self):
        state = BattleState()
        targets = [EntityRef(1), EntityRef(2)]
        property_id = 6
        for target in targets:
            runtime.ensure_property_entry(
                state,
                target,
                property_id,
                materialization_kind=int(
                    MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
                ),
            )
        modifier = make_modifier()
        executor = runtime.stack_property_executor_init(
            StackPropertyTaskContext(modifier=modifier),
            StackPropertyTaskConfig(property_id=property_id),
        )
        result = runtime.stack_property_execute(
            state,
            executor,
            TargetSet.of(*targets),
            fp(7),
        )
        self.assertEqual(result.applied_targets, tuple(targets))
        self.assertEqual(result.applied_source_indices, (1, 1))
        records = state.modifier_property_contributions[
            "modifier_property:1:0:StackModifier"
        ]
        self.assertEqual(
            [record["target"]["runtime_id"] for record in records],
            [1, 2],
        )

    def test_empty_target_list_is_deterministic_noop(self):
        state = BattleState()
        modifier = make_modifier()
        executor = runtime.stack_property_executor_init(
            StackPropertyTaskContext(modifier=modifier),
            StackPropertyTaskConfig(property_id=6),
        )
        result = runtime.stack_property_execute(
            state, executor, TargetSet.of(), fp(7)
        )
        self.assertEqual(result.applied_targets, ())
        self.assertEqual(result.applied_source_indices, ())
        self.assertEqual(state.modifier_property_contributions, {})


if __name__ == "__main__":
    unittest.main()
