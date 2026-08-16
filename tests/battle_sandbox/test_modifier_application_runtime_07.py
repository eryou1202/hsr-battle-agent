# -*- coding: utf-8 -*-
"""Sandbox runtime tests for Modifier Application Bridge 07.

Tests intentionally cover only the E4-proven boundary:

* ordered persistent append into BattleState.modifier_state_by_entity,
* duplicate preservation at the accepted AbilityComponent.AddModifierInstance
  leaf (the full TryAddModifierInstance stack policy stays UNKNOWN),
* identity = name + owner entity + instance ordinal,
* clone / snapshot / hash / deterministic replay,
* AddModifier OnTaskBegin boundary TaskState.Success projection.

No guessed stack merge, duration expiration or modifier-effect tests exist here.
"""
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
from hsr_battle_agent.battle_ir.modifiers import (  # noqa: E402
    ModifierContainer,
    ModifierRef,
    ModifierState,
    ModifierTaskApplication,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402

MODIFIER_IDS = {
    "battle.ir.action.add_modifier_executor_init",
    "battle.ir.modifier.add_modifier_task_begin_apply",
    "battle.ir.modifier.apply_modifier_instance",
    "battle.ir.modifier.container_get_by_index",
    "battle.ir.modifier.container_index_of",
    "battle.ir.modifier.container_has_modifier_by_name",
    "battle.ir.modifier.container_count",
    "battle.ir.modifier.state_name",
    "battle.ir.modifier.state_count",
    "battle.ir.modifier.state_state_raw",
    "battle.ir.modifier.state_stacking_flag_raw",
    "battle.ir.modifier.state_caster_entity",
    "battle.ir.modifier.state_layer",
    "battle.ir.modifier.state_max_layer",
    "battle.ir.modifier.state_current_life",
    "battle.ir.modifier.state_source_entity",
}


def make_modifier(
    *,
    name: str = "TestModifier",
    owner: EntityRef = EntityRef(1),
    layer: int = 1,
    current_life: int = 3,
    state_raw: int = 1,
    count: int = 1,
    source: EntityRef | None = None,
    caster: EntityRef | None = None,
) -> ModifierState:
    return ModifierState(
        name=name,
        owner_entity=owner,
        instance_ordinal=0,
        state_raw=state_raw,
        stacking_flag_raw=0,
        count=count,
        layer=layer,
        max_layer=max(1, layer),
        current_life=current_life,
        source_entity=source,
        caster_entity=caster,
    )


class TestModifierPrimitiveRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()

    def test_all_modifier_primitives_registered(self):
        self.assertTrue(MODIFIER_IDS.issubset(set(self.registry.known_primitive_ids)))

    def test_specs_and_provenance_come_from_semantic_artifact(self):
        for primitive_id in sorted(MODIFIER_IDS):
            with self.subTest(primitive_id=primitive_id):
                registered = self.registry.resolve(primitive_id)
                self.assertEqual(registered.spec.primitive_id, primitive_id)
                self.assertIn("4.4.54:", registered.provenance_ref or "")
                self.assertEqual(registered.spec.determinism, "DETERMINISTIC")
                self.assertEqual(registered.spec.context_writes, ())

    def test_state_write_spec_is_declared(self):
        spec = self.registry.resolve(
            "battle.ir.modifier.apply_modifier_instance"
        ).spec
        self.assertEqual(spec.result, "modifier_container")
        self.assertEqual(spec.input_names, ("target", "modifier"))


class TestNormalApplicationThroughExecutor(unittest.TestCase):
    def test_pre_apply_to_post_battle_state_transition(self):
        sandbox = Sandbox(seed=7)
        before_hash = sandbox.state_hash()
        before_state = sandbox.context.state.to_dict()
        modifier = make_modifier(owner=EntityRef(42), source=EntityRef(10))

        result = sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=EntityRef(42),
            modifier=modifier,
        )

        self.assertIsInstance(result.value, ModifierContainer)
        self.assertEqual(result.value.count, 1)
        applied = result.value.items[0]
        self.assertEqual(applied.name, "TestModifier")
        self.assertEqual(applied.owner_entity, EntityRef(42))
        self.assertEqual(applied.instance_ordinal, 0)
        self.assertEqual(applied.source_entity, EntityRef(10))
        self.assertNotEqual(sandbox.state_hash(), before_hash)

        post_state = sandbox.context.state.to_dict()
        raw = post_state["modifier_state_by_entity"]["42"]
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["name"], "TestModifier")
        self.assertEqual(raw[0]["instance_ordinal"], 0)
        # Pre-state clone is unchanged: executor only mutates the live branch.
        self.assertEqual(before_state["modifier_state_by_entity"], {})

    def test_add_modifier_executor_init_then_task_boundary(self):
        sandbox = Sandbox(seed=11)
        execution = sandbox.execute(
            "battle.ir.action.add_modifier_executor_init",
            config="RPG.GameCore.AddModifier",
        ).value
        self.assertEqual(execution.task_state, TaskState.READY)

        application = sandbox.execute(
            "battle.ir.modifier.add_modifier_task_begin_apply",
            execution=execution,
            targets=TargetSet.of(EntityRef(5), EntityRef(6)),
            modifier=make_modifier(owner=EntityRef(0), layer=2),
        ).value

        self.assertIsInstance(application, ModifierTaskApplication)
        self.assertEqual(application.task_state, TaskState.SUCCESS)
        self.assertEqual(
            application.applied_refs,
            (
                ModifierRef("TestModifier", EntityRef(5), 0),
                ModifierRef("TestModifier", EntityRef(6), 0),
            ),
        )
        state = sandbox.context.state.to_dict()["modifier_state_by_entity"]
        self.assertEqual([item["name"] for item in state["5"]], ["TestModifier"])
        self.assertEqual([item["name"] for item in state["6"]], ["TestModifier"])
        self.assertEqual(state["5"][0]["layer"], 2)

    def test_cross_layer_target_to_modifier_to_persistent_state(self):
        sandbox = Sandbox(seed=13)
        sandbox.context.task_action_target = EntityRef(99)

        targets = sandbox.execute("battle.ir.target.select_task_action_target").value
        single = sandbox.execute(
            "battle.ir.target.collapse_single_or_null", targets=targets
        ).value
        execution = sandbox.execute(
            "battle.ir.action.add_modifier_executor_init",
            config="RPG.GameCore.AddModifier",
        ).value

        sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=single,
            modifier=make_modifier(owner=single),
        )

        raw = sandbox.context.state.modifier_state_by_entity["99"]
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0]["owner_entity"]["runtime_id"], 99)
        self.assertEqual(execution.task_state, TaskState.READY)

    def test_task_boundary_is_deterministic_replay(self):
        def run() -> dict:
            sandbox = Sandbox(seed=21)
            sandbox.execute(
                "battle.ir.action.add_modifier_executor_init",
                config="RPG.GameCore.AddModifier",
            )
            sandbox.execute(
                "battle.ir.modifier.add_modifier_task_begin_apply",
                execution=TaskExecutionState(),
                targets=TargetSet.of(EntityRef(1), EntityRef(2), EntityRef(1)),
                modifier=make_modifier(),
            )
            return sandbox.context.state.to_dict()

        first = run()
        second = run()
        self.assertEqual(first, second)


