# -*- coding: utf-8 -*-
"""C02-001 acceptance tests for the D5 / D8 / D9 followup ledger import.

Expectations are built two ways and both must agree: literal frozen constants
that a reviewer can check by eye, and an independent re-read of the source JSON
through plain :mod:`json` with counts recomputed in the test.  A test that only
compared the module's output with itself would prove nothing.

The suite also asserts the *absences* that matter: no fuzzy or numeric matching
helper, no gate certificate, no native contract, no execution surface, and no
substituted file where the source recorded an absence.
"""
from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode  # noqa: E402
from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    PresenceValue as P,
)
from hsr_battle_agent.game_data.followup_ledger import (  # noqa: E402
    FOLLOWUP_ARTIFACTS,
    FOLLOWUP_EVIDENCE_MODE,
    STAGE_COMMON_TEMPLATE_PATH,
    FollowupDomain,
    FollowupFamily,
    FollowupLedger,
    FollowupLedgerError,
    FollowupRecord,
    FollowupState,
    load_followup_ledgers,
    parse_d5_binding_ledger,
    parse_d5_content_acquisition,
    parse_d5_sequence_id_binding,
    parse_d8_content_followup,
    parse_d9_content_followup,
    parse_followup_state,
)

BASE = REPO / "data/semantics/4.4.54/full_reconstruction"
MODULE_PATH = REPO / "src/hsr_battle_agent/game_data/followup_ledger.py"

D5_ACQUISITION = "monster_ai_content_acquisition_001.json"
D5_BINDING = "monster_ai_binding_ledger_001.json"
D5_SEQUENCE = "monster_ai_sequence_id_binding_001.json"
D8_ARTIFACT = "equipment_trace_eidolon_content_followup_001.json"
D9_ARTIFACT = "stage_environment_mode_content_followup_001.json"

# Independent read of the sources: the same bytes the module reads, parsed here
# without any of the module's code, so the two cannot agree by construction.
def source(name: str) -> dict:
    return json.loads((BASE / name).read_text(encoding="utf-8"))


D5_SEQ_DOC = source(D5_SEQUENCE)
D5_BINDING_DOC = source(D5_BINDING)
D5_ACQ_DOC = source(D5_ACQUISITION)
D8_DOC = source(D8_ARTIFACT)
D9_DOC = source(D9_ARTIFACT)


# Parsed once: every public read returns detached values, so sharing these
# instances across tests is safe, and re-parsing the 8276-record D8 ledger for
# every assertion would make the suite needlessly slow.
_D5_SEQ = parse_d5_sequence_id_binding(D5_SEQ_DOC)
_D5_BINDING = parse_d5_binding_ledger(D5_BINDING_DOC)
_D5_ACQ = parse_d5_content_acquisition(D5_ACQ_DOC)
_D8 = parse_d8_content_followup(D8_DOC)
_D9 = parse_d9_content_followup(D9_DOC)
_ALL = load_followup_ledgers(BASE)


def d5_sequence(**kwargs) -> FollowupLedger:
    if kwargs:
        return parse_d5_sequence_id_binding(D5_SEQ_DOC, **kwargs)
    return _D5_SEQ


def d5_binding(**kwargs) -> FollowupLedger:
    if kwargs:
        return parse_d5_binding_ledger(D5_BINDING_DOC, **kwargs)
    return _D5_BINDING


def d5_acquisition(**kwargs) -> FollowupLedger:
    if kwargs:
        return parse_d5_content_acquisition(D5_ACQ_DOC, **kwargs)
    return _D5_ACQ


def d8(**kwargs) -> FollowupLedger:
    if kwargs:
        return parse_d8_content_followup(D8_DOC, **kwargs)
    return _D8


def d9(**kwargs) -> FollowupLedger:
    if kwargs:
        return parse_d9_content_followup(D9_DOC, **kwargs)
    return _D9


# ---------------------------------------------------------------------------
# D5 -- sequence-id binding
# ---------------------------------------------------------------------------

