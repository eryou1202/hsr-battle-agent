# -*- coding: utf-8 -*-
"""Sandbox kernel tests for Generic Property Runtime (Handoffs 09/10/11).

All property mutations travel through the formal PrimitiveRegistry / Executor
path, so these tests also cover artifact binding, provenance, trace boundary
summaries, clone isolation, snapshot roundtrip and deterministic state hash.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.modifiers import (  # noqa: E402
    ModifierState,
)
from hsr_battle_agent.battle_ir.property import (  # noqa: E402
    CURRENT_HP_PROPERTY_ID,
    MaterializationKind,
    PropertyEntry,
    PropertyModifyFunction,
    StackPropertyTaskConfig,
    StackPropertyTaskContext,
)
from hsr_battle_agent.battle_ir.targets import EntityRef, TargetSet  # noqa: E402
from hsr_battle_agent.battle_runtime import property as property_runtime  # noqa: E402
from hsr_battle_agent.battle_runtime.predicates import (  # noqa: E402
    fixpoint_equal,
    fixpoint_from_int32,
)
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry  # noqa: E402
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox  # noqa: E402
from hsr_battle_agent.battle_sandbox.state import (  # noqa: E402
    BATTLE_STATE_SCHEMA_VERSION,
    BattleState,
)


def fp(value: int) -> int:
    return fixpoint_from_int32(value)


PROPERTY_PRIMITIVE_IDS = {
    "battle.ir.task.stack_property_executor_init",
    "battle.ir.task.stack_property_execute",
    "battle.ir.modifier.stack_property_contribution",
    "battle.ir.modifier.pop_property_contributions",
    "battle.ir.property.component_stack_boundary",
    "battle.ir.property.component_unstack_boundary",
    "battle.ir.property.component_stack_source",
    "battle.ir.property.update_contribution_source",
    "battle.ir.property.remove_contribution_source",
    "battle.ir.property.allocate_source_slot",
    "battle.ir.property.update_source_slot",
    "battle.ir.property.remove_source_slot",
    "battle.ir.property.rebuild_materialized",
    "battle.ir.property.materialize_kind_3",
    "battle.ir.property.materialize_kind_4",
    "battle.ir.property.materialize_kind_5",
    "battle.ir.property.materialize_kind_6",
    "battle.ir.property.materialize_kind_7",
    "battle.ir.fixedpoint.add",
    "battle.ir.fixedpoint.subtract",
    "battle.ir.fixedpoint.multiply",
    "battle.ir.property.apply_modify_function",
    "battle.ir.property.modify_source_zero_untransformed",
}


def make_modifier(
    *,
    name: str,
    ordinal: int,
    owner: EntityRef = EntityRef(1),
    state: int = 1,
) -> ModifierState:
    return ModifierState(
        name=name,
        owner_entity=owner,
        instance_ordinal=ordinal,
        state_raw=state,
    )


def seed_additive_entry(sandbox: Sandbox, entity: EntityRef, property_id: int) -> None:
    property_runtime.ensure_property_entry(
        sandbox.context.state,
        entity,
        property_id,
        materialization_kind=int(
            MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
        ),
        base_or_fallback=0,
    )


class TestPropertyRegistryBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = PrimitiveRegistry.create_default()

    def test_all_09_10_11_primitives_are_registered_from_catalog(self):
        self.assertTrue(
            PROPERTY_PRIMITIVE_IDS.issubset(
                set(self.registry.known_primitive_ids)
            )
        )
        for primitive_id in sorted(PROPERTY_PRIMITIVE_IDS):
            with self.subTest(primitive_id=primitive_id):
                registered = self.registry.resolve(primitive_id)
                self.assertEqual(registered.spec.primitive_id, primitive_id)
                self.assertIn("4.4.54:", registered.provenance_ref or "")
                self.assertEqual(
                    registered.provenance_ref.startswith("4.4.54:"),
                    True,
                )

    def test_source_slot_spec_contracts(self):
        allocate = self.registry.resolve(
            "battle.ir.property.allocate_source_slot"
        ).spec
        self.assertEqual(allocate.input_names, ("property_entry", "source_value"))
        self.assertEqual(allocate.result, "source_index:int32")
        update = self.registry.resolve(
            "battle.ir.property.update_source_slot"
        ).spec
        self.assertEqual(
            update.input_names,
            ("property_entry", "source_index", "source_value"),
        )

    def test_modify_spec_contract(self):
        spec = self.registry.resolve(
            "battle.ir.property.modify_source_zero_untransformed"
        ).spec
        self.assertEqual(
            spec.input_names,
            ("component", "property_id", "function_id", "operand", "context_token"),
        )
        self.assertEqual(spec.result, "bool changed")


class TestFullStateTransition(unittest.TestCase):
    def test_modifier_a_b_ownership_survives_pop_correctly(self):
        sandbox = Sandbox(seed=101)
        entity = EntityRef(1)
        property_id = 5
        seed_additive_entry(sandbox, entity, property_id)
        modifier_a = make_modifier(name="A", ordinal=0)
        modifier_b = make_modifier(name="B", ordinal=1)

        hash0 = sandbox.state_hash()
        index_a = sandbox.execute(
            "battle.ir.modifier.stack_property_contribution",
            modifier=modifier_a,
            property_id=property_id,
            value=fp(100),
            target_component=entity,
            context_token=None,
            is_refresh=False,
        ).value
        hash1 = sandbox.state_hash()
        index_b = sandbox.execute(
            "battle.ir.modifier.stack_property_contribution",
            modifier=modifier_b,
            property_id=property_id,
            value=fp(25),
            target_component=entity,
            context_token=None,
            is_refresh=False,
        ).value
        hash2 = sandbox.state_hash()

        self.assertEqual((index_a, index_b), (1, 2))
        self.assertNotEqual(hash0, hash1)
        self.assertNotEqual(hash1, hash2)

        sandbox.execute(
            "battle.ir.modifier.pop_property_contributions",
            modifier=modifier_a,
        )
        hash3 = sandbox.state_hash()

        entry = property_runtime.get_property_entry(
            sandbox.context.state, entity, property_id
        )
        # A disabled in place, B still active, no index shift/remap.
        self.assertEqual(entry.source_active, [False, False, True])
        self.assertEqual(entry.source_generation, [0, 0, 2])
        self.assertEqual(entry.source_value, [0, fp(100), fp(25)])
        self.assertTrue(fixpoint_equal(entry.materialized, fp(25)))
        self.assertNotIn(
            "modifier_property:1:0:A",
            sandbox.context.state.modifier_property_contributions,
        )
        self.assertIn(
            "modifier_property:1:1:B",
            sandbox.context.state.modifier_property_contributions,
        )
        self.assertNotEqual(hash2, hash3)

        # Deterministic replay yields the same hash ladder.
        def replay() -> tuple[str, str, str, str]:
            branch = Sandbox(seed=101)
            branch_entity = EntityRef(1)
            seed_additive_entry(branch, branch_entity, property_id)
            h0 = branch.state_hash()
            branch.execute(
                "battle.ir.modifier.stack_property_contribution",
                modifier=make_modifier(name="A", ordinal=0),
                property_id=property_id,
                value=fp(100),
                target_component=branch_entity,
                context_token=None,
                is_refresh=False,
            )
            h1 = branch.state_hash()
            branch.execute(
                "battle.ir.modifier.stack_property_contribution",
                modifier=make_modifier(name="B", ordinal=1),
                property_id=property_id,
                value=fp(25),
                target_component=branch_entity,
                context_token=None,
                is_refresh=False,
            )
            h2 = branch.state_hash()
            branch.execute(
                "battle.ir.modifier.pop_property_contributions",
                modifier=make_modifier(name="A", ordinal=0),
            )
            h3 = branch.state_hash()
            return h0, h1, h2, h3

        self.assertEqual(replay(), (hash0, hash1, hash2, hash3))

    def test_removed_modifier_is_noop_through_executor(self):
        sandbox = Sandbox(seed=102)
        entity = EntityRef(1)
        property_id = 5
        seed_additive_entry(sandbox, entity, property_id)
        before = sandbox.state_hash()
        result = sandbox.execute(
            "battle.ir.modifier.stack_property_contribution",
            modifier=make_modifier(name="Dead", ordinal=0, state=2),
            property_id=property_id,
            value=fp(10),
            target_component=entity,
            context_token=None,
            is_refresh=False,
        )
        self.assertIsNone(result.value)
        self.assertEqual(sandbox.state_hash(), before)

    def test_stack_property_task_primitive_through_executor(self):
        sandbox = Sandbox(seed=117)
        entity = EntityRef(1)
        property_id = 6
        seed_additive_entry(sandbox, entity, property_id)
        modifier = make_modifier(name="TaskM", ordinal=0)
        executor = sandbox.execute(
            "battle.ir.task.stack_property_executor_init",
            task_context={"modifier": modifier},
            task_config={"property_id": property_id},
        ).value
        result = sandbox.execute(
            "battle.ir.task.stack_property_execute",
            executor=executor,
            selected_targets=TargetSet.of(entity),
            evaluated_property_value=fp(11),
        ).value
        self.assertEqual(result.applied_targets, (entity,))
        self.assertEqual(result.applied_source_indices, (1,))
        self.assertIn(
            "modifier_property:1:0:TaskM",
            sandbox.context.state.modifier_property_contributions,
        )


class TestMutationThroughSandbox(unittest.TestCase):
    def test_modify_property_set_and_out_of_range_through_executor(self):
        sandbox = Sandbox(seed=103)
        entity = EntityRef(1)
        property_id = 5
        property_runtime.set_property_entry(
            sandbox.context.state,
            entity,
            property_id,
            PropertyEntry(
                source_generation=[1],
                source_active=[True],
                source_value=[fp(10)],
                materialization_kind=int(
                    MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
                ),
                generation_counter=1,
                active_source_extent=1,
                last_changed_source=0,
                base_or_fallback=0,
                materialized=fp(10),
            ),
        )
        changed = sandbox.execute(
            "battle.ir.property.modify_source_zero_untransformed",
            component=entity,
            property_id=property_id,
            function_id=int(PropertyModifyFunction.SET),
            operand=fp(7),
            context_token=None,
        ).value
        self.assertTrue(changed)
        entry = property_runtime.get_property_entry(
            sandbox.context.state, entity, property_id
        )
        self.assertTrue(fixpoint_equal(entry.materialized, fp(7)))

        changed = sandbox.execute(
            "battle.ir.property.modify_source_zero_untransformed",
            component=entity,
            property_id=property_id,
            function_id=12345,
            operand=fp(9),
            context_token=None,
        ).value
        self.assertTrue(changed)
        entry = property_runtime.get_property_entry(
            sandbox.context.state, entity, property_id
        )
        self.assertTrue(fixpoint_equal(entry.materialized, fp(9)))

    def test_current_hp_cannot_use_generic_mutation_through_executor(self):
        sandbox = Sandbox(seed=104)
        entity = EntityRef(1)
        property_runtime.ensure_property_entry(
            sandbox.context.state,
            entity,
            CURRENT_HP_PROPERTY_ID,
            materialization_kind=int(
                MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
            ),
        )
        before = sandbox.state_hash()
        with self.assertRaises(
            property_runtime.UnsupportedSpecialPropertyMutationError
        ):
            sandbox.execute(
                "battle.ir.property.modify_source_zero_untransformed",
                component=entity,
                property_id=CURRENT_HP_PROPERTY_ID,
                function_id=int(PropertyModifyFunction.SET),
                operand=fp(1),
                context_token=None,
            )
        self.assertEqual(sandbox.state_hash(), before)

    def test_post_hook_context_rejects_through_executor(self):
        sandbox = Sandbox(seed=105)
        entity = EntityRef(1)
        property_id = 5
        property_runtime.set_property_entry(
            sandbox.context.state,
            entity,
            property_id,
            PropertyEntry(
                source_generation=[1],
                source_active=[True],
                source_value=[fp(10)],
                post_hook_context={"opaque": 1},
                materialization_kind=int(
                    MaterializationKind.KIND_1_SOURCE_ZERO_SELECTION
                ),
                generation_counter=1,
                active_source_extent=1,
                last_changed_source=0,
                base_or_fallback=0,
                materialized=fp(10),
            ),
        )
        before = sandbox.state_hash()
        with self.assertRaises(property_runtime.UnsupportedPropertyPostStageError):
            sandbox.execute(
                "battle.ir.property.modify_source_zero_untransformed",
                component=entity,
                property_id=property_id,
                function_id=int(PropertyModifyFunction.SET),
                operand=fp(1),
                context_token=None,
            )
        self.assertEqual(sandbox.state_hash(), before)


class TestTraceBoundary(unittest.TestCase):
    def test_exactly_one_boundary_pair_per_component_mutation(self):
        sandbox = Sandbox(seed=106)
        entity = EntityRef(1)
        property_id = 5
        seed_additive_entry(sandbox, entity, property_id)

        for primitive_id, kwargs, operation in (
            (
                "battle.ir.property.component_stack_source",
                {
                    "component": entity,
                    "property_id": property_id,
                    "runtime_value": fp(10),
                    "context_token": None,
                },
                "battle.ir.property.boundary.source_allocated",
            ),
            (
                "battle.ir.property.update_contribution_source",
                {
                    "component": entity,
                    "property_id": property_id,
                    "source_index": 1,
                    "new_source_value": fp(20),
                    "context_token": None,
                },
                "battle.ir.property.boundary.source_updated",
            ),
            (
                "battle.ir.property.remove_contribution_source",
                {
                    "component": entity,
                    "property_id": property_id,
                    "source_index": 1,
                    "context_token": None,
                },
                "battle.ir.property.boundary.source_removed",
            ),
        ):
            with self.subTest(primitive_id=primitive_id):
                sandbox.context.trace = type(sandbox.context.trace)()
                sandbox.execute(primitive_id, **kwargs)
                boundary_starts = [
                    event
                    for event in sandbox.context.trace.events
                    if getattr(event, "event", None) == "PrimitiveStarted"
                    and getattr(event, "primitive_id", None) == operation
                ]
                boundary_finishes = [
                    event
                    for event in sandbox.context.trace.events
                    if getattr(event, "event", None) == "PrimitiveFinished"
                    and getattr(event, "primitive_id", None) == operation
                ]
                self.assertEqual(len(boundary_starts), 1)
                self.assertEqual(len(boundary_finishes), 1)
                self.assertIn("old:", boundary_finishes[0].result)
                self.assertIn("new:", boundary_finishes[0].result)


class TestCloneSnapshotHash(unittest.TestCase):
    def _populated(self, seed: int) -> tuple[Sandbox, EntityRef, int]:
        sandbox = Sandbox(seed=seed)
        entity = EntityRef(1)
        property_id = 5
        seed_additive_entry(sandbox, entity, property_id)
        modifier = make_modifier(name="M", ordinal=0)
        sandbox.execute(
            "battle.ir.modifier.stack_property_contribution",
            modifier=modifier,
            property_id=property_id,
            value=fp(100),
            target_component=entity,
            context_token=None,
            is_refresh=False,
        )
        return sandbox, entity, property_id

    def test_same_logical_state_same_hash(self):
        left = Sandbox(seed=107)
        right = Sandbox(seed=107)
        entity = EntityRef(1)
        seed_additive_entry(left, entity, 5)
        seed_additive_entry(right, entity, 5)
        self.assertEqual(left.state_hash(), right.state_hash())

    def test_source_changes_change_state_hash(self):
        sandbox, entity, property_id = self._populated(108)
        before = sandbox.state_hash()
        sandbox.execute(
            "battle.ir.property.update_contribution_source",
            component=entity,
            property_id=property_id,
            source_index=1,
            new_source_value=fp(200),
            context_token=None,
        )
        after = sandbox.state_hash()
        self.assertNotEqual(before, after)

    def test_clone_mutate_source_slot_original_unchanged(self):
        sandbox, entity, property_id = self._populated(109)
        branch = sandbox.clone()
        self.assertEqual(branch.state_hash(), sandbox.state_hash())
        branch.execute(
            "battle.ir.property.update_contribution_source",
            component=entity,
            property_id=property_id,
            source_index=1,
            new_source_value=fp(999),
            context_token=None,
        )
        original = property_runtime.get_property_entry(
            sandbox.context.state, entity, property_id
        )
        self.assertTrue(fixpoint_equal(original.source_value[1], fp(100)))
        self.assertNotEqual(branch.state_hash(), sandbox.state_hash())

    def test_snapshot_roundtrip_includes_property_state(self):
        sandbox, entity, property_id = self._populated(110)
        before_hash = sandbox.context.state.state_hash()
        before_dict = sandbox.context.state.to_dict()
        snapshot = sandbox.snapshot()
        sandbox.execute(
            "battle.ir.modifier.pop_property_contributions",
            modifier=make_modifier(name="M", ordinal=0),
        )
        restored = snapshot.restore_context()
        self.assertEqual(restored.state.to_dict(), before_dict)
        self.assertEqual(restored.state.state_hash(), before_hash)
        entry = property_runtime.get_property_entry(restored.state, entity, property_id)
        self.assertTrue(entry.source_active[1])
        self.assertTrue(fixpoint_equal(entry.materialized, fp(100)))

    def test_snapshot_dict_roundtrip_and_stable_hash(self):
        sandbox, _, _ = self._populated(111)
        snapshot = sandbox.snapshot()
        data = snapshot.to_dict()
        restored = type(snapshot).from_dict(data)
        self.assertEqual(restored.to_dict(), data)
        self.assertEqual(restored.state_hash(), snapshot.state_hash())


class TestBattleStateSchemaV3(unittest.TestCase):
    def test_v3_default_contains_property_fields(self):
        state = BattleState()
        self.assertEqual(state.schema_version, BATTLE_STATE_SCHEMA_VERSION)
        self.assertEqual(state.entity_property_entries, {})
        self.assertEqual(state.modifier_property_contributions, {})
        self.assertIn("entity_property_entries", state.to_dict())
        self.assertIn("modifier_property_contributions", state.to_dict())

    def test_v1_and_v2_migrate_to_v3(self):
        v1 = BattleState.from_dict({"schema_version": 1, "extensions": {"x": 1}})
        self.assertEqual(v1.schema_version, BATTLE_STATE_SCHEMA_VERSION)
        self.assertEqual(v1.extensions, {"x": 1})
        self.assertEqual(v1.entity_property_entries, {})

        v2 = BattleState.from_dict(
            {
                "schema_version": 2,
                "extensions": {},
                "modifier_state_by_entity": {"1": []},
            }
        )
        self.assertEqual(v2.schema_version, BATTLE_STATE_SCHEMA_VERSION)
        self.assertEqual(v2.modifier_state_by_entity, {"1": []})
        self.assertEqual(v2.modifier_property_contributions, {})

    def test_v3_roundtrip_and_hash(self):
        state = BattleState()
        property_runtime.ensure_property_entry(
            state,
            EntityRef(1),
            5,
            materialization_kind=int(
                MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
            ),
        )
        restored = BattleState.from_dict(state.to_dict())
        self.assertEqual(restored.to_dict(), state.to_dict())
        self.assertEqual(restored.state_hash(), state.state_hash())

    def test_property_state_is_not_smuggled_through_extensions(self):
        state = BattleState()
        property_runtime.ensure_property_entry(
            state,
            EntityRef(1),
            5,
            materialization_kind=int(
                MaterializationKind.KIND_3_ACTIVE_FOLD_ADD_CALLEE
            ),
        )
        data = state.to_dict()
        self.assertNotIn("entity_property_entries", data["extensions"])
        self.assertNotIn("modifier_property_contributions", data["extensions"])


if __name__ == "__main__":
    unittest.main()
