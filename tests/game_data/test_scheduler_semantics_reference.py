"""Tests for SCHEDULER-001 reference semantics."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.scheduler_semantics_reference import (
    ActionDelayState,
    InsertedActionSpec,
    LoopSpec,
    SchedulerSemanticError,
    TaskState,
    apply_delay_operation,
    conditional_loop_expand,
    expand_template_invocation,
    trace_completion_marker,
)


class SchedulerReferenceTest(unittest.TestCase):
    def test_task_states_keep_recovered_raw_values(self) -> None:
        self.assertEqual(int(TaskState.READY), 0x7777)
        self.assertEqual(int(TaskState.EXECUTING), 0x8888)
        self.assertEqual(int(TaskState.SUCCESS), 0x9999)
        self.assertEqual(int(TaskState.FAIL), 0xAAAA)

    def test_markers_transition_executing_then_success(self) -> None:
        start = trace_completion_marker({"kind": "ACTION_START_MARKER"}, task_id="t1")
        self.assertEqual(start.state, TaskState.EXECUTING)
        finish = trace_completion_marker({"kind": "ACTION_COMPLETION_MARKER"}, task_id="t1")
        self.assertEqual(finish.state, TaskState.SUCCESS)

    def test_delay_set_add_reset_and_clamp(self) -> None:
        current = ActionDelayState(Decimal("0.25"))
        set_result = apply_delay_operation(
            {"kind": "DELAY_ACTION", "source_type": "RPG.GameCore.SetActionDelay", "arguments": {"Value": {"IsDynamic": False, "FixedValue": {"Value": 0.5}}}},
            current,
        )
        self.assertEqual(set_result.delay.normalized_value, Decimal("0.5"))
        add_result = apply_delay_operation(
            {"kind": "DELAY_ACTION", "source_type": "RPG.GameCore.ModifyActionDelay", "arguments": {"AddNormalizedValue": {"IsDynamic": False, "FixedValue": {"Value": -1}}}},
            set_result.delay,
        )
        self.assertEqual(add_result.action, "ADD")
        self.assertEqual(add_result.delay.normalized_value, Decimal("0"))
        reset = apply_delay_operation(
            {"kind": "DELAY_ACTION", "source_type": "RPG.GameCore.ResetActionDelay", "arguments": {"SkipTargetTurn": True}},
            add_result.delay,
        )
        self.assertEqual((reset.action, reset.delay.normalized_value, reset.delay.skip_target_turn), ("RESET", Decimal("0"), True))

    def test_fixed_loop_and_conditional_loop(self) -> None:
        body = [{"operation_id": "body"}]
        loop = LoopSpec.from_operation({
            "arguments": {"MaxLoopCount": {"IsDynamic": False, "FixedValue": {"Value": 3}}},
            "children": [{"field_path": "TaskList", "operations": body}],
        })
        self.assertEqual(loop.expand(), tuple(body * 3))
        conditional = {
            "arguments": {"Predicate": {"$type": "RPG.GameCore.ByRandomChance"}},
            "children": [{"field_path": "TaskList", "operations": body}],
        }
        calls = [True, True, False]
        expanded = conditional_loop_expand(conditional, lambda _payload: calls.pop(0))
        self.assertEqual(expanded, tuple(body * 2))

    def test_template_invocation_expands_with_invocation_arguments(self) -> None:
        record = {
            "template_definitions": [{
                "template_id": "b:tpl:AddDot",
                "operations": [{"operation_id": "tpl-op", "children": []}],
            }],
        }
        operation = {"template_ref": "b:tpl:AddDot", "arguments": {"Name": "AddDot", "DynamicValues": {"Arg01": {"IsDynamic": False, "FixedValue": {"Value": 1}}}}}
        expanded = expand_template_invocation(record, operation)
        self.assertEqual(expanded[0]["operation_id"], "tpl-op")
        self.assertEqual(expanded[0]["invocation_arguments"], operation["arguments"])
        with self.assertRaises(SchedulerSemanticError):
            expand_template_invocation(record, {"template_ref": "b:tpl:Missing", "arguments": {}})

    def test_inserted_action_spec_is_lossless(self) -> None:
        spec = InsertedActionSpec.from_operation({
            "arguments": {
                "AbilityName": {"Value": "Skill_Insert"},
                "AbilityTarget": {"$type": "RPG.GameCore.TargetAlias", "Alias": "AllEnemy"},
                "AutoCast": True,
                "AutoCastTargetType": {"$type": "RPG.GameCore.TargetAlias", "Alias": "AllEnemy"},
                "InsertActionPriority": "Windfury",
                "ShowInActionBar": False,
                "CanRunAfterFightFinish": True,
                "CanRunOnUnselectableTarget": True,
                "CustomTags": [{"Value": "ActionTag_Windfury"}],
            },
        })
        self.assertEqual(spec.ability_name, "Skill_Insert")
        self.assertEqual(spec.insert_priority, "Windfury")
        self.assertEqual(spec.custom_tags, ("ActionTag_Windfury",))


if __name__ == "__main__":
    unittest.main()
