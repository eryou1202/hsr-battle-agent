# -*- coding: utf-8 -*-
"""F01-003 tests: ContractRef identity and provenance envelope.

Acceptance criteria: round trip, unknown schema rejected, mode mismatch
detected.  Also re-asserts the F01-001 canonical EvidenceMode invariants, since
this task extends the same module.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    CONTRACT_REF_SCHEMA,
    REQUIRED_CONTRACT_REF_FIELDS,
    ContractRef,
    EvidenceMode,
    EvidenceVocabularyError,
    parse_evidence_mode,
)

SHA = "06e62fa808390ac4f58af4164bb4f8d3b5151b0cbd3ab76bf203d9e8c2010396"
OTHER_SHA = "1" * 64


def contract(**overrides):
    base = {
        "contract_id": "battle.ir.value.dynamic_value_equals",
        "namespace": "battle.ir.value",
        "schema_version": "battle_semantics_batch/1",
        "evidence_mode": EvidenceMode.NATIVE_EVIDENCED,
        "content_sha256": SHA,
        "source_refs": ("vertical_slice_01.json",),
    }
    base.update(overrides)
    return ContractRef(**base)


class TestContractRefRoundTrip(unittest.TestCase):
    def test_dict_round_trip(self):
        original = contract()
        restored = ContractRef.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())
        self.assertEqual(restored, original)

    def test_json_round_trip(self):
        original = contract()
        text = json.dumps(original.to_dict(), sort_keys=True)
        restored = ContractRef.from_dict(json.loads(text))
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_round_trip_preserves_the_canonical_mode_object(self):
        original = contract(evidence_mode="REFERENCE_MODEL")
        restored = ContractRef.from_dict(original.to_dict())
        self.assertIs(restored.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIs(restored.evidence_mode, original.evidence_mode)

    def test_source_refs_are_a_tuple_and_order_is_preserved(self):
        original = contract(source_refs=("b", "a", "c"))
        self.assertIsInstance(original.source_refs, tuple)
        restored = ContractRef.from_dict(original.to_dict())
        self.assertEqual(restored.source_refs, ("b", "a", "c"))
        self.assertIsInstance(restored.source_refs, tuple)

    def test_empty_source_refs_stay_empty_not_missing(self):
        original = contract(source_refs=())
        self.assertEqual(original.source_refs, ())
        restored = ContractRef.from_dict(original.to_dict())
        self.assertEqual(restored.source_refs, ())
        self.assertIn("source_refs", restored.to_dict())

    def test_identity_is_stable_and_distinguishes_namespace(self):
        first = contract()
        second = contract(namespace="battle.ir.other")
        self.assertEqual(
            first.identity(),
            f"battle.ir.value:battle.ir.value.dynamic_value_equals"
            f"@battle_semantics_batch/1#{SHA}",
        )
        self.assertNotEqual(first.identity(), second.identity())


class TestRequiredFields(unittest.TestCase):
    def test_missing_each_required_field_is_rejected(self):
        for name in REQUIRED_CONTRACT_REF_FIELDS:
            with self.subTest(field=name):
                document = contract().to_dict()
                del document[name]
                with self.assertRaises(EvidenceVocabularyError):
                    ContractRef.from_dict(document)

    def test_empty_required_values_are_rejected(self):
        for name in ("contract_id", "namespace", "schema_version"):
            with self.subTest(field=name):
                with self.assertRaises(EvidenceVocabularyError):
                    contract(**{name: ""})
        with self.assertRaises(EvidenceVocabularyError):
            contract(content_sha256="")

    def test_malformed_hashes_are_rejected(self):
        for value in (SHA[:32], SHA.upper(), SHA + "0", "z" * 64, None, 12):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    contract(content_sha256=value)
        for value in (None, 1, True, []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    contract(contract_id=value)

    def test_unknown_schema_is_rejected(self):
        for schema in (
            "contract_ref/2",
            "CONTRACT_REF/1",
            "contract_ref",
            "",
            None,
            1,
        ):
            with self.subTest(schema=repr(schema)):
                document = {**contract().to_dict(), "schema": schema}
                with self.assertRaises(EvidenceVocabularyError):
                    ContractRef.from_dict(document)

    def test_non_mapping_document_is_rejected(self):
        for value in (None, [], "x", 1, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    ContractRef.from_dict(value)

    def test_source_refs_must_be_a_sequence_of_strings(self):
        for value in ("single", 1, None, {"a": 1}, ("ok", ""), ("ok", 1)):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    contract(source_refs=value)
        for value in ("single", 1, None):
            with self.subTest(document=repr(value)):
                document = {**contract().to_dict(), "source_refs": value}
                with self.assertRaises(EvidenceVocabularyError):
                    ContractRef.from_dict(document)


class TestModeMismatchDetection(unittest.TestCase):
    def test_matches_mode_is_exact(self):
        native = contract(evidence_mode="NATIVE_EVIDENCED")
        self.assertTrue(native.matches_mode(EvidenceMode.NATIVE_EVIDENCED))
        self.assertTrue(native.matches_mode("NATIVE_EVIDENCED"))
        self.assertFalse(native.matches_mode(EvidenceMode.REFERENCE_MODEL))
        self.assertFalse(native.matches_mode("REFERENCE_MODEL"))
        self.assertFalse(native.matches_mode("SANDBOX_EXTENSION"))
        self.assertFalse(native.matches_mode("UNSUPPORTED"))

    def test_require_mode_accepts_an_exact_match(self):
        native = contract(evidence_mode="NATIVE_EVIDENCED")
        self.assertIs(native.require_mode("NATIVE_EVIDENCED"), native)

    def test_require_mode_detects_every_mismatch(self):
        for actual in EvidenceMode:
            for expected in EvidenceMode:
                if actual is expected:
                    continue
                with self.subTest(actual=actual.value, expected=expected.value):
                    with self.assertRaises(EvidenceVocabularyError):
                        contract(evidence_mode=actual).require_mode(expected)

    def test_require_mode_rejects_unknown_expectations(self):
        for expected in ("NATIVE", "", None, True, "EXECUTABLE_REFERENCE"):
            with self.subTest(expected=repr(expected)):
                with self.assertRaises(EvidenceVocabularyError):
                    contract().require_mode(expected)

    def test_reference_evidenced_contract_cannot_satisfy_a_native_expectation(self):
        reference = contract(evidence_mode="REFERENCE_MODEL")
        with self.assertRaises(EvidenceVocabularyError):
            reference.require_mode("NATIVE_EVIDENCED")

    def test_mode_is_canonicalized_from_a_spelling(self):
        reference = contract(evidence_mode="REFERENCE_MODEL")
        self.assertIs(reference.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIs(
            reference.evidence_mode, parse_evidence_mode("REFERENCE_MODEL")
        )

    def test_unknown_mode_is_rejected(self):
        for value in ("NATIVE", "", None, True, "EXECUTABLE_REFERENCE"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    contract(evidence_mode=value)


class TestContractRefIsNotExecutable(unittest.TestCase):
    def test_no_executability_helpers(self):
        for name in (
            "executable",
            "is_executable",
            "can_execute",
            "implies_execution",
            "as_bool",
            "permission",
            "allowed",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ContractRef, name))
                self.assertFalse(hasattr(contract(), name))

    def test_evidence_mode_truthiness_is_not_permission(self):
        # API_DESIGN_LOCAL: plain Enum truthiness stays ordinary; the absence
        # of a gate/executability API is the enforced invariant.
        self.assertTrue(bool(contract().evidence_mode))
        self.assertFalse(hasattr(contract(), "executable"))

    def test_contract_ref_does_not_expose_a_native_gate_api(self):
        self.assertFalse(hasattr(ContractRef, "issue_gate_certificate"))
        self.assertFalse(hasattr(ContractRef, "is_native_evidenced"))

    def test_native_evidence_mode_is_not_a_permission(self):
        # The ref records provenance only; nothing about it grants execution.
        native = contract(evidence_mode="NATIVE_EVIDENCED")
        self.assertIs(native.evidence_mode, EvidenceMode.NATIVE_EVIDENCED)
        self.assertFalse(hasattr(native, "executable"))


class TestF01_001InvariantsPreserved(unittest.TestCase):
    def test_evidence_mode_vocabulary_is_unchanged(self):
        self.assertEqual(
            EvidenceMode.spellings(),
            (
                "NATIVE_EVIDENCED",
                "REFERENCE_MODEL",
                "SANDBOX_EXTENSION",
                "UNSUPPORTED",
            ),
        )

    def test_contract_ref_schema_constant(self):
        self.assertEqual(CONTRACT_REF_SCHEMA, "contract_ref/1")
        self.assertEqual(contract().to_dict()["schema"], CONTRACT_REF_SCHEMA)

    def test_evidence_mode_identity_is_still_canonical(self):
        from hsr_battle_agent.battle_sandbox import evidence_boundary as eb

        self.assertIs(eb.EvidenceMode, EvidenceMode)
        self.assertIs(ContractRef.__dataclass_fields__["evidence_mode"].type,
                      "EvidenceMode")


if __name__ == "__main__":
    unittest.main()
