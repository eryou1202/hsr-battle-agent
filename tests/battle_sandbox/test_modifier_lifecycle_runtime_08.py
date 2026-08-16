# -*- coding: utf-8 -*-
"""Sandbox kernel tests for Modifier Lifecycle Bridge 08.

All lifecycle mutations go through the formal PrimitiveRegistry/Executor path
(``Sandbox.execute``), so these tests also cover spec validation, provenance,
trace summarization, clone isolation, snapshot roundtrip and state hashing.
"""
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
from hsr_battle_agent.battle_ir.modifiers import (  # noqa: E402
    ModifierLifecycleResult,
    ModifierMatchKey,
    ModifierStacking,
    ModifierState,
    ModifierStateValue,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_ir.values import ObjectRef  # noqa: E402
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402

LIFECYCLE_IDS = {
    "battle.ir.modifier.try_add_modifier_instance",
    "battle.ir.modifier.container_find_modifier_instance",
    "battle.ir.modifier.match_modifier_search",
    "battle.ir.modifier.lifecycle_destroy",
    "battle.ir.modifier.container_remove_dirty",
    "battle.ir.modifier.lifecycle_process_redd",
    "battle.ir.modifier.lifecycle_on_added",
    "battle.ir.modifier.lifecycle_on_activate",
}


def make_modifier(
    *,
    name: str = "LifecycleModifier",
    owner: EntityRef = EntityRef(42),
    count: int = 1,
    life: int = 3,
    layer: int = 1,
    max_layer: int = 3,
    state: int = 1,
    caster: EntityRef | None = None,
    source_ref: ObjectRef | None = None,
) -> ModifierState:
    return ModifierState(
        name=name,
        owner_entity=owner,
        state_raw=state,
        count=count,
        layer=layer,
        max_layer=max_layer,
        current_life=life,
        caster_entity=caster,
        source_provider_ref=source_ref,
    )


def try_add(
    sandbox: Sandbox,
    target: EntityRef,
    modifier: ModifierState,
    stacking: int,
    *,
    stacking_flag: int = 0,
    caster: EntityRef | None = None,
    source_ref: ObjectRef | None = None,
) -> ModifierLifecycleResult:
    result = sandbox.execute(
        "battle.ir.modifier.try_add_modifier_instance",
        target=target,
        modifier=modifier,
        stacking=stacking,
        stacking_flag=stacking_flag,
        caster_entity=caster,
        source_provider_ref=source_ref,
        activate=True,
    )
    self = result.value
    assert isinstance(self, ModifierLifecycleResult)
    return self


class TestLifecycleRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()

    def test_lifecycle_primitives_registered_from_artifact(self):
        self.assertTrue(
            LIFECYCLE_IDS.issubset(set(self.registry.known_primitive_ids))
        )
        for primitive_id in sorted(LIFECYCLE_IDS):
            with self.subTest(primitive_id=primitive_id):
                registered = self.registry.resolve(primitive_id)
                self.assertEqual(registered.spec.primitive_id, primitive_id)
                self.assertIn("4.4.54:", registered.provenance_ref or "")
                self.assertEqual(registered.spec.determinism, "DETERMINISTIC")

    def test_try_add_spec_contract(self):
        spec = self.registry.resolve(
            "battle.ir.modifier.try_add_modifier_instance"
        ).spec
        self.assertEqual(spec.result, "modifier_lifecycle_result")
        self.assertEqual(
            spec.input_names,
            (
                "target",
                "modifier",
                "stacking",
                "stacking_flag",
                "caster_entity",
                "source_provider_ref",
                "activate",
            ),
        )


class TestLifecycleThroughExecutor(unittest.TestCase):
    def test_apply_to_empty_changes_state_hash(self):
        sandbox = Sandbox(seed=11)
        before = sandbox.state_hash()
        result = try_add(
            sandbox,
            EntityRef(42),
            make_modifier(),
            int(ModifierStacking.UNKNOW),
        )
        after = sandbox.state_hash()
        self.assertEqual(result.disposition, "APPENDED")
        self.assertNotEqual(before, after)

    def test_duplicate_application_branch(self):
        sandbox = Sandbox(seed=12)
        template = make_modifier()
        try_add(sandbox, EntityRef(42), template, int(ModifierStacking.UNKNOW))
        result = try_add(
            sandbox, EntityRef(42), template, int(ModifierStacking.MULTIPLE)
        )
        self.assertEqual(result.disposition, "DUPLICATE_APPENDED")
        items = sandbox.context.state.modifier_state_by_entity["42"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["instance_ordinal"], 0)
        self.assertEqual(items[1]["instance_ordinal"], 1)

    def test_destroy_and_remove_dirty_branch_preserves_order(self):
        sandbox = Sandbox(seed=13)
        keep0 = make_modifier(name="keep0")
        dead1 = make_modifier(name="dead1", state=2)
        keep2 = make_modifier(name="keep2")
        state = sandbox.context.state
        state.set_modifier_collection(
            42,
            [
                {"schema": "battle_ir_modifiers/1", "kind": "ModifierState",
                 **{**keep0.to_dict(), "instance_ordinal": 0}},
                {"schema": "battle_ir_modifiers/1", "kind": "ModifierState",
                 **{**dead1.to_dict(), "instance_ordinal": 1}},
                {"schema": "battle_ir_modifiers/1", "kind": "ModifierState",
                 **{**keep2.to_dict(), "instance_ordinal": 2}},
            ],
        )
        container = sandbox.execute(
            "battle.ir.modifier.container_remove_dirty", target=EntityRef(42)
        ).value
        self.assertEqual([item.name for item in container.items], ["keep0", "keep2"])
        self.assertEqual(
            [item.instance_ordinal for item in container.items], [0, 2]
        )

    def test_retain_global_latest_replace_branch(self):
        sandbox = Sandbox(seed=14)
        template = make_modifier()
        try_add(sandbox, EntityRef(42), template, int(ModifierStacking.UNKNOW))
        result = try_add(
            sandbox,
            EntityRef(42),
            template,
            int(ModifierStacking.RETAIN_GLOBAL_LATEST),
        )
        self.assertEqual(result.disposition, "DESTROYED_AND_APPENDED")
        items = sandbox.context.state.modifier_state_by_entity["42"]
        self.assertEqual(
            [item["state_raw"] for item in items],
            [int(ModifierStateValue.TO_BE_REMOVED), int(ModifierStateValue.ALIVE)],
        )
        # The old entry leaves the list only on RemoveDirtyModifiers.
        container = sandbox.execute(
            "battle.ir.modifier.container_remove_dirty", target=EntityRef(42)
        ).value
        self.assertEqual([item.state_raw for item in container.items], [1])

    def test_refresh_branch_updates_life_and_count(self):
        sandbox = Sandbox(seed=15)
        try_add(sandbox, EntityRef(42), make_modifier(), int(ModifierStacking.UNKNOW))
        result = try_add(
            sandbox,
            EntityRef(42),
            make_modifier(count=4, life=9),
            int(ModifierStacking.REFRESH),
        )
        self.assertEqual(result.disposition, "EXISTING_PROCESSED")
        self.assertEqual(result.modifier.current_life, 9)
        self.assertEqual(result.modifier.count, 4)

    def test_not_found_behavior_is_append(self):
        sandbox = Sandbox(seed=16)
        result = try_add(
            sandbox, EntityRef(42), make_modifier(name="missing"),
            int(ModifierStacking.REFRESH),
        )
        self.assertEqual(result.disposition, "APPENDED")

    def test_source_provider_identity_through_executor(self):
        sandbox = Sandbox(seed=17)
        source_ref = ObjectRef(ref_id=9001)
        first = try_add(
            sandbox,
            EntityRef(42),
            make_modifier(name="S", source_ref=source_ref),
            int(ModifierStacking.UNKNOW),
            source_ref=source_ref,
        )
        self.assertEqual(first.disposition, "APPENDED")
        result = try_add(
            sandbox,
            EntityRef(42),
            make_modifier(name="S", source_ref=source_ref),
            int(ModifierStacking.REPLACE_BY_CASTER),
            source_ref=source_ref,
        )
        self.assertEqual(result.disposition, "EXISTING_PROCESSED")

    def test_match_predicate_through_executor(self):
        sandbox = Sandbox(seed=18)
        match_key = ModifierMatchKey(name="A", stacking_flag=0)
        matched = sandbox.execute(
            "battle.ir.modifier.match_modifier_search",
            modifier=make_modifier(name="A"),
            match_key=match_key,
            state_filter=0,
        ).value
        self.assertTrue(matched)
        missed = sandbox.execute(
            "battle.ir.modifier.match_modifier_search",
            modifier=make_modifier(name="B"),
            match_key=match_key,
            state_filter=0,
        ).value
        self.assertFalse(missed)

    def test_on_added_does_not_change_state_hash(self):
        sandbox = Sandbox(seed=19)
        modifier = make_modifier()
        try_add(sandbox, EntityRef(42), modifier, int(ModifierStacking.UNKNOW))
        before = sandbox.state_hash()
        sandbox.execute("battle.ir.modifier.lifecycle_on_added", modifier=modifier)
        self.assertEqual(sandbox.state_hash(), before)

    def test_on_activate_transitions_state(self):
        sandbox = Sandbox(seed=20)
        modifier = make_modifier(state=0)
        state = sandbox.context.state
        state.set_modifier_collection(42, [modifier.to_dict()])
        updated = sandbox.execute(
            "battle.ir.modifier.lifecycle_on_activate",
            target=EntityRef(42),
            modifier=modifier,
        ).value
        self.assertEqual(updated.state_raw, int(ModifierStateValue.ALIVE))


class TestCloneSnapshotHashReplay(unittest.TestCase):
    def test_clone_divergence_is_isolated(self):
        sandbox = Sandbox(seed=21)
        try_add(sandbox, EntityRef(42), make_modifier(), int(ModifierStacking.UNKNOW))
        branch = sandbox.clone()
        self.assertEqual(branch.state_hash(), sandbox.state_hash())
        try_add(
            branch,
            EntityRef(42),
            make_modifier(),
            int(ModifierStacking.MULTIPLE),
        )
        self.assertNotEqual(branch.state_hash(), sandbox.state_hash())
        self.assertEqual(
            len(sandbox.context.state.modifier_state_by_entity["42"]), 1
        )
        self.assertEqual(
            len(branch.context.state.modifier_state_by_entity["42"]), 2
        )

    def test_snapshot_roundtrip_restores_lifecycle_state(self):
        sandbox = Sandbox(seed=22)
        try_add(sandbox, EntityRef(42), make_modifier(), int(ModifierStacking.UNKNOW))
        hash_before_branch = sandbox.context.state.state_hash()
        snapshot = sandbox.snapshot()
        try_add(
            sandbox,
            EntityRef(42),
            make_modifier(),
            int(ModifierStacking.RETAIN_GLOBAL_LATEST),
        )
        self.assertEqual(
            len(sandbox.context.state.modifier_state_by_entity["42"]), 2
        )
        restored = snapshot.restore_context()
        self.assertEqual(
            len(restored.state.modifier_state_by_entity["42"]), 1
        )
        self.assertEqual(restored.state.state_hash(), hash_before_branch)
        self.assertNotEqual(
            restored.state.state_hash(), sandbox.context.state.state_hash()
        )

    def test_deterministic_replay(self):
        def run():
            sandbox = Sandbox(seed=23)
            try_add(sandbox, EntityRef(42), make_modifier(), int(ModifierStacking.UNKNOW))
            try_add(
                sandbox,
                EntityRef(42),
                make_modifier(),
                int(ModifierStacking.RETAIN_GLOBAL_LATEST),
            )
            last = sandbox.context.trace.events[-1]
            return sandbox.state_hash(), last.primitive_id, last.result

        self.assertEqual(run(), run())


class TestCrossLayerChain(unittest.TestCase):
    def test_executor_init_try_add_remove_dirty_formal_path(self):
        sandbox = Sandbox(seed=24)
        execution = sandbox.execute(
            "battle.ir.action.add_modifier_executor_init",
            config="RPG.GameCore.AddModifier",
        ).value
        self.assertIsInstance(execution, TaskExecutionState)
        self.assertEqual(execution.task_state, TaskState.READY)
        targets = TargetSet.of(EntityRef(42))
        result = try_add(
            sandbox,
            targets.items[0],
            make_modifier(),
            int(ModifierStacking.UNKNOW),
        )
        self.assertEqual(result.disposition, "APPENDED")
        container = sandbox.execute(
            "battle.ir.modifier.container_remove_dirty", target=EntityRef(42)
        ).value
        self.assertEqual(container.count, 1)
        self.assertEqual(container.items[0].state_raw, 1)


if __name__ == "__main__":
    unittest.main()
