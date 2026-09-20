# -*- coding: utf-8 -*-
"""F02-001 tests: typed identity base and LOCAL_DESIGN_IDENTITY authority.

Acceptance criteria: cross-family inequality, serialization round trip, and an
identity above 2**53.  The suite also proves that float normalization and
implicit int coercion are impossible, that LOCAL_DESIGN_IDENTITY is explicit,
and that local identity can never be certified as native client identity.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.identity import (  # noqa: E402
    IDENTITY_SCHEMA,
    IdentityAuthority,
    IdentityFamily,
    TypedIdentity,
    TypedIdentityError,
    declare_identity_family,
    declared_identity_families,
    require_declared_family,
)

# F02-001 owns the framework only; the domain families arrive in F02-002 and
# F02-003.  Tests declare their own tags through the public API.
ALPHA = declare_identity_family("TEST_ALPHA")
BETA = declare_identity_family("TEST_BETA")
GAMMA = declare_identity_family("TEST_GAMMA")

ABOVE_2_53 = 2**53 + 1


def local(family=ALPHA, namespace="ns.test", value=1, generation=0):
    return TypedIdentity.local(family, namespace, value, generation=generation)


class TestFamilyDeclaration(unittest.TestCase):
    def test_families_are_declared_explicitly(self):
        self.assertTrue(ALPHA.is_declared())
        self.assertIn(ALPHA.name, [f.name for f in declared_identity_families()])

    def test_declaration_is_idempotent(self):
        again = declare_identity_family("TEST_ALPHA")
        self.assertIs(again, ALPHA)
        self.assertEqual(
            [f.name for f in declared_identity_families()].count("TEST_ALPHA"), 1
        )

    def test_undeclared_family_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            require_declared_family("NOT_DECLARED_ANYWHERE")

    def test_undeclared_tag_cannot_be_used_directly(self):
        with self.assertRaises(TypedIdentityError):
            TypedIdentity(
                family=IdentityFamily("TEST_UNDECLARED"),
                namespace="ns",
                generation=0,
                value=1,
                authority=IdentityAuthority.LOCAL_DESIGN_IDENTITY,
            )

    def test_invalid_family_tags_are_rejected(self):
        for tag in ("lower", "Mixed", "", "1ABC", "A-B", "A B", None, 1, "A.B"):
            with self.subTest(tag=repr(tag)):
                with self.assertRaises(TypedIdentityError):
                    declare_identity_family(tag)

    def test_family_equality_is_by_tag(self):
        self.assertEqual(ALPHA, ALPHA)
        self.assertNotEqual(ALPHA, BETA)
        self.assertNotEqual(ALPHA.name, BETA.name)

    def test_family_round_trip(self):
        self.assertEqual(IdentityFamily.from_dict(ALPHA.to_dict()), ALPHA)
        payload = ALPHA.to_dict()
        self.assertEqual(IdentityFamily.from_dict(json.loads(json.dumps(payload))), ALPHA)

    def test_family_document_requires_a_name(self):
        for broken in (None, [], {}, {"tag": "X"}):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedIdentityError):
                    IdentityFamily.from_dict(broken)


class TestAuthorityVocabulary(unittest.TestCase):
    def test_authority_spellings(self):
        self.assertEqual(
            IdentityAuthority.spellings(),
            (
                "LOCAL_DESIGN_IDENTITY",
                "SOURCE_RECORDED_IDENTITY",
                "NATIVE_CLIENT_IDENTITY",
            ),
        )

    def test_local_design_authority_is_explicit(self):
        identity = local()
        self.assertIs(
            identity.authority, IdentityAuthority.LOCAL_DESIGN_IDENTITY
        )
        self.assertTrue(identity.is_local_design())
        self.assertFalse(identity.is_source_recorded())

    def test_source_recorded_authority_is_distinct(self):
        identity = TypedIdentity.from_source_record(
            BETA, "ns.source", "Avatar_Advanced_BlackSwan_00_PassiveSkill01"
        )
        self.assertIs(
            identity.authority, IdentityAuthority.SOURCE_RECORDED_IDENTITY
        )
        self.assertTrue(identity.is_source_recorded())

    def test_local_and_source_recorded_are_not_equal(self):
        self.assertNotEqual(
            local(value="x"), TypedIdentity.from_source_record(ALPHA, "ns.test", "x")
        )

    def test_local_identity_cannot_be_certified_native(self):
        with self.assertRaises(TypedIdentityError):
            local().certify_native_identity()

    def test_source_recorded_identity_cannot_be_certified_native(self):
        with self.assertRaises(TypedIdentityError):
            TypedIdentity.from_source_record(
                ALPHA, "ns", 1
            ).certify_native_identity()

    def test_native_authority_cannot_be_constructed(self):
        with self.assertRaises(TypedIdentityError):
            TypedIdentity(
                family=ALPHA,
                namespace="ns",
                generation=0,
                value=1,
                authority=IdentityAuthority.NATIVE_CLIENT_IDENTITY,
            )
        with self.assertRaises(TypedIdentityError):
            TypedIdentity(
                family=ALPHA,
                namespace="ns",
                generation=0,
                value=1,
                authority="NATIVE_CLIENT_IDENTITY",
            )

    def test_unknown_authority_is_rejected(self):
        for value in ("LOCAL", "", None, 1, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity(
                        family=ALPHA,
                        namespace="ns",
                        generation=0,
                        value=1,
                        authority=value,
                    )

    def test_authority_has_no_truthiness(self):
        for authority in IdentityAuthority:
            with self.subTest(authority=authority.name):
                with self.assertRaises(TypedIdentityError):
                    bool(authority)


class TestCrossFamilyInequality(unittest.TestCase):
    def test_same_fields_different_family_are_not_equal(self):
        left = local(family=ALPHA, value=7)
        right = local(family=BETA, value=7)
        self.assertEqual(left.namespace, right.namespace)
        self.assertEqual(left.generation, right.generation)
        self.assertEqual(left.value, right.value)
        self.assertEqual(left.authority, right.authority)
        self.assertNotEqual(left, right)

    def test_cross_family_inequality_holds_for_every_pair(self):
        families = (ALPHA, BETA, GAMMA)
        for left in families:
            for right in families:
                if left.name == right.name:
                    continue
                with self.subTest(left=left.name, right=right.name):
                    self.assertNotEqual(
                        local(family=left, value="same"),
                        local(family=right, value="same"),
                    )

    def test_cross_family_inequality_holds_in_sets_and_dicts(self):
        left = local(family=ALPHA, value=7)
        right = local(family=BETA, value=7)
        self.assertEqual(len({left, right}), 2)
        self.assertNotEqual({left: 1}, {right: 1})

    def test_same_family_same_fields_are_equal(self):
        self.assertEqual(local(value=7), local(value=7))

    def test_same_family_helper(self):
        self.assertTrue(local().same_family(local()))
        self.assertFalse(local(family=ALPHA).same_family(local(family=BETA)))
        self.assertFalse(local().same_family("not-an-identity"))

    def test_matching_values_do_not_alias_families(self):
        # Identical values must not collapse two families into one.
        identity_pair = (
            local(family=ALPHA, value=1),
            local(family=BETA, value=1),
        )
        self.assertEqual({i.family.name for i in identity_pair}, {"TEST_ALPHA", "TEST_BETA"})
        self.assertEqual(len(set(identity_pair)), 2)


class TestExactIntegerIdentity(unittest.TestCase):
    def test_value_above_2_53_survives_exactly(self):
        identity = local(value=ABOVE_2_53)
        self.assertTrue(identity.value_is_int())
        self.assertEqual(identity.require_int_value(), ABOVE_2_53)
        self.assertEqual(identity.to_dict()["value"], ABOVE_2_53)

    def test_value_above_2_53_round_trips(self):
        identity = local(value=ABOVE_2_53)
        restored = TypedIdentity.from_dict(identity.to_dict())
        self.assertEqual(restored.require_int_value(), ABOVE_2_53)
        self.assertEqual(restored, identity)
        text = json.dumps(identity.to_dict(), sort_keys=True)
        self.assertEqual(
            TypedIdentity.from_dict(json.loads(text)).require_int_value(),
            ABOVE_2_53,
        )

    def test_very_large_integers_survive(self):
        for value in (2**53, 2**63, 2**64 - 1, 10**30 + 1):
            with self.subTest(value=value):
                self.assertEqual(local(value=value).require_int_value(), value)

    def test_float_is_refused(self):
        for value in (1.0, 0.5, float(ABOVE_2_53)):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    local(value=value)

    def test_float_is_refused_from_a_document(self):
        payload = local(value=1).to_dict()
        payload["value"] = 1.0
        with self.assertRaises(TypedIdentityError):
            TypedIdentity.from_dict(payload)

    def test_bool_is_not_an_identity_value(self):
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaises(TypedIdentityError):
                    local(value=value)

    def test_string_identity_is_not_coerced_to_int(self):
        identity = local(value="20021")
        self.assertTrue(identity.value_is_str())
        self.assertFalse(identity.value_is_int())
        self.assertEqual(identity.value, "20021")
        with self.assertRaises(TypedIdentityError):
            identity.require_int_value()

    def test_integer_identity_is_not_coerced_to_string(self):
        identity = local(value=20021)
        self.assertTrue(identity.value_is_int())
        self.assertIsInstance(identity.require_int_value(), int)
        self.assertNotEqual(identity.value, "20021")

    def test_string_and_int_values_are_distinct_identities(self):
        self.assertNotEqual(local(value=20021), local(value="20021"))

    def test_empty_string_value_is_rejected(self):
        with self.assertRaises(TypedIdentityError):
            local(value="")

    def test_other_value_types_are_rejected(self):
        for value in (None, [], {}, (), object()):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    local(value=value)


class TestConstructionValidation(unittest.TestCase):
    def test_namespace_must_be_non_empty(self):
        for namespace in ("", None, 1, []):
            with self.subTest(namespace=repr(namespace)):
                with self.assertRaises(TypedIdentityError):
                    local(namespace=namespace)

    def test_generation_must_be_a_non_negative_int(self):
        for generation in (-1, 1.0, "0", None, True):
            with self.subTest(generation=repr(generation)):
                with self.assertRaises(TypedIdentityError):
                    local(generation=generation)

    def test_generation_zero_and_positive_are_accepted(self):
        self.assertEqual(local(generation=0).generation, 0)
        self.assertEqual(local(generation=17).generation, 17)

    def test_identity_is_immutable(self):
        identity = local()
        with self.assertRaises(Exception):
            identity.value = 99

    def test_identity_has_no_truthiness(self):
        with self.assertRaises(TypedIdentityError):
            bool(local(value=0))


class TestSerialization(unittest.TestCase):
    def test_schema_constant(self):
        self.assertEqual(IDENTITY_SCHEMA, "typed_identity/1")
        self.assertEqual(local().to_dict()["schema"], IDENTITY_SCHEMA)

    def test_round_trip_preserves_every_field(self):
        identity = local(value=ABOVE_2_53, generation=3)
        payload = identity.to_dict()
        restored = TypedIdentity.from_dict(payload)
        self.assertEqual(restored, identity)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.family.name, identity.family.name)
        self.assertEqual(restored.namespace, identity.namespace)
        self.assertEqual(restored.generation, identity.generation)
        self.assertEqual(restored.value, identity.value)
        self.assertIs(restored.authority, identity.authority)

    def test_round_trip_preserves_the_value_type(self):
        for value in (ABOVE_2_53, 0, -5, "20021", "token"):
            with self.subTest(value=repr(value)):
                restored = TypedIdentity.from_dict(local(value=value).to_dict())
                self.assertIs(type(restored.value), type(value))

    def test_json_round_trip(self):
        identity = local(value=ABOVE_2_53, generation=2)
        text = json.dumps(identity.to_dict(), sort_keys=True)
        self.assertEqual(TypedIdentity.from_dict(json.loads(text)), identity)

    def test_serialization_does_not_alias_the_model(self):
        identity = local(value="token")
        payload = identity.to_dict()
        payload["value"] = "mutated"
        payload["namespace"] = "mutated"
        self.assertEqual(identity.value, "token")
        self.assertEqual(identity.namespace, "ns.test")

    def test_family_identity_is_canonical_after_round_trip(self):
        restored = TypedIdentity.from_dict(local().to_dict())
        self.assertIs(restored.family, ALPHA)

    def test_malformed_documents_are_rejected(self):
        for broken in (
            None,
            [],
            "x",
            {},
            {"schema": "typed_identity/2"},
            {
                "schema": IDENTITY_SCHEMA,
                "family": "TEST_ALPHA",
                "namespace": "ns",
                "generation": 0,
                "value": 1,
            },
            {
                "schema": IDENTITY_SCHEMA,
                "family": "UNDECLARED",
                "namespace": "ns",
                "generation": 0,
                "value": 1,
                "authority": "LOCAL_DESIGN_IDENTITY",
            },
            {
                "schema": IDENTITY_SCHEMA,
                "family": "TEST_ALPHA",
                "namespace": "ns",
                "generation": 0,
                "value": 1,
                "authority": "NATIVE_CLIENT_IDENTITY",
            },
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity.from_dict(broken)


class TestNamedConversions(unittest.TestCase):
    def test_family_conversion_requires_a_named_contract(self):
        for contract in ("", None, 1):
            with self.subTest(contract=repr(contract)):
                with self.assertRaises(TypedIdentityError):
                    local().convert_family(BETA, contract=contract)

    def test_family_conversion_preserves_value_and_names_the_change(self):
        converted = local(value=ABOVE_2_53).convert_family(
            BETA, contract="explicit.test.contract"
        )
        self.assertEqual(converted.family, BETA)
        self.assertEqual(converted.value, ABOVE_2_53)
        self.assertEqual(converted.namespace, "ns.test")
        self.assertNotEqual(converted, local(value=ABOVE_2_53))

    def test_same_family_conversion_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            local().convert_family(ALPHA, contract="c")

    def test_conversion_to_undeclared_family_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            local().convert_family("UNDECLARED", contract="c")

    def test_generation_advance_requires_a_named_contract(self):
        with self.assertRaises(TypedIdentityError):
            local().advance_generation(contract="")
        self.assertEqual(
            local(generation=4)
            .advance_generation(contract="explicit.bump")
            .generation,
            5,
        )

    def test_no_implicit_conversion_helpers_exist(self):
        for name in (
            "to_family",
            "as_family",
            "auto_convert",
            "coerce_value",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(TypedIdentity, name))
        # No numeric coercion protocols are defined, so an identity can never be
        # implicitly turned into an int or a float.  (``__str__`` is inherited
        # from object and is a display protocol, not a value conversion.)
        for protocol in ("__int__", "__index__", "__float__", "__complex__"):
            with self.subTest(protocol=protocol):
                self.assertNotIn(protocol, vars(TypedIdentity))

    def test_no_executability_helpers_exist(self):
        for name in (
            "executable",
            "is_executable",
            "can_execute",
            "implies_execution",
            "as_bool",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(TypedIdentity, name))


if __name__ == "__main__":
    unittest.main()
