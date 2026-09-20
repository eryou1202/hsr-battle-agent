# -*- coding: utf-8 -*-
"""F02-007 tests: concrete core and opaque unresolved stores.

Acceptance criteria: each family round trips, an opaque payload change changes
identity, and the scheduler stores are separate.  The suite also proves order,
duplicates, null and presence are preserved and that no lifecycle behaviour
exists.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue  # noqa: E402
from hsr_battle_agent.battle_sandbox.opaque import (  # noqa: E402
    OPAQUE_STORE_SCHEMA,
    OpaqueUnresolvedStore,
    opaque_store_definition,
)
from hsr_battle_agent.battle_sandbox.stores.core import (  # noqa: E402
    CORE_STORE_SCHEMA,
    STORE_FAMILIES,
    STORE_FAMILY_NAMES,
    StoreDefinition,
    StoreEntry,
    TypedStore,
    TypedStoreError,
    empty_stores,
    require_store_family,
    scheduler_store_family_names,
)
from hsr_battle_agent.battle_sandbox.stores.protocols import (  # noqa: E402
    FROZEN_FIELD_FAMILIES,
    StoreClass,
)


def handle(blocker_id="D8-Q2", payload=None, owner_family="MONSTER_AI"):
    return UnknownHandle(
        blocker_id=blocker_id,
        owner_family=owner_family,
        payload={"value": payload} if payload is not None else {"value": None},
        provenance={"game_version": "4.4.54"},
        required_evidence=("pinned observed transition",),
    )


class TestStoreFamilyCatalog(unittest.TestCase):
    def test_expected_family_names_are_present(self):
        for name in (
            "definitions",
            "entities",
            "teams",
            "topology",
            "invocation",
            "modifiers",
            "properties",
            "targets",
            "ai",
            "damage",
            "resources",
            "events",
            "scenario",
            "mode",
            "terminal",
            "allocator",
            "rng",
            "opaque_handles",
        ):
            with self.subTest(name=name):
                self.assertIn(name, STORE_FAMILY_NAMES)

    def test_family_names_and_namespaces_are_unique(self):
        self.assertEqual(len(set(STORE_FAMILY_NAMES)), len(STORE_FAMILY_NAMES))
        namespaces = [definition.namespace for definition in STORE_FAMILIES]
        self.assertEqual(len(set(namespaces)), len(namespaces))

    def test_require_store_family_rejects_unknown(self):
        for value in ("nope", "", None, 1, []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedStoreError):
                    require_store_family(value)

    def test_every_family_has_a_rationale(self):
        for definition in STORE_FAMILIES:
            with self.subTest(name=definition.name):
                self.assertTrue(definition.rationale)

    def test_state_field_families_reference_frozen_fields(self):
        for definition in STORE_FAMILIES:
            if definition.state_field_family is None:
                continue
            with self.subTest(name=definition.name):
                self.assertIn(
                    definition.state_field_family, FROZEN_FIELD_FAMILIES
                )


class TestSeparateSchedulerStores(unittest.TestCase):
    def test_scheduler_stores_are_separate(self):
        names = scheduler_store_family_names()
        self.assertEqual(
            names,
            (
                "scheduler_timeline",
                "scheduler_action_delay",
                "scheduler_insert_queue",
            ),
        )
        self.assertEqual(len(set(names)), 3)

    def test_scheduler_stores_have_distinct_namespaces(self):
        namespaces = tuple(
            require_store_family(name).namespace
            for name in scheduler_store_family_names()
        )
        self.assertEqual(len(namespaces), 3)
        self.assertEqual(len(set(namespaces)), 3)

    def test_scheduler_stores_are_independent(self):
        stores = empty_stores()
        timeline = stores["scheduler_timeline"].append("t", 1)
        delay = stores["scheduler_action_delay"].append("d", 1)
        queue = stores["scheduler_insert_queue"].append("q", 1)
        self.assertEqual(timeline.keys(), ("t",))
        self.assertEqual(delay.keys(), ("d",))
        self.assertEqual(queue.keys(), ("q",))
        self.assertNotEqual(timeline.identity(), delay.identity())
        self.assertNotEqual(delay.identity(), queue.identity())

    def test_timeline_maps_to_the_turn_timeline_state_field(self):
        self.assertEqual(
            require_store_family("scheduler_timeline").state_field_family,
            "turn_timeline",
        )


class TestEmptyStores(unittest.TestCase):
    def test_every_family_starts_empty(self):
        stores = empty_stores()
        self.assertEqual(len(stores), len(STORE_FAMILIES))
        self.assertEqual(tuple(stores), STORE_FAMILY_NAMES)
        for name, store in stores.items():
            with self.subTest(name=name):
                self.assertTrue(store.is_empty())
                self.assertEqual(len(store), 0)
                self.assertEqual(store.keys(), ())
                self.assertEqual(store.name, name)

    def test_store_carries_its_definition(self):
        stores = empty_stores()
        for definition in STORE_FAMILIES:
            with self.subTest(name=definition.name):
                store = stores[definition.name]
                self.assertIs(store.definition, definition)
                self.assertEqual(store.namespace, definition.namespace)
                self.assertIs(store.store_class, definition.store_class)


class TestPreservationRules(unittest.TestCase):
    def test_insertion_order_is_preserved(self):
        store = empty_stores()["entities"]
        for key in ("c", "a", "b", "a"):
            store = store.append(key, 1)
        self.assertEqual(store.keys(), ("c", "a", "b", "a"))

    def test_duplicate_keys_are_preserved(self):
        store = empty_stores()["entities"].append("k", 1).append("k", 2)
        self.assertEqual(store.keys(), ("k", "k"))
        self.assertEqual(len(store), 2)
        values = [value.require_present() for value in store.values_for("k")]
        self.assertEqual(values, [1, 2])
        self.assertEqual(
            [entry.occurrence for entry in store.entries], [0, 1]
        )

    def test_null_and_presence_are_preserved(self):
        store = (
            empty_stores()["entities"]
            .append("absent", PresenceValue.absent())
            .append("null", PresenceValue.null())
            .append("false", PresenceValue.present(False))
            .append("zero", PresenceValue.present(0))
            .append("empty_list", PresenceValue.present([]))
            .append("list_with_null", PresenceValue.present([None]))
            .append("empty_mapping", PresenceValue.present({}))
        )
        self.assertEqual(len(store), 7)
        self.assertTrue(store.values_for("absent")[0].is_absent())
        self.assertTrue(store.values_for("null")[0].is_null())
        for key in ("false", "zero", "empty_list", "list_with_null", "empty_mapping"):
            with self.subTest(key=key):
                self.assertTrue(store.values_for(key)[0].is_present())
        # Every recorded state stays distinguishable after a round trip.
        restored = TypedStore.from_dict(store.to_dict())
        self.assertEqual(restored.to_dict(), store.to_dict())
        encodings = {
            key: json.dumps(restored.values_for(key)[0].to_dict(), sort_keys=True)
            for key in restored.keys()
        }
        self.assertEqual(len(set(encodings.values())), len(encodings))

    def test_a_bare_value_becomes_a_present_presence_value(self):
        store = empty_stores()["entities"].append("k", 5)
        self.assertTrue(store.values_for("k")[0].is_present())
        self.assertEqual(store.values_for("k")[0].require_present(), 5)

    def test_append_requires_a_non_empty_key(self):
        store = empty_stores()["entities"]
        for key in ("", None, 1, []):
            with self.subTest(key=repr(key)):
                with self.assertRaises(TypedStoreError):
                    store.append(key, 1)

    def test_extend_preserves_order_and_duplicates(self):
        store = empty_stores()["entities"].extend([("a", 1), ("a", 2), ("b", 3)])
        self.assertEqual(store.keys(), ("a", "a", "b"))

    def test_extend_rejects_bad_input(self):
        store = empty_stores()["entities"]
        for broken in ("abc", 1, None, [object()]):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedStoreError):
                    store.extend(broken)

    def test_append_does_not_mutate_the_original(self):
        original = empty_stores()["entities"]
        extended = original.append("k", 1)
        self.assertTrue(original.is_empty())
        self.assertEqual(len(extended), 1)


class TestWritabilityRules(unittest.TestCase):
    def test_mutable_state_stores_accept_writes(self):
        for name in ("entities", "modifiers", "properties", "rng", "allocator"):
            with self.subTest(name=name):
                self.assertTrue(empty_stores()[name].is_writable())

    def test_immutable_input_stores_refuse_writes(self):
        store = empty_stores()["definitions"]
        self.assertFalse(store.is_writable())
        with self.assertRaises(TypedStoreError):
            store.append("k", 1)

    def test_generic_writes_to_the_opaque_family_are_refused(self):
        store = empty_stores()["opaque_handles"]
        self.assertFalse(store.is_writable())
        with self.assertRaises(TypedStoreError):
            store.append("k", 1)

    def test_each_class_is_used_by_at_least_one_family(self):
        used = {definition.store_class for definition in STORE_FAMILIES}
        self.assertIn(StoreClass.IMMUTABLE_INPUT, used)
        self.assertIn(StoreClass.MUTABLE_STATE, used)
        self.assertIn(StoreClass.OPAQUE_UNRESOLVED, used)


class TestRoundTripPerFamily(unittest.TestCase):
    def test_every_family_round_trips_empty(self):
        for definition in STORE_FAMILIES:
            with self.subTest(name=definition.name):
                store = TypedStore(definition=definition)
                payload = store.to_dict()
                self.assertEqual(
                    TypedStore.from_dict(payload).to_dict(), payload
                )

    def test_every_writable_family_round_trips_with_content(self):
        for definition in STORE_FAMILIES:
            if definition.store_class is not StoreClass.MUTABLE_STATE:
                continue
            with self.subTest(name=definition.name):
                store = (
                    TypedStore(definition=definition)
                    .append("a", PresenceValue.absent())
                    .append("a", PresenceValue.null())
                    .append("b", PresenceValue.present(False))
                    .append("c", PresenceValue.present([None]))
                )
                payload = store.to_dict()
                restored = TypedStore.from_dict(payload)
                self.assertEqual(restored.to_dict(), payload)
                self.assertEqual(restored.keys(), store.keys())
                self.assertEqual(restored.identity(), store.identity())

    def test_json_round_trip(self):
        store = empty_stores()["entities"].extend(
            [("a", 1), ("a", 2), ("b", False)]
        )
        text = json.dumps(store.to_dict(), sort_keys=True)
        self.assertEqual(TypedStore.from_dict(json.loads(text)), store)

    def test_identity_is_content_sensitive(self):
        base = empty_stores()["entities"].append("k", 1)
        other = empty_stores()["entities"].append("k", 2)
        self.assertNotEqual(base.identity(), other.identity())

    def test_identity_distinguishes_null_from_absent(self):
        absent = empty_stores()["entities"].append("k", PresenceValue.absent())
        null = empty_stores()["entities"].append("k", PresenceValue.null())
        self.assertNotEqual(absent.identity(), null.identity())

    def test_identity_distinguishes_families(self):
        left = empty_stores()["entities"]
        right = empty_stores()["teams"]
        self.assertNotEqual(left.identity(), right.identity())

    def test_schema_constants(self):
        self.assertEqual(CORE_STORE_SCHEMA, "typed_store/1")
        self.assertEqual(
            empty_stores()["entities"].to_dict()["schema"], CORE_STORE_SCHEMA
        )

    def test_serialization_does_not_alias_the_model(self):
        store = empty_stores()["entities"].append("k", {"raw": [1]})
        payload = store.to_dict()
        payload["entries"][0]["key"] = "mutated"
        payload["entries"][0]["value"]["value"]["raw"].append(2)
        self.assertEqual(store.keys(), ("k",))
        self.assertEqual(
            store.values_for("k")[0].require_present(), {"raw": [1]}
        )

    def test_malformed_documents_are_rejected(self):
        for broken in (
            None,
            [],
            "x",
            {},
            {"schema": "typed_store/2"},
            {"schema": CORE_STORE_SCHEMA},
            {"schema": CORE_STORE_SCHEMA, "definition": {"name": "x"}},
            {
                "schema": CORE_STORE_SCHEMA,
                "definition": {
                    "name": "entities",
                    "namespace": "battle.entity",
                    "store_class": "MUTABLE_STATE",
                    "rationale": "r",
                },
                "entries": [{"key": "k"}],
            },
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises((TypedStoreError, KeyError)):
                    TypedStore.from_dict(broken)

    def test_definition_validation(self):
        for broken in (
            {"name": "", "namespace": "n", "store_class": "MUTABLE_STATE",
             "rationale": "r"},
            {"name": "n", "namespace": "", "store_class": "MUTABLE_STATE",
             "rationale": "r"},
            {"name": "n", "namespace": "n", "store_class": "BOGUS",
             "rationale": "r"},
            {"name": "n", "namespace": "n", "store_class": "MUTABLE_STATE",
             "rationale": ""},
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedStoreError):
                    StoreDefinition(**broken)

    def test_store_entry_validation(self):
        for broken in (
            {"key": "", "value": PresenceValue.absent()},
            {"key": "k", "value": 1},
            {"key": "k", "value": PresenceValue.absent(), "occurrence": -1},
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedStoreError):
                    StoreEntry(**broken)


class TestNoLifecycleBehaviour(unittest.TestCase):
    def test_no_lifecycle_methods_exist(self):
        for name in (
            "create",
            "destroy",
            "remove",
            "delete",
            "activate",
            "deactivate",
            "tick",
            "expire",
            "step",
            "apply",
            "execute",
            "advance",
            "transition",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(TypedStore, name))
                self.assertFalse(hasattr(OpaqueUnresolvedStore, name))

    def test_no_executability_helpers_exist(self):
        for name in ("executable", "is_executable", "can_execute", "as_bool"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(TypedStore, name))
                self.assertFalse(hasattr(OpaqueUnresolvedStore, name))

    def test_store_has_no_truthiness(self):
        # A store reports emptiness explicitly; it is not a truthiness test.
        store = empty_stores()["entities"]
        self.assertTrue(store.is_empty())
        self.assertEqual(bool(store), False)

    def test_opaque_store_has_no_truthiness(self):
        with self.assertRaises(TypedStoreError):
            bool(OpaqueUnresolvedStore())


class TestOpaqueUnresolvedStore(unittest.TestCase):
    def test_starts_empty(self):
        store = OpaqueUnresolvedStore()
        self.assertTrue(store.is_empty())
        self.assertEqual(len(store), 0)
        self.assertEqual(store.blocker_ids(), ())

    def test_carries_handles_in_order_with_duplicates(self):
        store = (
            OpaqueUnresolvedStore()
            .with_handle(handle("D8-Q2"))
            .with_handle(handle("D8-Q3"))
            .with_handle(handle("D8-Q2"))
        )
        self.assertEqual(store.blocker_ids(), ("D8-Q2", "D8-Q3", "D8-Q2"))
        self.assertEqual(len(store), 3)

    def test_opaque_payload_changes_identity(self):
        first = OpaqueUnresolvedStore().with_handle(handle("D8-Q2", payload="a"))
        second = OpaqueUnresolvedStore().with_handle(handle("D8-Q2", payload="b"))
        self.assertNotEqual(first.identity_hash(), second.identity_hash())

    def test_identity_changes_with_owner_and_blocker(self):
        base = OpaqueUnresolvedStore().with_handle(handle("D8-Q2"))
        different_blocker = OpaqueUnresolvedStore().with_handle(handle("D8-Q3"))
        different_owner = OpaqueUnresolvedStore().with_handle(
            handle("D8-Q2", owner_family="TARGET")
        )
        self.assertNotEqual(base.identity_hash(), different_blocker.identity_hash())
        self.assertNotEqual(base.identity_hash(), different_owner.identity_hash())

    def test_identity_is_stable_for_equal_content(self):
        first = OpaqueUnresolvedStore().with_handle(handle("D8-Q2", payload="a"))
        second = OpaqueUnresolvedStore().with_handle(handle("D8-Q2", payload="a"))
        self.assertEqual(first.identity_hash(), second.identity_hash())

    def test_round_trip(self):
        store = (
            OpaqueUnresolvedStore()
            .with_handle(handle("D8-Q2", payload=[None, 0, {}]))
            .with_handle(handle("D8-Q3", owner_family="TARGET"))
        )
        payload = store.to_dict()
        restored = OpaqueUnresolvedStore.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored, store)
        self.assertEqual(restored.identity_hash(), store.identity_hash())

    def test_json_round_trip(self):
        store = OpaqueUnresolvedStore().with_handle(handle("D8-Q2", payload="a"))
        text = json.dumps(store.to_dict(), sort_keys=True)
        restored = OpaqueUnresolvedStore.from_dict(json.loads(text))
        self.assertEqual(restored.identity_hash(), store.identity_hash())

    def test_resolve_refuses(self):
        with self.assertRaises(TypedStoreError):
            OpaqueUnresolvedStore().with_handle(handle()).resolve()
        with self.assertRaises(TypedStoreError):
            OpaqueUnresolvedStore().resolve()

    def test_projects_onto_the_typed_store_shape(self):
        store = (
            OpaqueUnresolvedStore()
            .with_handle(handle("D8-Q2"))
            .with_handle(handle("D8-Q2"))
        )
        typed = store.to_typed_store()
        self.assertEqual(typed.name, "opaque_handles")
        self.assertIs(typed.store_class, StoreClass.OPAQUE_UNRESOLVED)
        self.assertEqual(typed.keys(), ("D8-Q2", "D8-Q2"))
        self.assertEqual([e.occurrence for e in typed.entries], [0, 1])
        self.assertFalse(typed.is_writable())

    def test_definition_is_the_declared_opaque_family(self):
        self.assertEqual(opaque_store_definition().name, "opaque_handles")
        self.assertIs(
            opaque_store_definition().store_class, StoreClass.OPAQUE_UNRESOLVED
        )

    def test_schema_constant(self):
        self.assertEqual(OPAQUE_STORE_SCHEMA, "opaque_unresolved_store/1")
        self.assertEqual(
            OpaqueUnresolvedStore().to_dict()["schema"], OPAQUE_STORE_SCHEMA
        )

    def test_requires_handles(self):
        for value in (None, "x", 1, [{"not": "a handle"}]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedStoreError):
                    OpaqueUnresolvedStore(handles=value)

    def test_with_handle_requires_a_handle(self):
        for value in (None, "x", 1):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedStoreError):
                    OpaqueUnresolvedStore().with_handle(value)

    def test_malformed_documents_are_rejected(self):
        for broken in (
            None,
            [],
            {},
            {"schema": "opaque_unresolved_store/2"},
            {"schema": OPAQUE_STORE_SCHEMA, "handles": "x"},
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedStoreError):
                    OpaqueUnresolvedStore.from_dict(broken)

    def test_serialization_does_not_alias_the_model(self):
        store = OpaqueUnresolvedStore().with_handle(handle("D8-Q2", payload="a"))
        payload = store.to_dict()
        payload["handles"][0]["payload"]["value"] = "mutated"
        self.assertEqual(
            store.handles[0].payload["value"], "a"
        )


if __name__ == "__main__":
    unittest.main()
