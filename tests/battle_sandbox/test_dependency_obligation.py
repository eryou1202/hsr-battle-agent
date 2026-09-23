# -*- coding: utf-8 -*-
"""G01-001 acceptance tests for the dependency-obligation representation.

The suite is built to fail if the representation is lossy *or* if it ever
becomes permissive.  Expectations are constructed independently of the
production code: literal documents are asserted against, ledger and evidence
vocabularies are cross-checked against this module's vocabulary, and the owner
code rule is cross-checked against the pre-existing ``StructuredRejection`` rule
rather than against itself.

This task is representation only, so several tests assert the *absence* of
behaviour: no closure, no traversal, no gate certificate, no execution entry
point.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import sys
import unittest
from enum import Enum
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import (  # noqa: E402
    ContractRef,
    EvidenceMode,
    UnknownHandle,
)
from hsr_battle_agent.battle_ir.lossless_value import (  # noqa: E402
    PresenceValue as P,
)
from hsr_battle_agent.battle_ir.resolution_ledger import ResolutionState  # noqa: E402
from hsr_battle_agent.battle_sandbox.errors import (  # noqa: E402
    RejectionDataError,
    StructuredRejection,
)
from hsr_battle_agent.battle_sandbox.evidence_boundary import (  # noqa: E402
    EvidenceBoundaryError,
    require_native_contract,
)
from hsr_battle_agent.battle_sandbox.preflight import (  # noqa: E402
    CHILD_OBLIGATION_REF_SCHEMA,
    DEPENDENCY_OBLIGATION_SCHEMA,
    OBLIGATION_ACCESS_SCHEMA,
    OBLIGATION_RESOLUTION_SPELLINGS,
    PUBLIC_REPRESENTATION_NAMES,
    SATISFIED_RESOLUTION,
    ChildObligationRef,
    DependencyObligation,
    DependencyObligationError,
    ObligationAccess,
    ObligationResolution,
    parse_obligation_resolution,
    require_owner_code,
)

MODULE_PATH = REPO / "src/hsr_battle_agent/battle_sandbox/preflight.py"


# ---------------------------------------------------------------------------
# Independently constructed fixtures
# ---------------------------------------------------------------------------

def contract(
    mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED,
    contract_id: str = "damage-request",
    sha: str = "a" * 64,
) -> ContractRef:
    return ContractRef(
        contract_id=contract_id,
        namespace="battle.preflight.test",
        schema_version="contract/1",
        evidence_mode=mode,
        content_sha256=sha,
        source_refs=("freeze:step_transaction_contract",),
    )


def handle(blocker_id: str = "PF-Q1") -> UnknownHandle:
    return UnknownHandle(
        blocker_id=blocker_id,
        owner_family="PREFLIGHT",
        payload={"missing": "native tie ordering"},
        provenance={"source": "freeze", "domain": "scheduler"},
        required_evidence=("native tie ordering",),
    )


def access(target: str, extent: P | None = None) -> ObligationAccess:
    return ObligationAccess(
        target=target,
        extent=P.absent() if extent is None else extent,
    )


def child(owner: str = "CHILD_OWNER", contract_id: str = "child-1") -> ChildObligationRef:
    return ChildObligationRef(
        owner=owner, contract_ref=contract(contract_id=contract_id, sha="b" * 64)
    )


def obligation(
    resolution: ObligationResolution = ObligationResolution.RESOLVED,
    mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED,
    reads=(),
    writes=(),
    children=(),
    handles=(),
    owner: str = "STEP_PREFLIGHT",
) -> DependencyObligation:
    return DependencyObligation(
        owner=owner,
        contract_ref=contract(mode),
        evidence_mode=mode,
        resolution=resolution,
        reads=tuple(reads),
        writes=tuple(writes),
        children=tuple(children),
        unknown_handles=tuple(handles),
    )


def unknown_obligation(**kwargs) -> DependencyObligation:
    kwargs.setdefault("handles", (handle(),))
    return obligation(resolution=ObligationResolution.UNKNOWN, **kwargs)


# ---------------------------------------------------------------------------
# 1. Full round trip
# ---------------------------------------------------------------------------

class TestFullRoundTrip(unittest.TestCase):
    def test_fully_populated_obligation_round_trips_exactly(self):
        original = obligation(
            reads=(
                access("state:modifier_table", P.present("ROWS")),
                access("rng:crit", P.null()),
                access("state:queues"),
            ),
            writes=(
                access("state:hp", P.present({"scope": "single"})),
                access("state:hp", P.present({"scope": "single"})),
            ),
            children=(child("CHILD_A", "c-1"), child("CHILD_A", "c-2"), child("CHILD_B", "c-1")),
        )
        document = original.to_dict()
        restored = DependencyObligation.from_dict(document)
        self.assertEqual(restored.to_dict(), document)
        self.assertEqual(restored, original)
        self.assertEqual(document["schema"], DEPENDENCY_OBLIGATION_SCHEMA)

    def test_document_key_set_is_exactly_the_declared_schema(self):
        document = obligation().to_dict()
        self.assertEqual(
            set(document),
            {
                "schema",
                "owner",
                "contract_ref",
                "evidence_mode",
                "resolution",
                "reads",
                "writes",
                "children",
                "unknown_handles",
            },
        )

    def test_missing_and_extra_fields_both_reject(self):
        document = obligation().to_dict()
        for key in sorted(document):
            with self.subTest(missing=key):
                broken = copy.deepcopy(document)
                broken.pop(key)
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation.from_dict(broken)
        extra = copy.deepcopy(document)
        extra["fallback"] = None
        with self.assertRaises(DependencyObligationError):
            DependencyObligation.from_dict(extra)

    def test_unknown_and_legacy_schemas_reject(self):
        for schema in ("dependency_obligation/2", "DESCRIPTOR", "", None):
            with self.subTest(schema=schema):
                broken = obligation().to_dict()
                broken["schema"] = schema
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation.from_dict(broken)

    def test_round_trips_through_json_without_loss(self):
        original = unknown_obligation(
            reads=(access("state:x", P.present([1, None, 3])),),
        )
        document = json.loads(json.dumps(original.to_dict()))
        restored = DependencyObligation.from_dict(document)
        self.assertEqual(
            json.loads(json.dumps(restored.to_dict())), document
        )

    def test_nested_access_and_child_documents_round_trip(self):
        item = access("state:x", P.present({"nested": [1, {"deep": None}]}))
        self.assertEqual(ObligationAccess.from_dict(item.to_dict()), item)
        self.assertEqual(item.to_dict()["schema"], OBLIGATION_ACCESS_SCHEMA)
        reference = child()
        self.assertEqual(ChildObligationRef.from_dict(reference.to_dict()), reference)
        self.assertEqual(
            reference.to_dict()["schema"], CHILD_OBLIGATION_REF_SCHEMA
        )

    def test_equality_is_the_serialized_representation(self):
        left = obligation(reads=(access("state:x", P.present(1)),))
        right = obligation(reads=(access("state:x", P.present(1)),))
        other = obligation(reads=(access("state:x", P.present(2)),))
        self.assertEqual(left, right)
        self.assertNotEqual(left, other)
        self.assertIsNot(left, right)
        with self.assertRaises(TypeError):
            hash(left)

    def test_detached_copy_keeps_content_and_is_a_new_object(self):
        original = unknown_obligation()
        clone = original.detached_copy()
        self.assertIsNot(clone, original)
        self.assertEqual(clone.to_dict(), original.to_dict())


# ---------------------------------------------------------------------------
# 2. UNKNOWN rejects / fails closed
# ---------------------------------------------------------------------------

class TestUnknownFailsClosed(unittest.TestCase):
    def test_unknown_without_a_handle_rejects(self):
        with self.assertRaises(DependencyObligationError):
            obligation(resolution=ObligationResolution.UNKNOWN)

    def test_unknown_with_a_handle_is_accepted_and_stays_unknown(self):
        item = unknown_obligation()
        self.assertIs(item.resolution, ObligationResolution.UNKNOWN)
        self.assertFalse(item.is_satisfied())
        self.assertEqual(len(item.unresolved_material), 1)

    def test_resolved_may_not_carry_unresolved_material(self):
        with self.assertRaises(DependencyObligationError):
            obligation(
                resolution=ObligationResolution.RESOLVED, handles=(handle(),)
            )

    def test_unsupported_is_settled_and_may_omit_a_handle(self):
        bare = obligation(resolution=ObligationResolution.UNSUPPORTED)
        self.assertIs(bare.resolution, ObligationResolution.UNSUPPORTED)
        self.assertFalse(bare.is_satisfied())
        self.assertEqual(bare.unresolved_material, ())
        cited = obligation(
            resolution=ObligationResolution.UNSUPPORTED, handles=(handle("PF-Q9"),)
        )
        self.assertEqual(len(cited.unresolved_material), 1)

    def test_a_missing_resolution_field_cannot_default_to_success(self):
        document = unknown_obligation().to_dict()
        document.pop("resolution")
        with self.assertRaises(DependencyObligationError):
            DependencyObligation.from_dict(document)

    def test_resolution_cannot_be_absent_or_null(self):
        for value in (None, "", "resolved", "RESOLVED "):
            with self.subTest(value=value):
                with self.assertRaises(DependencyObligationError):
                    parse_obligation_resolution(value)

    def test_unknown_is_a_real_constructed_state_in_the_vocabulary(self):
        # Guards against a future edit that quietly drops UNKNOWN and thereby
        # makes every remaining state look closed.
        self.assertIn("UNKNOWN", OBLIGATION_RESOLUTION_SPELLINGS)
        self.assertIs(
            parse_obligation_resolution("UNKNOWN"), ObligationResolution.UNKNOWN
        )


# ---------------------------------------------------------------------------
# 3. UNKNOWN is never a successful boolean gate
# ---------------------------------------------------------------------------

class TestUnknownTruthinessEscape(unittest.TestCase):
    def test_resolution_member_has_no_truthiness(self):
        for member in ObligationResolution:
            with self.subTest(member=member.name):
                with self.assertRaises(DependencyObligationError):
                    bool(member)

    def test_obligation_has_no_truthiness_in_any_state(self):
        states = {
            ObligationResolution.RESOLVED: obligation(),
            ObligationResolution.UNKNOWN: unknown_obligation(),
            ObligationResolution.UNSUPPORTED: obligation(
                resolution=ObligationResolution.UNSUPPORTED
            ),
        }
        for state, item in states.items():
            with self.subTest(state=state.name):
                with self.assertRaises(DependencyObligationError):
                    bool(item)

    def test_an_if_statement_cannot_silently_pass_a_gate(self):
        # The literal anti-pattern the task forbids: ``if obligation: permit()``.
        # It must raise rather than take the permissive branch.
        permitted = []
        item = unknown_obligation()
        with self.assertRaises(DependencyObligationError):
            if item:  # pragma: no cover - must raise before this branch
                permitted.append("UNKNOWN_PASSED_THE_GATE")
        self.assertEqual(permitted, [])

    def test_is_satisfied_is_false_for_every_unresolved_state(self):
        self.assertTrue(obligation().is_satisfied())
        self.assertFalse(unknown_obligation().is_satisfied())
        self.assertFalse(
            obligation(resolution=ObligationResolution.UNSUPPORTED).is_satisfied()
        )

    def test_only_one_member_can_ever_be_satisfied(self):
        satisfied = [
            member for member in ObligationResolution if member.is_satisfied()
        ]
        self.assertEqual(satisfied, [SATISFIED_RESOLUTION])
        self.assertIs(SATISFIED_RESOLUTION, ObligationResolution.RESOLVED)

    def test_resolved_is_not_a_permission_even_though_it_is_satisfied(self):
        item = obligation()
        self.assertTrue(item.is_satisfied())
        # A satisfied representation still cannot satisfy a native gate, and it
        # offers no execution entry point to call instead.
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(item, role="dependency obligation")
        for name in ("execute", "apply", "commit", "issue_gate_certificate"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(item, name))


# ---------------------------------------------------------------------------
# 4. Known resolution states remain distinct
# ---------------------------------------------------------------------------

class TestKnownResolutionStatesDistinct(unittest.TestCase):
    def test_the_three_states_are_separate_members_with_separate_spellings(self):
        members = tuple(ObligationResolution)
        self.assertEqual(len(members), 3)
        self.assertEqual(len(set(members)), 3)
        self.assertEqual(
            set(OBLIGATION_RESOLUTION_SPELLINGS), {"RESOLVED", "UNKNOWN", "UNSUPPORTED"}
        )
        self.assertIsNot(
            ObligationResolution.UNKNOWN, ObligationResolution.UNSUPPORTED
        )

    def test_the_three_states_produce_three_distinct_documents(self):
        documents = [
            obligation(resolution=ObligationResolution.RESOLVED).to_dict(),
            unknown_obligation().to_dict(),
            obligation(resolution=ObligationResolution.UNSUPPORTED).to_dict(),
        ]
        self.assertEqual(
            len({json.dumps(d, sort_keys=True) for d in documents}), 3
        )

    def test_no_state_is_an_alias_of_another(self):
        for left in ObligationResolution:
            for right in ObligationResolution:
                if left is right:
                    continue
                with self.subTest(left=left.name, right=right.name):
                    self.assertIsNot(left, right)
                    self.assertNotEqual(left.serialize(), right.serialize())

    def test_each_spelling_parses_back_to_its_own_member(self):
        for member in ObligationResolution:
            with self.subTest(member=member.name):
                self.assertIs(
                    parse_obligation_resolution(member.serialize()), member
                )

    def test_resolution_survives_a_round_trip_for_every_state(self):
        for item in (
            obligation(),
            unknown_obligation(),
            obligation(resolution=ObligationResolution.UNSUPPORTED),
        ):
            with self.subTest(state=item.resolution.name):
                restored = DependencyObligation.from_dict(item.to_dict())
                self.assertIs(restored.resolution, item.resolution)


# ---------------------------------------------------------------------------
# 5. Reads/writes preserve order and repeats
# ---------------------------------------------------------------------------

class TestReadsWritesOrderAndRepeats(unittest.TestCase):
    def test_reads_keep_source_order_and_do_not_sort(self):
        item = obligation(
            reads=(
                access("state:zulu"),
                access("state:alpha"),
                access("state:mike"),
            )
        )
        self.assertEqual(
            [entry.target for entry in item.read_targets],
            ["state:zulu", "state:alpha", "state:mike"],
        )

    def test_identical_reads_are_not_deduplicated(self):
        item = obligation(
            reads=(access("state:x"), access("state:x"), access("state:x"))
        )
        self.assertEqual(len(item.read_targets), 3)
        self.assertEqual(
            len(DependencyObligation.from_dict(item.to_dict()).read_targets), 3
        )

    def test_writes_keep_order_and_repeats_independently_of_reads(self):
        item = obligation(
            reads=(access("state:a"),),
            writes=(access("state:b"), access("state:a"), access("state:b")),
        )
        self.assertEqual(
            [entry.target for entry in item.write_targets],
            ["state:b", "state:a", "state:b"],
        )
        self.assertEqual([entry.target for entry in item.read_targets], ["state:a"])

    def test_reads_and_writes_are_separate_fields_never_merged(self):
        item = obligation(
            reads=(access("state:a"), access("state:b")),
            writes=(access("state:c"),),
        )
        document = item.to_dict()
        # Two distinct keys, and neither borrows the other's list.
        self.assertIn("reads", document)
        self.assertIn("writes", document)
        self.assertEqual([e["target"] for e in document["reads"]], ["state:a", "state:b"])
        self.assertEqual([e["target"] for e in document["writes"]], ["state:c"])
        self.assertIsNot(item.read_targets, item.write_targets)
        # A read is never returned as a write and vice versa.
        self.assertNotIn(
            document["reads"][0], document["writes"]
        )
        # Mutating the returned read tuple's content leaves writes untouched.
        before_writes = [e.to_dict() for e in item.write_targets]
        item.read_targets[0].detail()
        self.assertEqual(
            [e.to_dict() for e in item.write_targets], before_writes
        )
        restored = DependencyObligation.from_dict(document)
        self.assertEqual(
            [e["target"] for e in restored.to_dict()["reads"]], ["state:a", "state:b"]
        )
        self.assertEqual(
            [e["target"] for e in restored.to_dict()["writes"]], ["state:c"]
        )

    def test_order_and_repeats_survive_serialization(self):
        item = obligation(
            reads=(
                access("state:c", P.present(3)),
                access("state:a"),
                access("state:c", P.present(3)),
            )
        )
        restored = DependencyObligation.from_dict(item.to_dict())
        self.assertEqual(
            [entry.target for entry in restored.read_targets],
            ["state:c", "state:a", "state:c"],
        )
        self.assertEqual(
            [entry.detail().to_dict() for entry in restored.read_targets],
            [entry.detail().to_dict() for entry in item.read_targets],
        )
        self.assertEqual(restored.to_dict(), item.to_dict())

    def test_empty_reads_and_writes_stay_empty_and_absent_is_not_empty(self):
        item = obligation()
        self.assertEqual(item.read_targets, ())
        self.assertEqual(item.write_targets, ())
        document = item.to_dict()
        self.assertEqual(document["reads"], [])
        self.assertNotEqual(document["reads"], None)

    def test_a_bare_string_sequence_is_refused(self):
        with self.assertRaises(DependencyObligationError):
            obligation(reads=("state:x",))
        with self.assertRaises(DependencyObligationError):
            DependencyObligation(
                owner="STEP_PREFLIGHT",
                contract_ref=contract(),
                evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
                resolution=ObligationResolution.RESOLVED,
                reads="state:x",
            )

    def test_an_access_entry_requires_a_non_empty_target(self):
        for target in ("", " x", "x ", None, 3, True):
            with self.subTest(target=target):
                with self.assertRaises(DependencyObligationError):
                    ObligationAccess(target=target)


# ---------------------------------------------------------------------------
# 6. Children preserve order and repeats
# ---------------------------------------------------------------------------

class TestChildrenOrderAndRepeats(unittest.TestCase):
    def test_children_keep_source_order_and_are_not_sorted(self):
        item = obligation(
            children=(child("ZZZ", "c"), child("AAA", "c"), child("MMM", "c"))
        )
        self.assertEqual(
            [reference.owner for reference in item.child_references],
            ["ZZZ", "AAA", "MMM"],
        )

    def test_repeated_child_references_are_not_deduplicated(self):
        item = obligation(children=(child(), child(), child()))
        self.assertEqual(len(item.child_references), 3)
        self.assertEqual(
            len(DependencyObligation.from_dict(item.to_dict()).child_references), 3
        )

    def test_children_survive_serialization_with_identical_content(self):
        item = unknown_obligation(
            children=(
                child("A", "c-1"),
                child("B", "c-1"),
                child("A", "c-1"),
            )
        )
        restored = DependencyObligation.from_dict(item.to_dict())
        self.assertEqual(restored.to_dict(), item.to_dict())
        self.assertEqual(
            [
                (reference.owner, reference.contract_ref.contract_id)
                for reference in restored.child_references
            ],
            [("A", "c-1"), ("B", "c-1"), ("A", "c-1")],
        )

    def test_a_child_is_a_reference_not_an_embedded_obligation(self):
        reference = child()
        self.assertNotIsInstance(reference, DependencyObligation)
        # A nested obligation cannot be smuggled in as a child reference.
        with self.assertRaises(DependencyObligationError):
            obligation(children=(obligation(),))
        self.assertFalse(
            any(
                isinstance(reference, DependencyObligation)
                for reference in obligation(children=(child(),)).child_references
            )
        )

    def test_a_child_reference_requires_a_real_contract(self):
        with self.assertRaises(DependencyObligationError):
            ChildObligationRef(owner="A", contract_ref="not-a-contract")
        with self.assertRaises(DependencyObligationError):
            ChildObligationRef(owner="A", contract_ref=handle())
        with self.assertRaises(DependencyObligationError):
            ChildObligationRef(owner="lower", contract_ref=contract())

    def test_no_traversal_or_closure_surface_exists(self):
        # These belong to G01-002 and G01-011; their absence is the boundary.
        for name in (
            "closure",
            "resolve_all",
            "expand",
            "walk",
            "traverse",
            "resolve_children",
            "compute_closure",
            "detect_cycles",
            "bounded_footprint",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(DependencyObligation, name))
                self.assertFalse(hasattr(ChildObligationRef, name))


# ---------------------------------------------------------------------------
# 7. Evidence mode survives exactly
# ---------------------------------------------------------------------------

class TestEvidencePreservation(unittest.TestCase):
    def test_all_four_modes_survive_the_round_trip_as_the_same_member(self):
        for mode in EvidenceMode:
            with self.subTest(mode=mode.value):
                item = obligation(mode=mode)
                self.assertIs(item.evidence_mode, mode)
                restored = DependencyObligation.from_dict(item.to_dict())
                self.assertIs(restored.evidence_mode, mode)
                self.assertEqual(
                    restored.to_dict()["evidence_mode"], mode.value
                )

    def test_the_evidence_mode_must_equal_the_contract_mode(self):
        for declared, carried in (
            (EvidenceMode.NATIVE_EVIDENCED, EvidenceMode.REFERENCE_MODEL),
            (EvidenceMode.REFERENCE_MODEL, EvidenceMode.NATIVE_EVIDENCED),
            (EvidenceMode.SANDBOX_EXTENSION, EvidenceMode.NATIVE_EVIDENCED),
        ):
            with self.subTest(declared=declared.value, carried=carried.value):
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation(
                        owner="STEP_PREFLIGHT",
                        contract_ref=contract(carried),
                        evidence_mode=declared,
                        resolution=ObligationResolution.RESOLVED,
                    )

    def test_a_reference_obligation_never_becomes_native(self):
        item = obligation(mode=EvidenceMode.REFERENCE_MODEL)
        restored = DependencyObligation.from_dict(item.to_dict())
        self.assertIs(restored.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertIsNot(restored.evidence_mode, EvidenceMode.NATIVE_EVIDENCED)
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(restored, role="reference obligation")

    def test_the_mode_is_carried_by_both_the_obligation_and_its_contract(self):
        item = obligation(mode=EvidenceMode.SANDBOX_EXTENSION)
        self.assertIs(item.evidence_mode, item.contract_ref.evidence_mode)
        self.assertEqual(
            item.to_dict()["evidence_mode"],
            item.to_dict()["contract_ref"]["evidence_mode"],
        )

    def test_an_unknown_mode_spelling_rejects(self):
        document = obligation().to_dict()
        for spelling in ("native_evidenced", "NATIVE", "", "EXECUTABLE_REFERENCE"):
            with self.subTest(spelling=spelling):
                broken = copy.deepcopy(document)
                broken["evidence_mode"] = spelling
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation.from_dict(broken)


# ---------------------------------------------------------------------------
# 8. Malformed / unknown serialized resolution values reject
# ---------------------------------------------------------------------------

class TestMalformedResolutionRejects(unittest.TestCase):
    def test_unknown_and_malformed_spellings_reject(self):
        for spelling in (
            "UNKNOWN ",
            "unknown",
            "Unknown",
            "SATISFIED",
            "OK",
            "TRUE",
            "None",
            "",
            "BLOCKED",
            "EXACT",
            "MISSING",
            "AMBIGUOUS",
        ):
            with self.subTest(spelling=spelling):
                with self.assertRaises(DependencyObligationError):
                    parse_obligation_resolution(spelling)

    def test_non_string_resolution_values_reject(self):
        for value in (None, 1, 0, True, False, [], {}, ObligationResolution.RESOLVED.value.encode()):
            with self.subTest(value=value):
                with self.assertRaises(DependencyObligationError):
                    parse_obligation_resolution(value)

    def test_a_malformed_resolution_in_a_document_rejects(self):
        document = obligation().to_dict()
        for value in (None, "SATISFIED", "RESOLVED ", 1, True, []):
            with self.subTest(value=value):
                broken = copy.deepcopy(document)
                broken["resolution"] = value
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation.from_dict(broken)

    def test_a_mapping_ledger_state_cannot_be_smuggled_in(self):
        # G01-001: a ledger EXACT mapping is not an obligation resolution.
        for state in ResolutionState:
            with self.subTest(state=state.name):
                with self.assertRaises(DependencyObligationError):
                    parse_obligation_resolution(state.value)
                broken = obligation().to_dict()
                broken["resolution"] = state.value
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation.from_dict(broken)

    def test_the_two_vocabularies_are_disjoint_by_construction(self):
        ledger = {state.value for state in ResolutionState}
        obligations = set(OBLIGATION_RESOLUTION_SPELLINGS)
        self.assertEqual(ledger & obligations, set())
        self.assertEqual(ledger, {"EXACT", "MISSING", "AMBIGUOUS", "BLOCKED"})

    def test_a_descriptor_or_handle_is_not_an_obligation_contract(self):
        from hsr_battle_agent.battle_ir.descriptors.base import (
            DESCRIPTOR_OCCURRENCE_SCHEMA,
            DescriptorOccurrence,
        )

        for wrong in (handle(), "contract", DESCRIPTOR_OCCURRENCE_SCHEMA):
            with self.subTest(wrong=type(wrong).__name__):
                with self.assertRaises(DependencyObligationError):
                    DependencyObligation(
                        owner="STEP_PREFLIGHT",
                        contract_ref=wrong,
                        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
                        resolution=ObligationResolution.RESOLVED,
                    )
        self.assertTrue(hasattr(DescriptorOccurrence, "from_dict"))


# ---------------------------------------------------------------------------
# 9. Presence distinctions are not collapsed
# ---------------------------------------------------------------------------

class TestPresenceNotCollapsed(unittest.TestCase):
    def test_absent_null_and_present_extents_are_three_different_facts(self):
        absent, null, present = (
            access("state:x"),
            access("state:x", P.null()),
            access("state:x", P.present(0)),
        )
        documents = [item.to_dict() for item in (absent, null, present)]
        self.assertEqual(len({json.dumps(d, sort_keys=True) for d in documents}), 3)
        self.assertTrue(absent.extent.is_absent())
        self.assertTrue(null.extent.is_null())
        self.assertTrue(present.extent.is_present())
        self.assertIs(present.extent.require_present(), 0)

    def test_empty_present_values_are_still_present(self):
        for value in (False, 0, "", [], {}, ()):
            with self.subTest(value=value):
                entry = access("state:x", P.present(value))
                self.assertTrue(entry.extent.is_present())
                self.assertEqual(entry.detail().require_present(), value)

    def test_absent_and_null_never_resolve_a_value(self):
        for entry in (access("state:x"), access("state:x", P.null())):
            with self.subTest(state=entry.extent.to_dict()["presence"]):
                with self.assertRaises(Exception):
                    entry.extent.require_present()

    def test_the_three_states_survive_the_round_trip(self):
        item = obligation(
            reads=(
                access("state:absent"),
                access("state:null", P.null()),
                access("state:present", P.present([None])),
            )
        )
        restored = DependencyObligation.from_dict(item.to_dict())
        states = [entry.detail() for entry in restored.read_targets]
        self.assertTrue(states[0].is_absent())
        self.assertTrue(states[1].is_null())
        self.assertTrue(states[2].is_present())
        self.assertEqual(states[2].require_present(), [None])
        self.assertEqual(restored.to_dict(), item.to_dict())

    def test_an_invalid_extent_encoding_rejects(self):
        item = access("state:x", P.present(1))
        broken = item.to_dict()
        broken["extent"] = {"schema": "presence_value/1", "presence": "PRESENT"}
        with self.assertRaises(DependencyObligationError):
            ObligationAccess.from_dict(broken)
        broken = item.to_dict()
        broken["extent"] = "PRESENT"
        with self.assertRaises(DependencyObligationError):
            ObligationAccess.from_dict(broken)

    def test_a_bare_extent_value_is_refused_rather_than_guessed(self):
        for value in (None, 1, "x", [], {}, True):
            with self.subTest(value=value):
                with self.assertRaises(DependencyObligationError):
                    ObligationAccess(target="state:x", extent=value)

    def test_access_documents_require_exactly_the_declared_fields(self):
        document = access("state:x").to_dict()
        for key in sorted(document):
            with self.subTest(missing=key):
                broken = copy.deepcopy(document)
                broken.pop(key)
                with self.assertRaises(DependencyObligationError):
                    ObligationAccess.from_dict(broken)
        extra = copy.deepcopy(document)
        extra["note"] = "x"
        with self.assertRaises(DependencyObligationError):
            ObligationAccess.from_dict(extra)


# ---------------------------------------------------------------------------
# 10. No execute / apply / commit / gate-certificate surface
# ---------------------------------------------------------------------------

class TestNoExecutionOrGateSurface(unittest.TestCase):
    FORBIDDEN = (
        "execute",
        "apply",
        "commit",
        "run",
        "perform",
        "issue_gate_certificate",
        "as_native_contract",
        "gate_certificate",
        "native_contract",
        "execution_permitted",
        "stage",
        "publish",
        "allocate",
        "certify",
    )

    def test_no_forbidden_surface_exists_on_any_type(self):
        for type_ in (DependencyObligation, ObligationAccess, ChildObligationRef):
            for name in self.FORBIDDEN:
                with self.subTest(type=type_.__name__, name=name):
                    self.assertFalse(hasattr(type_, name))

    def test_the_resolution_vocabulary_exposes_no_permission_helper(self):
        for name in ("executable", "is_executable", "implies_execution", "permit"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ObligationResolution, name))

    def test_the_module_never_imports_the_certificate_producer(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported_modules = set()
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)
                for alias in node.names:
                    imported_names.add(alias.name)
        self.assertNotIn("issue_gate_certificate", imported_names)
        self.assertNotIn("GateCertificate", imported_names)
        self.assertNotIn("NativeContract", imported_names)
        self.assertFalse(
            any("evidence_boundary" in name for name in imported_modules),
            f"preflight must not import the evidence boundary: {imported_modules}",
        )

    def test_the_module_holds_no_loaded_reference_to_a_gate_symbol(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        loaded = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        for name in (
            "issue_gate_certificate",
            "GateCertificate",
            "require_native_contract",
            "certify_native_contract",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, loaded)

    def test_the_module_never_touches_battle_state_or_the_allocator(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        for forbidden in ("state", "stores", "identity", "rng", "revision"):
            with self.subTest(module=forbidden):
                self.assertFalse(
                    any(
                        name.endswith("battle_sandbox." + forbidden)
                        for name in imported_modules
                    ),
                    f"preflight must not import {forbidden}: {imported_modules}",
                )

    def test_no_module_level_function_returns_a_permission(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        public = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        self.assertEqual(
            sorted(public), ["parse_obligation_resolution", "require_owner_code"]
        )
        # Neither public function is a permission helper.
        for name in public:
            with self.subTest(name=name):
                for token in (
                    "permit", "allow", "execute", "gate", "certificate",
                    "satisf", "approve", "authorize",
                ):
                    self.assertNotIn(token, name)


# ---------------------------------------------------------------------------
# Owner code interop and read-surface isolation
# ---------------------------------------------------------------------------

class TestOwnerCodeInterop(unittest.TestCase):
    def test_the_owner_rule_matches_the_existing_structured_rejection_rule(self):
        accepted = ("STEP_PREFLIGHT", "A", "DAMAGE_ROOT", "G01", "STEP PREFLIGHT")
        rejected = ("", " x", "x ", "lower", "Mixed", None, 3, True)
        for code in accepted:
            with self.subTest(accepted=code):
                self.assertEqual(require_owner_code(code), code)
                # The pre-existing rejection carries the same rule, which is what
                # lets a G01-003 rejection name this obligation's owner verbatim
                # without a lossy conversion.
                rejection = StructuredRejection(
                    reason_code="UNKNOWN_OBLIGATION",
                    obligation_owner=code,
                    evidence_request="native proof",
                )
                self.assertEqual(rejection.obligation_owner, code)
        for code in rejected:
            with self.subTest(rejected=code):
                with self.assertRaises(DependencyObligationError):
                    require_owner_code(code)
                with self.assertRaises(RejectionDataError):
                    StructuredRejection(
                        reason_code="UNKNOWN_OBLIGATION",
                        obligation_owner=code,
                        evidence_request="native proof",
                    )

    def test_the_two_owner_rules_agree_on_every_probed_value(self):
        # Equivalence, not just a spot check: for each probe, this module and
        # StructuredRejection must accept or reject it together, otherwise a
        # G01-003 rejection could not carry the owner verbatim.
        probes = (
            "STEP_PREFLIGHT", "A", "G01", "DAMAGE_ROOT", "STEP PREFLIGHT",
            "STEP  PREFLIGHT", "A_B", "", " ", " x", "x ", "lower", "Mixed",
            "Mixed_Code", "café", "STEP-PREFLIGHT", "STEP.PREFLIGHT", "0", "G01_1",
        )
        for probe in probes:
            with self.subTest(probe=probe):
                try:
                    require_owner_code(probe)
                    ours = "ACCEPT"
                except DependencyObligationError:
                    ours = "REJECT"
                try:
                    StructuredRejection(
                        reason_code="X",
                        obligation_owner=probe,
                        evidence_request="y",
                    )
                    theirs = "ACCEPT"
                except RejectionDataError:
                    theirs = "REJECT"
                self.assertEqual(ours, theirs, f"disagreement on {probe!r}")

    def test_an_owner_code_is_never_a_battle_entity_identity(self):
        item = obligation(owner="STEP_PREFLIGHT")
        self.assertIsInstance(item.owner, str)
        # A typed entity identity is not silently accepted as an owner code.
        from hsr_battle_agent.battle_sandbox import identity as identity_module

        identity = identity_module.TypedIdentity.local(
            identity_module.OWNER, "battle.preflight.test", "owner:1"
        )
        self.assertNotIsInstance(identity, str)
        with self.assertRaises(DependencyObligationError):
            require_owner_code(identity)
        with self.assertRaises(DependencyObligationError):
            obligation(owner=identity)
        # An owner code and a team identity are not interchangeable either.
        team = identity_module.TypedIdentity.local(
            identity_module.TEAM, "battle.preflight.test", "team:1"
        )
        self.assertNotEqual(team, identity)
        with self.assertRaises(DependencyObligationError):
            obligation(owner=team)

    def test_the_owner_survives_the_round_trip(self):
        item = unknown_obligation(owner="MODIFIER_LIFECYCLE")
        restored = DependencyObligation.from_dict(item.to_dict())
        self.assertEqual(restored.owner, "MODIFIER_LIFECYCLE")


class TestReadSurfacesAreDetached(unittest.TestCase):
    def test_mutating_a_returned_document_cannot_rewrite_the_obligation(self):
        item = unknown_obligation(
            reads=(access("state:x", P.present({"items": [1]})),),
            children=(child(),),
        )
        before = item.to_dict()
        document = item.to_dict()
        document["reads"][0]["extent"]["value"]["items"].append("mutated")
        document["owner"] = "REWRITTEN"
        document["unknown_handles"][0]["payload"]["missing"] = "rewritten"
        self.assertEqual(item.to_dict(), before)

    def test_mutating_a_returned_access_extent_cannot_rewrite_the_obligation(self):
        item = obligation(reads=(access("state:x", P.present({"items": [1]})),))
        before = item.to_dict()
        exported = item.read_targets[0]
        exported.detail().require_present()["items"].append("mutated")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.read_targets[0].detail().require_present(), {"items": [1]})

    def test_mutating_a_returned_child_contract_cannot_rewrite_the_obligation(self):
        item = obligation(children=(child(),))
        before = item.to_dict()
        exported = item.child_references[0]
        self.assertEqual(exported.owner, "CHILD_OWNER")
        self.assertEqual(item.to_dict(), before)

    def test_mutating_a_construction_argument_cannot_rewrite_the_obligation(self):
        shared = {"items": [1]}
        extent = P.present(shared)
        item = obligation(reads=(ObligationAccess(target="state:x", extent=extent),))
        before = item.to_dict()
        shared["items"].append("mutated-after-construction")
        extent.require_present()["items"].append("mutated-envelope")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.read_targets[0].detail().require_present(), {"items": [1]})

    def test_reads_writes_and_children_are_separate_objects(self):
        item = obligation(
            reads=(access("state:a"),),
            writes=(access("state:a"),),
            children=(child(),),
        )
        self.assertIsNot(item.read_targets, item.write_targets)
        self.assertIsNot(
            item.read_targets[0].detail(), item.read_targets[0].detail()
        )
        self.assertEqual(len(item.read_targets), 1)
        self.assertEqual(len(item.write_targets), 1)
        self.assertEqual(len(item.child_references), 1)

    def test_a_returned_tuple_cannot_be_extended_in_place(self):
        item = obligation(reads=(access("state:a"),))
        exported = item.read_targets
        self.assertIsInstance(exported, tuple)
        with self.assertRaises(AttributeError):
            exported.append(access("state:b"))
        self.assertEqual(len(item.read_targets), 1)


# ---------------------------------------------------------------------------
# CR-G01-001-RAW-ALIAS-20260923-001 regressions
#
# These exercise the PUBLIC RAW names (``.reads``, ``.writes``, ``.children``,
# ``.unknown_handles``, ``.extent``, ``.contract_ref``) that the confirmed defect
# went through, not only the detached helper properties.  Every case compares the
# complete serialized representation before and after the attempted mutation.
# ---------------------------------------------------------------------------


def raw_obligation(resolution: ObligationResolution = ObligationResolution.UNKNOWN):
    """A fully populated obligation whose nested payloads are mutable."""
    return DependencyObligation(
        owner="STEP_PREFLIGHT",
        contract_ref=contract(),
        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        resolution=resolution,
        reads=(
            access("state:read_a", P.present({"items": [1], "nested": {"deep": [1]}})),
            access("state:read_b", P.present(["a", "b"])),
        ),
        writes=(
            access("state:write_a", P.present({"items": [2], "nested": {"deep": [2]}})),
        ),
        children=(child("CHILD_A", "c-1"), child("CHILD_A", "c-1")),
        unknown_handles=(
            UnknownHandle(
                blocker_id="PF-Q1",
                owner_family="PREFLIGHT",
                payload={"missing": {"deep": [1]}, "list": [1]},
                provenance={"source": "freeze", "nested": {"k": [1]}},
                required_evidence=("proof",),
            ),
        ),
    )


class TestRawFieldMutationIsolation(unittest.TestCase):
    """The exact public routes that were previously unsafe."""

    def test_the_original_confirmed_reproducer_now_passes(self):
        # Verbatim from CR-G01-001-RAW-ALIAS-20260923-001.
        item = raw_obligation()
        before = item.to_dict()
        item.reads[0].extent.require_present()["items"].append("MUTATED")
        self.assertEqual(item.to_dict(), before)

    # -- A. raw read extent -------------------------------------------------

    def test_A_raw_read_extent_mutation_is_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        item.reads[0].extent.require_present()["items"].append("MUTATED")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.reads[0].extent.require_present()["items"], [1])

    def test_A_raw_read_extent_is_isolated_on_every_documented_route(self):
        routes = (
            ("require_present nested dict", lambda e: e.require_present()["nested"]["deep"].append("M")),
            ("require_present top dict", lambda e: e.require_present().__setitem__("injected", True)),
            ("deepcopy then mutate is irrelevant", lambda e: e.require_present()["items"].clear()),
        )
        for label, mutate in routes:
            with self.subTest(route=label):
                item = raw_obligation()
                before = item.to_dict()
                mutate(item.reads[0].extent)
                self.assertEqual(item.to_dict(), before)

    def test_A_raw_read_extent_of_a_list_payload_is_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        item.reads[1].extent.require_present().append("MUTATED")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.reads[1].extent.require_present(), ["a", "b"])

    def test_A_raw_read_extent_replacement_is_blocked(self):
        item = raw_obligation()
        before = item.to_dict()
        with self.assertRaises(AttributeError):
            item.reads[0].extent = P.present({"items": ["replaced"]})
        with self.assertRaises(AttributeError):
            item.reads[0].target = "state:replaced"
        self.assertEqual(item.to_dict(), before)

    # -- B. raw write extent ------------------------------------------------

    def test_B_raw_write_extent_mutation_is_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        item.writes[0].extent.require_present()["items"].append("MUTATED")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.writes[0].extent.require_present()["items"], [2])

    def test_B_raw_write_extent_nested_mutation_is_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        item.writes[0].extent.require_present()["nested"]["deep"].append("MUTATED")
        item.writes[0].extent.require_present()["nested"]["injected"] = True
        self.assertEqual(item.to_dict(), before)

    def test_B_write_isolation_is_independent_of_read_isolation(self):
        item = raw_obligation()
        before = item.to_dict()
        item.reads[0].extent.require_present()["items"].append("MUTATED")
        item.writes[0].extent.require_present()["items"].append("MUTATED")
        self.assertEqual(item.to_dict(), before)

    # -- C. raw unknown handle nested payload -------------------------------

    def test_C_raw_unknown_handle_payload_mutation_is_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        item.unknown_handles[0].payload["missing"]["deep"].append("MUTATED")
        item.unknown_handles[0].payload["list"].append("MUTATED")
        item.unknown_handles[0].payload["injected"] = True
        self.assertEqual(item.to_dict(), before)

    def test_C_raw_unknown_handle_provenance_mutation_is_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        item.unknown_handles[0].provenance["source"] = "REWRITTEN"
        item.unknown_handles[0].provenance["nested"]["k"].append("MUTATED")
        item.unknown_handles[0].provenance["injected"] = True
        self.assertEqual(item.to_dict(), before)

    def test_C_raw_unknown_handle_identity_is_stable_after_attempted_mutation(self):
        item = raw_obligation()
        before_hash = item.unknown_handles[0].identity_hash()
        item.unknown_handles[0].payload["missing"]["deep"].append("MUTATED")
        item.unknown_handles[0].provenance["source"] = "REWRITTEN"
        self.assertEqual(item.unknown_handles[0].identity_hash(), before_hash)

    def test_C_raw_unknown_handle_required_evidence_and_ids_are_isolated(self):
        item = raw_obligation()
        before = item.to_dict()
        handle = item.unknown_handles[0]
        self.assertEqual(handle.blocker_id, "PF-Q1")
        self.assertEqual(handle.owner_family, "PREFLIGHT")
        self.assertEqual(tuple(handle.required_evidence), ("proof",))
        self.assertEqual(item.to_dict(), before)

    def test_C_every_returned_handle_is_a_fresh_object(self):
        item = raw_obligation()
        first = item.unknown_handles[0]
        second = item.unknown_handles[0]
        self.assertIsNot(first, second)
        self.assertIsNot(first.payload, second.payload)
        self.assertIsNot(first.provenance, second.provenance)

    # -- D. raw child contract route ----------------------------------------

    def test_D_raw_child_contract_ref_route_cannot_mutate_the_obligation(self):
        item = raw_obligation()
        before = item.to_dict()
        reference = item.children[0]
        exported = reference.contract_ref
        # A ContractRef is deeply immutable; assert the attempt is blocked *and*
        # that both the reference and the obligation are untouched.
        with self.assertRaises(AttributeError):
            exported.source_refs.append("MUTATED")
        self.assertEqual(reference.contract_ref.to_dict(), exported.to_dict())
        self.assertEqual(item.to_dict(), before)

    def test_D_raw_child_reference_returns_a_fresh_contract_each_time(self):
        item = raw_obligation()
        first = item.children[0].contract_ref
        second = item.children[0].contract_ref
        self.assertIsNot(first, second)
        self.assertEqual(first, second)

    def test_D_raw_child_reference_replacement_is_blocked(self):
        item = raw_obligation()
        before = item.to_dict()
        with self.assertRaises(AttributeError):
            item.children[0].contract_ref = contract(contract_id="replaced")
        with self.assertRaises(AttributeError):
            item.children[0].owner = "REPLACED"
        self.assertEqual(item.to_dict(), before)

    def test_D_raw_children_sequence_is_not_assignable_or_mutable(self):
        item = raw_obligation()
        before = item.to_dict()
        with self.assertRaises(AttributeError):
            item.children = ()
        self.assertIsInstance(item.children, tuple)
        with self.assertRaises(AttributeError):
            item.children.append(child("CHILD_B", "c-2"))
        self.assertEqual(item.to_dict(), before)

    # -- E. raw top-level contract_ref route --------------------------------

    def test_E_raw_top_level_contract_ref_route_cannot_mutate_the_obligation(self):
        item = raw_obligation()
        before = item.to_dict()
        exported = item.contract_ref
        with self.assertRaises(AttributeError):
            exported.source_refs.append("MUTATED")
        with self.assertRaises(AttributeError):
            exported.contract_id = "REWRITTEN"
        self.assertEqual(item.to_dict(), before)

    def test_E_raw_top_level_contract_ref_is_a_fresh_object(self):
        item = raw_obligation()
        first = item.contract_ref
        second = item.contract_ref
        self.assertIsNot(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertIs(item.contract_ref.evidence_mode, item.evidence_mode)

    # -- F. construction aliases --------------------------------------------

    def test_F_mutating_original_sequences_after_construction_is_isolated(self):
        extent = P.present({"items": [1]})
        reads = [ObligationAccess(target="state:r", extent=extent)]
        writes = [ObligationAccess(target="state:w", extent=P.present({"items": [2]}))]
        children = [child()]
        shared_handle = UnknownHandle(
            blocker_id="Q", owner_family="F", payload={"p": [1]}, provenance={"s": [1]},
            required_evidence=("e",),
        )
        handles = [shared_handle]
        item = DependencyObligation(
            owner="OWNER",
            contract_ref=contract(),
            evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
            resolution=ObligationResolution.UNKNOWN,
            reads=reads,
            writes=writes,
            children=children,
            unknown_handles=handles,
        )
        before = item.to_dict()

        reads.append(ObligationAccess(target="state:injected"))
        writes.clear()
        children.clear()
        handles.clear()
        extent.require_present()["items"].append("MUTATED")
        shared_handle.payload["p"].append("MUTATED")
        shared_handle.provenance["s"].append("MUTATED")

        self.assertEqual(item.to_dict(), before)
        self.assertEqual(len(item.reads), 1)
        self.assertEqual(len(item.writes), 1)
        self.assertEqual(len(item.children), 1)
        self.assertEqual(len(item.unknown_handles), 1)

    def test_F_mutating_the_original_access_object_is_isolated(self):
        original = access("state:x", P.present({"items": [1]}))
        item = obligation(reads=(original,))
        before = item.to_dict()
        original.extent.require_present()["items"].append("MUTATED")
        self.assertEqual(item.to_dict(), before)
        self.assertEqual(item.reads[0].extent.require_present()["items"], [1])

    def test_F_mutating_the_original_handle_is_isolated(self):
        original = UnknownHandle(
            blocker_id="Q", owner_family="F", payload={"p": [1]}, provenance={"s": [1]},
            required_evidence=("e",),
        )
        item = unknown_obligation(handles=(original,))
        before = item.to_dict()
        original.payload["p"].append("MUTATED")
        original.provenance["s"].append("MUTATED")
        self.assertEqual(item.to_dict(), before)

    def test_F_mutating_a_construction_document_is_isolated(self):
        document = raw_obligation().to_dict()
        item = DependencyObligation.from_dict(document)
        before = item.to_dict()
        document["reads"][0]["extent"]["value"]["items"].append("MUTATED")
        document["unknown_handles"][0]["payload"]["missing"]["deep"].append("MUTATED")
        document["owner"] = "REWRITTEN"
        self.assertEqual(item.to_dict(), before)


class TestOwnedRepresentationIsPrivate(unittest.TestCase):
    """The fix is structural, not a per-route patch."""

    def test_every_public_representation_name_is_a_property(self):
        for name in PUBLIC_REPRESENTATION_NAMES:
            with self.subTest(name=name):
                self.assertIsInstance(
                    vars(DependencyObligation)[name],
                    property,
                    f"{name} must be a property, not a stored field",
                )

    def test_the_nested_types_expose_no_public_stored_field(self):
        for type_ in (ObligationAccess, ChildObligationRef, DependencyObligation):
            names = [f.name for f in dataclasses.fields(type_)]
            with self.subTest(type=type_.__name__):
                self.assertTrue(names)
                for name in names:
                    self.assertTrue(
                        name.startswith("_"),
                        f"{type_.__name__}.{name} is a public stored field",
                    )

    def test_public_reads_always_return_new_objects(self):
        item = raw_obligation()
        for name in PUBLIC_REPRESENTATION_NAMES:
            with self.subTest(name=name):
                first = getattr(item, name)
                second = getattr(item, name)
                if isinstance(first, (str, Enum)):
                    self.assertIs(first, second)
                else:
                    self.assertIsNot(first, second)

    def test_assignment_through_a_public_name_is_refused(self):
        item = raw_obligation()
        before = item.to_dict()
        for name in PUBLIC_REPRESENTATION_NAMES:
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(item, name, None)
        for name in ("target", "extent"):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(item.reads[0], name, None)
        for name in ("owner", "contract_ref"):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(item.children[0], name, None)
        self.assertEqual(item.to_dict(), before)

    def test_mutating_every_reachable_public_route_leaves_to_dict_identical(self):
        # One sweep over every route the audit enumerated; the single assertion
        # that matters is that the whole serialized representation is unchanged.
        item = raw_obligation()
        before = item.to_dict()
        item.reads[0].extent.require_present()["items"].append("M")
        item.reads[1].extent.require_present().append("M")
        item.writes[0].extent.require_present()["items"].append("M")
        item.children[0].contract_ref.source_refs
        item.contract_ref.source_refs
        item.unknown_handles[0].payload["missing"]["deep"].append("M")
        item.unknown_handles[0].provenance["source"] = "M"
        item.unknown_handles[0].required_evidence
        self.assertEqual(item.to_dict(), before)
        # And the obligation still round-trips to exactly the same document.
        self.assertEqual(DependencyObligation.from_dict(item.to_dict()), item)


if __name__ == "__main__":
    unittest.main()