class TestD5SequenceIds(unittest.TestCase):
    def test_eleven_requested_ids_are_preserved(self):
        # Frozen fact, literal, plus an independent re-count from the source.
        self.assertEqual(len(d5_sequence().source_order("requested_ids")), 11)
        self.assertEqual(len(D5_SEQ_DOC["requested_ids"]), 11)
        self.assertEqual(len(d5_sequence().records_of_family(FollowupFamily.MONSTER_SKILL_ROW)), 11)

    def test_requested_id_values_are_verbatim_and_ordered(self):
        expected = [str(value) for value in D5_SEQ_DOC["requested_ids"]]
        self.assertEqual(d5_sequence().source_order("requested_ids"), tuple(expected))
        self.assertEqual(
            expected[:4],
            ["801503001", "801503002", "801503005", "801503006"],
        )

    def test_requested_order_and_table_source_order_are_separate_facts(self):
        # The artifact's own validation contract says the two orders are
        # distinct; neither may be sorted or merged into the other.
        ledger = d5_sequence()
        requested = ledger.source_order("requested_ids")
        table = ledger.source_order("table_source_order")
        self.assertNotEqual(requested, table)
        self.assertEqual(set(requested), set(table))
        self.assertEqual(
            table[-4:], ("801505003", "801505004", "801505005", "801505006")
        )
        self.assertEqual(
            requested[-4:], ("801505005", "801505006", "801505003", "801505004")
        )

    def test_fifteen_occurrences_are_preserved(self):
        self.assertEqual(len(d5_sequence().records_of_family(FollowupFamily.SEQUENCE_OCCURRENCE)), 15)
        self.assertEqual(len(D5_SEQ_DOC["sequence_occurrences"]), 15)
        self.assertEqual(d5_sequence().metric("summary/sequence_occurrences"), 15)

    def test_exact_binding_count_is_fifteen_from_both_paths(self):
        ledger = d5_sequence()
        self.assertEqual(ledger.state_count("summary/status_counts/EXACT"), 15)
        self.assertEqual(ledger.metric("summary/exact_character_bindings"), 15)
        independent = sum(
            1
            for row in D5_SEQ_DOC["sequence_occurrences"]
            if row["status"] == "EXACT"
        )
        self.assertEqual(independent, 15)
        # EXACT is ambiguous without a family in this ledger: the 11 skill rows
        # are EXACT too.  The family-scoped query is the meaningful one.
        self.assertEqual(
            len(
                ledger.records_in_state(
                    FollowupState.EXACT, family=FollowupFamily.SEQUENCE_OCCURRENCE
                )
            ),
            15,
        )
        self.assertEqual(len(ledger.records_in_state(FollowupState.EXACT)), 30)

    def test_declared_zero_statuses_are_kept_as_zeros(self):
        ledger = d5_sequence()
        for spelling in (
            "ROW_MISSING",
            "SKILL_TRIGGER_KEY_MISSING",
            "CHARACTER_SKILL_MISSING",
            "AMBIGUOUS",
            "UNRESOLVED",
        ):
            with self.subTest(spelling=spelling):
                self.assertEqual(
                    ledger.state_count(f"summary/status_counts/{spelling}"), 0
                )
        self.assertEqual(d5_sequence().metric("summary/blocked"), 0)

    def test_duplicates_remain_observable(self):
        ledger = d5_sequence()
        occurrences = ledger.records_of_family(FollowupFamily.SEQUENCE_OCCURRENCE)
        ids = [row.source_id for row in occurrences]
        self.assertEqual(len(ids), 15)
        self.assertEqual(len(set(ids)), 11)
        self.assertEqual(ledger.metric("sequence_occurrences/unique_source_ids"), 11)
        # The override sequence repeats 801503001 and 801503002; both repeats
        # must still be present as separate occurrence records.
        self.assertEqual(Counter(ids)["801503001"], 3)
        self.assertEqual(Counter(ids)["801503002"], 3)
        self.assertEqual(
            ledger.multiplicity_of(FollowupFamily.SEQUENCE_OCCURRENCE, "801503001"), 3
        )
        # And the same id in another family is a different fact, not a repeat.
        self.assertEqual(
            ledger.multiplicity_of(FollowupFamily.MONSTER_SKILL_ROW, "801503001"), 1
        )

    def test_duplicate_occurrences_have_distinct_identity_and_survive_round_trip(self):
        ledger = d5_sequence()
        occurrences = ledger.records_of_family(FollowupFamily.SEQUENCE_OCCURRENCE)
        repeats = [row for row in occurrences if row.source_id == "801503002"]
        self.assertEqual(len(repeats), 3)
        identities = {row.occurrence_identity() for row in repeats}
        self.assertEqual(len(identities), 3)
        restored = FollowupLedger.from_dict(ledger.to_dict())
        self.assertEqual(restored, ledger)
        self.assertEqual(
            [row.occurrence_identity() for row in restored.records_of_family(
                FollowupFamily.SEQUENCE_OCCURRENCE)],
            [row.occurrence_identity() for row in occurrences],
        )

    def test_exact_sequence_identity_survives_the_round_trip(self):
        ledger = d5_sequence()
        restored = FollowupLedger.from_dict(ledger.to_dict())
        self.assertEqual(restored.to_dict(), ledger.to_dict())
        first = ledger.records_of_family(FollowupFamily.SEQUENCE_OCCURRENCE)[0]
        same = next(
            row
            for row in restored.records_of_family(FollowupFamily.SEQUENCE_OCCURRENCE)
            if row.occurrence_identity() == first.occurrence_identity()
        )
        self.assertEqual(same.source_id, first.source_id)
        self.assertIs(same.state, FollowupState.EXACT)
        # The exact SkillTriggerKey and SkillID the artifact recorded are still
        # carried verbatim, and are not reinterpreted.
        self.assertEqual(
            first.payload["skill_trigger_key"].require_present(), "Skill01"
        )
        self.assertEqual(
            first.payload["monster_skill_row"].require_present()["SkillID"],
            801503001,
        )

    def test_sequence_sources_keep_kind_order_and_repeat_counts(self):
        ledger = d5_sequence()
        sources = ledger.records_of_family(FollowupFamily.SEQUENCE_SOURCE)
        self.assertEqual(len(sources), 4)
        kinds = [row.payload["kind"].require_present() for row in sources]
        self.assertEqual(kinds.count("TEMPLATE"), 3)
        self.assertEqual(kinds.count("MONSTER_OVERRIDE"), 1)
        self.assertEqual(kinds, ["TEMPLATE", "TEMPLATE", "TEMPLATE", "MONSTER_OVERRIDE"])

    def test_no_ai_execution_permission(self):
        ledger = d5_sequence()
        for name in (
            "execute", "apply", "commit", "run", "select_winner",
            "resolve_winner", "default_dse", "draw", "permit",
            "execution_permitted", "supported", "is_supported",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ledger, name))
                self.assertFalse(hasattr(FollowupState, name))
        # And nothing here may become a native contract.
        from hsr_battle_agent.battle_sandbox.evidence_boundary import (
            EvidenceBoundaryError,
            require_native_contract,
        )

        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(ledger, role="followup ledger")


# ---------------------------------------------------------------------------
# D5 -- binding ledger
# ---------------------------------------------------------------------------

