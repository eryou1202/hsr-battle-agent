# -*- coding: utf-8 -*-
"""F02-006 tests: owned store classification and the ownership catalog.

Acceptance criteria: the ownership catalog is complete, and a duplicate or
unclassified field is rejected.  The suite also proves the generic extension bag
cannot be written, that the classification vocabulary is complete, and that the
catalog cannot drift away from the frozen BattleState shape.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.stores.protocols import (  # noqa: E402
    DERIVED_CACHE_FIELD_FAMILIES,
    FROZEN_FIELD_FAMILIES,
    OWNERSHIP_CATALOG,
    STORE_CLASSES,
    StoreClass,
    StoreOwnershipError,
    StoreOwner,
    frozen_field_families,
    owner_for,
    require_writable,
    validate_catalog,
)


class TestClassificationVocabulary(unittest.TestCase):
    def test_declared_classes(self):
        self.assertEqual(
            STORE_CLASSES,
            (
                "IMMUTABLE_INPUT",
                "MUTABLE_STATE",
                "DERIVED_CACHE",
                "OPAQUE_UNRESOLVED",
            ),
        )
        self.assertEqual(StoreClass.spellings(), STORE_CLASSES)

    def test_classes_are_distinct(self):
        self.assertEqual(len({member.name for member in StoreClass}), 4)
        for left in StoreClass:
            for right in StoreClass:
                if left is right:
                    continue
                with self.subTest(left=left.name, right=right.name):
                    self.assertNotEqual(left, right)

    def test_classes_have_no_truthiness(self):
        for member in StoreClass:
            with self.subTest(member=member.name):
                with self.assertRaises(StoreOwnershipError):
                    bool(member)


class TestOwnershipCatalogComplete(unittest.TestCase):
    def test_catalog_covers_every_frozen_field_family_exactly_once(self):
        validate_catalog()
        catalogued = [owner.field_family for owner in OWNERSHIP_CATALOG]
        self.assertEqual(len(catalogued), len(set(catalogued)))
        self.assertEqual(
            sorted(catalogued), sorted(FROZEN_FIELD_FAMILIES)
        )

    def test_frozen_families_do_not_come_from_legacy_battle_state(self):
        self.assertEqual(len(FROZEN_FIELD_FAMILIES), 61)
        self.assertEqual(frozen_field_families(), FROZEN_FIELD_FAMILIES)
        self.assertNotIn("extensions", FROZEN_FIELD_FAMILIES)
        self.assertIn("unknown_extensions", FROZEN_FIELD_FAMILIES)

    def test_expected_frozen_family_set(self):
        freeze = json.loads(
            (REPO / "data" / "semantics" / "4.4.54" / "full_reconstruction"
             / "astra_semantic_freeze_v1.json").read_text(encoding="utf-8")
        )
        authority = freeze["battle_state_contract"]["state_fields"]
        self.assertEqual(
            FROZEN_FIELD_FAMILIES,
            tuple(row["name"] for row in authority),
        )
        class_map = {
            "OPAQUE_UNRESOLVED_STATE": "OPAQUE_UNRESOLVED",
        }
        self.assertEqual(
            [owner.store_class.value for owner in OWNERSHIP_CATALOG],
            [class_map.get(row["classification"], row["classification"])
             for row in authority],
        )
        self.assertEqual(
            [owner.authority_owner for owner in OWNERSHIP_CATALOG],
            [row["owner"] for row in authority],
        )
        self.assertIn("revision_and_transaction_sequence", FROZEN_FIELD_FAMILIES)
        self.assertIn("rng_streams", FROZEN_FIELD_FAMILIES)

    def test_at_least_one_family_uses_each_relevant_class(self):
        used = {owner.store_class for owner in OWNERSHIP_CATALOG}
        self.assertIn(StoreClass.IMMUTABLE_INPUT, used)
        self.assertIn(StoreClass.MUTABLE_STATE, used)
        self.assertIn(StoreClass.OPAQUE_UNRESOLVED, used)
        self.assertIn(StoreClass.DERIVED_CACHE, used)
        self.assertEqual(
            DERIVED_CACHE_FIELD_FAMILIES,
            (
                "definition_indexes",
                "target_query_cache",
                "candidate_visibility_cache",
                "property_materialization_cache",
                "gate_plan_cache",
            ),
        )


class TestDuplicateAndUnclassifiedRejection(unittest.TestCase):
    def test_duplicate_field_family_is_rejected(self):
        duplicate = OWNERSHIP_CATALOG + (OWNERSHIP_CATALOG[0],)
        with self.assertRaises(StoreOwnershipError):
            validate_catalog(duplicate)

    def test_unclassified_field_family_is_rejected(self):
        trimmed = OWNERSHIP_CATALOG[:-1]
        with self.assertRaises(StoreOwnershipError):
            validate_catalog(trimmed)

    def test_catalog_entry_for_a_non_frozen_field_is_rejected(self):
        invented = OWNERSHIP_CATALOG + (
            StoreOwner(
                field_family="not_a_real_field",
                store_class=StoreClass.MUTABLE_STATE,
                namespace="x",
                authority_owner="Test",
                writable=True,
                rationale="invented",
            ),
        )
        with self.assertRaises(StoreOwnershipError):
            validate_catalog(invented)

    def test_owner_for_unknown_field_is_rejected(self):
        for field_family in ("not_a_real_field", "", None, 1, []):
            with self.subTest(field_family=repr(field_family)):
                with self.assertRaises(StoreOwnershipError):
                    owner_for(field_family)

    def test_owner_for_every_frozen_field_succeeds(self):
        for field_family in FROZEN_FIELD_FAMILIES:
            with self.subTest(field_family=field_family):
                owner = owner_for(field_family)
                self.assertEqual(owner, owner_for(field_family))
                self.assertIsInstance(owner.store_class, StoreClass)

    def test_catalog_must_be_a_sequence_of_owners(self):
        for broken in (None, "x", 1, [("a", "b")]):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(StoreOwnershipError):
                    validate_catalog(broken)

    def test_owner_validation(self):
        with self.assertRaises(StoreOwnershipError):
            StoreOwner(
                field_family="",
                store_class=StoreClass.MUTABLE_STATE,
                namespace="x",
                authority_owner="Test",
                writable=True,
                rationale="r",
            )
        with self.assertRaises(StoreOwnershipError):
            StoreOwner(
                field_family="f",
                store_class="NOT_A_CLASS",
                namespace="x",
                authority_owner="Test",
                writable=True,
                rationale="r",
            )
        with self.assertRaises(StoreOwnershipError):
            StoreOwner(
                field_family="f",
                store_class=StoreClass.MUTABLE_STATE,
                namespace="",
                authority_owner="Test",
                writable=True,
                rationale="r",
            )
        with self.assertRaises(StoreOwnershipError):
            StoreOwner(
                field_family="f",
                store_class=StoreClass.MUTABLE_STATE,
                namespace="x",
                authority_owner="Test",
                writable="yes",
                rationale="r",
            )
        with self.assertRaises(StoreOwnershipError):
            StoreOwner(
                field_family="f",
                store_class=StoreClass.MUTABLE_STATE,
                namespace="x",
                authority_owner="Test",
                writable=True,
                rationale="",
            )

    def test_only_mutable_state_may_be_writable(self):
        for store_class in (
            StoreClass.IMMUTABLE_INPUT,
            StoreClass.DERIVED_CACHE,
            StoreClass.OPAQUE_UNRESOLVED,
        ):
            with self.subTest(store_class=store_class.name):
                with self.assertRaises(StoreOwnershipError):
                    StoreOwner(
                        field_family="f",
                        store_class=store_class,
                        namespace="x",
                        authority_owner="Test",
                        writable=True,
                        rationale="r",
                    )

    def test_store_class_spelling_is_accepted(self):
        owner = StoreOwner(
            field_family="f",
            store_class="MUTABLE_STATE",
            namespace="x",
            authority_owner="Test",
            writable=True,
            rationale="r",
        )
        self.assertIs(owner.store_class, StoreClass.MUTABLE_STATE)


class TestGenericExtensionWritesForbidden(unittest.TestCase):
    def test_extensions_is_not_writable(self):
        owner = owner_for("unknown_extensions")
        self.assertFalse(owner.is_writable())
        self.assertIs(owner.store_class, StoreClass.OPAQUE_UNRESOLVED)

    def test_require_writable_refuses_extension_writes(self):
        with self.assertRaises(StoreOwnershipError):
            require_writable("unknown_extensions")

    def test_require_writable_refuses_the_schema_marker(self):
        with self.assertRaises(StoreOwnershipError):
            require_writable("schema_and_numeric_profile")

    def test_require_writable_accepts_owned_mutable_families(self):
        for field_family in (
            "modifier_instances",
            "properties",
            "pending_damage",
            "ordinary_timeline",
            "rng_streams",
        ):
            with self.subTest(field_family=field_family):
                owner = require_writable(field_family)
                self.assertTrue(owner.is_writable())
                self.assertIs(owner.store_class, StoreClass.MUTABLE_STATE)

    def test_require_writable_rejects_unknown_fields(self):
        with self.assertRaises(StoreOwnershipError):
            require_writable("not_a_real_field")


class TestOwnershipNamespaces(unittest.TestCase):
    def test_namespaces_are_declared_and_unique_per_family(self):
        namespaces = [owner.namespace for owner in OWNERSHIP_CATALOG]
        self.assertEqual(len(namespaces), len(set(namespaces)))
        for namespace in namespaces:
            self.assertTrue(namespace)

    def test_rationale_is_recorded_for_every_owner(self):
        for owner in OWNERSHIP_CATALOG:
            with self.subTest(field_family=owner.field_family):
                self.assertTrue(owner.rationale)

    def test_owner_serialization_round_trips_by_value(self):
        for owner in OWNERSHIP_CATALOG:
            with self.subTest(field_family=owner.field_family):
                payload = owner.to_dict()
                self.assertEqual(payload["field_family"], owner.field_family)
                self.assertEqual(
                payload["store_class"], owner.store_class.value
                )
                self.assertEqual(payload["writable"], owner.writable)
                self.assertEqual(payload["authority_owner"], owner.authority_owner)
                rebuilt = StoreOwner(
                    field_family=payload["field_family"],
                    store_class=payload["store_class"],
                    namespace=payload["namespace"],
                    authority_owner=payload["authority_owner"],
                    writable=payload["writable"],
                    rationale=payload["rationale"],
                )
                self.assertEqual(rebuilt, owner)

    def test_package_reexports_the_catalog(self):
        from hsr_battle_agent.battle_sandbox import stores

        self.assertEqual(stores.OWNERSHIP_CATALOG, OWNERSHIP_CATALOG)
        self.assertEqual(stores.FROZEN_FIELD_FAMILIES, FROZEN_FIELD_FAMILIES)
        self.assertIs(stores.StoreClass, StoreClass)
        self.assertIs(stores.StoreOwnershipError, StoreOwnershipError)


if __name__ == "__main__":
    unittest.main()
