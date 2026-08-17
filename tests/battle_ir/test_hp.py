# -*- coding: utf-8 -*-
"""Battle IR HP representation tests (Handoff 12)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.catalog import load_catalog_primitives  # noqa: E402
from hsr_battle_agent.battle_ir.hp import (  # noqa: E402
    HPTransitionResult,
    LockHPRecord,
    LockHPResult,
)
from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import fixpoint_from_int32  # noqa: E402


class TestLockHPRecord(unittest.TestCase):
    def test_roundtrip(self):
        record = LockHPRecord(action_ref="a", kind=100, value=fixpoint_from_int32(80))
        data = record.to_dict()
        self.assertEqual(LockHPRecord.from_dict(data), record)

    def test_result_trace_summary_is_compact(self):
        result = LockHPResult(
            success=True,
            lock_value=fixpoint_from_int32(80),
            actions=("a", "b"),
        )
        self.assertIn("lock_hp_result", result.trace_summary())
        self.assertIn("a,b", result.trace_summary())


class TestHPCatalogPrimitives(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.primitives = load_catalog_primitives()
        cls.by_id = {p.spec.primitive_id: p for p in cls.primitives}

    def test_hp_primitives_are_present(self):
        self.assertIn("battle.ir.hp.try_get_lock_hp", self.by_id)
        self.assertIn("battle.ir.hp.direct_damage.transition", self.by_id)

    def test_hp_primitive_input_contracts(self):
        lock = self.by_id["battle.ir.hp.try_get_lock_hp"].spec
        self.assertEqual(lock.input_names, ("component", "damage_kind"))
        self.assertEqual(lock.result, "lock_hp_result")

        transition = self.by_id["battle.ir.hp.direct_damage.transition"].spec
        self.assertEqual(
            transition.input_names,
            (
                "component",
                "delta",
                "damage_kind",
                "context_token",
                "input_record",
                "mode",
                "negative_hp_gate",
            ),
        )
        self.assertEqual(transition.result, "hp_transition_result")

    def test_hp_transition_result_trace_summary(self):
        result = HPTransitionResult(
            component=EntityRef(1),
            old_current=fixpoint_from_int32(100),
            new_current=fixpoint_from_int32(70),
            applied_delta=fixpoint_from_int32(-30),
            lock_hit=False,
            lock_value=0,
            lock_actions=(),
            flag=0,
            p=0,
            y=fixpoint_from_int32(70),
            negative_hp_written=False,
            old_negative=None,
            new_negative=None,
            negative_record_boundary=False,
        )
        self.assertIn("hp_transition_result", result.trace_summary())


if __name__ == "__main__":
    unittest.main()