class TestD5BindingLedger(unittest.TestCase):
    def test_record_counts_match_the_declared_once_cross_checked(self):
        ledger = d5_binding()
        self.assertEqual(len(ledger.records_of_family(FollowupFamily.MONSTER_RECORD)), 14)
        self.assertEqual(len(ledger.records_of_family(FollowupFamily.TEMPLATE_RECORD)), 6)
        self.assertEqual(len(ledger.records_of_family(FollowupFamily.MONSTER_BINDING)), 14)
        self.assertEqual(len(D5_BINDING_DOC["monster_records"]), 14)
        self.assertEqual(len(D5_BINDING_DOC["template_records"]), 6)
        self.assertEqual(ledger.metric("join_summary/monster_rows"), 14)
        self.assertEqual(ledger.metric("join_summary/template_rows"), 6)

    def test_per_field_statuses_stay_separate_and_are_not_collapsed(self):
        ledger = d5_binding()
        self.assertEqual(ledger.state_count("static_policy_field_status/EXACT"), 15)
        self.assertEqual(ledger.state_count("static_policy_field_status/MISSING"), 13)
        # 13 MISSING override paths must not be folded into the EXACT count.
        self.assertNotEqual(
            ledger.state_count("static_policy_field_status/EXACT"),
            ledger.state_count("static_policy_field_status/MISSING"),
        )
        independent = Counter(
            field["status"]
            for binding in D5_BINDING_DOC["bindings"]
            for field in binding["static_policy_fields_in_source_order"]
        )
        self.assertEqual(independent["EXACT"], 15)
        self.assertEqual(independent["MISSING"], 13)

    def test_unresolved_precedence_is_the_recorded_monster_only(self):
        ledger = d5_binding()
        self.assertEqual(ledger.state_count("monster_binding/UNRESOLVED_PRECEDENCE"), 1)
        records = ledger.records_in_state(FollowupState.UNRESOLVED_PRECEDENCE)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_id, "801503001")
        self.assertEqual(
            D5_BINDING_DOC["join_summary"]["unresolved_precedence_monster_ids"],
            [801503001],
        )
        # No other binding may be upgraded or downgraded to match it.
        for record in ledger.records_of_family(FollowupFamily.MONSTER_BINDING):
            with self.subTest(monster=record.source_id):
                if record.source_id != "801503001":
                    self.assertIsNot(record.state, FollowupState.UNRESOLVED_PRECEDENCE)

    def test_policy_skill_edge_totals_are_not_combined_into_one_number(self):
        ledger = d5_binding()
        self.assertEqual(ledger.metric("join_summary/policy_skill_edges_total"), 312)
        self.assertEqual(ledger.metric("join_summary/policy_skill_edges_exact"), 293)
        self.assertEqual(ledger.metric("join_summary/policy_skill_edges_missing"), 19)
        self.assertEqual(
            ledger.metric("join_summary/policy_skill_edges_exact")
            + ledger.metric("join_summary/policy_skill_edges_missing"),
            ledger.metric("join_summary/policy_skill_edges_total"),
        )
        self.assertEqual(ledger.metric("join_summary/groupname_consumer_edges_exact"), 0)

    def test_duplicate_override_sequence_is_preserved_verbatim(self):
        ledger = d5_binding()
        elements = ledger.records_of_family(FollowupFamily.DUPLICATE_OVERRIDE_ELEMENT)
        self.assertEqual(len(elements), 4)
        self.assertEqual(
            [row.source_id for row in elements],
            ["801503001", "801503002", "801503002", "801503001"],
        )
        self.assertEqual(ledger.metric("join_summary/duplicate_override_sequence_preserved"), 4)
        # Repeats are kept as separate positions with distinct occurrence
        # identities, so ``a, b, b, a`` is not deduplicated into ``a, b``.
        identities = [row.occurrence_identity() for row in elements]
        self.assertEqual(len(set(identities)), 4)
        self.assertEqual(elements[1].source_id, elements[2].source_id)
        self.assertNotEqual(identities[1], identities[2])
        self.assertEqual(elements[0].source_id, elements[3].source_id)
        self.assertNotEqual(identities[0], identities[3])
        restored = FollowupLedger.from_dict(ledger.to_dict())
        self.assertEqual(
            [row.source_id for row in restored.records_of_family(
                FollowupFamily.DUPLICATE_OVERRIDE_ELEMENT)],
            ["801503001", "801503002", "801503002", "801503001"],
        )

    def test_round_trip_is_exact(self):
        ledger = d5_binding()
        self.assertEqual(FollowupLedger.from_dict(ledger.to_dict()), ledger)
        self.assertEqual(
            FollowupLedger.from_dict(json.loads(json.dumps(ledger.to_dict()))).to_dict(),
            ledger.to_dict(),
        )


# ---------------------------------------------------------------------------
# D8 -- trace joins, missing joins, behaviour candidates
# ---------------------------------------------------------------------------

class TestD8TraceJoins(unittest.TestCase):
    def test_4696_exact_trace_joins_are_preserved(self):
        self.assertEqual(
            d8().state_count("coverage_after/Trace/exact_composite_raw_joins/EXACT"),
            4696,
        )
        independent = D8_DOC["coverage_after"]["Trace"]["exact_composite_raw_joins"]
        self.assertEqual(independent["EXACT"], 4696)
        self.assertEqual(independent["AMBIGUOUS"], 0)
        self.assertEqual(independent["MISSING"], 322)

    def test_322_missing_joins_remain_missing(self):
        ledger = d8()
        self.assertEqual(
            ledger.state_count("coverage_after/Trace/exact_composite_raw_joins/MISSING"),
            322,
        )
        self.assertEqual(
            ledger.state_count("coverage_after/Trace/exact_composite_raw_joins/AMBIGUOUS"),
            0,
        )
        # 4696 + 0 + 322 must account for the 5018 existing static rows.
        self.assertEqual(
            ledger.metric("coverage_after/Trace/existing_static_rows"), 5018
        )
        self.assertEqual(4696 + 0 + 322, 5018)

    def test_missing_joins_are_not_turned_into_matches(self):
        ledger = d8()
        missing = ledger.records_in_state(FollowupState.MISSING)
        self.assertTrue(missing)
        for record in missing:
            with self.subTest(pointer=record.source_pointer):
                self.assertIsNot(record.state, FollowupState.EXACT)
        # The ledger's own MISSING tally is on its own path, never merged with
        # the composite counter above.
        self.assertEqual(ledger.state_count("exact_join_ledger/MISSING"), 370)
        self.assertEqual(ledger.state_count("exact_join_ledger/EXACT"), 6458)
        self.assertEqual(
            ledger.state_count("exact_join_ledger/NOT_INSPECTED_OUT_OF_SCOPE"), 620
        )

    def test_composite_join_pointer_shape_is_preserved(self):
        # 4696 composite joins carry a *list* of pointers; the rest a string.
        # The shape is a recorded distinction and must not be flattened.
        ledger = d8()
        joins = ledger.records_of_family(FollowupFamily.EXACT_JOIN)
        composite = [row for row in joins if row.has_composite_pointer()]
        single = [row for row in joins if not row.has_composite_pointer()]
        self.assertEqual(len(composite), 4696)
        self.assertEqual(len(single), 2752)
        independent = sum(
            1
            for row in D8_DOC["exact_join_ledger"]
            if isinstance(row["source_pointer"], list)
        )
        self.assertEqual(independent, 4696)
        for row in composite[:3]:
            self.assertIsInstance(row.source_pointer, tuple)
        for row in single[:3]:
            self.assertIsInstance(row.source_pointer, str)
        restored = FollowupLedger.from_dict(ledger.to_dict())
        restored_joins = restored.records_of_family(FollowupFamily.EXACT_JOIN)
        self.assertEqual(
            sum(1 for row in restored_joins if row.has_composite_pointer()), 4696
        )

    def test_a_one_element_composite_pointer_does_not_become_a_string(self):
        ledger = d8()
        composite = [
            row
            for row in ledger.records_of_family(FollowupFamily.EXACT_JOIN)
            if row.has_composite_pointer()
        ]
        one = [row for row in composite if len(row.source_pointer_values()) == 1]
        self.assertTrue(one)
        restored = FollowupRecord.from_dict(one[0].to_dict())
        self.assertTrue(restored.has_composite_pointer())
        self.assertEqual(restored.to_dict(), one[0].to_dict())


