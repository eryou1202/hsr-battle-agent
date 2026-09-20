# -*- coding: utf-8 -*-
"""F01-008: combined serialization invariants across the whole F01 surface.

This module is test and invariant integration only.  It constructs a
cross-product fixture that nests every F01 representation inside the others and
proves the invariants that no single task could prove alone:

* no absence or key-default loss;
* no tuple-to-list coercion;
* no numeric normalization;
* no enum identity split;
* no shared mutable alias after serialization;
* expected dictionaries written independently of the builders.

Tuples are asserted through ``to_dict``/``from_dict`` only.  A JSON transport
converts tuples to arrays by definition, so tuple fidelity is an in-process
envelope property, not a JSON one.
"""
from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    ContractRef,
    EvidenceMode,
    UnknownHandle,
)
from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    LosslessNumber,
    NumericCategory,
    PresenceState,
    PresenceValue,
)
from hsr_battle_agent.battle_ir.provenance import (  # noqa: E402
    PROVENANCE_NOTE_DEFAULT,
    SOURCE_PROVENANCE_SCHEMA_V2,
    SourceProvenance,
)
from hsr_battle_agent.battle_sandbox.errors import (  # noqa: E402
    StructuredRejection,
)

SHA = "06e62fa808390ac4f58af4164bb4f8d3b5151b0cbd3ab76bf203d9e8c2010396"
COMMIT = "b11066beacc4de454b625fafc7ea3dd540c5bbf3"

#: Values used across the matrix, chosen to catch every collapse the F01 tasks
#: were created to prevent.
FALSEY_OR_TUPLE_PAYLOADS = (
    False,
    0,
    "",
    [],
    [None],
    {},
    (),
    (1, 2),
    ("a", None, 0),
    [0, False, "", [], {}, None],
    {"t": (1, 2), "l": [None]},
)


def build_provenance() -> SourceProvenance:
    return SourceProvenance(
        game_version="4.4.54",
        runtime_type="RPG.GameCore.MonsterAI",
        method="Decide",
        method_index=None,
        native_rva="0xDEAD",
        evidence_level="E4_STATIC_MACHINE_CODE",
        note=PROVENANCE_NOTE_DEFAULT,
        schema_version=SOURCE_PROVENANCE_SCHEMA_V2,
        source_commit=COMMIT,
        version_relation="CLOSE_VERSION",
        content_sha256=SHA,
        profile="f01-roundtrip",
    )


def build_contract_ref() -> ContractRef:
    return ContractRef(
        contract_id="battle.ir.value.dynamic_value_equals",
        namespace="battle.ir.value",
        schema_version="battle_semantics_batch/1",
        evidence_mode=EvidenceMode.REFERENCE_MODEL,
        content_sha256=SHA,
        source_refs=("vertical_slice_01.json", "turn_av_semantics_29.json"),
    )


def build_unknown_handle(payload) -> UnknownHandle:
    return UnknownHandle(
        blocker_id="D8-Q2",
        owner_family="MONSTER_AI",
        payload=payload,
        provenance=build_provenance(),
        required_evidence=("pinned observed transition",),
    )


def build_rejection() -> StructuredRejection:
    # The cross-product fixture: a rejection whose links carry presence values,
    # lossless numbers and tuples in their opaque payloads.
    payload = {
        "absent": PresenceValue.absent().to_dict(),
        "null": PresenceValue.null().to_dict(),
        "false": PresenceValue.present(False).to_dict(),
        "zero": PresenceValue.present(0).to_dict(),
        "empty_list": PresenceValue.present([]).to_dict(),
        "list_with_null": PresenceValue.present([None]).to_dict(),
        "empty_mapping": PresenceValue.present({}).to_dict(),
        "big_identifier": LosslessNumber.from_lexeme(
            "9007199254740993"
        ).to_dict(),
        "decimal_lexeme": LosslessNumber.from_lexeme("0.10").to_dict(),
        "float_value": LosslessNumber.from_float(0.5).to_dict(),
        "tuple_inside_payload": (1, 2),
        "nested": {"deep": [None, 0, False, "", [], {}]},
    }
    return StructuredRejection(
        reason_code="UNKNOWN_WAVE_ADVANCE_PREDICATE",
        obligation_owner="MONSTER_AI",
        evidence_request="pinned observed wave advance transition",
        contract_refs=(build_contract_ref(),),
        unknown_handles=(build_unknown_handle(payload),),
        diagnostics={"note": "human text; never part of identity"},
    )


