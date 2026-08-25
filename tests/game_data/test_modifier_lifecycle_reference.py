"""Executable acceptance tests for PRIM-MODIFIER-001's bounded contract."""
from __future__ import annotations

import unittest

from hsr_battle_agent.game_data.modifier_lifecycle_reference import (
    ModifierInstance,
    ModifierState,
    StackingPolicy,
    activate,
    active_callback_keys,
    add_or_refresh,
    mark_destroy,
    remove_dirty,
)


def instance(
    identifier: str,
    stacking: int,
    *,
    life: int | None = 1,
    count: int | None = 1,
    state: ModifierState = ModifierState.ALIVE,
    callback_keys: tuple[str, ...] = (),
    property_keys: tuple[str, ...] = (),
) -> ModifierInstance:
    return ModifierInstance(
        identifier,
        "M_Test",
        stacking,
        100,
        "provider",
        life,
        count,
        state=state,
        callback_registration_keys=callback_keys,
        property_contribution_keys=property_keys,
    )


class ModifierLifecycleReferenceTest(unittest.TestCase):
    def test_append_stays_pending_until_activate_boundary(self) -> None:
        existing = instance("one", StackingPolicy.MULTIPLE, callback_keys=("cb:one",))
        appended = add_or_refresh((existing,), instance("two", StackingPolicy.MULTIPLE, state=ModifierState.TO_BE_ADDED))
        self.assertEqual(appended.action, "APPEND_MULTIPLE_PENDING")
        self.assertEqual([item.instance_id for item in appended.instances], ["one", "two"])
        self.assertEqual(appended.instances[1].state, ModifierState.TO_BE_ADDED)
        self.assertEqual(active_callback_keys(appended.instances), ("cb:one",))
        activated = activate(appended.instances, "two")
        self.assertEqual(activated.action, "ACTIVATE_ALIVE")
        self.assertEqual(activated.instances[1].state, ModifierState.ALIVE)

    def test_replace_refreshes_in_place(self) -> None:
        replace_result = add_or_refresh(
            (instance("one", StackingPolicy.REPLACE, life=2, count=1),),
            instance("incoming", StackingPolicy.REPLACE, life=7, count=3, state=ModifierState.TO_BE_ADDED),
        )
        self.assertEqual(replace_result.action, "REFRESH_REPLACE")
        self.assertEqual(replace_result.instances[0].instance_id, "one")
        self.assertEqual((replace_result.instances[0].current_life, replace_result.instances[0].count), (7, 3))

    def test_prolong_merge_and_keep_lifetime_are_distinct(self) -> None:
        prolong = add_or_refresh((instance("one", StackingPolicy.PROLONG, life=2),), instance("incoming", StackingPolicy.PROLONG, life=3))
        self.assertEqual((prolong.action, prolong.instances[0].current_life), ("REFRESH_PROLONG", 5))
        merge = add_or_refresh((instance("one", StackingPolicy.MERGE, life=2),), instance("incoming", StackingPolicy.MERGE, life=3))
        self.assertEqual((merge.action, merge.instances[0].current_life), ("REFRESH_MERGE", 3))
        keep = add_or_refresh((instance("one", StackingPolicy.REPLACE_KEEP_LIFETIME, life=2, count=1),), instance("incoming", StackingPolicy.REPLACE_KEEP_LIFETIME, life=8, count=4))
        self.assertEqual((keep.action, keep.instances[0].current_life, keep.instances[0].count), ("REFRESH_KEEP_LIFETIME", 2, 4))

    def test_destroy_is_mark_then_ordered_cleanup_with_registration_cleanup(self) -> None:
        alive_a = instance("a", StackingPolicy.MULTIPLE, callback_keys=("cb:a",), property_keys=("prop:a",))
        pending = instance("b", StackingPolicy.MULTIPLE, callback_keys=("cb:b",), property_keys=("prop:b",))
        alive_c = instance("c", StackingPolicy.MULTIPLE, callback_keys=("cb:c",), property_keys=("prop:c",))
        marked = mark_destroy((alive_a, pending, alive_c), "b", reason=9)
        self.assertEqual(marked.instances[1].state, ModifierState.TO_BE_REMOVED)
        cleaned = remove_dirty(marked.instances)
        self.assertEqual([item.instance_id for item in cleaned.instances], ["a", "c"])
        self.assertEqual(cleaned.affected_instance_id, "b")
        self.assertEqual(cleaned.deregistered_callback_keys, ("cb:b",))
        self.assertEqual(cleaned.removed_property_contribution_keys, ("prop:b",))
        self.assertEqual(active_callback_keys(cleaned.instances), ("cb:a", "cb:c"))

    def test_global_policy_is_explicitly_not_approximated(self) -> None:
        with self.assertRaises(NotImplementedError):
            add_or_refresh((instance("one", StackingPolicy.RETAIN_GLOBAL_LATEST),), instance("two", StackingPolicy.RETAIN_GLOBAL_LATEST))


if __name__ == "__main__":
    unittest.main()