class TestContainerSemantics(unittest.TestCase):
    def test_ordered_append_and_positional_read(self):
        container = ModifierContainer()
        a = make_modifier(name="A", owner=EntityRef(1))
        b = make_modifier(name="B", owner=EntityRef(1))
        container = container.append(a).append(b)
        self.assertEqual(container.get_by_index(0).name, "A")
        self.assertEqual(container.get_by_index(1).name, "B")
        self.assertIsNone(container.get_by_index(2))
        self.assertIsNone(container.get_by_index(-1))
        self.assertEqual(container.count, 2)

    def test_duplicate_application_is_preserved_by_append_leaf(self):
        """AbilityComponent.AddModifierInstance never deduplicates.

        Full TryAddModifierInstance duplicate stack policy remains UNKNOWN; the
        accepted persistent-write leaf is append-only.
        """
        sandbox = Sandbox()
        target = EntityRef(3)
        first = make_modifier(owner=target, layer=1)
        second = make_modifier(owner=target, layer=2)
        sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=target,
            modifier=first,
        )
        container = sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=target,
            modifier=second,
        ).value
        self.assertEqual(container.count, 2)
        self.assertEqual(container.items[0].instance_ordinal, 0)
        self.assertEqual(container.items[1].instance_ordinal, 1)
        raw = sandbox.context.state.modifier_state_by_entity["3"]
        self.assertEqual([item["layer"] for item in raw], [1, 2])

    def test_index_of_and_has_modifier_query(self):
        target = EntityRef(4)
        container = ModifierContainer.of(
            ModifierState(
                name="Shield",
                owner_entity=target,
                instance_ordinal=0,
                state_raw=1,
            ),
            ModifierState(
                name="Shield",
                owner_entity=target,
                instance_ordinal=1,
                state_raw=1,
            ),
            ModifierState(
                name="Regen",
                owner_entity=target,
                instance_ordinal=2,
                state_raw=0,
            ),
        )
        sandbox = Sandbox()
        self.assertEqual(
            sandbox.execute(
                "battle.ir.modifier.container_index_of",
                container=container,
                modifier=container.items[1],
            ).value,
            1,
        )
        self.assertTrue(
            sandbox.execute(
                "battle.ir.modifier.container_has_modifier_by_name",
                container=container,
                name="Shield",
            ).value
        )
        # Raw state != 1 is skipped by the native HasModifier body.
        self.assertFalse(
            sandbox.execute(
                "battle.ir.modifier.container_has_modifier_by_name",
                container=container,
                name="Regen",
            ).value
        )
        self.assertEqual(
            sandbox.execute(
                "battle.ir.modifier.container_count", container=container
            ).value,
            3,
        )


