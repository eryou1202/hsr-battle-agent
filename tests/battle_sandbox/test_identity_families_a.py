# -*- coding: utf-8 -*-
"""F02-002 tests: entity / actor / team / formation / topology families.

Acceptance criterion: the family construction and rejection matrix.  The suite
also proves no implicit int conversion and that source identity is preserved
separately from runtime identity.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.identity import (  # noqa: E402
    ACTOR,
    ENTITY,
    FAMILY_A,
    FAMILY_A_NAMES,
    FORMATION_SLOT,
    TEAM,
    TOPOLOGY_NODE,
    IdentityAuthority,
    IdentityFamily,
    SourcedIdentity,
    TypedIdentity,
    TypedIdentityError,
    declare_identity_family,
    require_family_a,
)

ABOVE_2_53 = 2**53 + 1


class TestFamilyDeclaration(unittest.TestCase):
    def test_declared_names(self):
        self.assertEqual(
            FAMILY_A_NAMES,
            ("ENTITY", "ACTOR", "TEAM", "FORMATION_SLOT", "TOPOLOGY_NODE"),
        )
        self.assertEqual(len(FAMILY_A), 5)

    def test_each_family_is_a_declared_instance(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                self.assertTrue(family.is_declared())
                self.assertIs(require_family_a(family.name), family)
                self.assertIs(require_family_a(family), family)

    def test_families_are_pairwise_distinct(self):
        self.assertEqual(len({family.name for family in FAMILY_A}), 5)
        self.assertEqual(len(set(FAMILY_A)), 5)
        for left in FAMILY_A:
            for right in FAMILY_A:
                if left.name == right.name:
                    continue
                with self.subTest(left=left.name, right=right.name):
                    self.assertNotEqual(left, right)

    def test_require_family_a_rejects_other_families(self):
        other = declare_identity_family("TEST_NOT_FAMILY_A")
        with self.assertRaises(TypedIdentityError):
            require_family_a(other)
        with self.assertRaises(TypedIdentityError):
            require_family_a("TEST_NOT_FAMILY_A")

    def test_require_family_a_rejects_undeclared_and_malformed(self):
        for value in ("UNDECLARED_FAMILY", "", None, 1, [], {}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    require_family_a(value)

    def test_no_alias_between_families(self):
        # No family may be an alias of another, and no automatic lookup by
        # value exists.
        self.assertIsNot(ENTITY, ACTOR)
        self.assertIsNot(TEAM, FORMATION_SLOT)
        self.assertIsNot(ACTOR, TOPOLOGY_NODE)


class TestConstructionMatrix(unittest.TestCase):
    def test_every_family_constructs_a_local_identity(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                identity = TypedIdentity.local(family, "battle.test", 1)
                self.assertIs(identity.family, family)
                self.assertIs(
                    identity.authority, IdentityAuthority.LOCAL_DESIGN_IDENTITY
                )
                self.assertTrue(identity.is_local_design())
                self.assertEqual(identity.namespace, "battle.test")
                self.assertEqual(identity.generation, 0)
                self.assertEqual(identity.value, 1)

    def test_every_family_constructs_a_source_recorded_identity(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                identity = TypedIdentity.from_source_record(
                    family, "external.source", "Avatar_Skill01"
                )
                self.assertIs(
                    identity.authority,
                    IdentityAuthority.SOURCE_RECORDED_IDENTITY,
                )
                self.assertEqual(identity.value, "Avatar_Skill01")

    def test_every_family_rejects_bad_namespaces(self):
        for family in FAMILY_A:
            for namespace in ("", None, 1, []):
                with self.subTest(family=family.name, namespace=repr(namespace)):
                    with self.assertRaises(TypedIdentityError):
                        TypedIdentity.local(family, namespace, 1)

    def test_every_family_rejects_bad_generations(self):
        for family in FAMILY_A:
            for generation in (-1, 1.0, "0", None, True):
                with self.subTest(
                    family=family.name, generation=repr(generation)
                ):
                    with self.assertRaises(TypedIdentityError):
                        TypedIdentity.local(
                            family, "ns", 1, generation=generation
                        )

    def test_every_family_rejects_bad_values(self):
        bad_values = (1.0, 0.5, True, False, None, [], {}, (), object())
        for family in FAMILY_A:
            for value in bad_values:
                with self.subTest(family=family.name, value=repr(value)):
                    with self.assertRaises(TypedIdentityError):
                        TypedIdentity.local(family, "ns", value)

    def test_every_family_rejects_native_authority(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity(
                        family=family,
                        namespace="ns",
                        generation=0,
                        value=1,
                        authority=IdentityAuthority.NATIVE_CLIENT_IDENTITY,
                    )

    def test_every_family_refuses_native_certification(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity.local(
                        family, "ns", 1
                    ).certify_native_identity()

    def test_every_family_rejects_undeclared_family_input(self):
        undeclared = IdentityFamily("TEST_UNDECLARED_FAMILY")
        with self.assertRaises(TypedIdentityError):
            TypedIdentity.local(undeclared, "ns", 1)
        with self.assertRaises(TypedIdentityError):
            TypedIdentity.local("TEST_UNDECLARED_FAMILY", "ns", 1)


class TestFamilySeparation(unittest.TestCase):
    def test_same_value_across_families_is_never_equal(self):
        identities = [
            TypedIdentity.local(family, "battle.test", "same", generation=3)
            for family in FAMILY_A
        ]
        self.assertEqual(len(set(identities)), len(FAMILY_A))
        for left in identities:
            for right in identities:
                if left.family.name == right.family.name:
                    self.assertEqual(left, right)
                    continue
                with self.subTest(left=left.family.name, right=right.family.name):
                    self.assertNotEqual(left, right)

    def test_no_implicit_family_conversion_between_family_a_members(self):
        entity = TypedIdentity.local(ENTITY, "battle.test", 1)
        for family in (ACTOR, TEAM, FORMATION_SLOT, TOPOLOGY_NODE):
            with self.subTest(family=family.name):
                with self.assertRaises(TypedIdentityError):
                    entity.convert_family(family, contract="")

    def test_named_conversion_is_required_and_preserves_the_value(self):
        entity = TypedIdentity.local(ENTITY, "battle.test", ABOVE_2_53)
        actor = entity.convert_family(ACTOR, contract="explicit.family.change")
        self.assertIs(actor.family, ACTOR)
        self.assertEqual(actor.value, ABOVE_2_53)
        self.assertNotEqual(entity, actor)

    def test_same_family_helper_distinguishes_families(self):
        entity = TypedIdentity.local(ENTITY, "ns", 1)
        actor = TypedIdentity.local(ACTOR, "ns", 1)
        self.assertTrue(entity.same_family(entity))
        self.assertFalse(entity.same_family(actor))


class TestNoImplicitIntConversion(unittest.TestCase):
    def test_string_values_are_never_parsed_to_int(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                identity = TypedIdentity.local(family, "ns", "20021")
                self.assertTrue(identity.value_is_str())
                self.assertFalse(identity.value_is_int())
                with self.assertRaises(TypedIdentityError):
                    identity.require_int_value()

    def test_int_values_are_never_stringified(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                identity = TypedIdentity.local(family, "ns", 20021)
                self.assertTrue(identity.value_is_int())
                self.assertIsInstance(identity.require_int_value(), int)
                self.assertNotEqual(identity.value, "20021")

    def test_string_and_int_values_remain_distinct(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                self.assertNotEqual(
                    TypedIdentity.local(family, "ns", 20021),
                    TypedIdentity.local(family, "ns", "20021"),
                )

    def test_ids_above_2_53_survive_for_every_family(self):
        for family in FAMILY_A:
            with self.subTest(family=family.name):
                identity = TypedIdentity.local(family, "ns", ABOVE_2_53)
                self.assertEqual(identity.require_int_value(), ABOVE_2_53)
                restored = TypedIdentity.from_dict(identity.to_dict())
                self.assertEqual(restored.require_int_value(), ABOVE_2_53)
                self.assertNotEqual(
                    restored.require_int_value(), 2**53
                )


class TestSourcedIdentity(unittest.TestCase):
    def make(self, source_family=None, with_source=True):
        runtime = TypedIdentity.local(ENTITY, "battle.local", ABOVE_2_53)
        source = None
        if with_source:
            source = TypedIdentity.from_source_record(
                source_family or ENTITY, "external.source", "20021"
            )
        return SourcedIdentity(runtime=runtime, source=source)

    def test_runtime_and_source_are_preserved_separately(self):
        pair = self.make()
        self.assertTrue(pair.has_source())
        self.assertIs(
            pair.runtime.authority, IdentityAuthority.LOCAL_DESIGN_IDENTITY
        )
        self.assertIs(
            pair.require_source().authority,
            IdentityAuthority.SOURCE_RECORDED_IDENTITY,
        )
        self.assertNotEqual(pair.runtime, pair.require_source())
        self.assertNotEqual(pair.runtime.value, pair.require_source().value)

    def test_source_may_be_absent_and_is_not_faked(self):
        pair = self.make(with_source=False)
        self.assertFalse(pair.has_source())
        with self.assertRaises(TypedIdentityError):
            pair.require_source()

    def test_assuming_source_equals_runtime_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            self.make().assume_source_equals_runtime()
        with self.assertRaises(TypedIdentityError):
            self.make(with_source=False).assume_source_equals_runtime()

    def test_identical_values_across_source_and_runtime_stay_separate(self):
        pair = SourcedIdentity(
            runtime=TypedIdentity.local(ENTITY, "ns", 7),
            source=TypedIdentity.from_source_record(ENTITY, "ns", 7),
        )
        self.assertEqual(pair.runtime.value, pair.require_source().value)
        self.assertNotEqual(pair.runtime, pair.require_source())
        self.assertIsNot(pair.runtime, pair.require_source())

    def test_source_family_may_differ_and_is_not_assumed_equal(self):
        same = self.make(source_family=ENTITY)
        different = self.make(source_family=ACTOR)
        self.assertTrue(same.same_family())
        self.assertFalse(different.same_family())
        self.assertIs(different.runtime.family, ENTITY)
        self.assertIs(different.require_source().family, ACTOR)

    def test_runtime_must_be_local_design(self):
        with self.assertRaises(TypedIdentityError):
            SourcedIdentity(
                runtime=TypedIdentity.from_source_record(ENTITY, "ns", 1)
            )

    def test_source_must_be_source_recorded(self):
        with self.assertRaises(TypedIdentityError):
            SourcedIdentity(
                runtime=TypedIdentity.local(ENTITY, "ns", 1),
                source=TypedIdentity.local(ENTITY, "ns", 2),
            )

    def test_runtime_must_be_a_typed_identity(self):
        for value in (None, "x", 1, {}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    SourcedIdentity(runtime=value)

    def test_round_trip_with_source(self):
        pair = self.make()
        payload = pair.to_dict()
        restored = SourcedIdentity.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.runtime, pair.runtime)
        self.assertEqual(restored.require_source(), pair.require_source())
        self.assertEqual(restored, pair)

    def test_round_trip_without_source_omits_the_key(self):
        pair = self.make(with_source=False)
        payload = pair.to_dict()
        self.assertNotIn("source", payload)
        restored = SourcedIdentity.from_dict(payload)
        self.assertFalse(restored.has_source())
        self.assertEqual(restored.to_dict(), payload)

    def test_json_round_trip(self):
        pair = self.make(source_family=TEAM)
        text = json.dumps(pair.to_dict(), sort_keys=True)
        restored = SourcedIdentity.from_dict(json.loads(text))
        self.assertEqual(restored, pair)
        self.assertIs(restored.require_source().family, TEAM)

    def test_malformed_documents_are_rejected(self):
        for broken in (
            None,
            [],
            {},
            {"schema": "sourced_identity/2", "runtime": self.make().runtime.to_dict()},
            {"schema": "sourced_identity/1"},
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedIdentityError):
                    SourcedIdentity.from_dict(broken)

    def test_no_truthiness(self):
        with self.assertRaises(TypedIdentityError):
            bool(self.make())
        with self.assertRaises(TypedIdentityError):
            bool(self.make(with_source=False))

    def test_no_merge_helper_exists(self):
        for name in (
            "merge",
            "unify",
            "as_runtime",
            "collapse",
            "prefer_source",
            "prefer_runtime",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(SourcedIdentity, name))


if __name__ == "__main__":
    unittest.main()
