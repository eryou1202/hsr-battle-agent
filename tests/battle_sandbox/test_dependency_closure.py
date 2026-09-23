# -*- coding: utf-8 -*-
"""Acceptance tests for G01-002 conservative dependency closure."""
from __future__ import annotations

import unittest
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.dependency_graph import (
    ClosureStatus,
    DependencyClosure,
    DependencyClosureError,
    DependencyGraph,
)
from hsr_battle_agent.battle_sandbox.preflight import (
    ChildObligationRef,
    DependencyObligation,
    ObligationAccess,
    ObligationResolution,
)


def contract(name: str, mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED) -> ContractRef:
    return ContractRef(
        contract_id=name,
        namespace="tests.g01",
        schema_version="1",
        evidence_mode=mode,
        content_sha256=(name.encode("utf-8").hex() + "0" * 64)[:64],
        source_refs=(f"fixture://{name}",),
    )


def ref(name: str, owner: str = "OWNER", mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED) -> ChildObligationRef:
    return ChildObligationRef(owner=owner, contract_ref=contract(name, mode))


def unknown(name: str) -> UnknownHandle:
    return UnknownHandle(
        blocker_id=name,
        owner_family="TEST",
        payload={"items": [name, None]},
        provenance={"source": "independent-fixture"},
        required_evidence=(f"resolve {name}",),
    )


def obligation(
    name: str,
    *,
    owner: str = "OWNER",
    mode: EvidenceMode = EvidenceMode.NATIVE_EVIDENCED,
    resolution: ObligationResolution = ObligationResolution.RESOLVED,
    children: tuple[ChildObligationRef, ...] = (),
    reads: tuple[ObligationAccess, ...] = (),
    writes: tuple[ObligationAccess, ...] = (),
    handles: tuple[UnknownHandle, ...] = (),
) -> DependencyObligation:
    return DependencyObligation(
        owner=owner,
        contract_ref=contract(name, mode),
        evidence_mode=mode,
        resolution=resolution,
        reads=reads,
        writes=writes,
        children=children,
        unknown_handles=handles,
    )


class TestFiniteClosure(unittest.TestCase):
    def test_simple_finite_closure(self) -> None:
        leaf = obligation("leaf")
        result = DependencyGraph((leaf,)).close((ref("leaf"),), expansion_budget=4)
        self.assertIs(result.status, ClosureStatus.CLOSED)
        self.assertTrue(result.is_closed())
        self.assertEqual([item.contract_ref.contract_id for item in result.obligations], ["leaf"])
        self.assertEqual(result.blockers, ())

    def test_nested_descendants_close_transitively_in_source_order(self) -> None:
        root = obligation("root", children=(ref("child"),))
        child = obligation("child", children=(ref("leaf"),))
        leaf = obligation("leaf")
        result = DependencyGraph((root, child, leaf)).close((ref("root"),), expansion_budget=8)
        self.assertEqual(
            [item.contract_ref.contract_id for item in result.obligations],
            ["root", "child", "leaf"],
        )

    def test_reads_and_writes_preserve_occurrence_order_and_duplicates(self) -> None:
        read = ObligationAccess("store.read", PresenceValue.present([1, None]))
        write = ObligationAccess("store.write", PresenceValue.null())
        item = obligation("root", reads=(read, read), writes=(write, write))
        result = DependencyGraph((item,)).close((ref("root"),), expansion_budget=2)
        self.assertEqual([x.target for x in result.allowed_reads], ["store.read", "store.read"])
        self.assertEqual([x.target for x in result.allowed_writes], ["store.write", "store.write"])
        self.assertEqual(result.allowed_reads[0].extent.to_dict()["value"], [1, None])

    def test_result_round_trip_is_exact(self) -> None:
        result = DependencyGraph((obligation("root"),)).close((ref("root"),), expansion_budget=2)
        self.assertEqual(DependencyClosure.from_dict(result.to_dict()), result)

    def test_closure_has_no_truthiness(self) -> None:
        result = DependencyGraph((obligation("root"),)).close((ref("root"),), expansion_budget=2)
        with self.assertRaises(DependencyClosureError):
            bool(result)