class TestModifierStateLeaves(unittest.TestCase):
    def test_state_getters_dispatch_and_return_proven_slots(self):
        sandbox = Sandbox()
        modifier = make_modifier(
            name="Burn",
            owner=EntityRef(8),
            layer=3,
            current_life=4,
            state_raw=1,
            count=2,
            source=EntityRef(12),
            caster=EntityRef(13),
        )
        self.assertEqual(
            sandbox.execute("battle.ir.modifier.state_name", modifier=modifier).value,
            "Burn",
        )
        self.assertEqual(
            sandbox.execute("battle.ir.modifier.state_count", modifier=modifier).value,
            2,
        )
        self.assertEqual(
            sandbox.execute("battle.ir.modifier.state_state_raw", modifier=modifier).value,
            1,
        )
        self.assertEqual(
            sandbox.execute(
                "battle.ir.modifier.state_stacking_flag_raw", modifier=modifier
            ).value,
            0,
        )
        self.assertEqual(
            sandbox.execute("battle.ir.modifier.state_layer", modifier=modifier).value,
            3,
        )
        self.assertEqual(
            sandbox.execute("battle.ir.modifier.state_max_layer", modifier=modifier).value,
            3,
        )
        self.assertEqual(
            sandbox.execute(
                "battle.ir.modifier.state_current_life", modifier=modifier
            ).value,
            4,
        )
        self.assertEqual(
            sandbox.execute(
                "battle.ir.modifier.state_source_entity", modifier=modifier
            ).value,
            EntityRef(12),
        )
        self.assertEqual(
            sandbox.execute(
                "battle.ir.modifier.state_caster_entity", modifier=modifier
            ).value,
            EntityRef(13),
        )

    def test_modifier_state_roundtrip_and_trace_summary(self):
        modifier = make_modifier(
            name="Poison", owner=EntityRef(9), source=EntityRef(1), caster=EntityRef(2)
        )
        restored = ModifierState.from_dict(modifier.to_dict())
        self.assertEqual(restored, modifier)
        self.assertEqual(restored.ref, modifier.ref)
        self.assertIn("modifier_ref:Poison", restored.trace_summary())


