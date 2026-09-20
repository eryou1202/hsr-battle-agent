# -*- coding: utf-8 -*-
"""F02-003 tests: owner / caster / provider / receiver and context families.

Acceptance criteria: all families distinct, and a provider/caster conflict
fixture.  The suite also proves no provider=caster shortcut exists, that any
conversion needs its own explicit named contract, and that every family refuses
float normalization.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.identity import (  # noqa: E402
    CASTER,
    DAMAGE_COMPONENT,
    DAMAGE_HIT,
    DAMAGE_ROOT,
    EQUIPMENT_INSTANCE,
    FAMILY_A,
    FAMILY_B,
    FAMILY_B_NAMES,
    GLOBAL_SERVICE,
    MODIFIER,
    OWNER,
    PROVIDER,
    RECEIVER,
    ROLE_FAMILIES,
    TARGET_CONTEXT,
    TASK,
    IdentityAuthority,
    IdentityFamily,
    RoleBundle,
    TypedIdentity,
    TypedIdentityError,
    require_family_b,
)

ABOVE_2_53 = 2**53 + 1


def ident(family, value=1, namespace="battle.test", generation=0):
    return TypedIdentity.local(family, namespace, value, generation=generation)


def role_bundle(owner_value=1, caster_value=2, provider_value=3, receiver_value=None):
    return RoleBundle(
        owner=ident(OWNER, owner_value),
        caster=ident(CASTER, caster_value),
        provider=ident(PROVIDER, provider_value),
        receiver=None if receiver_value is None else ident(RECEIVER, receiver_value),
    )


class TestFamilyDeclaration(unittest.TestCase):
    def test_declared_names(self):
        self.assertEqual(
            FAMILY_B_NAMES,
            (
                "OWNER",
                "CASTER",
                "PROVIDER",
                "RECEIVER",
                "EQUIPMENT_INSTANCE",
                "TARGET_CONTEXT",
                "GLOBAL_SERVICE",
                "TASK",
                "MODIFIER",
                "DAMAGE_ROOT",
                "DAMAGE_HIT",
                "DAMAGE_COMPONENT",
            ),
        )
        self.assertEqual(len(FAMILY_B), 12)

    def test_role_families_are_a_subset(self):
        self.assertEqual(len(ROLE_FAMILIES), 4)
        for family in ROLE_FAMILIES:
            self.assertIn(family.name, FAMILY_B_NAMES)

    def test_each_family_is_a_declared_instance(self):
        for family in FAMILY_B:
            with self.subTest(family=family.name):
                self.assertTrue(family.is_declared())
                self.assertIs(require_family_b(family.name), family)

    def test_require_family_b_rejects_other_families(self):
        with self.assertRaises(TypedIdentityError):
            require_family_b(FAMILY_A[0])
        with self.assertRaises(TypedIdentityError):
            require_family_b("NOT_DECLARED")
        for value in ("", None, 1, []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    require_family_b(value)


class TestAllFamiliesDistinct(unittest.TestCase):
    def test_family_a_and_family_b_do_not_overlap(self):
        overlap = set(FAMILY_B_NAMES) & set(f.name for f in FAMILY_A)
        self.assertEqual(overlap, set())

    def test_every_family_b_tag_is_unique(self):
        self.assertEqual(len(set(FAMILY_B_NAMES)), len(FAMILY_B_NAMES))
        self.assertEqual(len(set(FAMILY_B)), len(FAMILY_B))

    def test_all_seventeen_declared_families_are_distinct(self):
        combined = list(FAMILY_A) + list(FAMILY_B)
        self.assertEqual(len(combined), 17)
        self.assertEqual(len(set(combined)), 17)
        self.assertEqual(len({f.name for f in combined}), 17)

    def test_same_value_across_all_family_b_members_is_never_equal(self):
        identities = [ident(family, "same") for family in FAMILY_B]
        self.assertEqual(len(set(identities)), len(FAMILY_B))
        for left in identities:
            for right in identities:
                if left.family.name == right.family.name:
                    continue
                with self.subTest(left=left.family.name, right=right.family.name):
                    self.assertNotEqual(left, right)

    def test_provider_and_caster_are_different_families(self):
        provider = ident(PROVIDER, 7)
        caster = ident(CASTER, 7)
        self.assertIsNot(provider.family, caster.family)
        self.assertNotEqual(provider, caster)
        self.assertNotEqual(provider.family.name, caster.family.name)
        self.assertFalse(provider.same_family(caster))

    def test_owner_and_actor_are_different_families(self):
        from hsr_battle_agent.battle_sandbox.identity import ACTOR, ENTITY

        self.assertNotEqual(OWNER, ACTOR)
        self.assertNotEqual(ident(OWNER, 1), ident(ACTOR, 1))
        self.assertNotEqual(ident(ENTITY, 1), ident(OWNER, 1))

    def test_team_and_formation_slot_are_different_families(self):
        from hsr_battle_agent.battle_sandbox.identity import (
            FORMATION_SLOT,
            TEAM,
        )

        self.assertNotEqual(ident(TEAM, 1), ident(FORMATION_SLOT, 1))

    def test_damage_families_are_three_distinct_families(self):
        root = ident(DAMAGE_ROOT, 1)
        hit = ident(DAMAGE_HIT, 1)
        component = ident(DAMAGE_COMPONENT, 1)
        self.assertEqual(len({root, hit, component}), 3)
        self.assertEqual(
            {root.family.name, hit.family.name, component.family.name},
            {"DAMAGE_ROOT", "DAMAGE_HIT", "DAMAGE_COMPONENT"},
        )


class TestProviderCasterConflictFixture(unittest.TestCase):
    """The conflict fixture: provider and caster legitimately differ."""

    def test_provider_and_caster_may_differ(self):
        bundle = role_bundle(caster_value="Avatar_Skill01", provider_value="Modifier_Global01")
        self.assertNotEqual(bundle.caster.value, bundle.provider.value)
        self.assertIs(bundle.caster.family, CASTER)
        self.assertIs(bundle.provider.family, PROVIDER)
        self.assertFalse(bundle.values_coincide())

    def test_provider_and_caster_may_coincide_without_merging(self):
        bundle = role_bundle(caster_value="same", provider_value="same")
        self.assertEqual(bundle.caster.value, bundle.provider.value)
        self.assertTrue(bundle.values_coincide())
        self.assertNotEqual(bundle.caster, bundle.provider)
        self.assertIsNot(bundle.caster, bundle.provider)
        # Coincidence of values is recorded, never used to merge the roles.
        self.assertNotEqual(
            bundle.to_dict()["caster"], bundle.to_dict()["provider"]
        )

    def test_assume_provider_is_caster_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            role_bundle().assume_provider_is_caster()

    def test_assume_owner_is_actor_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            role_bundle().assume_owner_is_actor()

    def test_assume_team_is_formation_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            role_bundle().assume_team_is_formation()

    def test_no_role_shortcut_helpers_exist(self):
        for name in (
            "provider_from_caster",
            "caster_from_provider",
            "owner_from_actor",
            "actor_from_owner",
            "as_caster",
            "as_provider",
            "merge_roles",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(RoleBundle, name))

    def test_roles_are_stored_separately(self):
        bundle = role_bundle(receiver_value=9)
        self.assertEqual(bundle.roles(), ("owner", "caster", "provider", "receiver"))
        self.assertEqual(len(bundle.roles()), 4)
        self.assertIs(bundle.receiver.family, RECEIVER)

    def test_receiver_may_be_absent(self):
        bundle = role_bundle()
        self.assertIsNone(bundle.receiver)
        self.assertEqual(bundle.roles(), ("owner", "caster", "provider"))

    def test_role_families_are_enforced(self):
        with self.assertRaises(TypedIdentityError):
            RoleBundle(
                owner=ident(CASTER, 1),
                caster=ident(CASTER, 2),
                provider=ident(PROVIDER, 3),
            )
        with self.assertRaises(TypedIdentityError):
            RoleBundle(
                owner=ident(OWNER, 1),
                caster=ident(CASTER, 2),
                provider=ident(CASTER, 3),
            )
        with self.assertRaises(TypedIdentityError):
            RoleBundle(
                owner=ident(OWNER, 1),
                caster=ident(CASTER, 2),
                provider=ident(PROVIDER, 3),
                receiver=ident(OWNER, 4),
            )

    def test_roles_must_be_typed_identities(self):
        for value in (None, "x", 1, {}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    RoleBundle(owner=value, caster=ident(CASTER, 2),
                               provider=ident(PROVIDER, 3))

    def test_bundle_round_trips(self):
        bundle = role_bundle(caster_value="c", provider_value="p", receiver_value=9)
        payload = bundle.to_dict()
        restored = RoleBundle.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored, bundle)
        self.assertIs(restored.caster.family, CASTER)
        self.assertIs(restored.provider.family, PROVIDER)
        self.assertIs(restored.receiver.family, RECEIVER)

    def test_bundle_round_trips_without_a_receiver(self):
        bundle = role_bundle()
        payload = bundle.to_dict()
        self.assertNotIn("receiver", payload)
        self.assertEqual(RoleBundle.from_dict(payload).to_dict(), payload)

    def test_bundle_json_round_trip(self):
        bundle = role_bundle(receiver_value=9)
        text = json.dumps(bundle.to_dict(), sort_keys=True)
        self.assertEqual(RoleBundle.from_dict(json.loads(text)), bundle)

    def test_bundle_no_truthiness(self):
        with self.assertRaises(TypedIdentityError):
            bool(role_bundle())

    def test_malformed_bundle_documents_are_rejected(self):
        for broken in (
            None,
            [],
            {},
            {"schema": "role_bundle/2"},
            {"schema": "role_bundle/1"},
            {"owner": ident(OWNER, 1).to_dict()},
            {
                "owner": ident(OWNER, 1).to_dict(),
                "caster": ident(CASTER, 2).to_dict(),
            },
            {
                "owner": ident(CASTER, 1).to_dict(),
                "caster": ident(CASTER, 2).to_dict(),
                "provider": ident(PROVIDER, 3).to_dict(),
            },
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(TypedIdentityError):
                    RoleBundle.from_dict(broken)


class TestConstructionAndRejectionMatrix(unittest.TestCase):
    def test_every_family_constructs(self):
        for family in FAMILY_B:
            with self.subTest(family=family.name):
                identity = ident(family, 1)
                self.assertIs(identity.family, family)
                self.assertIs(
                    identity.authority, IdentityAuthority.LOCAL_DESIGN_IDENTITY
                )

    def test_every_family_rejects_bad_values(self):
        for family in FAMILY_B:
            for value in (1.0, 0.5, True, False, None, [], {}):
                with self.subTest(family=family.name, value=repr(value)):
                    with self.assertRaises(TypedIdentityError):
                        ident(family, value)

    def test_every_family_rejects_bad_namespace_and_generation(self):
        for family in FAMILY_B:
            with self.subTest(family=family.name):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity.local(family, "", 1)
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity.local(family, "ns", 1, generation=-1)
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity.local(family, "ns", 1, generation=1.0)

    def test_every_family_rejects_native_authority(self):
        for family in FAMILY_B:
            with self.subTest(family=family.name):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity(
                        family=family,
                        namespace="ns",
                        generation=0,
                        value=1,
                        authority=IdentityAuthority.NATIVE_CLIENT_IDENTITY,
                    )

    def test_every_family_preserves_ids_above_2_53(self):
        for family in FAMILY_B:
            with self.subTest(family=family.name):
                identity = ident(family, ABOVE_2_53)
                self.assertEqual(identity.require_int_value(), ABOVE_2_53)
                restored = TypedIdentity.from_dict(identity.to_dict())
                self.assertEqual(restored.require_int_value(), ABOVE_2_53)

    def test_every_family_rejects_undeclared_family_input(self):
        for value in (
            IdentityFamily("TEST_UNDECLARED"),
            "TEST_UNDECLARED",
            "lowercase",
            "",
            None,
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypedIdentityError):
                    TypedIdentity.local(value, "ns", 1)


class TestExplicitConversionsOnly(unittest.TestCase):
    def test_conversion_requires_a_named_contract(self):
        provider = ident(PROVIDER, 1)
        for contract in ("", None, 1):
            with self.subTest(contract=repr(contract)):
                with self.assertRaises(TypedIdentityError):
                    provider.convert_family(CASTER, contract=contract)

    def test_named_conversion_between_provider_and_caster(self):
        provider = ident(PROVIDER, ABOVE_2_53)
        caster = provider.convert_family(
            CASTER, contract="explicit.provider_to_caster"
        )
        self.assertIs(caster.family, CASTER)
        self.assertEqual(caster.value, ABOVE_2_53)
        self.assertNotEqual(provider, caster)

    def test_conversion_between_every_family_b_pair_needs_a_contract(self):
        for source in FAMILY_B:
            for target in FAMILY_B:
                if source.name == target.name:
                    continue
                with self.subTest(source=source.name, target=target.name):
                    with self.assertRaises(TypedIdentityError):
                        ident(source, 1).convert_family(target, contract="")
                    converted = ident(source, 1).convert_family(
                        target, contract="explicit.named.contract"
                    )
                    self.assertIs(converted.family, target)

    def test_conversion_to_undeclared_family_is_refused(self):
        with self.assertRaises(TypedIdentityError):
            ident(PROVIDER, 1).convert_family("UNDECLARED", contract="c")

    def test_no_implicit_conversion_protocols_exist(self):
        for protocol in ("__int__", "__index__", "__float__"):
            with self.subTest(protocol=protocol):
                self.assertNotIn(protocol, vars(TypedIdentity))


if __name__ == "__main__":
    unittest.main()