class TestD8BehaviourCandidates(unittest.TestCase):
    def test_136_candidates_are_preserved(self):
        ledger = d8()
        self.assertEqual(
            ledger.state_count(
                "coverage_after/Eidolon/behavior_candidates/EXACT_EXISTING_DEFINITION"
            ),
            136,
        )
        self.assertEqual(len(ledger.records_of_family(FollowupFamily.BEHAVIOR_CANDIDATE)), 136)
        independent = D8_DOC["coverage_after"]["Eidolon"]["behavior_candidates"]
        self.assertEqual(independent["EXACT_EXISTING_DEFINITION"], 136)
        self.assertEqual(independent["MISSING_DEFINITION"], 0)
        self.assertEqual(independent["AMBIGUOUS_DEFINITION"], 0)

    def test_candidates_keep_their_actual_classification(self):
        ledger = d8()
        candidates = ledger.records_of_family(FollowupFamily.BEHAVIOR_CANDIDATE)
        classifications = {
            row.payload["candidate_classification"].require_present()
            for row in candidates
        }
        self.assertEqual(classifications, {"EXACT_EXISTING_DEFINITION"})
        owners = {
            row.payload["owner_context"].require_present() for row in candidates
        }
        self.assertEqual(owners, {"UNKNOWN_UNLESS_INDEPENDENTLY_PROVED"})

    def test_a_candidate_is_not_an_activation_claim(self):
        ledger = d8()
        candidates = ledger.records_of_family(FollowupFamily.BEHAVIOR_CANDIDATE)
        self.assertEqual(len(candidates), 136)
        # The candidate's classification is carried verbatim, not resolved.
        self.assertEqual(
            {
                row.payload["candidate_classification"].require_present()
                for row in candidates
            },
            {"EXACT_EXISTING_DEFINITION"},
        )
        for record in candidates[:10]:
            for forbidden in (
                "activation", "activated", "cumulative", "threshold",
                "relic", "inherited", "executable", "resolved",
            ):
                with self.subTest(pointer=record.source_pointer, field=forbidden):
                    self.assertNotIn(forbidden, record.payload)
        # No activation-style claim was added to the state register either.
        for path in ledger.state_counts:
            with self.subTest(path=path):
                for token in ("activation", "cumulative", "threshold", "relic",
                              "inherited", "executable"):
                    self.assertNotIn(token, path.lower())
        for member in FollowupState:
            with self.subTest(state=member.name):
                for token in ("ACTIVAT", "CUMULATIVE", "THRESHOLD", "RELIC", "EXECUT"):
                    self.assertNotIn(token, member.name)

    def test_rank_and_skill_edges_are_counted_separately(self):
        ledger = d8()
        self.assertEqual(ledger.metric("coverage_after/Eidolon/raw_rows_found"), 546)
        self.assertEqual(ledger.metric("coverage_after/Eidolon/raw_rows_missing"), 36)
        self.assertEqual(
            ledger.metric("coverage_after/Eidolon/exact_skill_level_override_edges"), 488
        )
        self.assertEqual(len(ledger.records_of_family(FollowupFamily.SKILL_ADD_LEVEL_EDGE)), 488)
        self.assertEqual(ledger.metric("coverage_after/Eidolon/RankAbility_present"), 58)
        self.assertEqual(ledger.metric("coverage_after/Eidolon/SkillAddLevelList_nonempty"), 182)

    def test_recorded_absences_stay_absent(self):
        ledger = d8()
        absent = ledger.records_of_family(FollowupFamily.ABSENT_ROW)
        self.assertEqual(len(absent), 201)
        self.assertEqual(ledger.state_count("absent_rows/ABSENT_AT_PINNED_COMMIT"), 201)
        self.assertEqual(
            {row.state for row in absent}, {FollowupState.ABSENT_AT_PINNED_COMMIT}
        )
        independent = Counter(row["request"] for row in D8_DOC["absent_rows"])
        self.assertEqual(independent["Trace"], 111)
        self.assertEqual(independent["Eidolon"], 36)
        self.assertEqual(independent["AvatarConfig"], 6)
        self.assertEqual(independent["Missing SkillIDs"], 48)

    def test_remaining_gaps_keep_status_and_reason(self):
        ledger = d8()
        gaps = ledger.records_of_family(FollowupFamily.REMAINING_GAP)
        self.assertEqual(len(gaps), 3)
        self.assertEqual(ledger.state_count("remaining_content_gaps/STILL_CONTENT_BLOCKED"), 2)
        self.assertEqual(ledger.state_count("remaining_content_gaps/SOURCE_VERSION_LIMITED"), 1)
        for record in gaps:
            with self.subTest(portion=record.source_id):
                self.assertTrue(record.unknown_reason.is_present())


# ---------------------------------------------------------------------------
# D9 -- absence
# ---------------------------------------------------------------------------

