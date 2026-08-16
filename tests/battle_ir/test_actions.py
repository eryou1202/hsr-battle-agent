# -*- coding: utf-8 -*-
"""Canonical Action Execution Bridge 06 IR representation tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.actions import (  # noqa: E402
    TaskExecutionState,
    TaskState,
)
from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: E402


class TestTaskStateEnum(unittest.TestCase):
    def test_raw_values_match_recovered_constants(self):
        self.assertEqual(TaskState.READY.value, 0x7777)
        self.assertEqual(TaskState.EXECUTING.value, 0x8888)
        self.assertEqual(TaskState.SUCCESS.value, 0x9999)
        self.assertEqual(TaskState.FAIL.value, 0xAAAA)

    def test_names_match_recovered_enum_members(self):
        self.assertEqual(
            [state.name for state in TaskState],
            ["READY", "EXECUTING", "SUCCESS", "FAIL"],
        )

    def test_int_roundtrip(self):
        for state in TaskState:
            self.assertEqual(TaskState(state.value), state)

    def test_trace_summary_is_deterministic(self):
        self.assertEqual(TaskState.SUCCESS.trace_summary(), "TaskState.SUCCESS")


class TestTaskExecutionState(unittest.TestCase):
    def test_default_is_ready(self):
        execution = TaskExecutionState()
        self.assertEqual(execution.task_state, TaskState.READY)
        self.assertIsNone(execution.config_ref)
        self.assertIsNone(execution.selected_target)
        self.assertIsNone(execution.next_phase)

    def test_selected_target_and_phase_slots(self):
        execution = TaskExecutionState(
            task_state=TaskState.EXECUTING,
            config_ref="RPG.GameCore.Obsolete",
            selected_target=EntityRef(17),
            next_phase="Tick",
        )
        self.assertEqual(execution.selected_target.runtime_id, 17)
        self.assertEqual(execution.next_phase, "Tick")

    def test_invalid_slots_rejected(self):
        with self.assertRaises(TypeError):
            TaskExecutionState(task_state="SUCCESS")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            TaskExecutionState(config_ref=1)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            TaskExecutionState(selected_target="entity")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            TaskExecutionState(next_phase=1)  # type: ignore[arg-type]

    def test_trace_summary_contains_proven_slots(self):
        summary = TaskExecutionState(
            task_state=TaskState.SUCCESS, config_ref="cfg"
        ).trace_summary()
        self.assertIn("SUCCESS", summary)
        self.assertIn("'cfg'", summary)


if __name__ == "__main__":
    unittest.main()