class TestFullRoundTripMatrix(unittest.TestCase):
    def test_provenance_v2_round_trips_exactly(self):
        original = build_provenance()
        document = original.to_dict()
        restored = SourceProvenance.from_dict(document)
        self.assertEqual(restored.to_dict(), document)
        self.assertEqual(
            restored.effective_schema_version(), SOURCE_PROVENANCE_SCHEMA_V2
        )
        self.assertIs(
            restored.version_relation.__class__,
            original.version_relation.__class__,
        )

    def test_contract_ref_round_trips_exactly(self):
        original = build_contract_ref()
        document = original.to_dict()
        restored = ContractRef.from_dict(document)
        self.assertEqual(restored.to_dict(), document)
        self.assertIs(restored.evidence_mode, original.evidence_mode)

    def test_unknown_handle_round_trips_exactly(self):
        for payload in FALSEY_OR_TUPLE_PAYLOADS:
            with self.subTest(payload=repr(payload)):
                original = build_unknown_handle(payload)
                document = original.to_dict()
                restored = UnknownHandle.from_dict(document)
                self.assertEqual(restored.to_dict(), document)
                self.assertEqual(restored.payload, payload)
                self.assertEqual(
                    restored.identity_hash(), original.identity_hash()
                )

    def test_rejection_round_trips_exactly(self):
        original = build_rejection()
        document = original.to_dict()
        restored = StructuredRejection.from_dict(document)
        self.assertEqual(restored.to_dict(), document)
        self.assertEqual(restored, original)

    def test_json_round_trip_of_the_whole_fixture(self):
        document = build_rejection().to_dict()
        # A JSON transport turns tuples into arrays, so compare against the
        # JSON-normalized expectation rather than the tuple-bearing original.
        normalized = json.loads(json.dumps(document, sort_keys=True))
        text = json.dumps(document, sort_keys=True)
        restored = StructuredRejection.from_dict(json.loads(text))
        self.assertEqual(restored.to_dict(), normalized)

    def test_expected_document_is_written_independently(self):
        # The expected dictionary is written by hand, not by calling the
        # builders, so a builder and its reader cannot agree on a shared bug.
        expected_ref = {
            "schema": "contract_ref/1",
            "contract_id": "battle.ir.value.dynamic_value_equals",
            "namespace": "battle.ir.value",
            "schema_version": "battle_semantics_batch/1",
            "evidence_mode": "REFERENCE_MODEL",
            "content_sha256": SHA,
            "source_refs": [
                "vertical_slice_01.json",
                "turn_av_semantics_29.json",
            ],
        }
        self.assertEqual(build_contract_ref().to_dict(), expected_ref)

        expected_presence = {
            "absent": {"schema": "presence_value/1", "presence": "ABSENT"},
            "null": {"schema": "presence_value/1", "presence": "NULL"},
            "false": {
                "schema": "presence_value/1",
                "presence": "PRESENT",
                "value": False,
            },
            "zero": {
                "schema": "presence_value/1",
                "presence": "PRESENT",
                "value": 0,
            },
            "empty_list": {
                "schema": "presence_value/1",
                "presence": "PRESENT",
                "value": [],
            },
            "list_with_null": {
                "schema": "presence_value/1",
                "presence": "PRESENT",
                "value": [None],
            },
            "empty_mapping": {
                "schema": "presence_value/1",
                "presence": "PRESENT",
                "value": {},
            },
        }
        actual = {
            "absent": PresenceValue.absent().to_dict(),
            "null": PresenceValue.null().to_dict(),
            "false": PresenceValue.present(False).to_dict(),
            "zero": PresenceValue.present(0).to_dict(),
            "empty_list": PresenceValue.present([]).to_dict(),
            "list_with_null": PresenceValue.present([None]).to_dict(),
            "empty_mapping": PresenceValue.present({}).to_dict(),
        }
        self.assertEqual(actual, expected_presence)

    def test_expected_number_documents_are_independent(self):
        self.assertEqual(
            LosslessNumber.from_lexeme("9007199254740993").to_dict(),
            {
                "schema": "lossless_number/1",
                "category": "INTEGER",
                "lexeme": "9007199254740993",
            },
        )
        self.assertEqual(
            LosslessNumber.from_lexeme("0.10").to_dict(),
            {
                "schema": "lossless_number/1",
                "category": "DECIMAL",
                "lexeme": "0.10",
            },
        )