class TestD9Absence(unittest.TestCase):
    def test_the_requested_path_is_absent_at_the_pinned_commit(self):
        ledger = d9()
        self.assertEqual(ledger.status, "BLOCKED_BY_CONTENT_COVERAGE")
        self.assertEqual(ledger.source_order("attempted_paths"), (STAGE_COMMON_TEMPLATE_PATH,))
        self.assertEqual(
            D9_DOC["request_result"]["result"], "ABSENT_AT_PINNED_COMMIT"
        )
        self.assertEqual(
            D9_DOC["request_result"]["lookup_result"], "ABSENT_AT_PINNED_COMMIT"
        )
        self.assertEqual(ledger.state_count("request_result/ABSENT_AT_PINNED_COMMIT"), 1)

    def test_no_alternate_stage_file_is_substituted(self):
        ledger = d9()
        # Exactly one path was attempted, and it is the requested one.
        self.assertEqual(ledger.metric("validation/attempted_path_count"), 1)
        self.assertEqual(len(ledger.source_order("attempted_paths")), 1)
        self.assertEqual(
            D9_DOC["request_result"]["action_after_absence"],
            "STOPPED_WITHOUT_NEIGHBOR_PATH_SEARCH_OR_FETCH",
        )
        self.assertIs(D9_DOC["validation"]["neighbor_path_guessing"], False)
        self.assertIs(D9_DOC["validation"]["recursive_discovery"], False)
        request_record = ledger.records_of_family(FollowupFamily.SOURCE_REQUEST)[0]
        self.assertEqual(request_record.source_id, STAGE_COMMON_TEMPLATE_PATH)
        # No second source path and no other Stage document is represented: the
        # only path-bearing facts are the requested one, its cache location and
        # the recorded absence.
        for name in ledger.source_orders:
            for value in ledger.source_order(name):
                with self.subTest(value=value):
                    self.assertEqual(value, STAGE_COMMON_TEMPLATE_PATH)
        self.assertEqual(
            sorted(ledger.source_orders), ["attempted_paths"]
        )
        # The portions the ticket excluded are recorded as excluded facts, not
        # as substituted content; each carries no reason and no structure.
        excluded = [
            row
            for row in ledger.records_of_family(FollowupFamily.REMAINING_GAP)
            if row.state is FollowupState.EXCLUDED_BY_TICKET
        ]
        self.assertEqual(len(excluded), 4)
        for row in excluded:
            with self.subTest(portion=row.source_id):
                self.assertTrue(row.unknown_reason.is_absent())
                self.assertNotIn("source_pointer_value", row.payload)

    def test_the_absent_path_leaves_no_invented_hash(self):
        # The source records null for the absent path; null survives as null and
        # must not become a fabricated hash, size or document.
        self.assertIsNone(D9_DOC["source"]["raw_sha256"])
        self.assertIsNone(D9_DOC["source"]["bytes"])
        self.assertIsNone(D9_DOC["source"]["top_level_json_type"])
        ledger = d9()
        self.assertIsNone(ledger.provenance.content_sha256)
        record = ledger.records_of_family(FollowupFamily.SOURCE_REQUEST)[0]
        self.assertIs(record.state, FollowupState.ABSENT_AT_PINNED_COMMIT)
        self.assertEqual(
            record.payload["requested_path"].require_present(),
            STAGE_COMMON_TEMPLATE_PATH,
        )
        self.assertEqual(
            record.payload["result"].require_present(), "ABSENT_AT_PINNED_COMMIT"
        )
        self.assertEqual(
            record.payload["cache_lookup_path"].require_present(),
            ".external_refs/TurnBasedGameData/files/Config/Level/"
            "StageCommonTemplate.json",
        )
        self.assertEqual(
            record.unknown_reason.require_present(),
            "STOPPED_WITHOUT_NEIGHBOR_PATH_SEARCH_OR_FETCH",
        )

    def test_no_native_wave_or_terminal_structure_appears(self):
        ledger = d9()
        for name in ("node_index", "edge_index", "stage_config_key_refs",
                     "wave_spawn_refs", "terminal_refs", "behavior_refs",
                     "external_dependency_refs"):
            with self.subTest(index=name):
                self.assertEqual(ledger.metric(f"indexes/{name}"), 0)
                self.assertEqual(D9_DOC[name], [])
        self.assertEqual(
            D9_DOC["graph_structure"]["status"],
            "NOT_AVAILABLE_BECAUSE_EXACT_REQUESTED_PATH_IS_ABSENT_AT_PINNED_COMMIT",
        )
        self.assertIs(D9_DOC["graph_structure"]["raw_document_persisted"], False)
        self.assertEqual(
            ledger.metric("graph_structure/top_level_keys_types"), 0
        )

    def test_excluded_portions_are_marked_excluded_not_present(self):
        ledger = d9()
        gaps = ledger.records_of_family(FollowupFamily.REMAINING_GAP)
        self.assertEqual(len(gaps), 5)
        self.assertEqual(ledger.state_count("remaining_content_gaps/EXCLUDED_BY_TICKET"), 4)
        self.assertEqual(
            ledger.state_count("remaining_content_gaps/BLOCKED_BY_CONTENT_COVERAGE"), 1
        )
        excluded = [row for row in gaps if row.state is FollowupState.EXCLUDED_BY_TICKET]
        self.assertEqual(len(excluded), 4)
        for row in excluded:
            with self.subTest(portion=row.source_id):
                self.assertTrue(row.unknown_reason.is_absent())


# ---------------------------------------------------------------------------
# Global invariants
# ---------------------------------------------------------------------------