class TestConservativeMatching(unittest.TestCase):
    def test_multiple_owner_contract_matches_expand_all(self) -> None:
        first = obligation("same", reads=(ObligationAccess("first"),))
        second = obligation("same", reads=(ObligationAccess("second"),))
        result = DependencyGraph((first, second)).close((ref("same"),), expansion_budget=4)
        self.assertEqual([x.target for x in result.allowed_reads], ["first", "second"])
        self.assertEqual(len(result.obligations), 2)

    def test_duplicate_candidate_occurrences_survive(self) -> None:
        item = obligation("same")
        result = DependencyGraph((item, item)).close((ref("same"),), expansion_budget=4)
        self.assertEqual(len(result.obligations), 2)
        self.assertEqual(result.obligations[0].to_dict(), result.obligations[1].to_dict())

    def test_duplicate_root_references_expand_independently(self) -> None:
        item = obligation("same")
        result = DependencyGraph((item,)).close((ref("same"), ref("same")), expansion_budget=4)
        self.assertEqual(len(result.obligations), 2)

    def test_owner_is_part_of_match_identity(self) -> None:
        item = obligation("same", owner="OTHER")
        result = DependencyGraph((item,)).close((ref("same", owner="OWNER"),), expansion_budget=3)
        self.assertIs(result.status, ClosureStatus.BLOCKED_MISSING)

    def test_contract_identity_is_not_reduced_to_contract_id(self) -> None:
        item = obligation("same")
        different = ContractRef(
            contract_id="same",
            namespace="different.namespace",
            schema_version="1",
            evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
            content_sha256="f" * 64,
            source_refs=("fixture://different",),
        )
        result = DependencyGraph((item,)).close(
            (ChildObligationRef(owner="OWNER", contract_ref=different),),
            expansion_budget=3,
        )
        self.assertIs(result.status, ClosureStatus.BLOCKED_MISSING)


class TestBlockers(unittest.TestCase):
    def test_missing_child_blocks(self) -> None:
        root = obligation("root", children=(ref("missing"),))
        result = DependencyGraph((root,)).close((ref("root"),), expansion_budget=4)
        self.assertIs(result.status, ClosureStatus.BLOCKED_MISSING)
        self.assertEqual(result.blockers[0].contract_ref.contract_id, "missing")

    def test_unknown_child_blocks_and_preserves_handle(self) -> None:
        root = obligation("root", children=(ref("child"),))
        child = obligation(
            "child",
            resolution=ObligationResolution.UNKNOWN,
            handles=(unknown("U-1"),),
        )
        result = DependencyGraph((root, child)).close((ref("root"),), expansion_budget=5)
        self.assertIs(result.status, ClosureStatus.BLOCKED_UNKNOWN)
        self.assertEqual(result.blockers[0].unknown_handles[0].blocker_id, "U-1")

    def test_unsupported_child_blocks(self) -> None:
        root = obligation("root", children=(ref("child"),))
        child = obligation("child", resolution=ObligationResolution.UNSUPPORTED)
        result = DependencyGraph((root, child)).close((ref("root"),), expansion_budget=5)
        self.assertIs(result.status, ClosureStatus.BLOCKED_UNSUPPORTED)

    def test_late_blocker_is_found_after_earlier_supported_occurrence(self) -> None:
        root = obligation("root", children=(ref("ok"), ref("late")))
        ok = obligation("ok", writes=(ObligationAccess("would.write"),))
        late = obligation("late", resolution=ObligationResolution.UNSUPPORTED)
        result = DependencyGraph((root, ok, late)).close((ref("root"),), expansion_budget=8)
        self.assertFalse(result.is_closed())
        self.assertEqual(
            [x.contract_ref.contract_id for x in result.obligations],
            ["root", "ok", "late"],
        )
        self.assertEqual([x.target for x in result.allowed_writes], ["would.write"])

    def test_multiple_blockers_all_survive_in_traversal_order(self) -> None:
        root = obligation("root", children=(ref("u"), ref("x"), ref("missing")))
        u = obligation("u", resolution=ObligationResolution.UNKNOWN, handles=(unknown("U"),))
        x = obligation("x", resolution=ObligationResolution.UNSUPPORTED)
        result = DependencyGraph((root, u, x)).close((ref("root"),), expansion_budget=8)
        self.assertEqual(
            [item.status for item in result.blockers],
            [
                ClosureStatus.BLOCKED_UNKNOWN,
                ClosureStatus.BLOCKED_UNSUPPORTED,
                ClosureStatus.BLOCKED_MISSING,
            ],
        )

    def test_diagnostic_order_is_repeatable(self) -> None:
        root = obligation("root", children=(ref("z"), ref("a")))
        first = DependencyGraph((root,)).close((ref("root"),), expansion_budget=6)
        second = DependencyGraph((root,)).close((ref("root"),), expansion_budget=6)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            [x.contract_ref.contract_id for x in first.blockers], ["z", "a"]
        )


