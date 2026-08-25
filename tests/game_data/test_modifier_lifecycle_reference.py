"""Executable acceptance tests for PRIM-MODIFIER-001's bounded contract."""
from __future__ import annotations

import unittest

from hsr_battle_agent.game_data.modifier_lifecycle_reference import (
    ModifierInstance,
    ModifierState,
    StackingPolicy,
    add_or_refresh,
    mark_destroy,
    remove_dirty,
)


def instance(identifier: str, stacking: int, *, life: int | None = 1, count: int | None = 1) -> ModifierInstance:
    return ModifierInstance(identifier, "M_Test", stacking, 100, "provider", life, count, state=ModifierState.ALIVE)


class ModifierLifecycleReferenceTest(unittest.TestCase):
    def test_multiple_appends_while_replace_refreshes_in_place(self) -> None:
        first = instance("one", StackingPolicy.MULTIPLE)
        result = add_or_refresh((first,), instance("two", StackingPolicy.MULTIPLE))
        self.assertEqual(result.action, "APPEND_MULTIPLE")
        self.assertEqual([item.instance_id for item in result.instances], ["one", "two"])
        replace = add_or_refresh((instance("one", StackingPolicy.REPLACE, life=2, count=1),), instance("incoming", StackingPolicy.REPLACE, life=7, count=3))
        self.assertEqual(replace.action, "REFRESH_REPLACE")
        self.assertEqual(replace.instances[0].instance_id, "one")
        self.assertEqual((replace.instances[0].current_life, replace.instances[0].count), (7, 3))

    def test_prolong_merge_and_keep_lifetime_are_distinct(self) -> None:
        prolong = add_or_refresh((instance("one", StackingPolicy.PROLONG, life=2),), instance("incoming", StackingPolicy.PROLONG, life=3))
        self.assertEqual((prolong.action, prolong.instances[0].current_life), ("REFRESH_PROLONG", 5))
        merge = add_or_refresh((instance("one", StackingPolicy.MERGE, life=2),), instance("incoming", StackingPolicy.MERGE, life=3))
        self.assertEqual((merge.action, merge.instances[0].current_life), ("REFRESH_MERGE", 3))
        keep = add_or_refresh((instance("one", StackingPolicy.REPLACE_KEEP_LIFETIME, life=2, count=1),), instance("incoming", StackingPolicy.REPLACE_KEEP_LIFETIME, life=8, count=4))
        self.assertEqual((keep.action, keep.instances[0].current_life, keep.instances[0].count), ("REFRESH_KEEP_LIFETIME", 2, 4))

    def test_destroy_is_mark_then_ordered_cleanup(self) -> None:
        alive_a = instance("a", StackingPolicy.MULTIPLE)
        pending = instance("b", StackingPolicy.MULTIPLE)
        alive_c = instance("c", StackingPolicy.MULTIPLE)
        marked = mark_destroy((alive_a, pending, alive_c), "b", reason=9)
        self.assertEqual(marked.instances[1].state, ModifierState.TO_BE_REMOVED)
        cleaned = remove_dirty(marked.instances)
        self.assertEqual([item.instance_id for item in cleaned.instances], ["a", "c"])
        self.assertEqual(cleaned.affected_instance_id, "b")

    def test_global_policy_is_explicitly_not_approximated(self) -> None:
        with self.assertRaises(NotImplementedError):
            add_or_refresh((instance("one", StackingPolicy.RETAIN_GLOBAL_LATEST),), instance("two", StackingPolicy.RETAIN_GLOBAL_LATEST))
