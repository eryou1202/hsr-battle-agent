# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode, UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.dependency_graph import ClosureStatus, DependencyGraph
from hsr_battle_agent.battle_sandbox.evidence_boundary import certify_native_contract
from hsr_battle_agent.battle_sandbox.gate_certificate import GateCertificateError, certify_closed_preflight
from hsr_battle_agent.battle_sandbox.preflight import (
    ChildObligationRef, DependencyObligation, ObligationAccess,
    ObligationResolution, PreflightResult,
)
from tests.battle_sandbox.test_transaction_plan import make_policy, make_state


def contract(name: str) -> ContractRef:
    return ContractRef(
        contract_id=name, namespace="tests.g01.late", schema_version="1",
        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        content_sha256=(name.encode().hex() + "d" * 64)[:64],
        source_refs=(f"fixture://{name}",),
    )


def ref(name: str, owner: str = "FLOW") -> ChildObligationRef:
    return ChildObligationRef(owner, contract(name))


def handle(name: str) -> UnknownHandle:
    return UnknownHandle(
        blocker_id=name, owner_family="PREFLIGHT", payload={"category": name},
        provenance={"source": "frozen-control-category"},
        required_evidence=("exact native support",),
    )


def obligation(name: str, *, owner: str = "FLOW", resolution=ObligationResolution.RESOLVED,
               children=(), handles=(), writes=()):
    return DependencyObligation(
        owner, contract(name), EvidenceMode.NATIVE_EVIDENCED, resolution,
        children=children, unknown_handles=handles, writes=writes,
    )


def rejected_for_late(owner: str, *, random_resolution=None):
    debit = ObligationAccess(
        "store:resources:energy", PresenceValue.present({"delta": -1})
    )
    prefix = obligation("supported-prefix", writes=(debit,))
    if random_resolution is None:
        late = obligation("late", owner=owner, resolution=ObligationResolution.UNSUPPORTED)
        root = obligation("root", children=(ref("supported-prefix"), ref("late", owner)))
        candidates = (root, prefix, late)
    else:
        blocked = obligation(
            "blocked-arm", owner="RANDOM_ARM", resolution=random_resolution,
            handles=(handle("UNKNOWN-RANDOM"),) if random_resolution is ObligationResolution.UNKNOWN else (),
        )
        branch = obligation(
            "random-branch", owner="RANDOM_BRANCH",
            children=(ref("supported-arm", "RANDOM_ARM"), ref("blocked-arm", "RANDOM_ARM")),
        )
        good = obligation("supported-arm", owner="RANDOM_ARM")
        root = obligation("root", children=(ref("supported-prefix"), ref("random-branch", "RANDOM_BRANCH")))
        candidates = (root, prefix, branch, good, blocked)
    closure = DependencyGraph(candidates).close((ref("root"),), expansion_budget=32)
    return PreflightResult.from_closure(closure)


class TestLatePreflightRejection(unittest.TestCase):
    def assertRejectedWithoutEffects(self, result: PreflightResult, expected: ClosureStatus):
        live = make_state()
        before = live.to_dict()
        self.assertTrue(result.is_rejected())
        self.assertIs(result.closure.status, expected)
        with self.assertRaises(GateCertificateError):
            certify_closed_preflight(
                result, native_contract=certify_native_contract("root"),
                plan_identity="never-authorized", evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
                policy_identity=make_policy(), input_identity="input",
                input_revision="1", state_revision=live.revision,
                contract_ref=contract("root"), contract_revision="1",
            )
        self.assertEqual(live.to_dict(), before)
        self.assertEqual(live.stores["resources"].entries, ())
        self.assertEqual(live.allocator.to_dict(), before["allocator"])
        self.assertEqual(live.rng_state.to_dict(), before["rng_state"])

    def test_later_secondary_target_blocks_supported_prefix(self):
        self.assertRejectedWithoutEffects(rejected_for_late("SECONDARY_TARGET"), ClosureStatus.BLOCKED_UNSUPPORTED)

    def test_later_event_blocks_supported_prefix(self):
        self.assertRejectedWithoutEffects(rejected_for_late("EVENT"), ClosureStatus.BLOCKED_UNSUPPORTED)

    def test_later_global_blocks_supported_prefix(self):
        self.assertRejectedWithoutEffects(rejected_for_late("GLOBAL"), ClosureStatus.BLOCKED_UNSUPPORTED)

    def test_later_terminal_blocks_supported_prefix(self):
        self.assertRejectedWithoutEffects(rejected_for_late("TERMINAL"), ClosureStatus.BLOCKED_UNSUPPORTED)

    def test_unknown_random_arm_blocks_before_any_draw(self):
        result = rejected_for_late("RANDOM", random_resolution=ObligationResolution.UNKNOWN)
        self.assertEqual(
            [x.contract_ref.contract_id for x in result.closure.obligations],
            ["root", "supported-prefix", "random-branch", "supported-arm", "blocked-arm"],
        )
        self.assertRejectedWithoutEffects(result, ClosureStatus.BLOCKED_UNKNOWN)

    def test_unsupported_random_arm_blocks_before_any_draw(self):
        result = rejected_for_late("RANDOM", random_resolution=ObligationResolution.UNSUPPORTED)
        self.assertEqual(
            [x.contract_ref.contract_id for x in result.closure.obligations],
            ["root", "supported-prefix", "random-branch", "supported-arm", "blocked-arm"],
        )
        self.assertRejectedWithoutEffects(result, ClosureStatus.BLOCKED_UNSUPPORTED)

    def test_supported_prefix_remains_diagnostic_only_not_partial_permission(self):
        result = rejected_for_late("EVENT")
        self.assertEqual([x.target for x in result.closure.allowed_writes], ["store:resources:energy"])
        self.assertIsNone(getattr(result, "certificate", None))


if __name__ == "__main__":
    unittest.main()
