# -*- coding: utf-8 -*-
"""Acceptance tests for G01-003 PreflightResult."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_sandbox.dependency_graph import (  # noqa: E402
    ClosureStatus,
    DependencyGraph,
)
from hsr_battle_agent.battle_sandbox.preflight import (  # noqa: E402
    ChildObligationRef,
    DependencyObligation,
    DependencyObligationError,
    ObligationResolution,
    PreflightOutcome,
    PreflightResult,
)


def contract(name: str) -> ContractRef:
    return ContractRef(
        contract_id=name,
        namespace="tests.g01.result",
        schema_version="1",
        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        content_sha256=(name.encode().hex() + "1" * 64)[:64],
        source_refs=(f"fixture://{name}",),
    )


def ref(name: str) -> ChildObligationRef:
    return ChildObligationRef(owner="OWNER", contract_ref=contract(name))


def handle(name: str) -> UnknownHandle:
    return UnknownHandle(
        blocker_id=name,
        owner_family="TEST",
        payload={"nested": [name]},
        provenance={"source": "fixture"},
        required_evidence=("exact evidence",),
    )


def obligation(
    name: str,
    *,
    resolution: ObligationResolution = ObligationResolution.RESOLVED,
    children: tuple[ChildObligationRef, ...] = (),
    handles: tuple[UnknownHandle, ...] = (),
) -> DependencyObligation:
    return DependencyObligation(
        owner="OWNER",
        contract_ref=contract(name),
        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        resolution=resolution,
        children=children,
        unknown_handles=handles,
    )


def close(*items: DependencyObligation, root: str = "root", budget: int = 20):
    return DependencyGraph(items).close((ref(root),), expansion_budget=budget)


class TestTopLevelOutcomes(unittest.TestCase):
    def test_finite_closed_closure_becomes_closed(self) -> None:
        result = PreflightResult.from_closure(close(obligation("root")))
        self.assertIs(result.outcome, PreflightOutcome.CLOSED)
        self.assertTrue(result.is_closed())
        self.assertFalse(result.is_rejected())
        self.assertEqual(result.rejections, ())

    def test_unknown_becomes_rejected(self) -> None:
        closure = close(
            obligation(
                "root",
                resolution=ObligationResolution.UNKNOWN,
                handles=(handle("UNKNOWN-1"),),
            )
        )
        result = PreflightResult.from_closure(closure)
        self.assertIs(result.outcome, PreflightOutcome.REJECTED)
        self.assertEqual(result.rejections[0].reason_code, "PREFLIGHT_BLOCKED_UNKNOWN")
        self.assertEqual(result.rejections[0].unknown_handles[0].blocker_id, "UNKNOWN-1")

    def test_unsupported_becomes_rejected(self) -> None:
        result = PreflightResult.from_closure(
            close(obligation("root", resolution=ObligationResolution.UNSUPPORTED))
        )
        self.assertEqual(result.rejections[0].reason_code, "PREFLIGHT_BLOCKED_UNSUPPORTED")

    def test_missing_child_becomes_rejected(self) -> None:
        result = PreflightResult.from_closure(
            close(obligation("root", children=(ref("missing"),)))
        )
        self.assertEqual(result.rejections[0].reason_code, "PREFLIGHT_BLOCKED_MISSING")

    def test_cycle_becomes_rejected(self) -> None:
        result = PreflightResult.from_closure(
            close(obligation("root", children=(ref("root"),)))
        )
        self.assertEqual(result.rejections[0].reason_code, "PREFLIGHT_BLOCKED_CYCLE")

    def test_unbounded_becomes_rejected(self) -> None:
        closure = close(
            obligation("root", children=(ref("leaf"),)),
            obligation("leaf"),
            budget=1,
        )
        self.assertIs(closure.status, ClosureStatus.BLOCKED_UNBOUNDED)
        result = PreflightResult.from_closure(closure)
        self.assertEqual(result.rejections[0].reason_code, "PREFLIGHT_BLOCKED_UNBOUNDED")

    def test_result_has_no_truthiness(self) -> None:
        result = PreflightResult.from_closure(close(obligation("root")))
        with self.assertRaises(DependencyObligationError):
            bool(result)
        with self.assertRaises(DependencyObligationError):
            bool(result.outcome)


class TestCompleteDiagnostics(unittest.TestCase):
    def test_multiple_blockers_are_all_retained(self) -> None:
        root = obligation("root", children=(ref("u"), ref("x"), ref("missing")))
        unresolved = obligation(
            "u", resolution=ObligationResolution.UNKNOWN, handles=(handle("U"),)
        )
        unsupported = obligation("x", resolution=ObligationResolution.UNSUPPORTED)
        result = PreflightResult.from_closure(close(root, unresolved, unsupported))
        self.assertEqual(
            [item.reason_code for item in result.rejections],
            [
                "PREFLIGHT_BLOCKED_UNKNOWN",
                "PREFLIGHT_BLOCKED_UNSUPPORTED",
                "PREFLIGHT_BLOCKED_MISSING",
            ],
        )

    def test_diagnostic_order_follows_traversal_not_alphabetical_sort(self) -> None:
        root = obligation("root", children=(ref("z"), ref("a")))
        result = PreflightResult.from_closure(close(root))
        self.assertEqual(
            [item.contract_refs[0].contract_id for item in result.rejections],
            ["z", "a"],
        )

    def test_rejection_keeps_owner_reason_request_contract_and_handles(self) -> None:
        unresolved = obligation(
            "root",
            resolution=ObligationResolution.UNKNOWN,
            handles=(handle("U"),),
        )
        rejection = PreflightResult.from_closure(close(unresolved)).rejections[0]
        self.assertEqual(rejection.obligation_owner, "OWNER")
        self.assertEqual(rejection.reason_code, "PREFLIGHT_BLOCKED_UNKNOWN")
        self.assertEqual(rejection.evidence_request, "evidence resolving every UnknownHandle")
        self.assertEqual(rejection.contract_refs[0].contract_id, "root")
        self.assertEqual(rejection.unknown_handles[0].blocker_id, "U")

    def test_a_caller_cannot_omit_the_later_blocker(self) -> None:
        root = obligation("root", children=(ref("z"), ref("a")))
        closure = close(root)
        complete = PreflightResult.from_closure(closure)
        with self.assertRaises(DependencyObligationError):
            PreflightResult(
                outcome=PreflightOutcome.REJECTED,
                closure=closure,
                rejections=complete.rejections[:1],
            )

    def test_a_partial_blocked_closure_cannot_masquerade_as_closed(self) -> None:
        closure = close(obligation("root", children=(ref("missing"),)))
        with self.assertRaises(DependencyObligationError):
            PreflightResult(
                outcome=PreflightOutcome.CLOSED,
                closure=closure,
                rejections=(),
            )

    def test_closed_closure_cannot_be_labelled_rejected(self) -> None:
        closure = close(obligation("root"))
        with self.assertRaises(DependencyObligationError):
            PreflightResult(
                outcome=PreflightOutcome.REJECTED,
                closure=closure,
                rejections=(),
            )


class TestRoundTripIsolationAndNegativeBoundary(unittest.TestCase):
    def test_round_trip_is_exact_for_closed_and_rejected(self) -> None:
        values = (
            PreflightResult.from_closure(close(obligation("root"))),
            PreflightResult.from_closure(
                close(obligation("root", children=(ref("missing"),)))
            ),
        )
        for item in values:
            with self.subTest(outcome=item.outcome.value):
                self.assertEqual(PreflightResult.from_dict(item.to_dict()), item)

    def test_returned_unknown_payload_does_not_mutate_result(self) -> None:
        result = PreflightResult.from_closure(
            close(
                obligation(
                    "root",
                    resolution=ObligationResolution.UNKNOWN,
                    handles=(handle("U"),),
                )
            )
        )
        before = result.to_dict()
        result.rejections[0].unknown_handles[0].payload["nested"].append("MUTATED")
        self.assertEqual(result.to_dict(), before)

    def test_returned_closure_does_not_mutate_result(self) -> None:
        result = PreflightResult.from_closure(close(obligation("root")))
        self.assertIsNot(result.closure, result.closure)
        self.assertEqual(result.closure.to_dict(), result.to_dict()["closure"])

    def test_result_exposes_no_gate_state_or_execution_surface(self) -> None:
        forbidden = {
            "issue_certificate", "certificate", "execute", "apply", "commit",
            "mutate_state", "draw_rng", "allocate",
        }
        self.assertTrue(forbidden.isdisjoint(dir(PreflightResult)))


if __name__ == "__main__":
    unittest.main()
