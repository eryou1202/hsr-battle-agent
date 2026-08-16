# -*- coding: utf-8 -*-
"""Pure battle-runtime tests for Modifier Lifecycle Bridge 08.

Covered surface is exactly the E4 accepted projection:

* TryAdd duplicate decision tree (append / duplicate / destroy+append /
  process-in-place),
* duplicate match identity (name + StackingFlag + caster + source provider),
* Destroy -> ToBeRemoved -> RemoveDirtyModifiers shift-left removal,
* recovered _ProcessModifierRedd life/count arithmetic core,
* deterministic non-reused logical instance ordinals.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.modifiers import (  # noqa: E402
    MATCH_STATE_FILTER_ALIVE_ONLY,
    MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED,
    MATCH_STATE_FILTER_NONE,
    ModifierContainer,
    ModifierMatchKey,
    ModifierStacking,
    ModifierStackingFlag,
    ModifierState,
    ModifierStateValue,
)
from hsr_battle_agent.battle_ir.targets import EntityRef  # noqa: E402
from hsr_battle_agent.battle_ir.values import ObjectRef  # noqa: E402
from hsr_battle_agent.battle_runtime import modifiers as runtime  # noqa: E402
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402


def make_modifier(
    *,
    name: str = "TestModifier",
    owner: EntityRef = EntityRef(1),
    ordinal: int = 0,
    state: int = 1,
    flag: int = 0,
    count: int = 1,
    layer: int = 1,
    max_layer: int = 3,
    life: int = 3,
    previous_life: int = -1,
    caster: EntityRef | None = None,
    source_ref: ObjectRef | None = None,
    guard: int = 0,
) -> ModifierState:
    return ModifierState(
        name=name,
        owner_entity=owner,
        instance_ordinal=ordinal,
        state_raw=state,
        stacking_flag_raw=flag,
        count=count,
        layer=layer,
        max_layer=max_layer,
        current_life=life,
        previous_life=previous_life,
        caster_entity=caster,
        source_provider_ref=source_ref,
        destroy_guard=guard,
    )


class TestDuplicateMatchPredicate(unittest.TestCase):
    def test_name_flag_and_state_filters(self):
        item = make_modifier(name="A", flag=1, state=1)
        key = ModifierMatchKey(name="A", stacking_flag=1)
        self.assertTrue(runtime.modifier_match_search(
            item, key, MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED
        ))
        self.assertTrue(runtime.modifier_match_search(
            item, key, MATCH_STATE_FILTER_ALIVE_ONLY
        ))
        self.assertFalse(runtime.modifier_match_search(
            make_modifier(name="B", flag=1), key, MATCH_STATE_FILTER_NONE
        ))
        self.assertFalse(runtime.modifier_match_search(
            make_modifier(name="A", flag=2), key, MATCH_STATE_FILTER_NONE
        ))

    def test_state_filter_and_wildcard(self):
        key = ModifierMatchKey(name="A", stacking_flag=0)
        self.assertTrue(runtime.modifier_match_search(
            make_modifier(name="A", state=0), key, MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED
        ))
        self.assertFalse(runtime.modifier_match_search(
            make_modifier(name="A", state=0), key, MATCH_STATE_FILTER_ALIVE_ONLY
        ))
        self.assertFalse(runtime.modifier_match_search(
            make_modifier(name="A", state=2), key, MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED
        ))
        self.assertTrue(runtime.modifier_match_search(
            make_modifier(name="A", state=2), key, MATCH_STATE_FILTER_NONE
        ))

    def test_caster_and_source_provider_identity(self):
        key = ModifierMatchKey(
            name="A", stacking_flag=0, caster_entity=EntityRef(10),
            source_provider_ref=ObjectRef(77),
        )
        self.assertFalse(runtime.modifier_match_search(
            make_modifier(name="A"), key, MATCH_STATE_FILTER_NONE
        ))
        self.assertTrue(runtime.modifier_match_search(
            make_modifier(name="A", caster=EntityRef(10), source_ref=ObjectRef(77)),
            key,
            MATCH_STATE_FILTER_NONE,
        ))
        self.assertFalse(runtime.modifier_match_search(
            make_modifier(name="A", caster=EntityRef(10), source_ref=ObjectRef(78)),
            key,
            MATCH_STATE_FILTER_NONE,
        ))


class TestTryAddDecisionTree(unittest.TestCase):
    def test_apply_to_empty_appends(self):
        state = BattleState()
        result = runtime.try_add_modifier_instance(
            state,
            EntityRef(1),
            make_modifier(owner=EntityRef(1)),
            int(ModifierStacking.UNKNOW),
            0,
            None,
            None,
            True,
        )
        self.assertEqual(result.disposition, "APPENDED")
        self.assertEqual((result.before_count, result.after_count), (0, 1))
        self.assertEqual(
            len(state.modifier_state_by_entity["1"]), 1
        )
        self.assertEqual(
            ModifierState.from_dict(
                state.modifier_state_by_entity["1"][0]
            ).state_raw,
            ModifierStateValue.ALIVE,
        )

    def test_duplicate_multiple_appends_without_touching_old(self):
        state = BattleState()
        template = make_modifier(owner=EntityRef(1))
        runtime.try_add_modifier_instance(
            state, EntityRef(1), template, int(ModifierStacking.UNKNOW), 0, None, None, True
        )
        result = runtime.try_add_modifier_instance(
            state, EntityRef(1), template, int(ModifierStacking.MULTIPLE), 0, None, None, True
        )
        self.assertEqual(result.disposition, "DUPLICATE_APPENDED")
        items = [ModifierState.from_dict(x) for x in state.modifier_state_by_entity["1"]]
        self.assertEqual([i.instance_ordinal for i in items], [0, 1])
        self.assertTrue(all(i.state_raw == 1 for i in items))

    def test_refresh_processes_existing_in_place(self):
        state = BattleState()
        template = make_modifier(owner=EntityRef(1), life=3, count=1)
        runtime.try_add_modifier_instance(
            state, EntityRef(1), template, int(ModifierStacking.UNKNOW), 0, None, None, True
        )
        result = runtime.try_add_modifier_instance(
            state,
            EntityRef(1),
            make_modifier(owner=EntityRef(1), life=9, count=4),
            int(ModifierStacking.REFRESH),
            0,
            None,
            None,
            True,
        )
        self.assertEqual(result.disposition, "EXISTING_PROCESSED")
        self.assertEqual(result.after_count, 1)
        updated = ModifierState.from_dict(state.modifier_state_by_entity["1"][0])
        self.assertEqual(updated.current_life, 9)
        self.assertEqual(updated.count, 4)
        self.assertEqual(updated.previous_life, 9)

    def test_prolong_and_merge_arithmetic_core(self):
        for stacking, expected in (
            (ModifierStacking.PROLONG, 7),
            (ModifierStacking.MERGE, 5),
        ):
            with self.subTest(stacking=stacking):
                state = BattleState()
                existing = make_modifier(
                    owner=EntityRef(1), life=5, previous_life=5, count=1
                )
                state.set_modifier_collection(1, [existing.to_dict()])
                updated = runtime.process_modifier_redd(
                    state,
                    EntityRef(1),
                    existing,
                    int(stacking),
                    new_count=2,
                    new_life=2,
                )
                self.assertEqual(updated.current_life, expected)
                self.assertEqual(updated.previous_life, expected)

    def test_retain_global_latest_destroys_then_appends(self):
        state = BattleState()
        template = make_modifier(owner=EntityRef(1))
        runtime.try_add_modifier_instance(
            state, EntityRef(1), template, int(ModifierStacking.UNKNOW), 0, None, None, True
        )
        result = runtime.try_add_modifier_instance(
            state,
            EntityRef(1),
            template,
            int(ModifierStacking.RETAIN_GLOBAL_LATEST),
            0,
            None,
            None,
            True,
        )
        self.assertEqual(result.disposition, "DESTROYED_AND_APPENDED")
        self.assertIsNotNone(result.destroyed_ref)
        items = [ModifierState.from_dict(x) for x in state.modifier_state_by_entity["1"]]
        self.assertEqual([i.state_raw for i in items], [2, 1])

    def test_global_scope_searches_other_entities(self):
        state = BattleState()
        state.set_modifier_collection(7, [make_modifier(owner=EntityRef(7)).to_dict()])
        result = runtime.try_add_modifier_instance(
            state,
            EntityRef(8),
            make_modifier(owner=EntityRef(8)),
            int(ModifierStacking.RETAIN_GLOBAL_LATEST),
            0,
            None,
            None,
            True,
        )
        self.assertEqual(result.disposition, "DESTROYED_AND_APPENDED")
        old = ModifierState.from_dict(state.modifier_state_by_entity["7"][0])
        self.assertEqual(old.state_raw, 2)
        self.assertEqual(len(state.modifier_state_by_entity["8"]), 1)

    def test_source_provider_branches_require_identity(self):
        state = BattleState()
        with self.assertRaises(ValueError):
            runtime.try_add_modifier_instance(
                state,
                EntityRef(1),
                make_modifier(owner=EntityRef(1)),
                int(ModifierStacking.REPLACE_BY_CASTER),
                0,
                None,
                None,
                True,
            )


class TestRemovalSemantics(unittest.TestCase):
    def test_destroy_state_transition_and_idempotence(self):
        state = BattleState()
        item = make_modifier(owner=EntityRef(1))
        state.set_modifier_collection(1, [item.to_dict()])
        destroyed = runtime.destroy_modifier_instance(state, EntityRef(1), item, 0)
        self.assertEqual(destroyed.state_raw, ModifierStateValue.TO_BE_REMOVED)
        again = runtime.destroy_modifier_instance(state, EntityRef(1), item, 0)
        self.assertEqual(again.state_raw, ModifierStateValue.TO_BE_REMOVED)

    def test_remove_dirty_shift_left_preserves_order(self):
        state = BattleState()
        items = [
            make_modifier(name="keep0", ordinal=0, state=1),
            make_modifier(name="dead1", ordinal=1, state=2),
            make_modifier(name="keep2", ordinal=2, state=1),
            make_modifier(name="dead3", ordinal=3, state=0, guard=0),
        ]
        state.set_modifier_collection(1, [i.to_dict() for i in items])
        container = runtime.remove_dirty_modifiers(state, EntityRef(1))
        self.assertEqual(
            [item.name for item in container.items], ["keep0", "keep2"]
        )
        self.assertEqual(
            [item.instance_ordinal for item in container.items], [0, 2]
        )

    def test_destroy_guard_skips_removal(self):
        state = BattleState()
        state.set_modifier_collection(1, [make_modifier(state=2, guard=1).to_dict()])
        container = runtime.remove_dirty_modifiers(state, EntityRef(1))
        self.assertEqual(container.count, 1)

    def test_ordinal_is_not_reused_after_removal(self):
        state = BattleState()
        state.set_modifier_collection(
            1,
            [
                make_modifier(name="dead", ordinal=0, state=2).to_dict(),
                make_modifier(name="old", ordinal=1, state=1).to_dict(),
            ],
        )
        runtime.remove_dirty_modifiers(state, EntityRef(1))
        result = runtime.try_add_modifier_instance(
            state,
            EntityRef(1),
            make_modifier(name="new", owner=EntityRef(1)),
            int(ModifierStacking.UNKNOW),
            0,
            None,
            None,
            True,
        )
        self.assertEqual(result.modifier.instance_ordinal, 2)
        self.assertNotEqual(
            result.modifier.instance_ordinal,
            ModifierState.from_dict(
                state.modifier_state_by_entity["1"][0]
            ).instance_ordinal,
        )


class TestMatchHelpers(unittest.TestCase):
    def test_container_find_returns_first_match(self):
        container = ModifierContainer.of(
            make_modifier(name="A", ordinal=0),
            make_modifier(name="A", ordinal=1),
        )
        found = runtime.modifier_container_find(
            container, ModifierMatchKey(name="A", stacking_flag=0),
            MATCH_STATE_FILTER_ALIVE_OR_TO_BE_ADDED,
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.instance_ordinal, 0)


if __name__ == "__main__":
    unittest.main()
