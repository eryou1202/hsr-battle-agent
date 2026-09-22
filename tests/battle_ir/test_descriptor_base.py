# -*- coding: utf-8 -*-
"""R01-002 acceptance tests for representation-only descriptors."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptors.base import (  # noqa: E402
    DESCRIPTOR_BATCH_SCHEMA,
    DESCRIPTOR_OCCURRENCE_SCHEMA,
    DescriptorBatch,
    DescriptorError,
    DescriptorOccurrence,
)
from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    ContractRef,
    EvidenceMode,
)
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue  # noqa: E402
from hsr_battle_agent.battle_ir.provenance import SourceProvenance  # noqa: E402
from hsr_battle_agent.battle_sandbox.evidence_boundary import (  # noqa: E402
    EvidenceBoundaryError,
    require_native_contract,
)
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


def contract(mode: EvidenceMode = EvidenceMode.REFERENCE_MODEL) -> ContractRef:
    return ContractRef(
        contract_id="modifier-descriptor",
        namespace="battle.descriptor.test",
        schema_version="descriptor-source/1",
        evidence_mode=mode,
        content_sha256="a" * 64,
        source_refs=("fixture:descriptor",),
    )


def provenance() -> SourceProvenance:
    return SourceProvenance(
        game_version="4.4.54",
        runtime_type="TestDescriptor",
        method="Read",
        method_index=None,
        native_rva="UNKNOWN",
        evidence_level="REFERENCE_MODEL",
        unknown_fields={"source_extra": {"tuple": (1, 2)}},
    )


def occurrence(
    path=("modifiers", 0),
    order=0,
    payload=None,
    mode=EvidenceMode.REFERENCE_MODEL,
) -> DescriptorOccurrence:
    return DescriptorOccurrence(
        contract_ref=contract(mode),
        evidence_mode=mode,
        provenance=provenance(),
        occurrence_path=path,
        source_order=order,
        payload=(
            PresenceValue.present({"same": [1, None]})
            if payload is None
            else payload
        ),
        fields={
            "enabled": PresenceValue.present(False),
            "explicit_null": PresenceValue.null(),
        },
        unknown_fields={
            "future_b": PresenceValue.present((1, 2)),
            "future_a": PresenceValue.absent(),
        },
    )


class TestDescriptorBinding(unittest.TestCase):
    def test_binds_contract_mode_provenance_path_and_order(self):
        item = occurrence()
        self.assertIs(item.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIs(item.evidence_mode, item.contract_ref.evidence_mode)
        self.assertEqual(item.occurrence_path, ("modifiers", 0))
        self.assertEqual(item.source_order, 0)
        self.assertEqual(item.provenance.runtime_type, "TestDescriptor")

    def test_mode_mismatch_rejects(self):
        with self.assertRaises(DescriptorError):
            DescriptorOccurrence(
                contract_ref=contract(EvidenceMode.REFERENCE_MODEL),
                evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
                provenance=provenance(),
                occurrence_path=("x", 0),
                source_order=0,
            )

    def test_path_and_order_validation_fails_closed(self):
        for path in ((), "x", (True,), (-1,), ("",)):
            with self.subTest(path=path):
                with self.assertRaises(DescriptorError):
                    occurrence(path=path)
        for order in (-1, True, 1.0):
            with self.subTest(order=order):
                with self.assertRaises(DescriptorError):
                    occurrence(order=order)


class TestRepeatAndOrder(unittest.TestCase):
    def test_identical_payloads_at_different_occurrences_remain_distinct(self):
        first = occurrence(("modifiers", 0), 4)
        second = occurrence(("modifiers", 1), 5)
        self.assertEqual(first.payload, second.payload)
        self.assertNotEqual(first.occurrence_identity(), second.occurrence_identity())
        batch = DescriptorBatch((second, first))
        self.assertEqual(
            [item.occurrence_path for item in batch.occurrences],
            [("modifiers", 1), ("modifiers", 0)],
        )
        restored = DescriptorBatch.from_dict(batch.to_dict())
        self.assertEqual(restored, batch)
        self.assertEqual(restored.to_dict(), batch.to_dict())

    def test_batch_does_not_sort_by_source_order_or_path(self):
        batch = DescriptorBatch(
            (occurrence(("z",), 9), occurrence(("a",), 1))
        )
        self.assertEqual(
            [item.source_order for item in batch.occurrences], [9, 1]
        )

    def test_duplicate_occurrence_identity_rejects(self):
        with self.assertRaises(DescriptorError):
            DescriptorBatch((occurrence(), occurrence()))


class TestLosslessRoundTrip(unittest.TestCase):
    def test_occurrence_round_trip_is_stable(self):
        item = occurrence()
        payload = item.to_dict()
        restored = DescriptorOccurrence.from_dict(payload)
        self.assertEqual(restored, item)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(payload["schema"], DESCRIPTOR_OCCURRENCE_SCHEMA)
        with self.assertRaises(TypeError):
            hash(restored)

    def test_unknown_field_order_presence_and_tuple_are_preserved(self):
        restored = DescriptorOccurrence.from_dict(occurrence().to_dict())
        self.assertEqual(
            tuple(restored.unknown_fields), ("future_b", "future_a")
        )
        self.assertEqual(
            restored.unknown_fields["future_b"].require_present(), (1, 2)
        )
        self.assertTrue(restored.unknown_fields["future_a"].is_absent())
        self.assertTrue(restored.fields["explicit_null"].is_null())
        self.assertEqual(
            restored.provenance.unknown_fields["source_extra"]["tuple"],
            (1, 2),
        )

    def test_returned_document_has_no_mutable_alias(self):
        item = occurrence()
        document = item.to_dict()
        document["payload"]["value"]["same"].append("mutated")
        document["unknown_fields"][0]["value"]["value"] = ["changed"]
        self.assertEqual(item.payload.require_present(), {"same": [1, None]})
        self.assertEqual(
            item.unknown_fields["future_b"].require_present(), (1, 2)
        )

    def test_missing_extra_and_unknown_schema_reject(self):
        document = occurrence().to_dict()
        for key in ("payload", "occurrence_path", "unknown_fields"):
            with self.subTest(key=key):
                broken = copy.deepcopy(document)
                broken.pop(key)
                with self.assertRaises(DescriptorError):
                    DescriptorOccurrence.from_dict(broken)
        broken = copy.deepcopy(document)
        broken["extra"] = None
        with self.assertRaises(DescriptorError):
            DescriptorOccurrence.from_dict(broken)
        broken = copy.deepcopy(document)
        broken["schema"] = "descriptor_occurrence/2"
        with self.assertRaises(DescriptorError):
            DescriptorOccurrence.from_dict(broken)

    def test_batch_schema_is_explicit(self):
        payload = DescriptorBatch((occurrence(),)).to_dict()
        self.assertEqual(payload["schema"], DESCRIPTOR_BATCH_SCHEMA)

    def test_batch_round_trip_preserves_every_concrete_descriptor_type(self):
        original = (
            invocation(), modifier(), formation(), scheduler(), monster_ai(),
            damage(), target_intent(), resolved_targets(["entity:1", None]),
            retarget(), progression(), scenario(),
        )
        restored = DescriptorBatch.from_dict(DescriptorBatch(original).to_dict())
        self.assertEqual(
            [type(item) for item in restored.occurrences],
            [type(item) for item in original],
        )
        self.assertEqual(restored.to_dict(), DescriptorBatch(original).to_dict())

    def test_batch_discriminator_is_required_known_and_type_checked(self):
        document = DescriptorBatch((invocation(),)).to_dict()
        old_schema = copy.deepcopy(document)
        old_schema["schema"] = "descriptor_batch/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(old_schema)
        missing = copy.deepcopy(document)
        missing["occurrences"][0].pop("descriptor_type")
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(missing)
        unknown = copy.deepcopy(document)
        unknown["occurrences"][0]["descriptor_type"] = "future_descriptor/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(unknown)
        mismatch = copy.deepcopy(document)
        mismatch["occurrences"][0]["descriptor_type"] = "modifier/1"
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(mismatch)

    def test_family_validation_cannot_be_bypassed_through_batch_restore(self):
        document = DescriptorBatch((invocation(),)).to_dict()
        serialized = document["occurrences"][0]["descriptor"]
        arguments = next(
            item for item in serialized["fields"] if item["name"] == "arguments"
        )
        arguments["value"] = PresenceValue.present([]).to_dict()
        with self.assertRaises(DescriptorError):
            DescriptorBatch.from_dict(document)

    def test_public_presence_values_are_detached_from_descriptor_storage(self):
        item = occurrence(
            payload=PresenceValue.present({"items": []})
        )
        item = DescriptorOccurrence(
            item.contract_ref,
            item.evidence_mode,
            item.provenance,
            item.occurrence_path,
            item.source_order,
            item.payload,
            {"known": PresenceValue.present({"items": []})},
            {"future": PresenceValue.present({"items": []})},
        )
        before = item.to_dict()
        item.payload.require_present()["items"].append("payload")
        item.fields["known"].require_present()["items"].append("known")
        item.unknown_fields["future"].require_present()["items"].append("future")
        self.assertEqual(item.to_dict(), before)


class TestRepresentationOnly(unittest.TestCase):
    def test_descriptor_cannot_satisfy_native_gate(self):
        item = occurrence(mode=EvidenceMode.NATIVE_EVIDENCED)
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(item, role="descriptor")
        with self.assertRaises(DescriptorError):
            item.execution_permitted()

    def test_descriptor_exposes_no_gate_or_runtime_action(self):
        for name in (
            "execute", "apply", "issue_gate_certificate", "as_native_contract",
            "gate_certificate", "native_contract",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(DescriptorOccurrence, name))


if __name__ == "__main__":
    unittest.main()
