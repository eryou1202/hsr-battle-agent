# -*- coding: utf-8 -*-
"""Scoped HP Runtime unit tests (Handoff 12).

Covers the pure TryGetLockHP scan and the SetHP positive-delta rejection.
BattleState-level executor coverage lives in ``tests/battle_sandbox``.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.hp import LockHPRecord  # noqa: E402
from hsr_battle_agent.battle_runtime import hp as hp_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


def rec(action: str, kind: int, value: int) -> LockHPRecord:
    return LockHPRecord(action_ref=action, kind=kind, value=fp(value))


class TestTryGetLockHP(unittest.TestCase):
    def test_empty_list_returns_false_zero(self):
        result = hp_runtime.try_get_lock_hp([], 100)
        self.assertFalse(result.success)
        self.assertEqual(result.lock_value, 0)
        self.assertEqual(result.actions, ())

    def test_no_matching_kind_returns_false(self):
        result = hp_runtime.try_get_lock_hp([rec("a", 50, 80)], 100)
        self.assertFalse(result.success)
        self.assertEqual(result.lock_value, 0)
        self.assertEqual(result.actions, ())

    def test_one_matching_record(self):
        result = hp_runtime.try_get_lock_hp([rec("a", 100, 80)], 100)
        self.assertTrue(result.success)
        self.assertTrue(fixpoint_equal(result.lock_value, fp(80)))
        self.assertEqual(result.actions, ("a",))

    def test_equal_values_prefer_lower_index_and_forward_actions(self):
        records = [rec("a", 100, 80), rec("b", 100, 80), rec("c", 100, 80)]
        result = hp_runtime.try_get_lock_hp(records, 100)
        self.assertTrue(result.success)
        self.assertTrue(fixpoint_equal(result.lock_value, fp(80)))
        self.assertEqual(result.actions, ("a", "b", "c"))

    def test_non_equal_next_accepted_value_stops_scan(self):
        # Descending scan: c (80) best=2, b (80) best=1, a (90) non-equal break.
        records = [rec("a", 100, 90), rec("b", 100, 80), rec("c", 100, 80)]
        result = hp_runtime.try_get_lock_hp(records, 100)
        self.assertTrue(result.success)
        self.assertTrue(fixpoint_equal(result.lock_value, fp(80)))
        self.assertEqual(result.actions, ("b", "c"))

    def test_skip_kind_below_damage_kind(self):
        records = [
            rec("skip", 50, 70),
            rec("a", 100, 80),
            rec("b", 100, 80),
        ]
        result = hp_runtime.try_get_lock_hp(records, 100)
        self.assertTrue(result.success)
        self.assertEqual(result.actions, ("a", "b"))


class TestSetHPCompositionGuard(unittest.TestCase):
    def test_positive_direct_change_hp_raises_scoped_unsupported(self):
        # A tiny sandbox-free guard test: the helper raises before any write.
        # The full composition is covered through the Registry/Executor path.
        from hsr_battle_agent.battle_ir.property import (  # noqa: PLC0415
            MaterializationKind,
            PropertyEntry,
        )
        from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: PLC0415
        from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: PLC0415

        state = BattleState()
        entity = EntityRef(1)

        def seed(pid: int, value: int) -> None:
            from hsr_battle_agent.battle_runtime import property as pr  # noqa: PLC0415

            pr.set_property_entry(
                state,
                entity,
                pid,
                PropertyEntry(
                    source_generation=[1],
                    source_active=[True],
                    source_value=[value],
                    materialization_kind=int(
                        MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
                    ),
                    generation_counter=1,
                    active_source_extent=1,
                    last_changed_source=0,
                    base_or_fallback=0,
                    materialized=value,
                ),
            )

        seed(10, fp(50))
        seed(1, fp(100))
        # ModifyValue=100, ratio=0 => target=100, delta=+50 (positive).
        with self.assertRaises(hp_runtime.UnsupportedDirectChangeHPPositiveError):
            hp_runtime.direct_change_hp_mode1_negative(
                state, entity, modify_value=fp(100), modify_ratio=fp(0)
            )


if __name__ == "__main__":
    unittest.main()
