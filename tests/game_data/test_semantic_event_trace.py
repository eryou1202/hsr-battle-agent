"""Tests for the KERNEL-EVENT-001 reference trace contract."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from hsr_battle_agent.game_data.semantic_event_trace import (
    DeterministicEventTracer,
    UnsupportedSemanticOperation,
)


def operation(identifier: str, *, status: str = "MODELLED", risk: str = "NONE", kind: str = "TEST", children: list[dict] | None = None) -> dict:
    return {
        "operation_id": identifier,
        "source_type": "Test.Operation",
        "kind": kind,
        "semantic_status": status,
        "gating_risk": risk,
        "node_role": "OPERATION",
        "children": children or [],
    }


class SemanticEventTraceTest(unittest.TestCase):
    def test_priority_then_registration_and_depth_first_order(self) -> None:
        tracer = DeterministicEventTracer()
        tracer.register(event="OnPhase1", owner_instance_id="bs", behavior_id="setup", entrypoint_id="setup", priority=-11, operations=[operation("setup", children=[{"field_path":"SuccessTaskList", "operations":[operation("setup-child")]}])])
        tracer.register(event="OnPhase1", owner_instance_id="stage", behavior_id="stage", entrypoint_id="stage", priority=0, operations=[operation("stage")])
        tracer.register(event="OnPhase1", owner_instance_id="bs", behavior_id="cleanup", entrypoint_id="cleanup", priority=200, operations=[operation("cleanup")])
        result = tracer.trace(["onphase1"])
        self.assertEqual([step.operation_id for step in result.trace], ["setup", "setup-child", "stage", "cleanup"])
        self.assertEqual([step.priority for step in result.trace], [-11, -11, 0, 200])
        self.assertTrue(result.executable)

    def test_nested_event_is_fifo_after_current_entrypoint(self) -> None:
        tracer = DeterministicEventTracer()
        tracer.register(event="A", owner_instance_id="a", behavior_id="a", entrypoint_id="a", operations=[operation("a-emit"), operation("a-after")])
        tracer.register(event="B", owner_instance_id="b", behavior_id="b", entrypoint_id="b", operations=[operation("b")])
        result = tracer.trace(["A"], nested_events_after_operation={"a-emit":["B"]})
        self.assertEqual([step.operation_id for step in result.trace], ["a-emit", "a-after", "b"])
        self.assertEqual(result.queued_events, ("A", "B"))

    def test_nested_event_waits_for_all_registrations_of_current_event(self) -> None:
        tracer = DeterministicEventTracer()
        tracer.register(event="A", owner_instance_id="a", behavior_id="a", entrypoint_id="first", operations=[operation("a-first-emit")])
        tracer.register(event="A", owner_instance_id="a", behavior_id="a", entrypoint_id="second", operations=[operation("a-second")])
        tracer.register(event="B", owner_instance_id="b", behavior_id="b", entrypoint_id="b", operations=[operation("b")])
        result = tracer.trace(["A"], nested_events_after_operation={"a-first-emit":["B"]})
        self.assertEqual([step.operation_id for step in result.trace], ["a-first-emit", "a-second", "b"])

    def test_opaque_or_uncompiled_operation_never_becomes_noop(self) -> None:
        tracer = DeterministicEventTracer()
        tracer.register(event="A", owner_instance_id="a", behavior_id="a", entrypoint_id="a", operations=[operation("opaque", status="OPAQUE")])
        result = tracer.trace(["A"])
        self.assertFalse(result.executable)
        self.assertEqual(result.trace[0].trace_disposition, "OPAQUE_BLOCKS_EXECUTION")
        with self.assertRaises(UnsupportedSemanticOperation):
            tracer.trace(["A"], strict_semantics=True)

    def test_completion_marker_is_a_scheduler_boundary_not_presentation(self) -> None:
        tracer = DeterministicEventTracer()
        tracer.register(event="A", owner_instance_id="a", behavior_id="a", entrypoint_id="a", operations=[operation("finish", status="REQUIRES_PACKET", risk="KNOWN_STATE_COMMIT", kind="ACTION_COMPLETION_MARKER")])
        result = tracer.trace(["A"])
        self.assertFalse(result.executable)
        self.assertEqual(result.trace[0].kind, "ACTION_COMPLETION_MARKER")
        self.assertEqual(result.trace[0].commit_boundary, "PRIMITIVE_OWNED_IMMEDIATE")

    def test_real_black_swan_callbacks_and_stage_monster_entrypoints_are_ordered(self) -> None:
        corpus_path = Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json")
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        records = corpus["records"]
        black_swan = next(record for record in records if record["owner_ref"] == "Avatar_BlackSwan_00_PassiveSkill01")
        stage = next(record for record in records if record["owner_kind"] == "StageBuff" and any(entry.get("source_event") == "OnAdd" for entry in record["entrypoints"]))
        monster = next(record for record in records if record["owner_kind"] == "Monster" and any(entry.get("source_event") == "OnStart" for entry in record["entrypoints"]))
        tracer = DeterministicEventTracer()
        tracer.register_behavior_record(black_swan, owner_instance_id="bs")
        tracer.register_behavior_record(stage, owner_instance_id="stage")
        tracer.register_behavior_record(monster, owner_instance_id="monster")
        result = tracer.trace(["OnPhase1", "OnAdd", "OnStart"])
        phase = [step.priority for step in result.trace if step.event == "ONPHASE1"]
        self.assertGreaterEqual(len(phase), 2)
        self.assertEqual(phase, sorted(phase))
        self.assertTrue(any(step.event == "ONADD" for step in result.trace))
        self.assertTrue(any(step.event == "ONSTART" for step in result.trace))