class TestInvalidAndNullInputs(unittest.TestCase):
    def test_apply_rejects_null_target(self):
        sandbox = Sandbox()
        with self.assertRaises(TypeError):
            sandbox.execute(
                "battle.ir.modifier.apply_modifier_instance",
                target=None,
                modifier=make_modifier(),
            )

    def test_task_boundary_rejects_null_target_element(self):
        sandbox = Sandbox()
        with self.assertRaises(ValueError):
            sandbox.execute(
                "battle.ir.modifier.add_modifier_task_begin_apply",
                execution=TaskExecutionState(),
                targets=TargetSet.of(EntityRef(1), None),
                modifier=make_modifier(),
            )

    def test_task_boundary_rejects_invalid_modifier_type(self):
        sandbox = Sandbox()
        with self.assertRaises(TypeError):
            sandbox.execute(
                "battle.ir.modifier.add_modifier_task_begin_apply",
                execution=TaskExecutionState(),
                targets=TargetSet.of(EntityRef(1)),
                modifier=object(),
            )

    def test_empty_target_set_is_allowed_and_produces_no_writes(self):
        sandbox = Sandbox()
        before = sandbox.state_hash()
        result = sandbox.execute(
            "battle.ir.modifier.add_modifier_task_begin_apply",
            execution=TaskExecutionState(),
            targets=TargetSet(),
            modifier=make_modifier(),
        ).value
        self.assertEqual(result.applied_refs, ())
        self.assertEqual(result.task_state, TaskState.SUCCESS)
        self.assertEqual(sandbox.state_hash(), before)


class TestCloneSnapshotHashIsolation(unittest.TestCase):
    def test_clone_isolation_for_modifier_state(self):
        sandbox = Sandbox(seed=31)
        branch = sandbox.clone()
        branch.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=EntityRef(10),
            modifier=make_modifier(owner=EntityRef(10)),
        )
        self.assertEqual(sandbox.context.state.modifier_state_by_entity, {})
        self.assertEqual(len(branch.context.state.modifier_state_by_entity["10"]), 1)
        self.assertNotEqual(sandbox.state_hash(), branch.state_hash())

    def test_snapshot_roundtrip_preserves_modifier_state(self):
        sandbox = Sandbox(seed=33)
        sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=EntityRef(11),
            modifier=make_modifier(owner=EntityRef(11)),
        )
        snapshot = sandbox.snapshot()
        restored = Sandbox(seed=1)
        restored.restore(snapshot)
        self.assertEqual(
            restored.context.state.to_dict(), sandbox.context.state.to_dict()
        )
        self.assertEqual(restored.state_hash(), sandbox.state_hash())
        self.assertEqual(
            restored.context.state.modifier_state_by_entity["11"][0]["name"],
            "TestModifier",
        )

    def test_snapshot_dict_roundtrip(self):
        sandbox = Sandbox(seed=35)
        sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=EntityRef(12),
            modifier=make_modifier(owner=EntityRef(12)),
        )
        snapshot_dict = sandbox.snapshot().to_dict()
        restored = Sandbox(seed=1)
        from hsr_battle_agent.battle_sandbox.snapshot import SandboxSnapshot

        restored.restore(SandboxSnapshot.from_dict(snapshot_dict))
        self.assertEqual(restored.state_hash(), sandbox.state_hash())

    def test_state_hash_changes_and_json_roundtrip(self):
        sandbox = Sandbox()
        before = sandbox.state_hash()
        sandbox.execute(
            "battle.ir.modifier.apply_modifier_instance",
            target=EntityRef(13),
            modifier=make_modifier(owner=EntityRef(13)),
        )
        after = sandbox.state_hash()
        self.assertNotEqual(before, after)
        raw = sandbox.context.state.to_dict()
        json.dumps(raw)  # strict JSON contract remains valid
        from hsr_battle_agent.battle_sandbox.state import BattleState

        restored = BattleState.from_dict(raw)
        self.assertEqual(restored.to_dict(), raw)
        self.assertEqual(
            restored.state_hash(), sandbox.context.state.state_hash()
        )


if __name__ == "__main__":
    unittest.main()
