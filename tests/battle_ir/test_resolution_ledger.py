# -*- coding: utf-8 -*-
"""R01-001 tests: resolution states and ledger.

Acceptance criteria: all states round-trip, and AMBIGUOUS cannot expose a
value.  The suite also proves MISSING, AMBIGUOUS and BLOCKED are three distinct
states that are never collapsed, that unresolved entries carry an UnknownHandle
and provenance, and that EXACT never implies native executability.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_ir.resolution_ledger import (  # noqa: E402
    BLOCKED_CLASSIFICATIONS,
    EXACT_CLASSIFICATIONS,
    MISSING_CLASSIFICATIONS,
    REASON_MULTIPLE_CANDIDATES,
    REASON_NO_CANDIDATE_RECORDED,
    REASON_OUT_OF_STATIC_FAMILY_SCOPE,
    REASON_UNRECOGNISED_CLASSIFICATION,
    RESOLUTION_LEDGER_SCHEMA,
    RESOLUTION_STATES,
    ResolutionLedger,
    ResolutionLedgerEntry,
    ResolutionLedgerError,
    ResolutionProvenance,
    ResolutionState,
    classify_record,
)

MAPPING_PATH = (
    REPO
    / "data"
    / "semantics"
    / "4.4.54"
    / "full_reconstruction"
    / "full_content_behavior_mapping_001.json"
)


def record(
    behavior_id="external:example:path:Owner",
    classification="EXACT_CONFIG_ID",
    candidates=("20021",),
    owner_kind="LightCone",
    static_family="LightCone",
):
    return {
        "behavior_id": behavior_id,
        "owner_kind": owner_kind,
        "behavior_bearing": True,
        "compile_status": "COMPILED_STRUCTURE_ONLY",
        "source_ref": {
            "commit": "b11066beacc4de454b625fafc7ea3dd540c5bbf3",
            "path": "Config/ConfigAbility/LightCone/x.json",
            "raw_sha256": "0" * 64,
            "repository": "https://github.com/DimbrethBot/TurnBasedGameData",
            "version_relation": "CLOSE_4.4.0_TO_4.4.54",
        },
        "static_link": {
            "candidate_entity_ids": list(candidates),
            "classification": classification,
            "evidence": "recorded evidence text",
            "mapping_method": classification,
            "representation_tag": None,
            "static_family": static_family,
        },
    }


def document(records):
    return {
        "game_version": "4.4.54",
        "report_id": "TEST-MAPPING-001",
        "report_sha256": "a" * 64,
        "record_links": list(records),
    }


class TestStateVocabulary(unittest.TestCase):
    def test_declared_states(self):
        self.assertEqual(
            RESOLUTION_STATES, ("EXACT", "MISSING", "AMBIGUOUS", "BLOCKED")
        )
        self.assertEqual(ResolutionState.spellings(), RESOLUTION_STATES)

    def test_states_are_mutually_distinct(self):
        self.assertEqual(len({state for state in ResolutionState}), 4)
        for left in ResolutionState:
            for right in ResolutionState:
                if left is right:
                    continue
                with self.subTest(left=left.name, right=right.name):
                    self.assertIsNot(left, right)
                    self.assertNotEqual(left, right)

    def test_missing_is_not_ambiguous(self):
        self.assertIsNot(ResolutionState.MISSING, ResolutionState.AMBIGUOUS)
        self.assertNotEqual(
            ResolutionState.MISSING.value, ResolutionState.AMBIGUOUS.value
        )

    def test_states_have_no_truthiness(self):
        for state in ResolutionState:
            with self.subTest(state=state.name):
                with self.assertRaises(ResolutionLedgerError):
                    bool(state)

    def test_classification_lists_are_disjoint(self):
        combined = (
            set(EXACT_CLASSIFICATIONS)
            | set(MISSING_CLASSIFICATIONS)
            | set(BLOCKED_CLASSIFICATIONS)
        )
        self.assertEqual(
            len(combined),
            len(EXACT_CLASSIFICATIONS)
            + len(MISSING_CLASSIFICATIONS)
            + len(BLOCKED_CLASSIFICATIONS),
        )
        self.assertEqual(set(EXACT_CLASSIFICATIONS), {
            "EXACT_ID", "EXACT_CONFIG_ID", "STRUCTURED_MAPPING"
        })
        self.assertEqual(set(MISSING_CLASSIFICATIONS), {
            "UNMAPPED", "PARENT_AVATAR_ONLY", "REPRESENTATION_TRANSFORM_CANDIDATE"
        })
        self.assertEqual(
            set(BLOCKED_CLASSIFICATIONS), {"OUT_OF_STATIC_FAMILY_SCOPE"}
        )


class TestStatePolicy(unittest.TestCase):
    def test_exact_relation_with_one_candidate_is_exact(self):
        for classification in EXACT_CLASSIFICATIONS:
            with self.subTest(classification=classification):
                state, reason = classify_record(
                    record(classification=classification, candidates=("7",))
                )
                self.assertIs(state, ResolutionState.EXACT)
                self.assertIsNone(reason)

    def test_exact_relation_with_several_candidates_is_ambiguous(self):
        for classification in EXACT_CLASSIFICATIONS:
            with self.subTest(classification=classification):
                state, reason = classify_record(
                    record(classification=classification, candidates=("7", "8"))
                )
                self.assertIs(state, ResolutionState.AMBIGUOUS)
                self.assertEqual(reason, REASON_MULTIPLE_CANDIDATES)

    def test_exact_relation_with_no_candidate_is_missing_not_ambiguous(self):
        for classification in EXACT_CLASSIFICATIONS:
            with self.subTest(classification=classification):
                state, reason = classify_record(
                    record(classification=classification, candidates=())
                )
                self.assertIs(state, ResolutionState.MISSING)
                self.assertIsNot(state, ResolutionState.AMBIGUOUS)
                self.assertEqual(reason, REASON_NO_CANDIDATE_RECORDED)

    def test_non_relation_classifications_are_missing(self):
        for classification in MISSING_CLASSIFICATIONS:
            with self.subTest(classification=classification):
                state, reason = classify_record(
                    record(classification=classification, candidates=())
                )
                self.assertIs(state, ResolutionState.MISSING)
                self.assertIsNone(reason)

    def test_representation_candidate_is_missing_and_not_exact(self):
        # The mapping states this relation is "not native-ID proof".
        state, _ = classify_record(
            record(
                classification="REPRESENTATION_TRANSFORM_CANDIDATE",
                candidates=("20021",),
            )
        )
        self.assertIs(state, ResolutionState.MISSING)
        self.assertIsNot(state, ResolutionState.EXACT)

    def test_out_of_scope_is_blocked(self):
        state, reason = classify_record(
            record(classification="OUT_OF_STATIC_FAMILY_SCOPE", candidates=())
        )
        self.assertIs(state, ResolutionState.BLOCKED)
        self.assertEqual(reason, REASON_OUT_OF_STATIC_FAMILY_SCOPE)

    def test_unrecognised_classification_is_blocked_not_missing(self):
        for classification in ("SOMETHING_NEW", "", None, 7):
            with self.subTest(classification=repr(classification)):
                state, reason = classify_record(
                    record(classification=classification, candidates=())
                )
                self.assertIs(state, ResolutionState.BLOCKED)
                self.assertIsNot(state, ResolutionState.MISSING)
                self.assertEqual(reason, REASON_UNRECOGNISED_CLASSIFICATION)

    def test_unrecognised_classification_with_many_candidates_is_blocked(self):
        state, reason = classify_record(
            record(classification="SOMETHING_NEW", candidates=("1", "2"))
        )
        self.assertIs(state, ResolutionState.BLOCKED)
        self.assertEqual(reason, REASON_UNRECOGNISED_CLASSIFICATION)

    def test_missing_record_shape_is_blocked(self):
        for broken in ({}, {"behavior_id": "x"}, {"static_link": None}):
            with self.subTest(record=repr(broken)):
                state, reason = classify_record(broken)
                self.assertIs(state, ResolutionState.BLOCKED)
                self.assertEqual(reason, REASON_UNRECOGNISED_CLASSIFICATION)

    def test_three_unresolved_states_are_not_collapsed(self):
        states = {
            classify_record(record(candidates=()))[0],                       # MISSING
            classify_record(record(candidates=("1", "2")))[0],               # AMBIGUOUS
            classify_record(record(classification="OUT_OF_STATIC_FAMILY_SCOPE",
                                   candidates=()))[0],                       # BLOCKED
        }
        self.assertEqual(states, {
            ResolutionState.MISSING,
            ResolutionState.AMBIGUOUS,
            ResolutionState.BLOCKED,
        })


class TestEntryConstruction(unittest.TestCase):
    def test_exact_entry_exposes_exactly_the_recorded_candidate(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(classification="EXACT_CONFIG_ID", candidates=("20021",))
        )
        self.assertTrue(entry.is_exact())
        self.assertEqual(entry.require_resolved(), "20021")
        self.assertIsInstance(entry.require_resolved(), str)
        self.assertIsNone(entry.unknown_handle)
        self.assertIsNone(entry.reason_code)

    def test_resolved_id_is_a_string_never_float_normalized(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(candidates=("9007199254740993",))
        )
        resolved = entry.require_resolved()
        self.assertEqual(resolved, "9007199254740993")
        self.assertIsInstance(resolved, str)
        self.assertNotEqual(resolved, "9007199254740992")

    def test_missing_entry_carries_a_handle_and_exposes_no_value(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(classification="UNMAPPED", candidates=())
        )
        self.assertTrue(entry.is_missing())
        self.assertIsNone(entry.resolved_entity_id)
        self.assertIsInstance(entry.unknown_handle, UnknownHandle)
        self.assertIn("UNMAPPED", entry.unknown_handle.blocker_id)

    def test_ambiguous_entry_carries_a_handle_and_exposes_no_value(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(candidates=("1", "2"))
        )
        self.assertTrue(entry.is_ambiguous())
        self.assertIsNone(entry.resolved_entity_id)
        self.assertIsInstance(entry.unknown_handle, UnknownHandle)

    def test_blocked_entry_carries_a_reason_and_a_handle(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(classification="OUT_OF_STATIC_FAMILY_SCOPE", candidates=())
        )
        self.assertTrue(entry.is_blocked())
        self.assertEqual(entry.reason_code, REASON_OUT_OF_STATIC_FAMILY_SCOPE)
        self.assertIsInstance(entry.unknown_handle, UnknownHandle)

    def test_handle_preserves_the_recorded_payload(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(classification="UNMAPPED", candidates=("1", "2"))
        )
        payload = entry.unknown_handle.payload
        self.assertEqual(payload["classification"], "UNMAPPED")
        self.assertEqual(payload["candidate_entity_ids"], ["1", "2"])
        self.assertEqual(payload["evidence"], "recorded evidence text")
        self.assertIn("commit", payload["source_ref"])

    def test_handle_evidence_request_reflects_the_recorded_meaning(self):
        missing = ResolutionLedgerEntry.from_mapping_record(
            record(classification="REPRESENTATION_TRANSFORM_CANDIDATE",
                   candidates=("1",))
        )
        self.assertIn(
            "not native-ID proof", missing.unknown_handle.required_evidence[0]
        )
        ambiguous = ResolutionLedgerEntry.from_mapping_record(
            record(candidates=("1", "2"))
        )
        self.assertIn(
            "disambiguation", ambiguous.unknown_handle.required_evidence[0]
        )

    def test_provenance_records_the_source_reference_verbatim(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(candidates=("1",))
        )
        self.assertTrue(entry.provenance.has("source_ref.commit"))
        self.assertTrue(entry.provenance.has("source_ref.path"))
        self.assertTrue(entry.provenance.has("source_ref.version_relation"))
        self.assertEqual(
            entry.provenance.value("source_ref.version_relation"),
            "CLOSE_4.4.0_TO_4.4.54",
        )
        self.assertNotIn("commit", entry.provenance.absent_field_names())
        self.assertNotIn("path", entry.provenance.absent_field_names())
        self.assertNotIn("version_relation", entry.provenance.absent_field_names())

    def test_provenance_rejects_non_string_keys_without_coercion(self):
        with self.assertRaises(ResolutionLedgerError):
            ResolutionProvenance(fields={1: "not-a-string-key"})

    def test_unresolved_payload_distinguishes_absent_source_ref(self):
        raw = record(classification="UNMAPPED", candidates=())
        raw.pop("source_ref")
        entry = ResolutionLedgerEntry.from_mapping_record(raw)
        payload = entry.unknown_handle.payload
        self.assertFalse(payload["source_ref_present"])
        self.assertNotIn("source_ref", payload)

    def test_provenance_absence_is_observable(self):
        minimal = {"behavior_id": "b", "static_link": {"classification": "UNMAPPED"}}
        entry = ResolutionLedgerEntry.from_mapping_record(minimal)
        self.assertFalse(entry.provenance.has("source_ref.commit"))
        self.assertIn("commit", entry.provenance.absent_field_names())
        with self.assertRaises(ResolutionLedgerError):
            entry.provenance.value("source_ref.commit")

    def test_provenance_records_document_identity(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(candidates=("1",)), document=document([])
        )
        self.assertEqual(entry.provenance.value("report_id"), "TEST-MAPPING-001")
        self.assertEqual(entry.provenance.value("game_version"), "4.4.54")

    def test_exact_requires_exactly_one_candidate(self):
        with self.assertRaises(ResolutionLedgerError):
            ResolutionLedgerEntry(
                behavior_id="b",
                state=ResolutionState.EXACT,
                classification="EXACT_ID",
                owner_kind="X",
                static_family="X",
                candidate_entity_ids=("1", "2"),
                resolved_entity_id="1",
            )

    def test_exact_requires_a_resolved_value(self):
        with self.assertRaises(ResolutionLedgerError):
            ResolutionLedgerEntry(
                behavior_id="b",
                state=ResolutionState.EXACT,
                classification="EXACT_ID",
                owner_kind="X",
                static_family="X",
                candidate_entity_ids=("1",),
            )

    def test_exact_must_not_carry_a_handle(self):
        handle = UnknownHandle(
            blocker_id="b",
            owner_family="X",
            payload=None,
            provenance={"p": 1},
        )
        with self.assertRaises(ResolutionLedgerError):
            ResolutionLedgerEntry(
                behavior_id="b",
                state=ResolutionState.EXACT,
                classification="EXACT_ID",
                owner_kind="X",
                static_family="X",
                candidate_entity_ids=("1",),
                resolved_entity_id="1",
                unknown_handle=handle,
            )

    def test_unresolved_states_must_not_expose_a_value(self):
        handle = UnknownHandle(
            blocker_id="b", owner_family="X", payload=None, provenance={"p": 1}
        )
        for state, reason in (
            (ResolutionState.MISSING, None),
            (ResolutionState.AMBIGUOUS, REASON_MULTIPLE_CANDIDATES),
            (ResolutionState.BLOCKED, REASON_OUT_OF_STATIC_FAMILY_SCOPE),
        ):
            with self.subTest(state=state.name):
                with self.assertRaises(ResolutionLedgerError):
                    ResolutionLedgerEntry(
                        behavior_id="b",
                        state=state,
                        classification="X",
                        owner_kind="X",
                        static_family="X",
                        resolved_entity_id="1",
                        reason_code=reason,
                        unknown_handle=handle,
                    )

    def test_unresolved_states_must_carry_a_handle(self):
        for state, reason in (
            (ResolutionState.MISSING, None),
            (ResolutionState.AMBIGUOUS, REASON_MULTIPLE_CANDIDATES),
            (ResolutionState.BLOCKED, REASON_OUT_OF_STATIC_FAMILY_SCOPE),
        ):
            with self.subTest(state=state.name):
                with self.assertRaises(ResolutionLedgerError):
                    ResolutionLedgerEntry(
                        behavior_id="b",
                        state=state,
                        classification="X",
                        owner_kind="X",
                        static_family="X",
                        reason_code=reason,
                    )

    def test_blocked_requires_a_reason(self):
        handle = UnknownHandle(
            blocker_id="b", owner_family="X", payload=None, provenance={"p": 1}
        )
        with self.assertRaises(ResolutionLedgerError):
            ResolutionLedgerEntry(
                behavior_id="b",
                state=ResolutionState.BLOCKED,
                classification="X",
                owner_kind="X",
                static_family="X",
                unknown_handle=handle,
            )

    def test_entry_has_no_truthiness(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1",)))
        with self.assertRaises(ResolutionLedgerError):
            bool(entry)


class TestAmbiguousNeverExposesAValue(unittest.TestCase):
    def test_require_resolved_refuses_for_every_unresolved_state(self):
        samples = [
            ResolutionLedgerEntry.from_mapping_record(
                record(classification="UNMAPPED", candidates=())
            ),
            ResolutionLedgerEntry.from_mapping_record(record(candidates=("1", "2"))),
            ResolutionLedgerEntry.from_mapping_record(
                record(classification="OUT_OF_STATIC_FAMILY_SCOPE", candidates=())
            ),
        ]
        for entry in samples:
            with self.subTest(state=entry.state.name):
                with self.assertRaises(ResolutionLedgerError):
                    entry.require_resolved()

    def test_ambiguous_serialization_omits_the_resolved_key(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1", "2")))
        payload = entry.to_dict()
        self.assertNotIn("resolved_entity_id", payload)
        self.assertEqual(payload["state"], "AMBIGUOUS")

    def test_ambiguous_candidates_are_still_recorded(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(candidates=("1", "2", "3"))
        )
        self.assertEqual(entry.candidate_entity_ids, ("1", "2", "3"))
        self.assertEqual(
            entry.to_dict()["candidate_entity_ids"], ["1", "2", "3"]
        )

    def test_ambiguous_round_trips_without_gaining_a_value(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1", "2")))
        restored = ResolutionLedgerEntry.from_dict(entry.to_dict())
        self.assertTrue(restored.is_ambiguous())
        self.assertIsNone(restored.resolved_entity_id)
        with self.assertRaises(ResolutionLedgerError):
            restored.require_resolved()


class TestExactIsNotExecutability(unittest.TestCase):
    def test_execution_permitted_refuses(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1",)))
        with self.assertRaises(ResolutionLedgerError):
            entry.execution_permitted()

    def test_no_executability_helpers(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1",)))
        for name in (
            "executable",
            "is_executable",
            "can_execute",
            "implies_execution",
            "as_bool",
            "permission",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ResolutionLedgerEntry, name))
                self.assertFalse(hasattr(entry, name))

    def test_exact_records_the_static_link_only(self):
        entry = ResolutionLedgerEntry.from_mapping_record(
            record(classification="EXACT_CONFIG_ID", candidates=("20021",))
        )
        self.assertTrue(entry.is_exact())
        # The record's own reference-execution flags are not ledger claims.
        self.assertFalse(hasattr(entry, "whole_record_executable_reference"))


class TestEntryRoundTrip(unittest.TestCase):
    def test_every_state_round_trips(self):
        samples = [
            record(classification="EXACT_CONFIG_ID", candidates=("20021",)),
            record(classification="UNMAPPED", candidates=()),
            record(candidates=("1", "2")),
            record(classification="OUT_OF_STATIC_FAMILY_SCOPE", candidates=()),
            record(classification="SOMETHING_NEW", candidates=()),
        ]
        seen_states = set()
        for raw in samples:
            original = ResolutionLedgerEntry.from_mapping_record(raw)
            document_ = original.to_dict()
            restored = ResolutionLedgerEntry.from_dict(document_)
            with self.subTest(state=original.state.name):
                self.assertEqual(restored.to_dict(), document_)
                self.assertEqual(restored, original)
                self.assertIs(restored.state, original.state)
            seen_states.add(original.state)
        # The sample set really does exercise every state except pure AMBIGUOUS
        # via classification, which is covered above.
        self.assertIn(ResolutionState.EXACT, seen_states)
        self.assertIn(ResolutionState.MISSING, seen_states)
        self.assertIn(ResolutionState.AMBIGUOUS, seen_states)
        self.assertIn(ResolutionState.BLOCKED, seen_states)

    def test_json_round_trip(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1", "2")))
        text = json.dumps(entry.to_dict(), sort_keys=True)
        restored = ResolutionLedgerEntry.from_dict(json.loads(text))
        self.assertEqual(restored.to_dict(), entry.to_dict())
        self.assertIs(restored.state, ResolutionState.AMBIGUOUS)

    def test_provenance_round_trips(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1",)))
        restored = ResolutionLedgerEntry.from_dict(entry.to_dict())
        self.assertEqual(restored.provenance.fields, entry.provenance.fields)
        self.assertEqual(
            restored.provenance.absent_field_names(),
            entry.provenance.absent_field_names(),
        )

    def test_attached_handle_round_trips(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1", "2")))
        restored = ResolutionLedgerEntry.from_dict(entry.to_dict())
        self.assertEqual(
            restored.unknown_handle.identity_hash(),
            entry.unknown_handle.identity_hash(),
        )
        self.assertEqual(
            restored.unknown_handle.required_evidence,
            entry.unknown_handle.required_evidence,
        )

    def test_serialization_does_not_alias_the_model(self):
        entry = ResolutionLedgerEntry.from_mapping_record(record(candidates=("1", "2")))
        returned = entry.to_dict()
        returned["classification"] = "MUTATED"
        returned["candidate_entity_ids"].append("99")
        returned["unknown_handle"]["payload"]["candidate_entity_ids"].append("99")
        self.assertEqual(entry.classification, "EXACT_CONFIG_ID")
        self.assertEqual(entry.candidate_entity_ids, ("1", "2"))
        self.assertEqual(entry.to_dict()["classification"], "EXACT_CONFIG_ID")

    def test_malformed_documents_are_rejected(self):
        for broken in (
            None,
            [],
            "x",
            {},
            {"behavior_id": "b"},
            {"behavior_id": "b", "state": "BOGUS", "classification": "X"},
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(ResolutionLedgerError):
                    ResolutionLedgerEntry.from_dict(broken)


class TestLedger(unittest.TestCase):
    def build(self):
        return ResolutionLedger.from_mapping_document(
            document([
                record(behavior_id="b-exact", candidates=("20021",)),
                record(behavior_id="b-missing", classification="UNMAPPED",
                       candidates=()),
                record(behavior_id="b-ambiguous", candidates=("1", "2")),
                record(behavior_id="b-blocked",
                       classification="OUT_OF_STATIC_FAMILY_SCOPE", candidates=()),
            ])
        )

    def test_counts_and_queries(self):
        ledger = self.build()
        self.assertEqual(len(ledger), 4)
        self.assertEqual(
            ledger.counts(),
            {"EXACT": 1, "MISSING": 1, "AMBIGUOUS": 1, "BLOCKED": 1},
        )
        self.assertEqual(len(ledger.by_state("EXACT")), 1)
        self.assertEqual(len(ledger.by_state(ResolutionState.MISSING)), 1)
        self.assertEqual(
            ledger.reasons(),
            {
                REASON_OUT_OF_STATIC_FAMILY_SCOPE: 1,
                REASON_MULTIPLE_CANDIDATES: 1,
            },
        )

    def test_get_and_require_resolved(self):
        ledger = self.build()
        self.assertEqual(ledger.require_resolved("b-exact"), "20021")
        for behavior_id in ("b-missing", "b-ambiguous", "b-blocked"):
            with self.subTest(behavior_id=behavior_id):
                with self.assertRaises(ResolutionLedgerError):
                    ledger.require_resolved(behavior_id)

    def test_unknown_behavior_id_is_rejected(self):
        with self.assertRaises(ResolutionLedgerError):
            self.build().get("nope")

    def test_ledger_round_trips(self):
        ledger = self.build()
        payload = ledger.to_dict()
        restored = ResolutionLedger.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.counts(), ledger.counts())
        self.assertEqual(restored.report_id, "TEST-MAPPING-001")

    def test_ledger_json_round_trip(self):
        ledger = self.build()
        text = json.dumps(ledger.to_dict(), sort_keys=True)
        restored = ResolutionLedger.from_dict(json.loads(text))
        self.assertEqual(restored.to_dict(), ledger.to_dict())
        self.assertEqual(
            [e.state.value for e in restored.entries],
            [e.state.value for e in ledger.entries],
        )

    def test_ledger_requires_record_links(self):
        for broken in (None, [], "x", {}, {"game_version": "4.4.54"}):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(ResolutionLedgerError):
                    ResolutionLedger.from_mapping_document(broken)

    def test_ledger_rejects_unknown_schema(self):
        payload = self.build().to_dict()
        payload["schema"] = "resolution_ledger/2"
        with self.assertRaises(ResolutionLedgerError):
            ResolutionLedger.from_dict(payload)

    def test_schema_constant(self):
        self.assertEqual(RESOLUTION_LEDGER_SCHEMA, "resolution_ledger/1")
        self.assertEqual(
            self.build().to_dict()["schema"], RESOLUTION_LEDGER_SCHEMA
        )

    def test_digest_is_stable_and_state_sensitive(self):
        ledger = self.build()
        self.assertEqual(ledger.digest(), self.build().digest())
        changed = ResolutionLedger.from_mapping_document(
            document([record(behavior_id="b", classification="UNMAPPED",
                             candidates=())])
        )
        self.assertNotEqual(ledger.digest(), changed.digest())

    def test_entries_preserve_source_order(self):
        ledger = self.build()
        self.assertEqual(
            [entry.behavior_id for entry in ledger.entries],
            ["b-exact", "b-missing", "b-ambiguous", "b-blocked"],
        )


class TestAgainstPublishedMapping(unittest.TestCase):
    """Read-only checks against the real published mapping report."""

    @classmethod
    def setUpClass(cls):
        if not MAPPING_PATH.is_file():
            raise unittest.SkipTest("published mapping report is unavailable")
        cls.document = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
        cls.ledger = ResolutionLedger.from_mapping_document(cls.document)

    def test_entry_count_matches_record_links(self):
        self.assertEqual(len(self.ledger), len(self.document["record_links"]))

    def test_every_entry_is_exactly_one_state(self):
        counts = self.ledger.counts()
        self.assertEqual(sum(counts.values()), len(self.ledger))
        for name, count in counts.items():
            self.assertGreaterEqual(count, 0, name)

    def test_no_join_is_performed(self):
        # The ledger's EXACT count must equal the number of records whose own
        # static_link classification is exact and which record one candidate.
        expected = sum(
            1
            for record_ in self.document["record_links"]
            if record_["static_link"]["classification"] in EXACT_CLASSIFICATIONS
            and len(record_["static_link"]["candidate_entity_ids"]) == 1
        )
        self.assertEqual(self.ledger.counts()["EXACT"], expected)

    def test_unresolved_entries_all_carry_a_handle_and_provenance(self):
        unresolved = [e for e in self.ledger.entries if e.is_unresolved()]
        self.assertTrue(unresolved)
        for entry in unresolved:
            self.assertIsInstance(entry.unknown_handle, UnknownHandle)
            self.assertIsNone(entry.resolved_entity_id)
            self.assertTrue(entry.provenance.recorded_names())

    def test_exact_entries_resolve_to_recorded_string_ids(self):
        for entry in self.ledger.by_state("EXACT"):
            with self.subTest(behavior_id=entry.behavior_id):
                resolved = entry.require_resolved()
                self.assertIsInstance(resolved, str)
                self.assertIn(resolved, entry.candidate_entity_ids)
                self.assertEqual(resolved, entry.candidate_entity_ids[0])

    def test_full_ledger_round_trips(self):
        payload = self.ledger.to_dict()
        restored = ResolutionLedger.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)


if __name__ == "__main__":
    unittest.main()
