# -*- coding: utf-8 -*-
"""F01-007 tests: StructuredRejection model.

Acceptance criteria: round trip, stable code independent of message, and
unknown-handle links preserved.  Also asserts the pre-existing sandbox error
classes are unchanged.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    ContractRef,
    EvidenceMode,
    UnknownHandle,
)
from hsr_battle_agent.battle_ir.provenance import SourceProvenance  # noqa: E402
from hsr_battle_agent.battle_sandbox.errors import (  # noqa: E402
    REJECTION_SCHEMA,
    BattleSandboxError,
    DuplicatePrimitiveError,
    FrozenRegistryError,
    InvalidPrimitiveInputError,
    RejectionDataError,
    StructuredRejection,
    StructuredRejectionError,
    StubNotImplementedError,
    UnsupportedPrimitiveError,
    UnsupportedStateVersionError,
)

SHA = "06e62fa808390ac4f58af4164bb4f8d3b5151b0cbd3ab76bf203d9e8c2010396"

PROVENANCE = SourceProvenance(
    game_version="4.4.54",
    runtime_type="RPG.GameCore.MonsterAI",
    method="Decide",
    method_index=None,
    native_rva="0xDEAD",
    evidence_level="E4_STATIC_MACHINE_CODE",
)


def contract_ref(**overrides):
    base = {
        "contract_id": "c-1",
        "namespace": "battle.ir.value",
        "schema_version": "battle_semantics_batch/1",
        "evidence_mode": EvidenceMode.NATIVE_EVIDENCED,
        "content_sha256": SHA,
        "source_refs": ("a.json",),
    }
    base.update(overrides)
    return ContractRef(**base)


def unknown_handle(**overrides):
    base = {
        "blocker_id": "D8-Q2",
        "owner_family": "MONSTER_AI",
        "payload": {"raw": [None, 0]},
        "provenance": PROVENANCE,
        "required_evidence": ("pinned observed transition",),
    }
    base.update(overrides)
    return UnknownHandle(**base)


def rejection(**overrides):
    base = {
        "reason_code": "UNKNOWN_WAVE_ADVANCE_PREDICATE",
        "obligation_owner": "MONSTER_AI",
        "evidence_request": "pinned observed wave advance transition",
        "contract_refs": (contract_ref(),),
        "unknown_handles": (unknown_handle(),),
        "diagnostics": {"detail": "no bound predicate", "count": 2},
    }
    base.update(overrides)
    return StructuredRejection(**base)


class TestRoundTrip(unittest.TestCase):
    def test_dict_round_trip(self):
        original = rejection()
        restored = StructuredRejection.from_dict(original.to_dict())
        self.assertEqual(restored, original)
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_json_round_trip(self):
        original = rejection()
        text = json.dumps(original.to_dict(), sort_keys=True)
        restored = StructuredRejection.from_dict(json.loads(text))
        self.assertEqual(restored, original)
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_empty_links_round_trip_as_present_and_empty(self):
        original = rejection(contract_refs=(), unknown_handles=())
        document = original.to_dict()
        self.assertEqual(document["contract_refs"], [])
        self.assertEqual(document["unknown_handles"], [])
        self.assertEqual(
            StructuredRejection.from_dict(document).to_dict(), document
        )

    def test_diagnostics_round_trip_exactly(self):
        diagnostics = {"z": None, "a": [1, None], "nested": {"b": False}}
        original = rejection(diagnostics=diagnostics)
        restored = StructuredRejection.from_dict(original.to_dict())
        self.assertEqual(restored.diagnostics, diagnostics)

    def test_diagnostics_are_excluded_from_equality(self):
        # Regression guard: diagnostics must never be part of the identity.
        first = rejection(diagnostics={"x": 1})
        second = rejection(diagnostics={"x": 2})
        third = rejection(diagnostics={})
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual(first.to_dict() == second.to_dict(), False)

    def test_serialization_does_not_alias_the_model(self):
        original = rejection(diagnostics={"raw": [1, 2]})
        returned = original.to_dict()
        returned["diagnostics"]["raw"].append(99)
        returned["reason_code"] = "MUTATED"
        self.assertEqual(original.diagnostics, {"raw": [1, 2]})
        self.assertEqual(original.reason_code, "UNKNOWN_WAVE_ADVANCE_PREDICATE")


class TestStableReasonIdentity(unittest.TestCase):
    def test_reason_identity_is_the_reason_code(self):
        # AUTHORITY_REQUIRED: message rewording cannot change the stable code.
        self.assertEqual(rejection().reason(), "UNKNOWN_WAVE_ADVANCE_PREDICATE")
        self.assertEqual(len(rejection().identity()), 64)

    def test_identity_is_independent_of_diagnostic_message_text(self):
        first = rejection(diagnostics={"detail": "short message"})
        second = rejection(
            diagnostics={"detail": "a completely different, longer message"}
        )
        self.assertEqual(first.identity(), second.identity())
        self.assertEqual(first, second)
        self.assertNotEqual(first.diagnostics, second.diagnostics)
        # The human-readable summary deliberately carries no diagnostic text.
        self.assertEqual(first.describe(), second.describe())

    def test_evidence_request_participates_in_object_identity(self):
        first = rejection(evidence_request="request A")
        second = rejection(evidence_request="a differently worded request")
        self.assertEqual(first.reason(), second.reason())
        self.assertNotEqual(first.identity(), second.identity())
        self.assertNotEqual(first, second)

    def test_different_reason_codes_have_different_identities(self):
        self.assertNotEqual(
            rejection().identity(),
            rejection(reason_code="UNKNOWN_SPAWN_SEMANTICS").identity(),
        )

    def test_contract_links_participate_in_identity(self):
        self.assertNotEqual(
            rejection().identity(), rejection(contract_refs=()).identity()
        )

    def test_unknown_links_participate_in_identity(self):
        self.assertNotEqual(
            rejection(unknown_handles=()).identity(), rejection().identity()
        )

    def test_obligation_owner_participates_in_identity(self):
        self.assertNotEqual(
            rejection().identity(),
            rejection(obligation_owner="TARGET").identity(),
        )

    def test_hash_matches_structural_equality(self):
        # API_DESIGN_LOCAL: diagnostics are human detail, all other structural
        # fields participate in equality, identity and hashing.
        first = rejection(diagnostics={"message": "one"})
        second = rejection(diagnostics={"message": "two"})
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        self.assertNotEqual(hash(first), hash(rejection(contract_refs=())))


class TestUnknownHandleLinksPreserved(unittest.TestCase):
    def test_unknown_handles_survive_round_trip(self):
        original = rejection(
            unknown_handles=(
                unknown_handle(),
                unknown_handle(blocker_id="D8-Q3", owner_family="TARGET"),
            )
        )
        restored = StructuredRejection.from_dict(original.to_dict())
        self.assertEqual(len(restored.unknown_handles), 2)
        self.assertEqual(
            [h.blocker_id for h in restored.unknown_handles], ["D8-Q2", "D8-Q3"]
        )
        self.assertEqual(
            [h.identity_hash() for h in restored.unknown_handles],
            [h.identity_hash() for h in original.unknown_handles],
        )

    def test_unknown_handle_payload_survives(self):
        original = rejection(
            unknown_handles=(unknown_handle(payload={"raw": [None, 0, {}]}),)
        )
        restored = StructuredRejection.from_dict(original.to_dict())
        self.assertEqual(
            restored.unknown_handles[0].payload, {"raw": [None, 0, {}]}
        )

    def test_contract_refs_survive_round_trip(self):
        original = rejection(
            contract_refs=(
                contract_ref(),
                contract_ref(
                    contract_id="c-2", evidence_mode=EvidenceMode.REFERENCE_MODEL
                ),
            )
        )
        restored = StructuredRejection.from_dict(original.to_dict())
        self.assertEqual(len(restored.contract_refs), 2)
        self.assertIs(
            restored.contract_refs[0].evidence_mode, EvidenceMode.NATIVE_EVIDENCED
        )
        self.assertIs(
            restored.contract_refs[1].evidence_mode, EvidenceMode.REFERENCE_MODEL
        )
        self.assertEqual(
            [ref.identity() for ref in restored.contract_refs],
            [ref.identity() for ref in original.contract_refs],
        )

    def test_links_must_be_typed(self):
        with self.assertRaises(RejectionDataError):
            rejection(contract_refs=(unknown_handle(),))
        with self.assertRaises(RejectionDataError):
            rejection(unknown_handles=(contract_ref(),))
        with self.assertRaises(RejectionDataError):
            rejection(contract_refs=("c-1",))

    def test_malformed_linked_documents_are_rejected(self):
        document = rejection().to_dict()
        broken = {**document, "unknown_handles": [{"schema": "unknown_handle/2"}]}
        with self.assertRaises(RejectionDataError):
            StructuredRejection.from_dict(broken)


class TestNoSuccessOrFallback(unittest.TestCase):
    def test_resolve_refuses(self):
        with self.assertRaises(RejectionDataError):
            rejection().resolve()

    def test_no_value_or_default_helpers(self):
        for name in (
            "value",
            "default",
            "fallback",
            "or_else",
            "value_or",
            "as_bool",
            "is_success",
            "ok",
            "unwrap",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(StructuredRejection, name))
                self.assertFalse(hasattr(rejection(), name))

    def test_no_truthiness(self):
        with self.assertRaises(RejectionDataError):
            bool(rejection())

    def test_rejection_is_not_an_exception_subclass(self):
        self.assertFalse(issubclass(StructuredRejection, BaseException))
        self.assertNotIsInstance(rejection(), BaseException)


class TestExceptionAdapter(unittest.TestCase):
    def test_exception_carries_the_structured_data(self):
        data = rejection()
        error = data.to_exception()
        self.assertIsInstance(error, StructuredRejectionError)
        self.assertIsInstance(error, BattleSandboxError)
        self.assertIs(error.rejection, data)
        self.assertEqual(error.reason_code, data.reason_code)

    def test_exception_message_is_not_the_identity(self):
        first = rejection(diagnostics={"d": "one"}).to_exception()
        second = rejection(diagnostics={"d": "two"}).to_exception()
        self.assertEqual(first.reason_code, second.reason_code)
        self.assertEqual(first.rejection.identity(), second.rejection.identity())

    def test_exception_adapter_requires_structured_data(self):
        with self.assertRaises(RejectionDataError):
            StructuredRejectionError("just a string")

    def test_exception_can_be_raised_and_caught(self):
        with self.assertRaises(StructuredRejectionError) as caught:
            raise rejection().to_exception()
        self.assertEqual(
            caught.exception.rejection.reason_code,
            "UNKNOWN_WAVE_ADVANCE_PREDICATE",
        )

    def test_existing_error_classes_are_unchanged(self):
        self.assertTrue(issubclass(UnsupportedPrimitiveError, BattleSandboxError))
        self.assertTrue(issubclass(DuplicatePrimitiveError, BattleSandboxError))
        self.assertTrue(issubclass(FrozenRegistryError, BattleSandboxError))
        self.assertTrue(
            issubclass(UnsupportedStateVersionError, BattleSandboxError)
        )
        self.assertTrue(
            issubclass(InvalidPrimitiveInputError, BattleSandboxError)
        )
        self.assertTrue(issubclass(StubNotImplementedError, BattleSandboxError))
        self.assertIn("unsupported battle IR primitive", str(
            UnsupportedPrimitiveError("p")
        ))
        self.assertEqual(
            DuplicatePrimitiveError("p").primitive_id, "p"
        )
        self.assertEqual(UnsupportedStateVersionError(9).schema_version, 9)
        self.assertEqual(str(FrozenRegistryError()), "primitive registry is frozen")

    def test_errors_module_still_exports_the_legacy_names(self):
        import hsr_battle_agent.battle_sandbox.errors as errors

        for name in (
            "BattleSandboxError",
            "UnsupportedPrimitiveError",
            "InvalidPrimitiveInputError",
            "DuplicatePrimitiveError",
            "FrozenRegistryError",
            "UnsupportedStateVersionError",
            "StubNotImplementedError",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(errors, name))


class TestValidation(unittest.TestCase):
    def test_reason_codes_must_be_uppercase_machine_codes(self):
        for value in ("lower", "Mixed", " with_space", "with_space ", "", None, 1):
            with self.subTest(value=repr(value)):
                with self.assertRaises(RejectionDataError):
                    rejection(reason_code=value)

    def test_obligation_owner_must_be_a_machine_code(self):
        for value in ("lower", "", None, [1]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(RejectionDataError):
                    rejection(obligation_owner=value)

    def test_evidence_request_must_be_non_empty(self):
        for value in ("", None, 1, []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(RejectionDataError):
                    rejection(evidence_request=value)

    def test_diagnostics_must_be_a_mapping(self):
        for value in ([], "x", 1, None):
            with self.subTest(value=repr(value)):
                with self.assertRaises(RejectionDataError):
                    rejection(diagnostics=value)

    def test_diagnostics_are_deep_copied_and_keys_are_not_coerced(self):
        diagnostics = {"nested": [1]}
        original = rejection(diagnostics=diagnostics)
        diagnostics["nested"].append(2)
        self.assertEqual(original.diagnostics, {"nested": [1]})
        with self.assertRaises(RejectionDataError):
            rejection(diagnostics={1: "detail"})

    def test_malformed_documents_are_rejected(self):
        for document in (
            None,
            [],
            "x",
            1,
            {"schema": "structured_rejection/2", "reason_code": "X",
             "obligation_owner": "Y", "evidence_request": "z"},
            {"reason_code": "X", "obligation_owner": "Y"},
            {"obligation_owner": "Y", "evidence_request": "z"},
            {"reason_code": "X", "evidence_request": "z"},
            {"reason_code": "X", "obligation_owner": "Y",
             "evidence_request": "z", "contract_refs": "not-a-list"},
            {"reason_code": "X", "obligation_owner": "Y",
             "evidence_request": "z", "unknown_handles": 5},
        ):
            with self.subTest(document=repr(document)):
                with self.assertRaises(RejectionDataError):
                    StructuredRejection.from_dict(document)

    def test_schema_constant(self):
        self.assertEqual(REJECTION_SCHEMA, "structured_rejection/1")
        self.assertEqual(
            rejection().to_dict()["schema"], REJECTION_SCHEMA
        )


if __name__ == "__main__":
    unittest.main()
