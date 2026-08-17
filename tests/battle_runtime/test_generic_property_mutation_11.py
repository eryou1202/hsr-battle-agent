# -*- coding: utf-8 -*-
"""Battle runtime tests for Handoff 11 generic source-0 property mutation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.modifiers import ModifierState  # noqa: E402
from hsr_battle_agent.battle_ir.property import (  # noqa: E402
    CURRENT_HP_PROPERTY_ID,
    SPECIAL_PROPERTY_IDS,
    MaterializationKind,
    PropertyEntry,
    PropertyModifyFunction,
)
from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: E402
from hsr_battle_agent.battle_runtime import property as runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def kind1_entry(value: int = 0, **kwargs) -> PropertyEntry:
    return PropertyEntry(
        source_generation=[1],
        source_active=[True],
        source_value=[fp(value)],
        materialization_kind=int(
            MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
        ),
        generation_counter=1,
        active_source_extent=1,
        last_changed_source=0,
        base_or_fallback=0,
        materialized=fp(value),
        **kwargs,
    )


class TestFixedPointArithmetic(unittest.TestCase):
    def test_add_subtract_multiply_saturating_domain(self):
        for left, right in ((2, 3), (-5, 9), (10, -4)):
            with self.subTest(left=left, right=right):
                self.assertTrue(
                    fixpoint_equal(
                        runtime.fixedpoint_add(fp(left), fp(right)),
                        fp(left + right),
                    )
                )
                self.assertTrue(
                    fixpoint_equal(
                        runtime.fixedpoint_subtract(fp(left), fp(right)),
                        fp(left - right),
                    )
                )
                self.assertTrue(
                    fixpoint_equal(
                        runtime.fixedpoint_multiply(fp(left), fp(right)),
                        fp(left * right),
                    )
                )

    def test_apply_modify_function_exact_semantics(self):
        old = fp(10)
        operand = fp(4)
        self.assertTrue(fixpoint_equal(
            runtime.apply_modify_function(int(PropertyModifyFunction.SET), old, operand),
            operand,
        ))
        self.assertTrue(fixpoint_equal(
            runtime.apply_modify_function(int(PropertyModifyFunction.ADD), old, operand),
            fp(14),
        ))
        self.assertTrue(fixpoint_equal(
            runtime.apply_modify_function(int(PropertyModifyFunction.MUL), old, operand),
            fp(40),
        ))
        self.assertTrue(fixpoint_equal(
            runtime.apply_modify_function(int(PropertyModifyFunction.MIN_SET), old, operand),
            operand,
        ))
        self.assertTrue(fixpoint_equal(
            runtime.apply_modify_function(int(PropertyModifyFunction.MAX_SET), old, operand),
            old,
        ))
        for out_of_range in (0, 6, 99, -1):
            with self.subTest(function_id=out_of_range):
                self.assertTrue(fixpoint_equal(
                    runtime.apply_modify_function(out_of_range, old, operand),
                    operand,
                ))


class TestSourceZeroMutation(unittest.TestCase):
    def setUp(self) -> None:
        self.state = BattleState()
        self.entity = EntityRef(1)
        self.property_id = 5
        runtime.set_property_entry(
            self.state, self.entity, self.property_id, kind1_entry(10)
        )

    def test_set_add_mul_min_max_update_source_zero_and_rebuild(self):
        cases = (
            (int(PropertyModifyFunction.SET), 3, 3),
            (int(PropertyModifyFunction.ADD), 4, 11),
            (int(PropertyModifyFunction.MUL), 3, 21),
            (int(PropertyModifyFunction.MIN_SET), 5, 5),
            (int(PropertyModifyFunction.MAX_SET), 30, 30),
        )
        for function_id, operand, expected in cases:
            with self.subTest(function_id=function_id):
                runtime.set_property_entry(
                    self.state, self.entity, self.property_id, kind1_entry(7)
                )
                changed = runtime.modify_source_zero_untransformed(
                    self.state,
                    self.entity,
                    self.property_id,
                    function_id,
                    fp(operand),
                )
                self.assertTrue(changed)
                entry = runtime.get_property_entry(
                    self.state, self.entity, self.property_id
                )
                self.assertTrue(entry.source_active[0])
                self.assertTrue(fixpoint_equal(entry.source_value[0], fp(expected)))
                self.assertTrue(fixpoint_equal(entry.materialized, fp(expected)))

    def test_out_of_range_function_uses_set_fallthrough(self):
        changed = runtime.modify_source_zero_untransformed(
            self.state,
            self.entity,
            self.property_id,
            999,
            fp(77),
        )
        self.assertTrue(changed)
        entry = runtime.get_property_entry(self.state, self.entity, self.property_id)
        self.assertTrue(fixpoint_equal(entry.materialized, fp(77)))

    def test_mutation_records_after_property_changed_boundary_once(self):
        boundaries = []
        runtime.modify_source_zero_untransformed(
            self.state,
            self.entity,
            self.property_id,
            int(PropertyModifyFunction.SET),
            fp(12),
            boundary_sink=boundaries.append,
        )
        self.assertEqual(len(boundaries), 1)
        boundary = boundaries[0]
        self.assertEqual(boundary.operation, "after_property_changed")
        self.assertEqual(boundary.source_index, 0)
        self.assertTrue(fixpoint_equal(boundary.old_materialized, fp(10)))
        self.assertTrue(fixpoint_equal(boundary.new_materialized, fp(12)))

    def test_modifier_contribution_indices_are_unaffected_by_source_zero(self):
        runtime.ensure_property_entry(
            self.state,
            self.entity,
            9,
            materialization_kind=int(
                MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
            ),
            base_or_fallback=0,
        )
        modifier = ModifierState(name="M", owner_entity=EntityRef(1), instance_ordinal=0)
        first = runtime.stack_property_contribution(
            self.state, modifier, 9, fp(100), self.entity
        )
        second = runtime.stack_property_contribution(
            self.state, modifier, 9, fp(25), self.entity
        )
        self.assertEqual((first, second), (1, 2))

        runtime.modify_source_zero_untransformed(
            self.state,
            self.entity,
            9,
            int(PropertyModifyFunction.SET),
            fp(50),
        )
        entry = runtime.get_property_entry(self.state, self.entity, 9)
        self.assertEqual(entry.source_generation[1], 1)
        self.assertEqual(entry.source_generation[2], 2)
        self.assertTrue(entry.source_active[1])
        self.assertTrue(entry.source_active[2])
        self.assertTrue(fixpoint_equal(entry.source_value[1], fp(100)))
        self.assertTrue(fixpoint_equal(entry.source_value[2], fp(25)))

    def test_non_null_post_hook_context_rejects_without_write(self):
        state = BattleState()
        entity = EntityRef(1)
        property_id = 5
        runtime.set_property_entry(
            state, entity, property_id, kind1_entry(10, post_hook_context={"x": 1})
        )
        before = runtime.get_property_entry(state, entity, property_id).to_dict()
        with self.assertRaises(runtime.UnsupportedPropertyPostStageError):
            runtime.modify_source_zero_untransformed(
                state, entity, property_id, int(PropertyModifyFunction.SET), fp(1)
            )
        self.assertEqual(
            runtime.get_property_entry(state, entity, property_id).to_dict(),
            before,
        )

    def test_non_null_post_transform_stage_rejects_without_write(self):
        state = BattleState()
        entity = EntityRef(1)
        property_id = 5
        runtime.set_property_entry(
            state, entity, property_id, kind1_entry(10, post_transform_a="opaque")
        )
        with self.assertRaises(runtime.UnsupportedPropertyPostStageError):
            runtime.modify_source_zero_untransformed(
                state, entity, property_id, int(PropertyModifyFunction.SET), fp(1)
            )

    def test_every_special_property_id_is_deferred(self):
        before = self.state.to_dict()
        for property_id in sorted(SPECIAL_PROPERTY_IDS):
            with self.subTest(property_id=property_id):
                with self.assertRaises(
                    runtime.UnsupportedSpecialPropertyMutationError
                ):
                    runtime.modify_source_zero_untransformed(
                        self.state,
                        self.entity,
                        property_id,
                        int(PropertyModifyFunction.SET),
                        fp(1),
                    )
        self.assertEqual(self.state.to_dict(), before)

    def test_current_hp_property_10_cannot_use_generic_path(self):
        self.assertEqual(CURRENT_HP_PROPERTY_ID, 10)
        state = BattleState()
        entity = EntityRef(1)
        runtime.set_property_entry(state, entity, 10, kind1_entry(1000))
        with self.assertRaises(runtime.UnsupportedSpecialPropertyMutationError) as raised:
            runtime.modify_source_zero_untransformed(
                state, entity, 10, int(PropertyModifyFunction.SET), fp(1)
            )
        self.assertEqual(raised.exception.property_id, 10)
        self.assertTrue(
            fixpoint_equal(
                runtime.get_property_entry(state, entity, 10).materialized,
                fp(1000),
            )
        )


if __name__ == "__main__":
    unittest.main()