class TestNoAbsenceOrDefaultLoss(unittest.TestCase):
    def test_absent_keys_stay_absent_through_the_stack(self):
        document = {**build_provenance().to_dict()}
        del document["source_commit"]
        del document["profile"]
        restored = SourceProvenance.from_dict(document)
        serialized = restored.to_dict()
        self.assertEqual(set(serialized), set(document))
        self.assertNotIn("source_commit", serialized)
        self.assertNotIn("profile", serialized)
        self.assertIn("source_commit", restored.absent_field_names())

    def test_present_null_is_not_absence(self):
        without = build_provenance().to_dict()
        without.pop("source_commit")
        with_null = {**build_provenance().to_dict(), "source_commit": None}
        self.assertNotEqual(
            SourceProvenance.from_dict(without).to_dict(),
            SourceProvenance.from_dict(with_null).to_dict(),
        )

    def test_absent_and_null_presence_are_different_states(self):
        self.assertNotEqual(
            PresenceValue.absent().to_dict(), PresenceValue.null().to_dict()
        )
        self.assertNotEqual(PresenceValue.absent(), PresenceValue.null())

    def test_no_presence_encoding_is_lost_in_a_key_set(self):
        source = {"a": None, "b": 0, "c": [], "d": [None], "e": {}, "f": "", "g": False}
        decoded = PresenceValue.matrix(list(source) + ["missing"], source)
        self.assertEqual(len(decoded), len(source) + 1)
        self.assertTrue(decoded["missing"].is_absent())
        self.assertTrue(decoded["a"].is_null())
        for key in ("b", "c", "d", "e", "f", "g"):
            self.assertTrue(decoded[key].is_present())
        # Re-encoding every decoded state must reproduce the same distinctions.
        encodings = {key: json.dumps(v.to_dict(), sort_keys=True)
                     for key, v in decoded.items()}
        self.assertEqual(len(set(encodings.values())), len(encodings))

    def test_unknown_keys_are_not_dropped(self):
        document = {**build_provenance().to_dict(), "future_key": {"x": [None]}}
        restored = SourceProvenance.from_dict(document)
        self.assertEqual(restored.to_dict(), document)
        self.assertEqual(restored.unknown_fields, {"future_key": {"x": [None]}})


class TestNoTupleCoercion(unittest.TestCase):
    def test_source_refs_stay_a_tuple(self):
        restored = ContractRef.from_dict(build_contract_ref().to_dict())
        self.assertIsInstance(restored.source_refs, tuple)
        self.assertEqual(restored.source_refs, (
            "vertical_slice_01.json", "turn_av_semantics_29.json"
        ))

    def test_presence_payload_keeps_its_tuple(self):
        for payload in ((1, 2), (), ("a", None, 0)):
            with self.subTest(payload=repr(payload)):
                restored = PresenceValue.from_dict(
                    PresenceValue.present(payload).to_dict()
                )
                self.assertIsInstance(restored.require_present(), tuple)
                self.assertEqual(restored.require_present(), payload)

    def test_nested_tuple_inside_a_presence_payload_is_preserved(self):
        payload = {"t": (1, 2), "l": [None]}
        restored = PresenceValue.from_dict(
            PresenceValue.present(payload).to_dict()
        )
        self.assertIsInstance(restored.require_present()["t"], tuple)

    def test_unknown_handle_payload_keeps_its_tuple(self):
        original = build_unknown_handle({"t": (1, 2)})
        restored = UnknownHandle.from_dict(original.to_dict())
        self.assertIsInstance(restored.payload["t"], tuple)
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_required_evidence_stays_a_tuple(self):
        restored = UnknownHandle.from_dict(build_unknown_handle({}).to_dict())
        self.assertIsInstance(restored.required_evidence, tuple)

    def test_rejection_link_lists_stay_tuples(self):
        restored = StructuredRejection.from_dict(build_rejection().to_dict())
        self.assertIsInstance(restored.contract_refs, tuple)
        self.assertIsInstance(restored.unknown_handles, tuple)


