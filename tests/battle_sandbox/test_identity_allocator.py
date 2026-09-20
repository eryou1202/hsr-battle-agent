# -*- coding: utf-8 -*-
"""F02-004 tests: deterministic non-reusing allocator.

Acceptance criteria: deterministic sequence, no reuse after removal, and abort
leaves the allocator identical.  The suite also proves per-namespace isolation,
generation behaviour, and that a failed construction consumes no ID.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.identity import (  # noqa: E402
    ACTOR,
    CASTER,
    ENTITY,
    MODIFIER,
    PROVIDER,
    AllocationTicket,
    IdentityAllocator,
    TypedIdentity,
    TypedIdentityError,
)


class TestDeterministicSequence(unittest.TestCase):
    def test_sequence_starts_at_zero_and_advances_by_one(self):
        allocator = IdentityAllocator()
        values = [allocator.allocate(ENTITY, "battle.entity").value for _ in range(5)]
        self.assertEqual(values, [0, 1, 2, 3, 4])

    def test_two_allocators_produce_identical_sequences(self):
        first = IdentityAllocator()
        second = IdentityAllocator()
        for _ in range(6):
            self.assertEqual(
                first.allocate(ENTITY, "ns").value,
                second.allocate(ENTITY, "ns").value,
            )

    def test_sequence_is_reproducible_after_replaying_the_same_calls(self):
        def run():
            allocator = IdentityAllocator()
            allocator.allocate(ENTITY, "a")
            allocator.allocate(ACTOR, "a")
            allocator.allocate(ENTITY, "b")
            return allocator.snapshot()

        self.assertEqual(run(), run())

    def test_allocator_is_deterministic_without_a_clock_or_random_source(self):
        import ast

        source = (
            REPO / "src" / "hsr_battle_agent" / "battle_sandbox" / "identity.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for module in ("random", "time", "datetime", "uuid", "secrets", "os"):
            with self.subTest(module=module):
                self.assertNotIn(module, imported)

    def test_ids_are_plain_ints_never_floats(self):
        identity = IdentityAllocator().allocate(ENTITY, "ns")
        self.assertTrue(identity.value_is_int())
        self.assertIsInstance(identity.require_int_value(), int)


class TestPerNamespaceIsolation(unittest.TestCase):
    def test_namespaces_have_independent_counters(self):
        allocator = IdentityAllocator()
        self.assertEqual(allocator.allocate(ENTITY, "a").value, 0)
        self.assertEqual(allocator.allocate(ENTITY, "b").value, 0)
        self.assertEqual(allocator.allocate(ENTITY, "a").value, 1)
        self.assertEqual(allocator.allocate(ENTITY, "b").value, 1)

    def test_namespaces_are_tracked_separately(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "b")
        allocator.allocate(ENTITY, "a")
        self.assertEqual(allocator.namespaces(), ("a", "b"))
        self.assertEqual(allocator.state_for("a").next_value, 1)
        self.assertEqual(allocator.state_for("b").next_value, 1)

    def test_retirement_in_one_namespace_does_not_affect_another(self):
        allocator = IdentityAllocator()
        first = allocator.allocate(ENTITY, "a")
        allocator.allocate(ENTITY, "b")
        allocator.retire(first)
        self.assertEqual(allocator.state_for("a").next_value, 1)
        self.assertEqual(allocator.state_for("b").next_value, 1)
        self.assertEqual(allocator.allocate(ENTITY, "b").value, 1)

    def test_namespace_must_be_valid(self):
        for namespace in ("", None, 1, []):
            with self.subTest(namespace=repr(namespace)):
                with self.assertRaises(TypedIdentityError):
                    IdentityAllocator().allocate(ENTITY, namespace)


class TestNoReuseAfterRemoval(unittest.TestCase):
    def test_retired_value_is_never_handed_out_again(self):
        allocator = IdentityAllocator()
        first = allocator.allocate(ENTITY, "ns")
        allocator.retire(first)
        second = allocator.allocate(ENTITY, "ns")
        self.assertNotEqual(second.value, first.value)
        self.assertEqual(second.value, 1)

    def test_tombstone_is_recorded(self):
        allocator = IdentityAllocator()
        first = allocator.allocate(ENTITY, "ns")
        state = allocator.retire(first)
        self.assertTrue(state.is_tombstoned(0))
        self.assertFalse(state.is_live(0))
        self.assertEqual(state.tombstones, (0,))
        self.assertIn(0, state.to_dict()["tombstones"])

    def test_many_retirements_never_reuse_a_value(self):
        allocator = IdentityAllocator()
        issued = []
        for _ in range(12):
            identity = allocator.allocate(ENTITY, "ns")
            issued.append(identity.value)
            allocator.retire(identity)
        self.assertEqual(len(set(issued)), 12)
        self.assertEqual(allocator.state_for("ns").tombstones, tuple(range(12)))
        self.assertEqual(allocator.allocate(ENTITY, "ns").value, 12)

    def test_retiring_a_non_live_value_is_refused(self):
        allocator = IdentityAllocator()
        identity = allocator.allocate(ENTITY, "ns")
        allocator.retire(identity)
        with self.assertRaises(TypedIdentityError):
            allocator.retire(identity)

    def test_retiring_an_unallocated_value_is_refused(self):
        allocator = IdentityAllocator()
        foreign = TypedIdentity.local(ENTITY, "ns", 99)
        with self.assertRaises(TypedIdentityError):
            allocator.retire(foreign)

    def test_retiring_a_string_identity_is_refused(self):
        allocator = IdentityAllocator()
        with self.assertRaises(TypedIdentityError):
            allocator.retire(TypedIdentity.local(ENTITY, "ns", "20021"))

    def test_retire_requires_an_identity(self):
        for value in (None, 0, "x", {}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    IdentityAllocator().retire(value)


class TestReservationIsPrivateUntilCommit(unittest.TestCase):
    def test_reserve_publishes_nothing(self):
        allocator = IdentityAllocator()
        before = allocator.snapshot()
        ticket = allocator.reserve(ENTITY, "ns")
        self.assertEqual(allocator.snapshot(), before)
        self.assertEqual(ticket.value, 0)
        self.assertFalse(ticket.committed)

    def test_abort_leaves_the_allocator_identical(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "ns")
        before = allocator.snapshot()
        ticket = allocator.reserve(ENTITY, "ns")
        allocator.abort(ticket)
        self.assertEqual(allocator.snapshot(), before)
        self.assertEqual(allocator.allocate(ENTITY, "ns").value, 1)

    def test_abort_after_many_reservations_still_no_change(self):
        allocator = IdentityAllocator()
        before = allocator.snapshot()
        for _ in range(5):
            allocator.abort(allocator.reserve(ENTITY, "ns"))
        self.assertEqual(allocator.snapshot(), before)

    def test_commit_publishes_exactly_one_value(self):
        allocator = IdentityAllocator()
        ticket = allocator.reserve(ENTITY, "ns")
        identity = allocator.commit(ticket)
        self.assertEqual(identity.value, 0)
        self.assertEqual(allocator.state_for("ns").next_value, 1)
        self.assertTrue(allocator.state_for("ns").is_live(0))

    def test_a_ticket_is_committed_at_most_once(self):
        allocator = IdentityAllocator()
        ticket = allocator.reserve(ENTITY, "ns")
        allocator.commit(ticket)
        with self.assertRaises(TypedIdentityError):
            allocator.commit(ticket)

    def test_stale_ticket_after_another_commit_is_refused(self):
        allocator = IdentityAllocator()
        first = allocator.reserve(ENTITY, "ns")
        second = allocator.reserve(ENTITY, "ns")
        allocator.commit(first)
        with self.assertRaises(TypedIdentityError):
            allocator.commit(second)

    def test_a_failed_construction_consumes_no_id(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "ns")
        before = allocator.snapshot()
        ticket = allocator.reserve(ENTITY, "ns")

        class Boom(Exception):
            pass

        def build():
            # Simulates a transaction failing between reserve and commit.
            raise Boom("construction failed")

        with self.assertRaises(Boom):
            build()
        allocator.abort(ticket)
        self.assertEqual(allocator.snapshot(), before)
        # The next successful allocation still receives the same value.
        self.assertEqual(allocator.allocate(ENTITY, "ns").value, 1)

    def test_commit_requires_a_ticket(self):
        for value in (None, 0, "x", ()):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    IdentityAllocator().commit(value)

    def test_abort_requires_a_ticket(self):
        for value in (None, 0, "x", ()):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    IdentityAllocator().abort(value)

    def test_committed_identity_carries_the_requested_family_and_namespace(self):
        allocator = IdentityAllocator()
        identity = allocator.allocate(PROVIDER, "battle.provider")
        self.assertIs(identity.family, PROVIDER)
        self.assertEqual(identity.namespace, "battle.provider")

    def test_reserve_requires_a_declared_family(self):
        for value in ("UNDECLARED", "lower", "", None, 1):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    IdentityAllocator().reserve(value, "ns")


class TestGenerationAwareness(unittest.TestCase):
    def test_begin_generation_starts_a_fresh_value_space(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "ns")
        allocator.allocate(ENTITY, "ns")
        state = allocator.begin_generation("ns")
        self.assertEqual(state.generation, 1)
        self.assertEqual(state.next_value, 0)
        self.assertEqual(allocator.allocate(ENTITY, "ns").value, 0)

    def test_tombstones_survive_a_generation_change(self):
        allocator = IdentityAllocator()
        first = allocator.allocate(ENTITY, "ns")
        allocator.retire(first)
        state = allocator.begin_generation("ns")
        self.assertTrue(state.is_tombstoned(0))

    def test_ticket_from_a_previous_generation_is_stale(self):
        allocator = IdentityAllocator()
        ticket = allocator.reserve(ENTITY, "ns")
        allocator.begin_generation("ns")
        with self.assertRaises(TypedIdentityError):
            allocator.commit(ticket)

    def test_reserve_for_a_wrong_generation_is_refused(self):
        allocator = IdentityAllocator()
        with self.assertRaises(TypedIdentityError):
            allocator.reserve(ENTITY, "ns", generation=3)

    def test_reserve_for_the_current_generation_is_accepted(self):
        allocator = IdentityAllocator()
        allocator.begin_generation("ns")
        ticket = allocator.reserve(ENTITY, "ns", generation=1)
        self.assertEqual(ticket.generation, 1)

    def test_generation_is_recorded_on_the_identity(self):
        allocator = IdentityAllocator()
        allocator.begin_generation("ns")
        identity = allocator.allocate(ENTITY, "ns")
        self.assertEqual(identity.generation, 1)

    def test_allocator_is_independent_per_generation_of_other_namespaces(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "a")
        allocator.begin_generation("b")
        self.assertEqual(allocator.state_for("a").generation, 0)
        self.assertEqual(allocator.state_for("b").generation, 1)


class TestSnapshotAndSerialization(unittest.TestCase):
    def test_snapshot_reflects_published_state(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "a")
        snapshot = allocator.snapshot()
        self.assertEqual(
            snapshot["a"],
            {
                "namespace": "a",
                "generation": 0,
                "next_value": 1,
                "issued": [0],
                "tombstones": [],
            },
        )

    def test_snapshot_is_a_copy_not_a_live_view(self):
        allocator = IdentityAllocator()
        allocator.allocate(ENTITY, "a")
        snapshot = allocator.snapshot()
        snapshot["a"]["next_value"] = 99
        snapshot["a"]["issued"].append(42)
        self.assertEqual(allocator.state_for("a").next_value, 1)
        self.assertEqual(allocator.state_for("a").issued, (0,))

    def test_ticket_is_serializable(self):
        ticket = IdentityAllocator().reserve(MODIFIER, "ns")
        payload = ticket.to_dict()
        self.assertEqual(payload["family"], "MODIFIER")
        self.assertEqual(payload["namespace"], "ns")
        self.assertEqual(payload["value"], 0)
        self.assertFalse(payload["committed"])

    def test_namespace_state_serialization_round_trips(self):
        allocator = IdentityAllocator()
        identity = allocator.allocate(CASTER, "ns")
        allocator.retire(identity)
        payload = allocator.state_for("ns").to_dict()
        self.assertEqual(payload["tombstones"], [0])
        self.assertEqual(payload["issued"], [])


if __name__ == "__main__":
    unittest.main()
