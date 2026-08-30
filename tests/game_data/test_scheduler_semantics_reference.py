"""Tests for SCHEDULER-001 reference semantics."""
from __future__ import annotations

from decimal import Decimal
import unittest

from hsr_battle_agent.game_data.scheduler_semantics_reference import (
    ActionDelayState,
    InsertedActionSpec,
    LoopSpec,
    OrdinaryTurnTimeline,
    SchedulerSemanticError,
    TaskState,
    apply_delay_operation,
    complete_ordinary_action,
    conditional_loop_expand,
    expand_template_invocation,
    ordered_ordinary_candidates,
    select_initial_ordinary_actor,
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

    def test_ordinary_completion_recharges_then_stably_advances_property_38_scope(self) -> None:
        timeline = OrdinaryTurnTimeline(
            action_order=("p1105", "p1307", "m4014030"),
            remaining_delays={
                "p1105": Decimal("0"),
                "p1307": Decimal("20"),
                "m4014030": Decimal("30"),
            },
            current_actor_id="p1105",
            turn_index=1,
        )
        transition = complete_ordinary_action(
            timeline,
            actor_id="p1105",
            eligible_ids=("p1105", "p1307", "m4014030"),
            speeds={
                "p1105": Decimal("100"),
                "p1307": Decimal("100"),
                "m4014030": Decimal("100"),
            },
        )
        self.assertEqual(transition.recharged_delay, Decimal("100"))
        self.assertEqual(transition.ordered_candidates_before_advance, ("p1307", "m4014030", "p1105"))
        self.assertEqual(transition.selected_actor_id, "p1307")
        self.assertEqual(transition.selected_delay, Decimal("20"))
        self.assertEqual(
            transition.timeline.remaining_delays,
            {"p1307": Decimal("0"), "m4014030": Decimal("10"), "p1105": Decimal("80")},
        )
        self.assertEqual(transition.timeline.current_actor_id, "p1307")
        self.assertEqual(transition.timeline.elapsed_action_delay, Decimal("20"))
        self.assertEqual(transition.timeline.turn_index, 2)

    def test_ordinary_initial_selection_uses_stable_prior_action_list_tie_order(self) -> None:
        timeline = OrdinaryTurnTimeline(
            action_order=("b", "a"),
            remaining_delays={"b": Decimal("0"), "a": Decimal("0")},
        )
        transition = select_initial_ordinary_actor(timeline, ("a", "b"))
        self.assertEqual(transition.ordered_candidates_before_advance, ("b", "a"))
        self.assertEqual(transition.selected_actor_id, "b")
        self.assertEqual(ordered_ordinary_candidates(timeline, ("a", "b")), ("b", "a"))

    def test_ordinary_completion_rejects_wrong_actor_or_nonpositive_speed(self) -> None:
        timeline = OrdinaryTurnTimeline(
            action_order=("p1", "e1"),
            remaining_delays={"p1": Decimal("0"), "e1": Decimal("5")},
            current_actor_id="p1",
        )
        with self.assertRaisesRegex(SchedulerSemanticError, "match the active"):
            complete_ordinary_action(timeline, actor_id="e1", eligible_ids=("p1", "e1"), speeds={"e1": Decimal("100")})
        with self.assertRaisesRegex(SchedulerSemanticError, "positive explicit speed"):
            complete_ordinary_action(timeline, actor_id="p1", eligible_ids=("p1", "e1"), speeds={"p1": Decimal("0")})

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