class TestNoNumericNormalization(unittest.TestCase):
    def test_big_identifiers_survive_the_nested_stack(self):
        payload = build_rejection().to_dict()
        handle = payload["unknown_handles"][0]
        number = LosslessNumber.from_dict(
            handle["payload"]["big_identifier"]
        )
        self.assertIs(number.category, NumericCategory.INTEGER)
        self.assertEqual(number.require_int(), 2**53 + 1)

    def test_decimal_lexeme_survives_without_becoming_a_float(self):
        payload = build_rejection().to_dict()
        handle = payload["unknown_handles"][0]
        number = LosslessNumber.from_dict(handle["payload"]["decimal_lexeme"])
        self.assertIs(number.category, NumericCategory.DECIMAL)
        self.assertEqual(number.lexeme, "0.10")
        self.assertNotEqual(number.lexeme, "0.1")
        self.assertEqual(number.as_decimal(), Decimal("0.10"))

    def test_float_category_is_not_relabelled_as_decimal(self):
        payload = build_rejection().to_dict()
        handle = payload["unknown_handles"][0]
        number = LosslessNumber.from_dict(handle["payload"]["float_value"])
        self.assertIs(number.category, NumericCategory.FLOAT)
        self.assertEqual(number.to_python(), 0.5)
        self.assertIs(type(number.to_python()), float)

    def test_one_and_one_point_zero_stay_distinct_in_a_keyed_matrix(self):
        values = {
            "int": LosslessNumber.from_lexeme("1"),
            "decimal": LosslessNumber.from_lexeme("1.0"),
            "same_value_other_lexeme": LosslessNumber.from_lexeme("1.00"),
        }
        encodings = {
            key: json.dumps(number.to_dict(), sort_keys=True)
            for key, number in values.items()
        }
        self.assertEqual(len(set(encodings.values())), 3)

    def test_rejection_round_trip_preserves_numeric_categories(self):
        restored = StructuredRejection.from_dict(build_rejection().to_dict())
        payload = restored.unknown_handles[0].payload
        self.assertIs(
            LosslessNumber.from_dict(payload["big_identifier"]).category,
            NumericCategory.INTEGER,
        )
        self.assertIs(
            LosslessNumber.from_dict(payload["decimal_lexeme"]).category,
            NumericCategory.DECIMAL,
        )
        self.assertIs(
            LosslessNumber.from_dict(payload["float_value"]).category,
            NumericCategory.FLOAT,
        )