class TestGlobalInvariants(unittest.TestCase):
    def test_all_five_artifacts_load_and_round_trip(self):
        self.assertEqual(len(_ALL), 5)
        self.assertEqual(
            [ledger.artifact for ledger in _ALL],
            [
                D5_ACQUISITION, D5_BINDING, D5_SEQUENCE, D8_ARTIFACT, D9_ARTIFACT,
            ],
        )
        self.assertEqual(
            [ledger.domain for ledger in _ALL],
            [
                FollowupDomain.D5_MONSTER_AI,
                FollowupDomain.D5_MONSTER_AI,
                FollowupDomain.D5_MONSTER_AI,
                FollowupDomain.D8_EQUIPMENT_TRACE_EIDOLON,
                FollowupDomain.D9_STAGE_ENVIRONMENT_MODE,
            ],
        )
        # Full-document round trip on the small ledgers (30, 38, 9 and 6
        # records); D8's exact round trip is asserted in its own test, once,
        # because a deep compare of two 8276-record documents is expensive.
        for ledger in _ALL:
            if ledger.artifact == D8_ARTIFACT:
                continue
            with self.subTest(artifact=ledger.artifact):
                restored = FollowupLedger.from_dict(ledger.to_dict())
                self.assertEqual(restored, ledger)
                self.assertEqual(restored.to_dict(), ledger.to_dict())
                self.assertEqual(
                    FollowupLedger.from_dict(
                        json.loads(json.dumps(ledger.to_dict()))
                    ).to_dict(),
                    ledger.to_dict(),
                )

    def test_the_d8_document_round_trips_exactly(self):
        ledger = _D8
        document = ledger.to_dict()
        restored = FollowupLedger.from_dict(document)
        self.assertEqual(restored.to_dict(), document)
        self.assertEqual(restored, ledger)
        self.assertEqual(
            restored.state_counts, ledger.state_counts
        )
        self.assertEqual(len(restored.records), len(ledger.records))

    def test_every_record_round_trips_individually(self):
        # A single pass over each ledger, sampled to keep the suite fast; the
        # whole-ledger round trip is asserted separately.
        for ledger in _ALL:
            for index, record in enumerate(ledger.records):
                if index % 401:
                    continue
                with self.subTest(artifact=ledger.artifact, ordinal=index):
                    self.assertEqual(
                        FollowupRecord.from_dict(record.to_dict()), record
                    )

    def test_source_order_carries_source_position_and_never_reranks(self):
        # Position within a family is the source position: dense, ascending and
        # starting at zero.  The module copies position and never re-ranks or
        # sorts by id, pointer or value.
        for ledger in _ALL:
            with self.subTest(artifact=ledger.artifact):
                by_family: dict[FollowupFamily, list[int]] = {}
                for row in ledger.records:
                    by_family.setdefault(row.family, []).append(row.ordinal)
                self.assertTrue(by_family)
                for family, ordinals in by_family.items():
                    with self.subTest(family=family.name):
                        self.assertEqual(ordinals, list(range(len(ordinals))))

    def test_evidence_mode_is_preserved_exactly(self):
        for ledger in _ALL:
            with self.subTest(artifact=ledger.artifact):
                self.assertIs(ledger.evidence_mode, EvidenceMode.REFERENCE_MODEL)
                self.assertIs(ledger.evidence_mode, FOLLOWUP_EVIDENCE_MODE)
                self.assertEqual(
                    ledger.to_dict()["evidence_mode"], "REFERENCE_MODEL"
                )
        # Mode identity survives a full round trip on a small ledger.
        restored = FollowupLedger.from_dict(d5_sequence().to_dict())
        self.assertIs(restored.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIs(restored.evidence_mode, d5_sequence().evidence_mode)

    def test_the_native_mode_is_refused_outright(self):
        for parser, document in (
            (parse_d5_sequence_id_binding, D5_SEQ_DOC),
            (parse_d5_binding_ledger, D5_BINDING_DOC),
            (parse_d5_content_acquisition, D5_ACQ_DOC),
            (parse_d8_content_followup, D8_DOC),
            (parse_d9_content_followup, D9_DOC),
        ):
            with self.subTest(parser=parser.__name__):
                with self.assertRaises(FollowupLedgerError):
                    parser(document, evidence_mode=EvidenceMode.NATIVE_EVIDENCED)
                with self.assertRaises(FollowupLedgerError):
                    parser(document, evidence_mode="NATIVE_EVIDENCED")

    def test_provenance_records_the_commit_and_the_close_relation(self):
        for ledger in _ALL:
            with self.subTest(artifact=ledger.artifact):
                self.assertEqual(
                    ledger.provenance.source_commit,
                    "b11066beacc4de454b625fafc7ea3dd540c5bbf3",
                )
                self.assertEqual(ledger.provenance.game_version, "4.4.54")
                # A close version never becomes exact native.
                from hsr_battle_agent.battle_ir.provenance import VersionRelation

                if ledger.provenance.version_relation is not None:
                    self.assertIs(
                        ledger.provenance.version_relation,
                        VersionRelation.CLOSE_VERSION,
                    )
                    self.assertIsNot(
                        ledger.provenance.version_relation,
                        VersionRelation.EXACT_NATIVE,
                    )

    # -- fail-closed behaviour --------------------------------------------

    def test_malformed_state_spellings_fail_closed(self):
        for value in (
            None, "", "exact", "EXACT ", "Supported", "SUPPORTED", "OK",
            "TRUE", "RESOLVED", 0, 1, True, [], {},
        ):
            with self.subTest(value=value):
                with self.assertRaises(FollowupLedgerError):
                    parse_followup_state(value)

    def test_a_malformed_state_in_a_document_fails_closed(self):
        document = copy.deepcopy(D5_SEQ_DOC)
        document["sequence_occurrences"][0]["status"] = "SUPPORTED"
        with self.assertRaises(FollowupLedgerError):
            parse_d5_sequence_id_binding(document)
        document = copy.deepcopy(D8_DOC)
        document["exact_join_ledger"][0]["status"] = "exact"
        with self.assertRaises(FollowupLedgerError):
            parse_d8_content_followup(document)

    def test_a_disagreeing_declared_count_stops_and_reports_the_difference(self):
        # C02-001's stop condition: never patch the count.
        document = copy.deepcopy(D5_SEQ_DOC)
        document["summary"]["sequence_occurrences"] = 14
        with self.assertRaises(FollowupLedgerError) as caught:
            parse_d5_sequence_id_binding(document)
        message = str(caught.exception)
        self.assertIn("summary.sequence_occurrences", message)
        self.assertIn("14", message)
        self.assertIn("15", message)

    def test_a_disagreeing_d8_composite_total_stops(self):
        document = copy.deepcopy(D8_DOC)
        document["coverage_after"]["Trace"]["existing_static_rows"] = 5019
        with self.assertRaises(FollowupLedgerError) as caught:
            parse_d8_content_followup(document)
        self.assertIn("existing_static_rows", str(caught.exception))

    def test_an_absent_artifact_is_not_substituted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(FollowupLedgerError) as caught:
                load_followup_ledgers(empty)
            self.assertIn("does not substitute another file", str(caught.exception))
        with self.assertRaises(FollowupLedgerError):
            load_followup_ledgers(BASE / "no-such-directory")

    def test_unknown_paths_and_metrics_fail_closed(self):
        ledger = d5_sequence()
        with self.assertRaises(FollowupLedgerError):
            ledger.state_count("summary/status_counts/NOT_A_STATE")
        with self.assertRaises(FollowupLedgerError):
            ledger.state_count("no/such/path")
        with self.assertRaises(FollowupLedgerError):
            ledger.metric("no/such/metric")
        with self.assertRaises(FollowupLedgerError):
            ledger.source_order("no_such_order")

    def test_missing_and_extra_fields_reject(self):
        record = d5_sequence().records[0].to_dict()
        for key in sorted(record):
            with self.subTest(missing=key):
                broken = copy.deepcopy(record)
                broken.pop(key)
                with self.assertRaises(FollowupLedgerError):
                    FollowupRecord.from_dict(broken)
        extra = copy.deepcopy(record)
        extra["supported"] = True
        with self.assertRaises(FollowupLedgerError):
            FollowupRecord.from_dict(extra)
        ledger = d5_sequence().to_dict()
        extra_ledger = copy.deepcopy(ledger)
        extra_ledger["executable"] = True
        with self.assertRaises(FollowupLedgerError):
            FollowupLedger.from_dict(extra_ledger)

    def test_a_bad_pointer_shape_rejects(self):
        record = d5_sequence().records[0].to_dict()
        broken = copy.deepcopy(record)
        broken["source_pointer"]["shape"] = "MAYBE"
        with self.assertRaises(FollowupLedgerError):
            FollowupRecord.from_dict(broken)
        broken = copy.deepcopy(record)
        broken["source_pointer"] = "/0"
        with self.assertRaises(FollowupLedgerError):
            FollowupRecord.from_dict(broken)

    # -- no dangerous surface ---------------------------------------------

    FORBIDDEN_NAMES = (
        "execute", "apply", "commit", "run", "perform", "issue_gate_certificate",
        "as_native_contract", "gate_certificate", "native_contract",
        "execution_permitted", "supported", "is_supported", "ready",
        "is_ready", "match", "fuzzy_match", "nearest", "closest", "similar",
        "normalize_id", "guess", "infer", "promote",
    )

    def test_no_forbidden_surface_exists_on_any_type(self):
        for type_ in (FollowupLedger, FollowupRecord, FollowupState,
                      FollowupFamily, FollowupDomain):
            for name in self.FORBIDDEN_NAMES:
                with self.subTest(type=type_.__name__, name=name):
                    self.assertFalse(hasattr(type_, name))

    def test_no_state_predicate_can_be_read_as_a_gate(self):
        for member in FollowupState:
            with self.subTest(state=member.name):
                with self.assertRaises(FollowupLedgerError):
                    bool(member)
                for name in ("is_exact", "is_resolved", "is_supported",
                             "executable", "implies_execution"):
                    self.assertFalse(hasattr(member, name))

    def test_no_truthiness_escape_on_a_record_or_ledger(self):
        for value in (d5_sequence(), d8(), d9()):
            with self.subTest(artifact=value.artifact):
                with self.assertRaises(FollowupLedgerError):
                    bool(value)
                with self.assertRaises(FollowupLedgerError):
                    bool(value.records[0])
        # The literal anti-pattern the task forbids: ``if ledger: promote()``.
        permitted = []
        with self.assertRaises(FollowupLedgerError):
            if d8():  # pragma: no cover - must raise before this branch
                permitted.append("LEDGER_PASSED_THE_GATE")
        self.assertEqual(permitted, [])

    def test_the_module_performs_no_pattern_matching_or_numeric_coercion(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for banned in ("re", "difflib", "fuzzywuzzy", "rapidfuzz", "Levenshtein"):
            with self.subTest(module=banned):
                self.assertNotIn(banned, imported)
        # No int() coercion anywhere: a source id must never pass through int.
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"int", "float", "bool"}
        }
        self.assertEqual(calls, set())
        # No string-normalization helpers: these would let a near-match be
        # manufactured out of a string that is not literally equal.
        attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr in {"lower", "upper", "casefold", "startswith",
                              "endswith", "replace", "find", "search"}
        }
        self.assertEqual(attributes, set())
        # ``strip`` appears, but only as a fail-closed check that a token carries
        # no surrounding whitespace -- never to normalise a stored value.  Pin
        # the single site so a future edit cannot start coercing ids with it.
        sites = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            for inner in ast.walk(node)
            if isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == "strip"
        }
        self.assertEqual(sites, {"_require_token"})

    def test_the_shared_ledger_instances_were_not_polluted_by_other_tests(self):
        # The suite shares parsed ledgers; this proves no test mutated one.
        self.assertEqual(parse_d5_sequence_id_binding(D5_SEQ_DOC), _D5_SEQ)
        self.assertEqual(parse_d5_binding_ledger(D5_BINDING_DOC), _D5_BINDING)
        self.assertEqual(parse_d8_content_followup(D8_DOC), _D8)
        self.assertEqual(parse_d9_content_followup(D9_DOC), _D9)

    def test_the_module_never_imports_the_gate_or_native_surface(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add(alias.name)
        for banned in ("GateCertificate", "NativeContract",
                       "issue_gate_certificate", "require_native_contract",
                       "certify_native_contract"):
            with self.subTest(name=banned):
                self.assertNotIn(banned, names)
        source_text = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("evidence_boundary", source_text)

    def test_the_module_defines_no_matching_helper(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        public_functions = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        self.assertEqual(
            sorted(public_functions),
            [
                "load_followup_ledgers",
                "parse_d5_binding_ledger",
                "parse_d5_content_acquisition",
                "parse_d5_sequence_id_binding",
                "parse_d8_content_followup",
                "parse_d9_content_followup",
                "parse_followup_state",
                "require_evidence_mode",
            ],
        )
        for name in public_functions:
            with self.subTest(name=name):
                for token in ("match", "fuzzy", "nearest", "similar", "join",
                              "resolve", "infer", "guess", "promote", "support"):
                    self.assertNotIn(token, name)


# ---------------------------------------------------------------------------
# Mutation isolation (house pattern from the R01 and G01 correctives)
# ---------------------------------------------------------------------------

class TestMutationIsolation(unittest.TestCase):
    """Isolation is a type property, so the small ledgers carry these tests.

    The full-document comparison is the assertion that matters, and it is run on
    a ledger small enough to compare completely; D8 keeps one family-scoped
    check because a deep compare of two 8276-record documents is needlessly slow.
    """

    def test_mutating_a_source_document_after_parse_is_isolated(self):
        document = copy.deepcopy(D5_SEQ_DOC)
        ledger = parse_d5_sequence_id_binding(document)
        before = ledger.to_dict()
        document["sequence_occurrences"][0]["raw_id"] = 999
        document["summary"]["blocked"] = 7
        document["requested_ids"].append(1)
        self.assertEqual(ledger.to_dict(), before)
        self.assertEqual(ledger.metric("summary/blocked"), 0)

    def test_a_returned_document_cannot_rewrite_the_ledger(self):
        ledger = d5_sequence()
        before = ledger.to_dict()
        exported = ledger.to_dict()
        exported["records"][0]["source_id"] = "REWRITTEN"
        exported["records"][0]["source_pointer"]["values"][0] = "REWRITTEN"
        exported["state_counts"][0]["count"] = 1
        exported["records"][0]["state"] = "MISSING"
        payload_value = exported["records"][0]["payload"][0]["value"]
        if isinstance(payload_value.get("value"), dict):
            payload_value["value"]["status"] = "REWRITTEN"
        self.assertEqual(ledger.to_dict(), before)
        self.assertNotEqual(ledger.records[0].source_id, "REWRITTEN")
        self.assertEqual(
            ledger.records[0].source_id,
            str(D5_SEQ_DOC["monster_skill_rows"][0]["SkillID"]),
        )

    def test_a_returned_d8_family_cannot_rewrite_the_d8_ledger(self):
        family = FollowupFamily.EXACT_JOIN
        observed = d8().records_of_family(family)[:5]
        before = [row.to_dict() for row in observed]
        # The container is an immutable tuple, and each record is a fresh copy.
        self.assertIsInstance(observed, tuple)
        with self.assertRaises(AttributeError):
            observed.append(observed[0])
        self.assertIsNot(observed[0], d8().records_of_family(family)[0])
        observed[0].payload["status"]
        observed[0].payload
        self.assertEqual(
            [row.to_dict() for row in d8().records_of_family(family)[:5]], before
        )

    def test_payload_reads_are_detached(self):
        ledger = d8()
        family = FollowupFamily.BEHAVIOR_CANDIDATE
        before = [
            row.to_dict()
            for row in ledger.records_of_family(family)[:3]
        ]
        owned = ledger.records_of_family(family)[0].payload["candidates"].require_present()
        self.assertIsInstance(owned, list)
        owned.clear()
        self.assertEqual(
            [row.to_dict() for row in ledger.records_of_family(family)[:3]], before
        )
        self.assertTrue(
            ledger.records_of_family(family)[0]
            .payload["candidates"]
            .require_present()
        )

    def test_every_public_read_returns_a_fresh_object_or_immutable_scalar(self):
        ledger = d5_sequence()
        for name in ("records", "state_counts", "metric_counts", "source_orders",
                     "provenance"):
            with self.subTest(name=name):
                self.assertIsNot(getattr(ledger, name), getattr(ledger, name))
        for name in ("artifact", "status", "domain", "schema_id", "evidence_mode"):
            with self.subTest(name=name):
                self.assertIs(getattr(ledger, name), getattr(ledger, name))
        self.assertIsNot(ledger.records[0], ledger.records[0])
        record = ledger.records[0]
        for name in ("payload", "unknown_reason"):
            with self.subTest(name=name):
                self.assertIsNot(getattr(record, name), getattr(record, name))
        for name in ("source_id", "state", "family", "domain", "artifact", "ordinal"):
            with self.subTest(name=name):
                self.assertIs(getattr(record, name), getattr(record, name))

    def test_public_names_are_not_assignable(self):
        ledger = d5_sequence()
        before = ledger.to_dict()
        for name in ("artifact", "status", "records", "state_counts",
                     "metric_counts", "source_orders", "evidence_mode"):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(ledger, name, None)
        record = ledger.records[0]
        for name in ("source_id", "state", "family", "payload"):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(record, name, None)
        self.assertEqual(ledger.to_dict(), before)

    def test_unknown_reason_presence_is_not_collapsed(self):
        # D8's first gap records a reason, D9's excluded portions record none.
        d8_gaps = d8().records_of_family(FollowupFamily.REMAINING_GAP)
        self.assertTrue(all(row.unknown_reason.is_present() for row in d8_gaps))
        d9_excluded = [
            row
            for row in d9().records_of_family(FollowupFamily.REMAINING_GAP)
            if row.state is FollowupState.EXCLUDED_BY_TICKET
        ]
        self.assertTrue(d9_excluded)
        for row in d9_excluded:
            with self.subTest(portion=row.source_id):
                self.assertTrue(row.unknown_reason.is_absent())
                self.assertNotEqual(
                    row.unknown_reason.to_dict(), P.null().to_dict()
                )


# ---------------------------------------------------------------------------
# Authority identity
# ---------------------------------------------------------------------------

class TestFrozenAuthorityIdentity(unittest.TestCase):
    """The import must match the frozen authority's own followup registry."""

    FREEZE = BASE / "astra_semantic_freeze_v1.json"

    def registry(self) -> list[dict]:
        return json.loads(self.FREEZE.read_text(encoding="utf-8"))["followup_registry"]

    def test_the_registered_artifacts_are_exactly_these_five(self):
        declared = [
            Path(entry["artifact"]).name for entry in self.registry()
        ]
        imported = [
            name for names in FOLLOWUP_ARTIFACTS.values() for name in names
        ]
        self.assertEqual(sorted(declared), sorted(imported))
        self.assertEqual(len(imported), 5)
        self.assertEqual(
            [ledger.artifact for ledger in _ALL], imported
        )

    def test_every_registered_artifact_grants_zero_native_execution(self):
        entries = self.registry()
        self.assertEqual(len(entries), 5)
        for entry in entries:
            with self.subTest(artifact=entry["artifact"]):
                self.assertEqual(entry["native_execution_gain"], 0)
        # That is the grounding for refusing the native evidence mode.
        self.assertEqual(
            {entry["native_execution_gain"] for entry in entries}, {0}
        )

    def test_the_recorded_registry_status_matches_the_ledger_status(self):
        by_name = {Path(e["artifact"]).name: e for e in self.registry()}
        for ledger in _ALL:
            with self.subTest(artifact=ledger.artifact):
                self.assertEqual(by_name[ledger.artifact]["status"], ledger.status)

    def test_the_four_self_describing_artifacts_agree_with_the_registry(self):
        by_name = {Path(e["artifact"]).name: e for e in self.registry()}
        self_describing = {
            D5_ACQUISITION: D5_ACQ_DOC["result"],
            D5_SEQUENCE: D5_SEQ_DOC["result"],
            D8_ARTIFACT: D8_DOC["status"],
            D9_ARTIFACT: D9_DOC["status"],
        }
        for name, declared in self_describing.items():
            with self.subTest(artifact=name):
                self.assertEqual(declared, by_name[name]["status"])
        # The binding ledger declares no status of its own; its posture comes
        # from the registry, which is why the constant is named and cited.
        self.assertNotIn("status", D5_BINDING_DOC)
        self.assertNotIn("result", D5_BINDING_DOC)
        self.assertEqual(
            by_name[D5_BINDING]["status"], d5_binding().status
        )

    def test_the_consumed_documents_carry_no_duplicate_json_keys(self):
        # Duplicate keys would let a later key silently win, which is exactly the
        # loss this import must not commit.
        def hook(pairs):
            keys = [key for key, _ in pairs]
            self.assertEqual(
                len(keys), len(set(keys)), f"duplicate key in {keys}"
            )
            return dict(pairs)

        for name in (
            D5_ACQUISITION, D5_BINDING, D5_SEQUENCE, D8_ARTIFACT, D9_ARTIFACT,
        ):
            with self.subTest(artifact=name):
                json.loads(
                    (BASE / name).read_text(encoding="utf-8"),
                    object_pairs_hook=hook,
                )


if __name__ == "__main__":
    unittest.main()
