# -*- coding: utf-8 -*-
"""Sandbox runtime tests for Action Execution Bridge 06."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.actions import (  # noqa: E402
    TaskExecutionState,
    TaskState,
)
from hsr_battle_agent.battle_ir.model import PrimitiveCall  # noqa: E402
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_sandbox.context import ExecutionContext  # noqa: E402
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor  # noqa: E402
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402
from hsr_battle_agent.battle_sandbox.trace import ExecutionTrace  # noqa: E402

ACTION_IDS = {
    "battle.ir.action.task_executor_init",
    "battle.ir.action.task_begin_immediate_success",
    "battle.ir.action.task_reset_ready",
    "battle.ir.action.task_state_read",
    "battle.ir.action.task_executor_base_ready_init",
    "battle.ir.action.task_begin_select_single_target",
    "battle.ir.action.task_reset_ready_clear_selected_target",
}


class TestActionPrimitiveRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()

    def test_all_action_primitives_registered(self):
        known = set(self.registry.known_primitive_ids)
        self.assertTrue(ACTION_IDS.issubset(known))

    def test_specs_and_provenance_come_from_semantic_artifact(self):
        for primitive_id in sorted(ACTION_IDS):
            with self.subTest(primitive_id=primitive_id):
                registered = self.registry.resolve(primitive_id)
                self.assertEqual(
                    registered.spec.primitive_id, primitive_id
                )
                self.assertTrue(registered.provenance_ref)
                self.assertIn("4.4.54:", registered.provenance_ref)
                self.assertEqual(registered.spec.determinism, "DETERMINISTIC")
                self.assertEqual(registered.spec.context_writes, ())
                expected_reads = (
                    ("targets",)
                    if primitive_id
                    == "battle.ir.action.task_begin_select_single_target"
                    else ()
                )
                self.assertEqual(registered.spec.context_reads, expected_reads)


class TestObsoleteActionChainThroughExecutor(unittest.TestCase):
    def test_full_empty_action_chain(self):
        sandbox = Sandbox()
        started = sandbox.execute(
            "battle.ir.action.task_executor_init",
            config="RPG.GameCore.Obsolete",
        )
        execution = started.value
        self.assertIsInstance(execution, TaskExecutionState)
        self.assertEqual(execution.task_state, TaskState.READY)

        begun = sandbox.execute(
            "battle.ir.action.task_begin_immediate_success", execution=execution
        )
        self.assertEqual(begun.value.task_state, TaskState.SUCCESS)
        self.assertEqual(begun.value.config_ref, "RPG.GameCore.Obsolete")

        read = sandbox.execute(
            "battle.ir.action.task_state_read", execution=begun.value
        )
        self.assertEqual(read.value, TaskState.SUCCESS)

        reset = sandbox.execute(
            "battle.ir.action.task_reset_ready", execution=begun.value
        )
        self.assertEqual(reset.value.task_state, TaskState.READY)

    def test_base_ready_init_executes_without_inputs(self):
        sandbox = Sandbox()
        result = sandbox.execute("battle.ir.action.task_executor_base_ready_init")
        self.assertEqual(result.value.task_state, TaskState.READY)

    def test_trace_roundtrip_after_action_chain(self):
        sandbox = Sandbox()
        sandbox.execute(
            "battle.ir.action.task_executor_init", config="RPG.GameCore.Obsolete"
        )
        trace_dict = sandbox.context.trace.to_dict()
        restored = ExecutionTrace.from_dict(trace_dict)
        self.assertEqual(len(restored.events), 2)
        finished = restored.events[1]
        self.assertEqual(finished.event, "PrimitiveFinished")
        self.assertIn("READY", finished.result)
        # Trace results stay JSON-safe scalar summaries.
        json.dumps(trace_dict)

    def test_action_primitives_leave_logical_state_untouched(self):
        sandbox = Sandbox()
        before = sandbox.state_hash()
        sandbox.execute(
            "battle.ir.action.task_executor_init", config="RPG.GameCore.Obsolete"
        )
        sandbox.execute(
            "battle.ir.action.task_begin_select_single_target",
            execution=TaskExecutionState(),
            targets=TargetSet.of(EntityRef(1)),
        )
        self.assertEqual(sandbox.state_hash(), before)


class TestCrossLayerComposition(unittest.TestCase):
    def test_context_target_to_action_write_chain(self):
        """ExecutionContext -> Target primitive -> Action primitive -> result.

        This is the real recovered chain shape: the native OnTaskBegin leaf
        consumes the single-target collapse result produced by Batch 05 target
        semantics, stores it in the generated executor slot and marks the Tick
        phase.
        """
        sandbox = Sandbox()
        sandbox.context.task_action_target = EntityRef(99)

        targets = sandbox.execute("battle.ir.target.select_task_action_target")
        self.assertEqual(targets.value.items, (EntityRef(99),))

        execution = sandbox.execute(
            "battle.ir.action.task_executor_init",
            config="RPG.GameCore.SwitchHandItemSetBreathingLight",
        ).value
        action = sandbox.execute(
            "battle.ir.action.task_begin_select_single_target",
            execution=execution,
            targets=targets.value,
        )
        self.assertEqual(action.value.task_state, TaskState.EXECUTING)
        self.assertEqual(action.value.selected_target.runtime_id, 99)
        self.assertEqual(action.value.next_phase, "Tick")

    def test_null_target_field_composes_to_null_selected_target(self):
        sandbox = Sandbox()
        targets = sandbox.execute("battle.ir.target.select_task_action_target")
        action = sandbox.execute(
            "battle.ir.action.task_begin_select_single_target",
            execution=TaskExecutionState(),
            targets=targets.value,
        )
        self.assertEqual(action.value.task_state, TaskState.EXECUTING)
        self.assertIsNone(action.value.selected_target)

    def test_branch_specific_two_targets_rejected_by_collapse(self):
        sandbox = Sandbox()
        targets = TargetSet.of(EntityRef(1), EntityRef(2))
        action = sandbox.execute(
            "battle.ir.action.task_begin_select_single_target",
            execution=TaskExecutionState(),
            targets=targets,
        )
        self.assertIsNone(action.value.selected_target)


class TestContextCloneIsolation(unittest.TestCase):
    def test_cloned_branch_action_does_not_affect_original(self):
        sandbox = Sandbox()
        branch = sandbox.clone()
        branch.execute(
            "battle.ir.action.task_executor_init", config="RPG.GameCore.Obsolete"
        )
        self.assertEqual(sandbox.context.state_hash(), branch.context.state_hash())
        self.assertEqual(len(sandbox.context.trace.events), 0)
        self.assertEqual(len(branch.context.trace.events), 2)

    def test_immutable_action_results_are_independent(self):
        execution = TaskExecutionState(config_ref="cfg")
        begun = PrimitiveExecutor(
            PrimitiveRegistry.create_default()
        ).execute(
            PrimitiveCall.create(
                "battle.ir.action.task_begin_immediate_success",
                execution=execution,
            ),
            ExecutionContext(),
        ).value
        self.assertEqual(execution.task_state, TaskState.READY)
        self.assertEqual(begun.task_state, TaskState.SUCCESS)


if __name__ == "__main__":
    unittest.main()