class TestBranchesCyclesAndBounds(unittest.TestCase):
    def test_random_branch_representation_expands_every_arm_before_draw(self) -> None:
        branch = obligation("random-branch", children=(ref("arm-b"), ref("arm-a")))
        arm_b = obligation("arm-b")
        arm_a = obligation("arm-a")
        result = DependencyGraph((branch, arm_b, arm_a)).close(
            (ref("random-branch"),), expansion_budget=8
        )
        self.assertEqual(
            [item.contract_ref.contract_id for item in result.obligations],
            ["random-branch", "arm-b", "arm-a"],
        )

    def test_unknown_random_arm_blocks_whole_closure(self) -> None:
        branch = obligation("random-branch", children=(ref("arm-ok"), ref("arm-u")))
        ok = obligation("arm-ok")
        unresolved = obligation(
            "arm-u", resolution=ObligationResolution.UNKNOWN, handles=(unknown("RNG-ARM"),)
        )
        result = DependencyGraph((branch, ok, unresolved)).close(
            (ref("random-branch"),), expansion_budget=8
        )
        self.assertIs(result.status, ClosureStatus.BLOCKED_UNKNOWN)

    def test_simple_cycle_blocks(self) -> None:
        self_ref = ref("self")
        result = DependencyGraph((obligation("self", children=(self_ref,)),)).close(
            (self_ref,), expansion_budget=8
        )
        self.assertIs(result.status, ClosureStatus.BLOCKED_CYCLE)

    def test_indirect_cycle_blocks(self) -> None:
        a = obligation("a", children=(ref("b"),))
        b = obligation("b", children=(ref("a"),))
        result = DependencyGraph((a, b)).close((ref("a"),), expansion_budget=8)
        self.assertIs(result.status, ClosureStatus.BLOCKED_CYCLE)
        self.assertEqual([x.contract_ref.contract_id for x in result.obligations], ["a", "b"])

    def test_budget_exhaustion_is_blocked_unbounded_never_closed(self) -> None:
        a = obligation("a", children=(ref("b"),))
        b = obligation("b")
        result = DependencyGraph((a, b)).close((ref("a"),), expansion_budget=1)
        self.assertIs(result.status, ClosureStatus.BLOCKED_UNBOUNDED)
        self.assertFalse(result.is_closed())

    def test_no_arbitrary_non_positive_budget_is_accepted(self) -> None:
        graph = DependencyGraph((obligation("a"),))
        for value in (0, -1, True, None):
            with self.subTest(value=value), self.assertRaises(DependencyClosureError):
                graph.close((ref("a"),), expansion_budget=value)  # type: ignore[arg-type]


class TestNegativeBoundariesAndIsolation(unittest.TestCase):
    def test_graph_exposes_no_gate_or_execution_surface(self) -> None:
        forbidden = {
            "execute", "apply", "commit", "issue_certificate", "gate_certificate",
            "draw_rng", "allocate", "mutate_state",
        }
        for subject in (DependencyGraph, DependencyClosure):
            self.assertTrue(forbidden.isdisjoint(dir(subject)))

    def test_no_state_or_rng_input_exists(self) -> None:
        self.assertEqual(
            set(DependencyGraph.close.__annotations__),
            {"roots", "expansion_budget", "return"},
        )

    def test_candidate_construction_alias_is_detached(self) -> None:
        extent = ["original"]
        item = obligation(
            "a", reads=(ObligationAccess("read", PresenceValue.present(extent)),)
        )
        graph = DependencyGraph((item,))
        extent.append("mutated")
        result = graph.close((ref("a"),), expansion_budget=2)
        self.assertEqual(result.allowed_reads[0].extent.require_present(), ["original"])

    def test_closure_read_alias_is_detached(self) -> None:
        item = obligation(
            "a",
            reads=(ObligationAccess("read", PresenceValue.present({"items": []})),),
        )
        result = DependencyGraph((item,)).close((ref("a"),), expansion_budget=2)
        before = result.to_dict()
        result.allowed_reads[0].extent.require_present()["items"].append("mutated")
        self.assertEqual(result.to_dict(), before)

    def test_reference_evidence_is_not_promoted(self) -> None:
        mode = EvidenceMode.REFERENCE_MODEL
        item = obligation("ref", mode=mode)
        result = DependencyGraph((item,)).close((ref("ref", mode=mode),), expansion_budget=2)
        self.assertTrue(result.is_closed())
        self.assertIs(result.obligations[0].evidence_mode, EvidenceMode.REFERENCE_MODEL)


if __name__ == "__main__":
    unittest.main()