class TestNoEnumIdentitySplit(unittest.TestCase):
    def test_evidence_mode_is_one_class_object_everywhere(self):
        from hsr_battle_agent.battle_sandbox import evidence_boundary as eb
        from hsr_battle_agent.battle_sandbox import reference_boundary as rb
        from hsr_battle_agent.battle_ir import evidence as ir_evidence

        self.assertIs(ir_evidence.EvidenceMode, eb.EvidenceMode)
        self.assertIs(ir_evidence.EvidenceMode, rb.EvidenceMode)

    def test_mode_identity_survives_a_full_round_trip(self):
        restored = StructuredRejection.from_dict(build_rejection().to_dict())
        self.assertIs(
            restored.contract_refs[0].evidence_mode,
            EvidenceMode.REFERENCE_MODEL,
        )
        from hsr_battle_agent.battle_sandbox import evidence_boundary as eb

        self.assertIs(restored.contract_refs[0].evidence_mode,
                      eb.EvidenceMode.REFERENCE_MODEL)

    def test_presence_and_category_identities_survive(self):
        self.assertIs(
            PresenceValue.from_dict(
                PresenceValue.absent().to_dict()
            ).state,
            PresenceState.ABSENT,
        )
        self.assertIs(
            LosslessNumber.from_dict(
                LosslessNumber.from_lexeme("1.0").to_dict()
            ).category,
            NumericCategory.DECIMAL,
        )

    def test_version_relation_identity_survives(self):
        from hsr_battle_agent.battle_ir.evidence import VersionRelation

        restored = SourceProvenance.from_dict(build_provenance().to_dict())
        self.assertIs(restored.version_relation, VersionRelation.CLOSE_VERSION)

    def test_no_duplicate_enum_classes_exist(self):
        import ast

        seen: dict[str, list[str]] = {}
        for path in sorted((REPO / "src").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in (
                    "EvidenceMode",
                    "PresenceState",
                    "NumericCategory",
                    "VersionRelation",
                    "ReadinessClass",
                ):
                    seen.setdefault(node.name, []).append(path.name)
        for name, files in seen.items():
            with self.subTest(name=name):
                self.assertEqual(len(files), 1, f"{name} defined in {files}")


class TestNoSharedMutableAlias(unittest.TestCase):
    def test_mutating_a_returned_document_cannot_mutate_the_model(self):
        rejection = build_rejection()
        returned = rejection.to_dict()
        returned["reason_code"] = "MUTATED"
        returned["diagnostics"]["note"] = "mutated"
        returned["contract_refs"].append({"schema": "contract_ref/1"})
        returned["unknown_handles"][0]["payload"]["nested"]["deep"].append(99)

        fresh = rejection.to_dict()
        self.assertEqual(fresh, build_rejection().to_dict())
        self.assertEqual(rejection.reason_code, "UNKNOWN_WAVE_ADVANCE_PREDICATE")
        self.assertEqual(
            rejection.diagnostics, {"note": "human text; never part of identity"}
        )
        self.assertEqual(len(rejection.contract_refs), 1)

    def test_mutating_a_model_payload_cannot_change_the_model(self):
        source = {"k": [1]}
        value = PresenceValue.from_mapping(source, "k")
        source["k"].append(2)
        self.assertEqual(value.require_present(), [1])

    def test_mutating_a_handle_source_payload_cannot_change_the_handle(self):
        payload = {"raw": [1]}
        handle = build_unknown_handle(payload)
        payload["raw"].append(2)
        self.assertEqual(handle.payload, {"raw": [1]})

    def test_two_documents_from_one_model_are_independent(self):
        value = PresenceValue.present({"raw": [1]})
        first = value.to_dict()
        second = value.to_dict()
        first["value"]["raw"].append(2)
        self.assertEqual(second["value"]["raw"], [1])

    def test_diagnostics_mapping_cannot_alias_the_caller(self):
        diagnostics = {"raw": [1]}
        rejection = StructuredRejection(
            reason_code="X_CODE",
            obligation_owner="OWNER",
            evidence_request="evidence",
            diagnostics=diagnostics,
        )
        rejection.to_dict()["diagnostics"]["raw"].append(2)
        self.assertEqual(rejection.to_dict()["diagnostics"], {"raw": [1]})

    def test_provenance_serialization_is_independent(self):
        provenance = build_provenance()
        first = provenance.to_dict()
        first["profile"] = "mutated"
        self.assertEqual(provenance.to_dict(), build_provenance().to_dict())


class TestCrossCuttingConsistency(unittest.TestCase):
    def test_every_f01_representation_declares_a_schema(self):
        # Provenance carries its marker under "schema_version"; the other five
        # representations use "schema".
        declarations = [
            ("source_provenance/2", build_provenance().to_dict()["schema_version"]),
            ("contract_ref/1", build_contract_ref().to_dict()["schema"]),
            ("unknown_handle/1", build_unknown_handle({}).to_dict()["schema"]),
            ("presence_value/1", PresenceValue.absent().to_dict()["schema"]),
            ("lossless_number/1", LosslessNumber.from_int(1).to_dict()["schema"]),
            ("structured_rejection/1", build_rejection().to_dict()["schema"]),
        ]
        expected = [name for name, _ in declarations]
        actual = [value for _, value in declarations]
        self.assertEqual(actual, expected)
        self.assertEqual(len(set(actual)), len(actual))
        self.assertEqual(len(actual), 6)

    def test_no_representation_exposes_an_executability_shortcut(self):
        samples = [
            build_provenance(),
            build_contract_ref(),
            build_unknown_handle({}),
            PresenceValue.present(0),
            LosslessNumber.from_int(0),
            build_rejection(),
        ]
        for sample in samples:
            for name in ("executable", "is_executable", "can_execute", "as_bool"):
                with self.subTest(sample=type(sample).__name__, name=name):
                    self.assertFalse(hasattr(sample, name))

    def test_truthiness_policy_is_type_specific(self):
        # API_DESIGN_LOCAL: ordinary Enum truthiness is not executability.
        self.assertTrue(bool(build_contract_ref().evidence_mode))
        self.assertTrue(bool(build_provenance().version_relation))
        # REGRESSION_ONLY: value/rejection envelopes refuse conversions that
        # would discard their explicit state or invent a success/fallback path.
        refusing_samples = [
            PresenceValue.present(0),
            LosslessNumber.from_int(0),
            build_rejection(),
        ]
        for sample in refusing_samples:
            with self.subTest(sample=type(sample).__name__):
                # PresenceValueError / LosslessValueError / EvidenceVocabularyError
                # are ValueError subclasses; RejectionDataError derives from
                # BattleSandboxError, so assert on the common base.
                with self.assertRaises(Exception):
                    bool(sample)

    def test_round_trip_is_idempotent(self):
        document = build_rejection().to_dict()
        once = StructuredRejection.from_dict(document).to_dict()
        twice = StructuredRejection.from_dict(once).to_dict()
        self.assertEqual(once, document)
        self.assertEqual(twice, document)


if __name__ == "__main__":
    unittest.main()
