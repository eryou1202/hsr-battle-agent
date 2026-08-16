# -*- coding: utf-8 -*-
"""Battle runtime tests for Action Execution Bridge 06 (E4 primitives)."""
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
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_runtime.actions import (  # noqa: E402
    task_begin_immediate_success,
    task_begin_select_single_target,
    task_executor_base_ready_init,
    task_executor_init,
    task_reset_ready,
    task_reset_ready_clear_selected_target,
    task_state_read,
)


class TestTaskExecutorInit(unittest.TestCase):
    def test_normal_config_reference(self):
        execution = task_executor_init("RPG.GameCore.Obsolete")
        self.assertEqual(execution.task_state, TaskState.READY)
        self.assertEqual(execution.config_ref, "RPG.GameCore.Obsolete")
        self.assertIsNone(execution.selected_target)
        self.assertIsNone(execution.next_phase)

    def test_null_config_reference(self):
        execution = task_executor_init(None)
        self.assertEqual(execution.task_state, TaskState.READY)
        self.assertIsNone(execution.config_ref)

    def test_invalid_config_rejected(self):
        with self.assertRaises(TypeError):
            task_executor_init(1)  # type: ignore[arg-type]


class TestTaskBeginImmediateSuccess(unittest.TestCase):
    def test_ready_to_success(self):
        execution = task_executor_init("cfg")
        result = task_begin_immediate_success(execution)
        self.assertEqual(result.task_state, TaskState.SUCCESS)
        # The accepted native leaf writes only [+0x10]; other slots preserved.
        self.assertEqual(result.config_ref, "cfg")

    def test_from_any_state_to_success(self):
        for state in (TaskState.READY, TaskState.EXECUTING, TaskState.SUCCESS, TaskState.FAIL):
            with self.subTest(state=state):
                execution = TaskExecutionState(task_state=state, config_ref="cfg")
                self.assertEqual(
                    task_begin_immediate_success(execution).task_state,
                    TaskState.SUCCESS,
                )

    def test_invalid_execution_rejected(self):
        with self.assertRaises(TypeError):
            task_begin_immediate_success("not-an-execution")  # type: ignore[arg-type]


class TestTaskResetReady(unittest.TestCase):
    def test_success_to_ready(self):
        execution = TaskExecutionState(task_state=TaskState.SUCCESS, config_ref="cfg")
        result = task_reset_ready(execution)
        self.assertEqual(result.task_state, TaskState.READY)
        # Obsolete OnTaskReset writes only [+0x10]; other slots are untouched.
        self.assertEqual(result.config_ref, "cfg")

    def test_preserves_other_slots_exactly(self):
        execution = TaskExecutionState(
            task_state=TaskState.EXECUTING,
            config_ref="cfg",
            selected_target=EntityRef(5),
            next_phase="Tick",
        )
        result = task_reset_ready(execution)
        self.assertEqual(result.config_ref, "cfg")
        self.assertEqual(result.selected_target.runtime_id, 5)
        self.assertEqual(result.next_phase, "Tick")


class TestTaskStateRead(unittest.TestCase):
    def test_reads_raw_state(self):
        for state in TaskState:
            with self.subTest(state=state):
                execution = TaskExecutionState(task_state=state)
                self.assertEqual(task_state_read(execution), state)

    def test_invalid_execution_rejected(self):
        with self.assertRaises(TypeError):
            task_state_read(None)  # type: ignore[arg-type]


class TestTaskExecutorBaseReadyInit(unittest.TestCase):
    def test_returns_fresh_ready_execution(self):
        execution = task_executor_base_ready_init()
        self.assertEqual(execution.task_state, TaskState.READY)
        self.assertIsNone(execution.config_ref)
        self.assertIsNone(execution.selected_target)
        self.assertIsNone(execution.next_phase)


class TestTaskBeginSelectSingleTarget(unittest.TestCase):
    def _execution(self) -> TaskExecutionState:
        return task_executor_init("RPG.GameCore.SwitchHandItemSetBreathingLight")

    def test_single_target_selected(self):
        result = task_begin_select_single_target(
            self._execution(), TargetSet.of(EntityRef(7))
        )
        self.assertEqual(result.task_state, TaskState.EXECUTING)
        self.assertEqual(result.selected_target.runtime_id, 7)
        self.assertEqual(result.next_phase, "Tick")

    def test_empty_targets_gives_null_selected_target(self):
        result = task_begin_select_single_target(self._execution(), TargetSet())
        self.assertEqual(result.task_state, TaskState.EXECUTING)
        self.assertIsNone(result.selected_target)
        self.assertEqual(result.next_phase, "Tick")

    def test_two_targets_gives_null_selected_target(self):
        result = task_begin_select_single_target(
            self._execution(),
            TargetSet.of(EntityRef(1), EntityRef(2)),
        )
        self.assertEqual(result.task_state, TaskState.EXECUTING)
        self.assertIsNone(result.selected_target)

    def test_single_null_element_gives_null_selected_target(self):
        result = task_begin_select_single_target(
            self._execution(), TargetSet.of(None)
        )
        self.assertEqual(result.task_state, TaskState.EXECUTING)
        self.assertIsNone(result.selected_target)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(TypeError):
            task_begin_select_single_target(self._execution(), [EntityRef(1)])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            task_begin_select_single_target("execution", TargetSet())  # type: ignore[arg-type]


class TestTaskResetReadyClearSelectedTarget(unittest.TestCase):
    def test_clears_selected_target_and_phase(self):
        execution = TaskExecutionState(
            task_state=TaskState.EXECUTING,
            config_ref="cfg",
            selected_target=EntityRef(7),
            next_phase="Tick",
        )
        result = task_reset_ready_clear_selected_target(execution)
        self.assertEqual(result.task_state, TaskState.READY)
        self.assertIsNone(result.selected_target)
        self.assertIsNone(result.next_phase)
        self.assertEqual(result.config_ref, "cfg")

    def test_invalid_execution_rejected(self):
        with self.assertRaises(TypeError):
            task_reset_ready_clear_selected_target(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
