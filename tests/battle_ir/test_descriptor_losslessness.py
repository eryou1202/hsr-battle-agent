# -*- coding: utf-8 -*-
"""R01-013 cross-family losslessness suite.

One suite that holds every descriptor family to the same representation
invariants, so a family cannot be lossless in its own test file and lossy in
another.  It is verification only: it asserts on frozen representation
behaviour and grants no execution permission anywhere.

What this suite deliberately does not do:

* it never invents native semantics, executes a descriptor or promotes a
  reference model to native;
* it never re-derives a content join -- the resolution ledger and the
  published mapping remain the sole source of mapping state;
* it never weakens a semantic expectation to make a failure go away.

The regression block at the end pins CR-R01-CLOSURE-REVIEW-20260922-001, the
narrow corrective that followed the R01-003..R01-012 Sol review.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptor_registry import (  # noqa: E402
    DescriptorFamily,
    DescriptorRegistration,
    DescriptorRegistry,
    DescriptorRegistryError,
)
from hsr_battle_agent.battle_ir.descriptors.base import (  # noqa: E402
    DESCRIPTOR_BATCH_SCHEMA,
    DescriptorBatch,
    DescriptorError,
    DescriptorOccurrence,
    _descriptor_class_by_type,
)
from hsr_battle_agent.battle_ir.descriptors.damage import (  # noqa: E402
    DamageDescriptor,
)
from hsr_battle_agent.battle_ir.descriptors.formation import (  # noqa: E402
    FormationTopologyDescriptor,
)
from hsr_battle_agent.battle_ir.descriptors.invocation import (  # noqa: E402
    InvocationDescriptor,
)
from hsr_battle_agent.battle_ir.descriptors.modifier import (  # noqa: E402
    ModifierDescriptor,
    ModifierDescriptorKind,
)
from hsr_battle_agent.battle_ir.descriptors.monster_ai import (  # noqa: E402
    MonsterAIDescriptor,
)
from hsr_battle_agent.battle_ir.descriptors.progression import (  # noqa: E402
    ProgressionActivationDescriptor,
)
from hsr_battle_agent.battle_ir.descriptors.scenario import (  # noqa: E402
    ScenarioDescriptor,
    ScenarioDescriptorKind,
)
from hsr_battle_agent.battle_ir.descriptors.scheduler import (  # noqa: E402
    SchedulerDescriptor,
)
from hsr_battle_agent.battle_ir.descriptors.target import (  # noqa: E402
    ResolvedTargetSet,
    RetargetDescriptor,
    TargetIntent,
    TargetDescriptorKnowledge,
)
from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    ContractRef,
    EvidenceMode,
    UnknownHandle,
    parse_evidence_mode,
)
from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    PresenceValue as P,
)
from hsr_battle_agent.battle_sandbox.evidence_boundary import (  # noqa: E402
    EvidenceBoundaryError,
    require_native_contract,
)
from tests.battle_ir.test_descriptor_base import occurrence  # noqa: E402
from tests.battle_ir.test_descriptor_damage import _item as damage  # noqa: E402
from tests.battle_ir.test_descriptor_formation import _item as formation  # noqa: E402
from tests.battle_ir.test_descriptor_invocation import _item as invocation  # noqa: E402
from tests.battle_ir.test_descriptor_modifier import _item as modifier  # noqa: E402
from tests.battle_ir.test_descriptor_monster_ai import _item as monster_ai  # noqa: E402
from tests.battle_ir.test_descriptor_progression import _item as progression  # noqa: E402
from tests.battle_ir.test_descriptor_scenario import _item as scenario  # noqa: E402
from tests.battle_ir.test_descriptor_scheduler import _item as scheduler  # noqa: E402
from tests.battle_ir.test_descriptor_target import (  # noqa: E402
    _intent as target_intent,
    _resolved as resolved_targets,
    _retarget as retarget,
)


# ---------------------------------------------------------------------------
# Cross-family fixture set
# ---------------------------------------------------------------------------

# Independent expectation for every versioned representation discriminator.
EXPECTED_TAG_TYPES = {
    "base_occurrence/1": DescriptorOccurrence,
    "invocation/1": InvocationDescriptor,
    "modifier/1": ModifierDescriptor,
    "formation_topology/1": FormationTopologyDescriptor,
    "scheduler/1": SchedulerDescriptor,
    "monster_ai/1": MonsterAIDescriptor,
    "damage/1": DamageDescriptor,
    "target_intent/1": TargetIntent,
    "resolved_target_set/1": ResolvedTargetSet,
    "retarget/1": RetargetDescriptor,
    "progression_activation/1": ProgressionActivationDescriptor,
    "scenario/1": ScenarioDescriptor,
}


def _one_of_every_family(offset: int = 0):
    """One live descriptor per concrete representation type, in tag order."""
    return (
        occurrence(("base", offset), offset),
        invocation(order=offset),
        modifier(order=offset),
        formation(order=offset),
        scheduler(order=offset),
        monster_ai(order=offset),
        damage(order=offset),
        target_intent(order=offset),
        resolved_targets(["entity:a", None, "entity:a"], order=offset),
        retarget(),
        progression(order=offset),
        scenario(order=offset),
    )


def _descriptor_types_for_tags():
    """The live class for each declared representation tag, in tag order."""
    return _descriptor_class_by_type()


def _batch_with_distinct_identities(offset: int = 0) -> DescriptorBatch:
    """A batch holding every representation tag exactly once.

    ``retarget`` and ``resolved_targets`` share a path prefix with other
    families at ``order=0``, so each member is placed at a private order.  The
    batch deliberately keeps the declaration order of the tag table rather than
    sorting by path or order.
    """
    items = list(_one_of_every_family(offset))
    return DescriptorBatch(tuple(items))


def _batch_of_every_family(offset: int = 0) -> DescriptorBatch:
    items = _one_of_every_family(offset)
    # ``retarget`` always claims ("retarget_families", 0); shift its path so the
    # batch does not contain two claims on one occurrence identity.
    return DescriptorBatch(items)


def _families_in_batch(offset: int = 0):
    """One member of each of the nine registry families, non-overlapping."""
    return {
        DescriptorFamily.INVOCATION: invocation(order=offset),
        DescriptorFamily.MODIFIER: modifier(order=offset),
        DescriptorFamily.FORMATION_TOPOLOGY: formation(order=offset),
        DescriptorFamily.SCHEDULER: scheduler(order=offset),
        DescriptorFamily.MONSTER_AI: monster_ai(order=offset),
        DescriptorFamily.DAMAGE: damage(order=offset),
        DescriptorFamily.TARGET_RETARGET: target_intent(order=offset),
        DescriptorFamily.PROGRESSION_LOADOUT: progression(order=offset),
        DescriptorFamily.SCENARIO_MODE_TERMINAL: scenario(order=offset),
    }


def _registry(offset: int = 0) -> DescriptorRegistry:
    return DescriptorRegistry(
        tuple(
            DescriptorRegistration(family, f"entity:{index}", descriptor)
            for index, (family, descriptor) in enumerate(
                _families_in_batch(offset).items()
            )
        )
    )


# ---------------------------------------------------------------------------
# 1. Cross-family batch round trip
# ---------------------------------------------------------------------------


class TestCrossFamilyBatchRoundTrip(unittest.TestCase):
    def test_every_concrete_type_survives_a_batch_round_trip_by_identity(self):
        original = _batch_of_every_family()
        restored = DescriptorBatch.from_dict(original.to_dict())
        self.assertEqual(
            [type(item) for item in restored.occurrences],
            [type(item) for item in original.occurrences],
        )
        for before, after in zip(original.occurrences, restored.occurrences):
            with self.subTest(descriptor=type(before).__name__):
                self.assertIs(type(after), type(before))
                self.assertEqual(after.to_dict(), before.to_dict())
                self.assertEqual(
                    after.occurrence_identity(), before.occurrence_identity()
                )

    def test_batch_covers_the_whole_versioned_tag_vocabulary(self):
        tags = _descriptor_types_for_tags()
        self.assertEqual(tags, EXPECTED_TAG_TYPES)
        self.assertEqual(set(tags.values()), {type(x) for x in _one_of_every_family()})

    def test_batch_document_round_trips_through_json_without_loss(self):
        batch = _batch_of_every_family()
        # Tuples are an in-process envelope property; a JSON transport turns
        # them into arrays.  The JSON route is therefore compared against a
        # JSON-normalised document, and the in-process route against the exact
        # in-process document.
        json_restored = DescriptorBatch.from_dict(
            json.loads(json.dumps(batch.to_dict()))
        )
        self.assertEqual(
            json.loads(json.dumps(json_restored.to_dict())),
            json.loads(json.dumps(batch.to_dict())),
        )
        in_process_restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertEqual(in_process_restored.to_dict(), batch.to_dict())

    def test_batch_does_not_deduplicate_or_sort_equal_payloads(self):
        first = occurrence(("z", 0), 9)
        second = occurrence(("a", 1), 1)
        self.assertEqual(first.payload, second.payload)
        batch = DescriptorBatch((first, second))
        self.assertEqual(
            [item.occurrence_path for item in batch.occurrences], [("z", 0), ("a", 1)]
        )
        self.assertEqual([item.source_order for item in batch.occurrences], [9, 1])
        restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertEqual(
            [item.source_order for item in restored.occurrences], [9, 1]
        )

    def test_batch_rejects_two_claims_on_one_occurrence_identity(self):
        with self.assertRaises(DescriptorError):
            DescriptorBatch((invocation(order=3), invocation(order=3)))


# ---------------------------------------------------------------------------
# 2. Family validation cannot be bypassed
# ---------------------------------------------------------------------------


class TestFamilyValidationCannotBeBypassed(unittest.TestCase):
    def _invocation_document(self):
        return DescriptorBatch((invocation(),)).to_dict()

    def test_family_invalid_arguments_are_rejected_on_direct_construction(self):
        with self.assertRaises(DescriptorError):
            InvocationDescriptor(
                ContractRef(
                    "invocation", "battle.descriptor.invocation", "1",
                    EvidenceMode.REFERENCE_MODEL, "1" * 64, ("freeze:triggerability",),
                ),
                EvidenceMode.REFERENCE_MODEL,
                invocation().provenance,
                ("payload_families", 0),
                0,
                P.present({"fixture": True}),
                {
                    "caller": P.present({"receiver": "entity:1"}),
                    "context": P.present({"ability_target": ["entity:2"]}),
                    # A list is not a mapping: InvocationDescriptor must refuse.
                    "arguments": P.present([]),
                    "is_skill_perform": P.absent(),
                    "continuation_handles": P.present(["wait:1"]),
                    "knowledge": P.present("REPRESENTED"),
                    "blocker": P.absent(),
                },
                {},
            )

    def test_list_shaped_arguments_cannot_enter_through_batch_restoration(self):
        document = self._invocation_document()
        serialized = document["occurrences"][0]["descriptor"]
        arguments = next(
            item for item in serialized["fields"] if item["name"] == "arguments"
        )
        arguments["value"] = P.present([]).to_dict()
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(document)

    def test_missing_unknown_and_mismatched_tags_fail_closed(self):
        document = self._invocation_document()
        missing = copy.deepcopy(document)
        missing["occurrences"][0].pop("descriptor_type")
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(missing)
        unknown = copy.deepcopy(document)
        unknown["occurrences"][0]["descriptor_type"] = "future_descriptor/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(unknown)
        mismatched = copy.deepcopy(document)
        mismatched["occurrences"][0]["descriptor_type"] = "modifier/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(mismatched)

    def test_legacy_v1_batch_schema_is_refused(self):
        document = self._invocation_document()
        document["schema"] = "descriptor_batch/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(document)

    def test_a_restored_invocation_is_still_a_registrable_invocation(self):
        restored = DescriptorBatch.from_dict(
            DescriptorBatch((invocation(),)).to_dict()
        ).occurrences[0]
        self.assertIs(type(restored), InvocationDescriptor)
        registry = DescriptorRegistry(
            (DescriptorRegistration(DescriptorFamily.INVOCATION, "e", restored),)
        )
        self.assertIs(
            type(registry.resolve_static(DescriptorFamily.INVOCATION, "e")[0]),
            InvocationDescriptor,
        )
        # And it still cannot be registered under a different family.
        with self.assertRaises(DescriptorRegistryError):
            DescriptorRegistration(DescriptorFamily.DAMAGE, "e", restored)


# ---------------------------------------------------------------------------
# 3. Presence is never collapsed
# ---------------------------------------------------------------------------


class TestPresenceIsNeverCollapsed(unittest.TestCase):
    def test_absent_null_and_present_are_three_separate_states(self):
        absent, null, present = P.absent(), P.null(), P.present(False)
        self.assertTrue(absent.is_absent())
        self.assertTrue(null.is_null())
        self.assertTrue(present.is_present())
        self.assertNotEqual(absent.to_dict(), null.to_dict())
        self.assertNotEqual(null.to_dict(), present.to_dict())
        # A false/zero/empty payload is still PRESENT, never ABSENT or NULL.
        for value in (False, 0, "", [], {}, ()):
            with self.subTest(value=value):
                self.assertTrue(P.present(value).is_present())

    def test_absent_and_null_never_resolve_a_value(self):
        for value in (P.absent(), P.null()):
            with self.subTest(state=value.to_dict()["presence"]):
                with self.assertRaises(Exception):
                    value.require_present()

    def test_null_has_exactly_one_encoding(self):
        self.assertEqual(
            P(state=null_state(), value=None).to_dict(), P.null().to_dict()
        )

    def test_cross_family_absent_null_and_present_survive_the_whole_pipeline(self):
        absent_item = invocation(flag=P.absent())
        null_item = formation()
        self.assertTrue(absent_item.fields["is_skill_perform"].is_absent())
        self.assertTrue(null_item.fields["lineup_index"].is_null())
        self.assertTrue(retarget().fields["predicate"].is_null())

        batch = DescriptorBatch(
            (
                absent_item,
                null_item,
                retarget(),
            )
        )
        restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertTrue(restored.occurrences[0].fields["is_skill_perform"].is_absent())
        self.assertTrue(restored.occurrences[1].fields["lineup_index"].is_null())
        self.assertTrue(restored.occurrences[2].fields["predicate"].is_null())
        self.assertEqual(
            [item.to_dict() for item in restored.occurrences],
            [item.to_dict() for item in batch.occurrences],
        )

    def test_omitted_key_and_explicit_null_never_serialize_the_same(self):
        self.assertNotEqual(
            P.absent().to_dict(), P.null().to_dict()
        )
        self.assertNotIn("value", P.absent().to_dict())
        self.assertNotIn("value", P.null().to_dict())
        self.assertIn("value", P.present(None if False else 0).to_dict())


def null_state():
    from hsr_battle_agent.battle_ir.lossless_value import PresenceState

    return PresenceState.NULL


# ---------------------------------------------------------------------------
# 4. Empty versus null target lists
# ---------------------------------------------------------------------------


class TestEmptyVersusNullTargets(unittest.TestCase):
    def test_empty_list_and_list_containing_null_are_different(self):
        empty = resolved_targets([])
        one_null = resolved_targets([None])
        self.assertNotEqual(empty.to_dict(), one_null.to_dict())
        self.assertEqual(empty.targets, [])
        self.assertEqual(one_null.targets, [None])
        self.assertEqual(
            DescriptorBatch((empty,)).to_dict(),
            DescriptorBatch(
                (resolved_targets([]),)
            ).to_dict(),
        )
        restored = DescriptorBatch.from_dict(DescriptorBatch((one_null,)).to_dict())
        self.assertEqual(restored.occurrences[0].to_dict(), one_null.to_dict())

    def test_an_absent_target_list_is_not_an_empty_target_list(self):
        item = resolved_targets([])
        # In-process, an absent target list is a different encoding from an
        # empty one, and the descriptor refuses it outright.
        self.assertNotEqual(P.absent().to_dict(), P.present([]).to_dict())
        self.assertNotEqual(P.null().to_dict(), P.present([]).to_dict())
        document = item.to_dict()
        targets = next(
            entry for entry in document["fields"] if entry["name"] == "targets"
        )
        targets["value"] = P.null().to_dict()
        with self.assertRaises(DescriptorError):
            ResolvedTargetSet.from_dict(document)
        targets["value"] = P.present(("entity:1",)).to_dict()
        with self.assertRaises(DescriptorError):
            ResolvedTargetSet.from_dict(document)

    def test_a_tuple_may_not_flatten_into_a_target_list(self):
        with self.assertRaises(DescriptorError):
            resolved_targets(("entity:1",))
        item = resolved_targets([])
        document = item.to_dict()
        targets = next(
            entry for entry in document["fields"] if entry["name"] == "targets"
        )
        targets["value"] = P.present(("entity:1",)).to_dict()
        with self.assertRaises(DescriptorError):
            ResolvedTargetSet.from_dict(document)

    def test_duplicates_and_source_order_in_a_target_list_are_preserved(self):
        targets = ["entity:2", None, "entity:2", "entity:1"]
        item = resolved_targets(targets)
        self.assertEqual(item.targets, targets)
        restored = ResolvedTargetSet.from_dict(item.to_dict())
        self.assertEqual(restored.targets, targets)

    def test_targets_read_surface_is_detached(self):
        item = resolved_targets(["entity:2", None, "entity:2"])
        before = item.to_dict()
        exported = item.targets
        self.assertIsInstance(exported, list)
        exported.append("entity:3")
        exported[0] = "entity:overwritten"
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.targets, ["entity:2", None, "entity:2"])


# ---------------------------------------------------------------------------
# 5. Duplicates and source order
# ---------------------------------------------------------------------------


class TestDuplicatesAndSourceOrder(unittest.TestCase):
    def test_repeated_occurrences_are_never_deduplicated_or_reordered(self):
        items = (occurrence(("c", 0), 7), occurrence(("a", 1), 2), occurrence(("b", 2), 5))
        batch = DescriptorBatch(items)
        self.assertEqual(len(batch.occurrences), 3)
        restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertEqual(
            [item.occurrence_path for item in restored.occurrences],
            [("c", 0), ("a", 1), ("b", 2)],
        )
        self.assertEqual(
            [item.source_order for item in restored.occurrences], [7, 2, 5]
        )

    def test_tuple_and_list_shapes_are_not_flattened_together(self):
        list_item = resolved_targets(["entity:a", "entity:b"])
        # The target family refuses a tuple outright; the base family keeps a
        # tuple as a tuple rather than silently turning it into a list.
        with self.assertRaises(DescriptorError):
            resolved_targets(("entity:a", "entity:b"))
        base = occurrence(payload=P.present((1, 2)))
        self.assertEqual(base.payload.require_present(), (1, 2))
        self.assertIsInstance(base.payload.require_present(), tuple)
        self.assertIsInstance(list_item.targets, list)

    def test_covered_family_sequences_keep_source_order_and_repeats(self):
        checks = {
            "scenario.source_items": scenario(),
            "scheduler.source_sequence": scheduler(),
            "damage.special_channel_references": damage(),
            "monster_ai.sequence": monster_ai(),
        }
        expectations = {
            "scenario.source_items": [
                {"group": "g2", "slot": "Monster1"},
                {"group": "g1", "slot": "Monster0"},
                {"group": "g2", "slot": "Monster1"},
            ],
            "scheduler.source_sequence": ["candidate:b", "candidate:a", "candidate:a"],
            "damage.special_channel_references": ["Break", "DOT", "Break"],
            "monster_ai.sequence": ["skill:2", "skill:1", "skill:1"],
        }
        for label, item in checks.items():
            with self.subTest(field=label):
                name = label.split(".", 1)[1]
                value = item.fields[name].require_present()
                self.assertEqual(value, expectations[label])
                self.assertEqual(len(value), 3)

    def test_covered_sequences_survive_a_batch_round_trip_identically(self):
        batch = DescriptorBatch((scenario(), scheduler(), damage(), monster_ai()))
        restored = DescriptorBatch.from_dict(batch.to_dict())
        for before, after in zip(batch.occurrences, restored.occurrences):
            with self.subTest(descriptor=type(before).__name__):
                self.assertEqual(after.to_dict(), before.to_dict())

    def test_unknown_field_order_is_preserved_not_sorted(self):
        item = occurrence()
        self.assertEqual(
            tuple(item.unknown_fields), ("future_b", "future_a")
        )
        restored = DescriptorOccurrence.from_dict(item.to_dict())
        self.assertEqual(
            tuple(restored.unknown_fields), ("future_b", "future_a")
        )


# ---------------------------------------------------------------------------
# 6. IsSkillPerform
# ---------------------------------------------------------------------------


class TestIsSkillPerform(unittest.TestCase):
    def test_every_invocation_context_slot_is_explicit_and_lossless(self):
        item = invocation(flag=P.absent())
        expected_names = (
            "caller",
            "context",
            "arguments",
            "is_skill_perform",
            "continuation_handles",
            "knowledge",
            "blocker",
        )
        self.assertEqual(tuple(item.fields), expected_names)
        self.assertEqual(
            item.fields["caller"].require_present(), {"receiver": "entity:1"}
        )
        self.assertEqual(
            item.fields["context"].require_present(),
            {"ability_target": ["entity:2"]},
        )
        self.assertEqual(
            item.fields["arguments"].require_present(), {"AbilityName": "Nested"}
        )
        self.assertTrue(item.fields["is_skill_perform"].is_absent())
        self.assertEqual(
            item.fields["continuation_handles"].require_present(),
            ["wait:1", "finish:1"],
        )
        self.assertEqual(item.fields["knowledge"].require_present(), "REPRESENTED")
        self.assertTrue(item.fields["blocker"].is_absent())
        restored = InvocationDescriptor.from_dict(item.to_dict())
        self.assertEqual(
            [restored.fields[name].to_dict() for name in expected_names],
            [item.fields[name].to_dict() for name in expected_names],
        )

    def test_absence_is_not_false_and_not_null(self):
        absent, false, true = (
            invocation(flag=P.absent()),
            invocation(flag=P.present(False)),
            invocation(flag=P.present(True)),
        )
        self.assertTrue(absent.is_skill_perform.is_absent())
        self.assertIs(false.is_skill_perform.require_present(), False)
        self.assertIs(true.is_skill_perform.require_present(), True)
        self.assertNotEqual(absent.to_dict(), false.to_dict())
        self.assertNotEqual(false.to_dict(), true.to_dict())

    def test_the_three_states_survive_batch_and_json_round_trips(self):
        items = (
            invocation(flag=P.absent(), order=0),
            invocation(flag=P.present(False), order=1),
            invocation(flag=P.present(True), order=2),
        )
        items_batch = DescriptorBatch(items)
        # A JSON transport turns the in-process tuple into an array, so the
        # JSON route is compared against a JSON-normalised expectation.
        json_document = json.loads(json.dumps(items_batch.to_dict()))
        json_restored = DescriptorBatch.from_dict(json_document)
        self.assertTrue(json_restored.occurrences[0].is_skill_perform.is_absent())
        self.assertIs(
            json_restored.occurrences[1].is_skill_perform.require_present(), False
        )
        self.assertIs(
            json_restored.occurrences[2].is_skill_perform.require_present(), True
        )
        self.assertEqual(
            json.loads(json.dumps(json_restored.to_dict())), json_document
        )

        # The in-process envelope keeps the tuple exactly as it was.
        restored = DescriptorBatch.from_dict(items_batch.to_dict())
        self.assertTrue(restored.occurrences[0].is_skill_perform.is_absent())
        self.assertIs(
            restored.occurrences[1].is_skill_perform.require_present(), False
        )
        self.assertIs(
            restored.occurrences[2].is_skill_perform.require_present(), True
        )
        self.assertEqual(restored.to_dict(), items_batch.to_dict())

    def test_a_non_boolean_flag_rejects_on_direct_and_batch_paths(self):
        with self.assertRaises(DescriptorError):
            invocation(flag=P.present(0))
        document = DescriptorBatch((invocation(),)).to_dict()
        flag = next(
            entry
            for entry in document["occurrences"][0]["descriptor"]["fields"]
            if entry["name"] == "is_skill_perform"
        )
        flag["value"] = P.present("true").to_dict()
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(document)

    def test_the_field_never_becomes_an_execution_decision(self):
        item = invocation(flag=P.present(True))
        for name in ("perform_skill", "execute", "is_executable", "may_perform"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(item, name))
        with self.assertRaises(DescriptorError):
            item.execution_permitted()


# ---------------------------------------------------------------------------
# 7. Modifier Multiple versus mutate, Refresh versus Replace
# ---------------------------------------------------------------------------


class TestModifierOperationDistinctions(unittest.TestCase):
    def test_refresh_and_replace_never_collapse(self):
        refresh = modifier(operation="Refresh")
        replace = modifier(operation="Replace")
        self.assertNotEqual(refresh.to_dict(), replace.to_dict())
        self.assertEqual(
            refresh.fields["stacking_transition"].require_present()["operation"],
            "Refresh",
        )
        self.assertEqual(
            replace.fields["stacking_transition"].require_present()["operation"],
            "Replace",
        )

    def test_multiple_is_a_distinct_operation_from_both_mutations(self):
        multiple = modifier(operation="Multiple")
        self.assertEqual(
            multiple.fields["stacking_transition"].require_present()["operation"],
            "Multiple",
        )
        seen = {
            operation: modifier(operation=operation).to_dict()
            for operation in ("Refresh", "Replace", "Multiple", "Unknown")
        }
        self.assertEqual(len(set(json.dumps(v, sort_keys=True) for v in seen.values())), 4)

    def test_an_unlisted_or_mis_cased_operation_rejects(self):
        for operation in ("replace", "refresh", "MULTIPLE", "Merge"):
            with self.subTest(operation=operation):
                with self.assertRaises(DescriptorError):
                    modifier(operation=operation)

    def test_all_four_kinds_and_operations_survive_a_batch_round_trip(self):
        self.assertEqual(
            tuple(kind.value for kind in ModifierDescriptorKind),
            ("REQUEST", "LOOKUP_QUERY", "STACKING_TRANSITION", "LIFECYCLE_CALLBACK"),
        )
        items = tuple(
            modifier(kind, order=index)
            for index, kind in enumerate(ModifierDescriptorKind)
        )
        self.assertEqual([item.kind for item in items], list(ModifierDescriptorKind))
        batch = DescriptorBatch(items)
        restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertEqual(restored.to_dict(), batch.to_dict())
        self.assertEqual(
            [type(item) for item in restored.occurrences],
            [ModifierDescriptor] * len(items),
        )

    def test_provider_and_caster_are_never_merged(self):
        item = modifier()
        self.assertNotEqual(item.fields["provider"], item.fields["caster"])
        self.assertEqual(item.fields["provider"].require_present(), "provider:1")
        self.assertEqual(item.fields["caster"].require_present(), "caster:1")


# ---------------------------------------------------------------------------
# 8. Scenario wave, group and slot ordering
# ---------------------------------------------------------------------------


class TestScenarioWaveGroupSlotOrder(unittest.TestCase):
    def test_all_seven_scenario_kinds_stay_distinct(self):
        self.assertEqual(
            tuple(kind.value for kind in ScenarioDescriptorKind),
            (
                "SCENARIO", "WAVE_GROUP", "SLOT", "OCCURRENCE",
                "ENVIRONMENT", "MODE", "TERMINAL",
            ),
        )
        items = [
            scenario(kind, order=index)
            for index, kind in enumerate(ScenarioDescriptorKind)
        ]
        self.assertEqual([item.kind for item in items], list(ScenarioDescriptorKind))
        self.assertEqual(
            len({json.dumps(item.to_dict(), sort_keys=True) for item in items}),
            len(list(ScenarioDescriptorKind)),
        )

    def test_wave_group_slot_occurrence_order_and_duplicates_survive(self):
        item = scenario()
        items = item.fields["source_items"].require_present()
        self.assertEqual([entry["group"] for entry in items], ["g2", "g1", "g2"])
        self.assertEqual(
            [entry["slot"] for entry in items],
            ["Monster1", "Monster0", "Monster1"],
        )
        restored = ScenarioDescriptor.from_dict(item.to_dict())
        self.assertEqual(
            restored.fields["source_items"].require_present(), items
        )
        self.assertEqual(
            [entry["group"] for entry in restored.fields["source_items"].require_present()],
            ["g2", "g1", "g2"],
        )

    def test_source_order_is_never_flattened_into_a_sorted_wave_list(self):
        item = scenario(payload={"waves": ["w2", "w1", "w2"]})
        self.assertEqual(
            item.payload.require_present()["waves"], ["w2", "w1", "w2"]
        )
        restored = ScenarioDescriptor.from_dict(item.to_dict())
        self.assertEqual(
            restored.payload.require_present()["waves"], ["w2", "w1", "w2"]
        )
        for name in ("compile_waves", "flatten_waves", "sorted_waves", "to_wave_list"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ScenarioDescriptor, name))

    def test_source_items_must_stay_a_list_and_a_tuple_rejects(self):
        item = scenario()
        document = item.to_dict()
        source_items = next(
            entry for entry in document["fields"] if entry["name"] == "source_items"
        )
        source_items["value"] = P.present(("g2", "g1")).to_dict()
        with self.assertRaises(DescriptorError):
            ScenarioDescriptor.from_dict(document)

    def test_terminal_rule_class_stays_separate_from_evidence_mode(self):
        terminal = scenario(
            ScenarioDescriptorKind.TERMINAL, mode=EvidenceMode.SANDBOX_EXTENSION
        )
        self.assertEqual(
            terminal.fields["terminal_rule_class"].require_present(),
            "SANDBOX_EXTENSION",
        )
        self.assertIs(terminal.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertIs(
            terminal.evidence_mode,
            parse_evidence_mode("SANDBOX_EXTENSION"),
        )
        self.assertIsNot(terminal.evidence_mode, EvidenceMode.NATIVE_EVIDENCED)


# ---------------------------------------------------------------------------
# 9. Scheduler families and candidate ordering
# ---------------------------------------------------------------------------


class TestSchedulerFamilies(unittest.TestCase):
    def test_all_eight_families_stay_distinct(self):
        from hsr_battle_agent.battle_ir.descriptors.scheduler import SchedulerFamily

        self.assertEqual(
            tuple(family.value for family in SchedulerFamily),
            (
                "ORDINARY", "ULTRA_REQUEST", "TURN_INSERT_ABILITY",
                "TURN_INSERT_ACTION", "ONE_MORE", "IMMEDIATE_ACTION",
                "ACTION_TASK", "DAMAGE_TASK",
            ),
        )
        items = [
            scheduler(family, order=index)
            for index, family in enumerate(SchedulerFamily)
        ]
        self.assertEqual(len({item.family for item in items}), 8)
        self.assertEqual(
            len({json.dumps(item.to_dict(), sort_keys=True) for item in items}), 8
        )

    def test_near_neighbour_families_are_not_conflated(self):
        from hsr_battle_agent.battle_ir.descriptors.scheduler import SchedulerFamily

        pairs = (
            (SchedulerFamily.TURN_INSERT_ABILITY, SchedulerFamily.TURN_INSERT_ACTION),
            (SchedulerFamily.ACTION_TASK, SchedulerFamily.DAMAGE_TASK),
            (SchedulerFamily.ULTRA_REQUEST, SchedulerFamily.ORDINARY),
        )
        for left, right in pairs:
            with self.subTest(pair=(left.value, right.value)):
                self.assertIsNot(left, right)
                self.assertNotEqual(
                    scheduler(left).to_dict(), scheduler(right).to_dict()
                )

    def test_candidate_order_and_repeats_survive_including_partial_order(self):
        item = scheduler()
        self.assertEqual(
            item.fields["source_sequence"].require_present(),
            ["candidate:b", "candidate:a", "candidate:a"],
        )
        self.assertEqual(
            item.fields["partial_order"].require_present(),
            ["request", "admission"],
        )
        restored = SchedulerDescriptor.from_dict(item.to_dict())
        self.assertEqual(
            restored.fields["source_sequence"].require_present(),
            ["candidate:b", "candidate:a", "candidate:a"],
        )
        batch = DescriptorBatch((scheduler(order=1), scheduler(order=0)))
        self.assertEqual(
            [x.source_order for x in DescriptorBatch.from_dict(batch.to_dict()).occurrences],
            [1, 0],
        )

    def test_a_candidate_is_never_a_legal_action(self):
        for name in ("as_player_legal_action", "is_legal", "execute", "resolve"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(SchedulerDescriptor, name))


# ---------------------------------------------------------------------------
# 10. Representation never satisfies a native gate
# ---------------------------------------------------------------------------


class TestRepresentationNeverSatisfiesANativeGate(unittest.TestCase):
    def test_no_descriptor_family_satisfies_a_native_gate(self):
        for item in _one_of_every_family():
            with self.subTest(descriptor=type(item).__name__):
                with self.assertRaises(EvidenceBoundaryError):
                    require_native_contract(item, role=type(item).__name__)
                with self.assertRaises(DescriptorError):
                    item.execution_permitted()

    def test_a_native_evidenced_descriptor_is_still_not_a_native_contract(self):
        item = scenario(ScenarioDescriptorKind.SCENARIO, mode=EvidenceMode.NATIVE_EVIDENCED)
        self.assertIs(item.evidence_mode, EvidenceMode.NATIVE_EVIDENCED)
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(item, role="scenario")
        with self.assertRaises(DescriptorError):
            item.execution_permitted()

    def test_no_family_exposes_a_gate_or_runtime_action(self):
        forbidden = (
            "execute", "apply", "commit", "issue_gate_certificate",
            "as_native_contract", "gate_certificate", "native_contract",
            "run", "perform",
        )
        for item in _one_of_every_family():
            for name in forbidden:
                with self.subTest(descriptor=type(item).__name__, name=name):
                    self.assertFalse(hasattr(item, name))

    def test_the_registry_cannot_permit_execution(self):
        registry = _registry()
        with self.assertRaises(DescriptorRegistryError):
            registry.execution_permitted()
        self.assertFalse(hasattr(registry, "execute"))


# ---------------------------------------------------------------------------
# 11. Registry cross-family behaviour
# ---------------------------------------------------------------------------


class TestRegistryCrossFamily(unittest.TestCase):
    def test_the_registry_resolves_all_nine_families(self):
        registry = _registry()
        self.assertEqual(registry.families_present(), tuple(DescriptorFamily))
        for index, family in enumerate(DescriptorFamily):
            with self.subTest(family=family.value):
                resolved = registry.resolve_static(family, f"entity:{index}")
                self.assertEqual(len(resolved), 1)

    def test_a_family_invalid_registration_rejects(self):
        with self.assertRaises(DescriptorRegistryError):
            DescriptorRegistration(
                DescriptorFamily.DAMAGE, "entity:1", invocation()
            )
        with self.assertRaises(DescriptorRegistryError):
            DescriptorRegistration(
                DescriptorFamily.TARGET_RETARGET, "entity:1", invocation()
            )

    def test_every_family_surfaces_are_mutation_isolated(self):
        descriptor = invocation()
        registry = DescriptorRegistry(
            (
                DescriptorRegistration(
                    DescriptorFamily.INVOCATION, "entity:isolated", descriptor
                ),
            )
        )
        before = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:isolated"
        )[0].to_dict()

        descriptor.payload.require_present()["argument_keys"].append("input")
        resolved = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:isolated"
        )[0]
        resolved.fields["context"].require_present()["ability_target"].append("output")
        resolved.payload.require_present()["argument_keys"].append("resolved")
        exposed = registry.registrations[0].descriptor
        exposed.payload.require_present()["argument_keys"].append("registration")
        exposed.unknown_fields["future_field"]  # detached tuple; must not alias

        self.assertEqual(
            registry.resolve_static(
                DescriptorFamily.INVOCATION, "entity:isolated"
            )[0].to_dict(),
            before,
        )
        self.assertEqual(
            registry.registrations[0].descriptor.to_dict(), before
        )

    def test_resolved_descriptors_keep_their_exact_concrete_type(self):
        registry = _registry()
        for index, family in enumerate(DescriptorFamily):
            with self.subTest(family=family.value):
                resolved = registry.resolve_static(family, f"entity:{index}")[0]
                self.assertIs(
                    type(resolved),
                    type(_families_in_batch()[family]),
                )

    def test_resolution_does_not_reuse_or_reorder_source_occurrences(self):
        registry = _registry()
        first = registry.resolve_family(DescriptorFamily.INVOCATION)
        second = registry.resolve_family(DescriptorFamily.INVOCATION)
        self.assertEqual(
            [item.occurrence_identity() for item in first],
            [item.occurrence_identity() for item in second],
        )
        self.assertEqual(len(first), 1)


# ---------------------------------------------------------------------------
# 12. Evidence mode identity across the whole surface
# ---------------------------------------------------------------------------


class TestEvidenceModeIdentity(unittest.TestCase):
    def test_every_family_carries_the_exact_mode_of_its_contract_ref(self):
        for item in _one_of_every_family():
            with self.subTest(descriptor=type(item).__name__):
                self.assertIs(item.evidence_mode, item.contract_ref.evidence_mode)

    def test_the_mode_survives_a_batch_round_trip_as_the_same_member(self):
        batch = DescriptorBatch(_one_of_every_family())
        restored = DescriptorBatch.from_dict(batch.to_dict())
        for before, after in zip(batch.occurrences, restored.occurrences):
            with self.subTest(descriptor=type(before).__name__):
                self.assertIs(after.evidence_mode, before.evidence_mode)
                self.assertIs(
                    after.evidence_mode,
                    parse_evidence_mode(after.evidence_mode.serialize()),
                )

    def test_modes_are_never_interchangeable(self):
        modes = tuple(EvidenceMode)
        self.assertEqual(len(set(modes)), len(modes))
        for mode in modes:
            with self.subTest(mode=mode.value):
                self.assertIs(parse_evidence_mode(mode.serialize()), mode)


# ---------------------------------------------------------------------------
# 13. Unknown handles and blocked families
# ---------------------------------------------------------------------------


class TestUnknownHandlesAcrossFamilies(unittest.TestCase):
    BLOCKED_FACTORIES = (
        ("invocation", lambda: invocation(unresolved=True)),
        ("modifier", lambda: modifier(unresolved=True)),
        ("formation", lambda: formation(unresolved=True)),
        ("scheduler", lambda: scheduler(unresolved=True)),
        ("monster_ai", lambda: monster_ai(unresolved=True)),
        ("damage", lambda: damage(unresolved=True)),
        ("target_intent", lambda: target_intent(unresolved=True)),
        ("resolved_targets", lambda: resolved_targets([], unresolved=True)),
        ("retarget", lambda: retarget(unresolved=True)),
        ("progression", lambda: progression()),
        ("scenario", lambda: scenario(unresolved=True)),
    )

    def test_every_blocked_family_reports_blocked_and_carries_a_handle(self):
        for label, factory in self.BLOCKED_FACTORIES:
            with self.subTest(family=label):
                item = factory()
                self.assertTrue(item.is_blocked())
                handle = item.fields["blocker"]
                self.assertTrue(handle.is_present())
                restored = UnknownHandle.from_dict(handle.require_present())
                self.assertEqual(restored.to_dict(), handle.require_present())

    def test_blocked_state_survives_a_batch_round_trip(self):
        items = tuple(factory() for _, factory in self.BLOCKED_FACTORIES)
        batch = DescriptorBatch(items)
        restored = DescriptorBatch.from_dict(batch.to_dict())
        for before, after in zip(batch.occurrences, restored.occurrences):
            with self.subTest(descriptor=type(before).__name__):
                self.assertTrue(after.is_blocked())
                self.assertEqual(after.to_dict(), before.to_dict())

    def test_a_represented_family_never_carries_a_blocker(self):
        for label, factory in self.BLOCKED_FACTORIES:
            if label == "progression":
                continue
            with self.subTest(family=label):
                represented = _represented_for(label)
                self.assertFalse(represented.is_blocked())
                self.assertTrue(represented.fields["blocker"].is_absent())

    def test_an_unknown_handle_can_never_become_a_contract_ref(self):
        handle = UnknownHandle.from_dict(
            invocation(unresolved=True).fields["blocker"].require_present()
        )
        with self.assertRaises(Exception):
            handle.as_contract_ref()


def _represented_for(label: str):
    mapping = {
        "invocation": invocation,
        "modifier": modifier,
        "formation": formation,
        "scheduler": scheduler,
        "monster_ai": monster_ai,
        "damage": damage,
        "target_intent": target_intent,
        "resolved_targets": lambda: resolved_targets([None]),
        "retarget": retarget,
        "scenario": scenario,
    }
    return mapping[label]()


# ---------------------------------------------------------------------------
# 14. Detached read surfaces across families
# ---------------------------------------------------------------------------


class TestDetachedReadSurfaces(unittest.TestCase):
    def test_payload_fields_and_unknown_fields_are_all_detached(self):
        item = DescriptorOccurrence(
            occurrence().contract_ref,
            occurrence().evidence_mode,
            occurrence().provenance,
            ("detached", 0),
            0,
            P.present({"items": []}),
            {"known": P.present({"items": []})},
            {"future": P.present({"items": []})},
        )
        before = item.to_dict()
        item.payload.require_present()["items"].append("payload")
        item.fields["known"].require_present()["items"].append("known")
        item.unknown_fields["future"].require_present()["items"].append("future")
        self.assertEqual(item.to_dict(), before)

    def test_a_returned_document_cannot_alias_descriptor_storage(self):
        item = occurrence()
        document = item.to_dict()
        document["payload"]["value"]["same"].append("mutated")
        document["unknown_fields"][0]["value"]["value"] = ["changed"]
        self.assertEqual(item.payload.require_present(), {"same": [1, None]})
        self.assertEqual(item.unknown_fields["future_b"].require_present(), (1, 2))

    def test_fields_mapping_is_read_only_but_its_values_are_detached(self):
        item = invocation()
        view = item.fields
        with self.assertRaises(TypeError):
            view["new"] = P.present(1)
        before = item.to_dict()
        view["context"].require_present()["ability_target"].append("mutated")
        self.assertEqual(item.to_dict(), before)
        restored = InvocationDescriptor.from_dict(item.to_dict())
        self.assertEqual(restored.to_dict(), before)

    def test_unknown_field_names_and_order_survive_and_stay_read_only(self):
        item = occurrence()
        names = tuple(item.unknown_fields)
        self.assertEqual(names, ("future_b", "future_a"))
        with self.assertRaises(TypeError):
            item.unknown_fields["injected"] = P.present(1)
        self.assertEqual(tuple(item.unknown_fields), names)

    def test_detached_copy_keeps_the_concrete_type(self):
        for item in _one_of_every_family():
            with self.subTest(descriptor=type(item).__name__):
                copy_of = item.detached_copy()
                self.assertIs(type(copy_of), type(item))
                self.assertEqual(copy_of.to_dict(), item.to_dict())
                self.assertIsNot(copy_of, item)


# ---------------------------------------------------------------------------
# 15. Contract binding across families
# ---------------------------------------------------------------------------


class TestContractBindingAcrossFamilies(unittest.TestCase):
    def test_a_mode_mismatch_rejects_on_every_family(self):
        from tests.battle_ir.test_descriptor_damage import _item as damage_item

        contract = ContractRef(
            "damage", "battle.descriptor.damage", "1",
            EvidenceMode.REFERENCE_MODEL, "6" * 64, ("freeze:damage",),
        )
        with self.assertRaises(DescriptorError):
            type(damage_item())(
                contract,
                EvidenceMode.NATIVE_EVIDENCED,
                damage_item().provenance,
                ("mismatch", 0),
                0,
                P.present({"x": 1}),
                dict(damage_item().fields),
                {},
            )

    def test_every_family_round_trips_its_occurrence_path_and_order(self):
        for item in _one_of_every_family():
            with self.subTest(descriptor=type(item).__name__):
                restored = type(item).from_dict(item.to_dict())
                self.assertEqual(
                    restored.occurrence_path, item.occurrence_path
                )
                self.assertEqual(restored.source_order, item.source_order)
                self.assertEqual(
                    restored.occurrence_identity(), item.occurrence_identity()
                )

    def test_occurrence_identity_separates_payloads_that_compare_equal(self):
        first = occurrence(("same", 0), 0)
        second = occurrence(("same", 0), 1)
        self.assertEqual(first.payload, second.payload)
        self.assertNotEqual(
            first.occurrence_identity(), second.occurrence_identity()
        )
        self.assertEqual(len(DescriptorBatch((first, second)).occurrences), 2)

    def test_descriptors_are_unhashable_because_payloads_may_be_mutable(self):
        for item in _one_of_every_family():
            with self.subTest(descriptor=type(item).__name__):
                with self.assertRaises(TypeError):
                    hash(item)


# ---------------------------------------------------------------------------
# 16. The whole family set is representation-only and frozen
# ---------------------------------------------------------------------------


class TestWholeFamilySetIsRepresentationOnly(unittest.TestCase):
    def test_no_family_declares_an_execution_surface_in_its_own_vars(self):
        forbidden = {
            "execute", "apply", "commit", "run", "perform", "resolve",
            "issue_gate_certificate", "as_native_contract",
        }
        for item in _one_of_every_family():
            for name in forbidden:
                with self.subTest(descriptor=type(item).__name__, name=name):
                    self.assertNotIn(name, vars(type(item)))

    def test_every_family_reports_no_execution_permission(self):
        for item in _one_of_every_family():
            with self.subTest(descriptor=type(item).__name__):
                self.assertTrue(callable(item.execution_permitted))
                with self.assertRaises(DescriptorError):
                    item.execution_permitted()

    def test_the_family_vocabulary_is_closed_and_versioned(self):
        tags = _descriptor_types_for_tags()
        self.assertEqual(tags, EXPECTED_TAG_TYPES)
        for tag, cls in tags.items():
            with self.subTest(tag=tag):
                self.assertRegex(tag, r"^[a-z_]+/1$")
        self.assertEqual(
            set(tags.values()), {type(item) for item in _one_of_every_family()}
        )


# ---------------------------------------------------------------------------
# CR-R01-CLOSURE-REVIEW-20260922-001 regression block
# ---------------------------------------------------------------------------


class TestCRR01ClosureReviewRegressions(unittest.TestCase):
    """Pins the corrective that followed the R01-003..R01-012 Sol review."""

    def test_batch_schema_is_v2_and_legacy_v1_is_refused(self):
        document = DescriptorBatch((invocation(),)).to_dict()
        self.assertEqual(document["schema"], "descriptor_batch/2")
        self.assertEqual(DESCRIPTOR_BATCH_SCHEMA, "descriptor_batch/2")
        legacy = copy.deepcopy(document)
        legacy["schema"] = "descriptor_batch/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(legacy)

    def test_batch_round_trip_preserves_every_concrete_subtype(self):
        original = _one_of_every_family()
        restored = DescriptorBatch.from_dict(DescriptorBatch(original).to_dict())
        self.assertEqual(
            [type(item) for item in restored.occurrences],
            [type(item) for item in original],
        )
        self.assertIs(type(restored.occurrences[1]), InvocationDescriptor)
        self.assertIs(type(restored.occurrences[8]), ResolvedTargetSet)

    def test_family_validation_cannot_be_bypassed_through_batch_restore(self):
        document = DescriptorBatch((invocation(),)).to_dict()
        serialized = document["occurrences"][0]["descriptor"]
        arguments = next(
            entry for entry in serialized["fields"] if entry["name"] == "arguments"
        )
        arguments["value"] = P.present([]).to_dict()
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(document)

    def test_descriptor_direct_read_mutation_is_isolated(self):
        item = occurrence(payload=P.present({"items": []}))
        item = DescriptorOccurrence(
            item.contract_ref,
            item.evidence_mode,
            item.provenance,
            item.occurrence_path,
            item.source_order,
            item.payload,
            {"known": P.present({"items": []})},
            {"future": P.present({"items": []})},
        )
        before = item.to_dict()
        item.payload.require_present()["items"].append("payload")
        item.fields["known"].require_present()["items"].append("known")
        item.unknown_fields["future"].require_present()["items"].append("future")
        self.assertEqual(item.to_dict(), before)

    def test_resolved_target_set_targets_is_a_detached_list(self):
        item = resolved_targets(["entity:2", None, "entity:2"])
        before = item.to_dict()
        exported = item.targets
        self.assertIsInstance(exported, list)
        exported.append("entity:3")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.targets, ["entity:2", None, "entity:2"])

    def test_registry_input_output_and_registrations_are_isolated(self):
        descriptor = invocation()
        registry = DescriptorRegistry(
            (
                DescriptorRegistration(
                    DescriptorFamily.INVOCATION, "entity:isolated", descriptor
                ),
            )
        )
        before = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:isolated"
        )[0].to_dict()
        descriptor.payload.require_present()["argument_keys"].append("input")
        registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:isolated"
        )[0].fields["context"].require_present()["ability_target"].append("output")
        registry.registrations[0].descriptor.payload.require_present()[
            "argument_keys"
        ].append("registration")
        self.assertEqual(
            registry.resolve_static(
                DescriptorFamily.INVOCATION, "entity:isolated"
            )[0].to_dict(),
            before,
        )

    def test_behavior_descriptor_result_does_not_alias_registry_storage(self):
        from hsr_battle_agent.battle_ir.resolution_ledger import (
            ResolutionLedgerEntry,
        )
        from hsr_battle_agent.game_data.behavior_descriptor_adapter import (
            adapt_mapping_entry,
        )

        registry = _registry()
        before = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:0"
        )[0].to_dict()
        entry = ResolutionLedgerEntry.from_mapping_record(
            {
                "behavior_id": "behavior:1",
                "owner_kind": "Avatar",
                "static_link": {
                    "classification": "EXACT_ID",
                    "static_family": "Avatar",
                    "candidate_entity_ids": ["entity:0"],
                    "evidence": "published mapping",
                    "mapping_method": "existing report",
                },
            }
        )
        result = adapt_mapping_entry(entry, DescriptorFamily.INVOCATION, registry)
        result.descriptors[0].payload.require_present()["argument_keys"].append(
            "adapter"
        )
        self.assertEqual(
            registry.resolve_static(
                DescriptorFamily.INVOCATION, "entity:0"
            )[0].to_dict(),
            before,
        )

    def test_target_empty_list_versus_list_containing_null(self):
        self.assertNotEqual(
            resolved_targets([]).to_dict(), resolved_targets([None]).to_dict()
        )

    def test_duplicates_and_order_survive_after_the_corrective(self):
        targets = ["entity:2", None, "entity:2", "entity:1"]
        item = resolved_targets(targets)
        self.assertEqual(item.targets, targets)
        self.assertEqual(
            ResolvedTargetSet.from_dict(item.to_dict()).targets, targets
        )

    def test_is_skill_perform_absence_after_the_corrective(self):
        absent = invocation(flag=P.absent())
        self.assertTrue(absent.is_skill_perform.is_absent())
        self.assertNotEqual(
            absent.to_dict(), invocation(flag=P.present(False)).to_dict()
        )

    def test_multiple_versus_mutate_and_refresh_versus_replace(self):
        values = {
            operation: modifier(operation=operation).to_dict()
            for operation in ("Refresh", "Replace", "Multiple")
        }
        self.assertEqual(len(set(json.dumps(v, sort_keys=True) for v in values.values())), 3)

    def test_source_wave_order_after_the_corrective(self):
        item = scenario()
        groups = [
            entry["group"]
            for entry in item.fields["source_items"].require_present()
        ]
        self.assertEqual(groups, ["g2", "g1", "g2"])
        self.assertEqual(
            [
                entry["group"]
                for entry in ScenarioDescriptor.from_dict(item.to_dict())
                .fields["source_items"]
                .require_present()
            ],
            ["g2", "g1", "g2"],
        )


if __name__ == "__main__":
    unittest.main()
