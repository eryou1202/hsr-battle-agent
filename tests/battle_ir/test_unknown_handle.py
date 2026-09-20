# -*- coding: utf-8 -*-
"""F01-004 tests: UnknownHandle opaque unresolved-blocker envelope.

Acceptance criteria: opaque payload round trip, different blocker/owner/payload
hashes differ, and an unknown handle cannot satisfy a ContractRef.
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
    REQUIRED_UNKNOWN_HANDLE_FIELDS,
    UNKNOWN_HANDLE_SCHEMA,
    ContractRef,
    EvidenceMode,
    EvidenceVocabularyError,
    UnknownHandle,
    require_contract_ref,
)
from hsr_battle_agent.battle_ir.provenance import (  # noqa: E402
    PROVENANCE_NOTE_DEFAULT,
    SourceProvenance,
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

#: Payload shapes that must all survive a round trip byte-for-byte in content.
OPAQUE_PAYLOADS = (
    None,
    False,
    True,
    0,
    1,
    -1,
    "",
    "text",
    [],
    [None],
    [None, False, 0, "", [], {}],
    {},
    {"a": None},
    {"nested": {"deep": [1, 2, {"n": None}]}},
    [[[]]],
    {"ordered": [3, 1, 2]},
    2**53 + 1,
    {"big": 9007199254740993},
)


def handle(**overrides):
    base = {
        "blocker_id": "D8-Q2",
        "owner_family": "MONSTER_AI",
        "payload": {"reason": "unknown", "raw": [1, None]},
        "provenance": PROVENANCE,
        "required_evidence": ("pinned observed transition",),
    }
    base.update(overrides)
    return UnknownHandle(**base)


class TestOpaquePayloadRoundTrip(unittest.TestCase):
    def test_every_opaque_payload_shape_round_trips(self):
        for payload in OPAQUE_PAYLOADS:
            with self.subTest(payload=repr(payload)):
                original = handle(payload=payload)
                restored = UnknownHandle.from_dict(original.to_dict())
                self.assertEqual(restored.payload, payload)
                self.assertEqual(restored.to_dict(), original.to_dict())
                # type fidelity: no tuple/list or bool/int coercion
                self.assertIs(type(restored.payload), type(payload))

    def test_list_containing_null_stays_a_list_containing_null(self):
        original = handle(payload=[None])
        restored = UnknownHandle.from_dict(original.to_dict())
        self.assertIsInstance(restored.payload, list)
        self.assertEqual(restored.payload, [None])
        self.assertIsNone(restored.payload[0])
        self.assertNotEqual(restored.payload, [])

    def test_empty_mapping_and_empty_list_stay_distinct(self):
        empty_list = UnknownHandle.from_dict(
            handle(payload=[]).to_dict()
        ).payload
        empty_map = UnknownHandle.from_dict(
            handle(payload={}).to_dict()
        ).payload
        self.assertNotEqual(empty_list, empty_map)
        self.assertIsInstance(empty_list, list)
        self.assertIsInstance(empty_map, dict)

    def test_big_integers_survive_without_float_normalization(self):
        payload = {"big": 2**53 + 1, "also": 2**63 - 1}
        restored = UnknownHandle.from_dict(handle(payload=payload).to_dict())
        self.assertEqual(restored.payload["big"], 2**53 + 1)
        self.assertIsInstance(restored.payload["big"], int)
        self.assertEqual(restored.payload["also"], 2**63 - 1)

    def test_json_round_trip(self):
        original = handle(payload={"nested": [None, 0, False, []]})
        text = json.dumps(original.to_dict(), sort_keys=True)
        restored = UnknownHandle.from_dict(json.loads(text))
        self.assertEqual(restored.payload, original.payload)
        self.assertEqual(restored.identity_hash(), original.identity_hash())

    def test_payload_is_required_and_not_defaulted(self):
        document = handle().to_dict()
        del document["payload"]
        with self.assertRaises(EvidenceVocabularyError):
            UnknownHandle.from_dict(document)

    def test_non_finite_payload_is_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), {"x": float("nan")}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    handle(payload=value)

    def test_unencodable_payload_is_rejected(self):
        for value in (object(), {1, 2}, b"bytes", {object(): 1}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    handle(payload=value)

    def test_serialization_does_not_alias_the_model(self):
        original = handle(payload={"raw": [1, 2]})
        returned = original.to_dict()
        returned["payload"]["raw"].append(99)
        returned["blocker_id"] = "mutated"
        self.assertEqual(original.payload, {"raw": [1, 2]})
        self.assertEqual(original.blocker_id, "D8-Q2")
        self.assertEqual(original.to_dict()["payload"], {"raw": [1, 2]})


class TestIdentityHash(unittest.TestCase):
    def test_hash_is_stable(self):
        self.assertEqual(handle().identity_hash(), handle().identity_hash())
        self.assertEqual(len(handle().identity_hash()), 64)

    def test_different_blocker_ids_hash_differently(self):
        self.assertNotEqual(
            handle().identity_hash(),
            handle(blocker_id="D8-Q3").identity_hash(),
        )

    def test_different_owner_families_hash_differently(self):
        self.assertNotEqual(
            handle().identity_hash(),
            handle(owner_family="TARGET").identity_hash(),
        )

    def test_different_payloads_hash_differently(self):
        # AUTHORITY_REQUIRED: opaque payload identity must be lossless.
        base = handle().identity_hash()
        for payload in (None, {}, [], [None], 0, False, {"reason": "other"}):
            with self.subTest(payload=repr(payload)):
                self.assertNotEqual(base, handle(payload=payload).identity_hash())

    def test_different_required_evidence_hashes_differently(self):
        self.assertNotEqual(
            handle().identity_hash(),
            handle(required_evidence=("different evidence",)).identity_hash(),
        )

    def test_provenance_changes_identity_without_changing_blocker_code(self):
        other = SourceProvenance(
            game_version="4.4.54",
            runtime_type="RPG.GameCore.Other",
            method="Other",
            method_index=1,
            native_rva="0x0",
            evidence_level="E4_STATIC_MACHINE_CODE",
        )
        self.assertNotEqual(
            handle().identity_hash(),
            handle(provenance=other).identity_hash(),
        )
        self.assertEqual(handle().blocker_id, handle(provenance=other).blocker_id)

    def test_provenance_is_normalized_to_a_mapping(self):
        # API_DESIGN_LOCAL: the structurally typed boundary stores the exact
        # serialized provenance document; this avoids an import cycle without
        # dropping or inventing provenance fields.
        original = handle()
        self.assertIsInstance(original.provenance, dict)
        self.assertEqual(
            UnknownHandle.from_dict(original.to_dict()), original
        )

    def test_provenance_is_still_carried(self):
        restored = UnknownHandle.from_dict(handle().to_dict())
        self.assertEqual(restored.provenance["game_version"], "4.4.54")
        self.assertEqual(
            restored.provenance["note"], PROVENANCE_NOTE_DEFAULT
        )

    def test_tuple_and_list_payloads_have_distinct_identity_hashes(self):
        self.assertNotEqual(
            handle(payload=(1, 2)).identity_hash(),
            handle(payload=[1, 2]).identity_hash(),
        )

    def test_provenance_input_is_deep_copied(self):
        provenance = {"source": {"refs": ["a"]}}
        original = handle(provenance=provenance)
        provenance["source"]["refs"].append("b")
        self.assertEqual(original.provenance, {"source": {"refs": ["a"]}})

    def test_non_string_mapping_keys_are_rejected_not_coerced(self):
        with self.assertRaises(EvidenceVocabularyError):
            handle(payload={1: "value"})
        with self.assertRaises(EvidenceVocabularyError):
            handle(provenance={1: "source"})


class TestUnknownHandleCannotSatisfyContractRef(unittest.TestCase):
    def test_require_contract_ref_rejects_a_handle(self):
        with self.assertRaises(EvidenceVocabularyError):
            require_contract_ref(handle())

    def test_require_contract_ref_accepts_a_real_contract_ref(self):
        contract = ContractRef(
            contract_id="c",
            namespace="ns",
            schema_version="v1",
            evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
            content_sha256=SHA,
        )
        self.assertIs(require_contract_ref(contract), contract)

    def test_as_contract_ref_refuses(self):
        with self.assertRaises(EvidenceVocabularyError):
            handle().as_contract_ref()

    def test_handle_is_not_a_contract_ref(self):
        self.assertNotIsInstance(handle(), ContractRef)
        self.assertFalse(issubclass(UnknownHandle, ContractRef))
        self.assertFalse(issubclass(ContractRef, UnknownHandle))

    def test_contract_ref_reader_rejects_a_handle_document(self):
        with self.assertRaises(EvidenceVocabularyError):
            ContractRef.from_dict(handle().to_dict())

    def test_handle_reader_rejects_a_contract_document(self):
        contract = ContractRef(
            contract_id="c",
            namespace="ns",
            schema_version="v1",
            evidence_mode=EvidenceMode.REFERENCE_MODEL,
            content_sha256=SHA,
        ).to_dict()
        with self.assertRaises(EvidenceVocabularyError):
            UnknownHandle.from_dict(contract)

    def test_handle_does_not_expose_contract_fields(self):
        for name in ("evidence_mode", "content_sha256", "require_mode", "identity"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(handle(), name))

    def test_unknown_schemas_are_rejected(self):
        for schema in (CONTRACT_REF_SCHEMA, "unknown_handle/2", "", None, 7):
            with self.subTest(schema=repr(schema)):
                document = {**handle().to_dict(), "schema": schema}
                with self.assertRaises(EvidenceVocabularyError):
                    UnknownHandle.from_dict(document)

    def test_non_mapping_document_is_rejected(self):
        for value in (None, [], "x", 1, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    UnknownHandle.from_dict(value)


class TestUnknownHandleIsNotExecutable(unittest.TestCase):
    def test_no_executability_or_fallback_shortcut(self):
        for name in (
            "executable",
            "is_executable",
            "can_execute",
            "fallback",
            "default",
            "resolve",
            "value_or_default",
            "as_bool",
            "is_resolved",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(UnknownHandle, name))
                self.assertFalse(hasattr(handle(), name))

    def test_handle_is_not_truthy_success(self):
        # There is no boolean protocol; the class must not define __bool__.
        self.assertNotIn("__bool__", vars(UnknownHandle))

    def test_required_fields_are_enforced(self):
        for name in REQUIRED_UNKNOWN_HANDLE_FIELDS:
            with self.subTest(field=name):
                document = handle().to_dict()
                del document[name]
                with self.assertRaises(EvidenceVocabularyError):
                    UnknownHandle.from_dict(document)

    def test_identifiers_must_be_non_empty(self):
        for field in ("blocker_id", "owner_family"):
            with self.subTest(field=field):
                with self.assertRaises(EvidenceVocabularyError):
                    handle(**{field: ""})
                with self.assertRaises(EvidenceVocabularyError):
                    handle(**{field: None})
                with self.assertRaises(EvidenceVocabularyError):
                    handle(**{field: 1})

    def test_required_evidence_entries_must_be_non_empty(self):
        for value in ("single", ("",), ("ok", ""), 1, None):
            with self.subTest(value=repr(value)):
                with self.assertRaises(EvidenceVocabularyError):
                    handle(required_evidence=value)

    def test_empty_required_evidence_is_allowed_but_present(self):
        original = handle(required_evidence=())
        self.assertEqual(original.required_evidence, ())
        self.assertIn("required_evidence", original.to_dict())

    def test_provenance_is_required(self):
        with self.assertRaises(EvidenceVocabularyError):
            handle(provenance=None)
        with self.assertRaises(EvidenceVocabularyError):
            handle(provenance=object())

    def test_mapping_provenance_is_accepted(self):
        original = handle(provenance={"game_version": "4.4.54"})
        restored = UnknownHandle.from_dict(original.to_dict())
        self.assertEqual(restored.provenance, {"game_version": "4.4.54"})


class TestSharedModuleInvariants(unittest.TestCase):
    def test_schema_constants(self):
        self.assertEqual(UNKNOWN_HANDLE_SCHEMA, "unknown_handle/1")
        self.assertEqual(CONTRACT_REF_SCHEMA, "contract_ref/1")

    def test_f01_003_contract_ref_still_works(self):
        contract = ContractRef(
            contract_id="c",
            namespace="ns",
            schema_version="v1",
            evidence_mode="SANDBOX_EXTENSION",
            content_sha256=SHA,
            source_refs=("a",),
        )
        restored = ContractRef.from_dict(contract.to_dict())
        self.assertEqual(restored.to_dict(), contract.to_dict())
        self.assertIs(
            restored.evidence_mode, EvidenceMode.SANDBOX_EXTENSION
        )

    def test_f01_001_mode_identity_is_still_canonical(self):
        from hsr_battle_agent.battle_sandbox import evidence_boundary as eb

        self.assertIs(eb.EvidenceMode, EvidenceMode)


if __name__ == "__main__":
    unittest.main()
