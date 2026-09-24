# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import ContractRef, EvidenceMode
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.dependency_graph import DependencyGraph
from hsr_battle_agent.battle_sandbox.evidence_boundary import certify_native_contract
from hsr_battle_agent.battle_sandbox.gate_certificate import certify_closed_preflight
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.identity import IdentityAllocator
from hsr_battle_agent.battle_sandbox.preflight import (
    ChildObligationRef, DependencyObligation, ObligationAccess,
    ObligationResolution, PreflightResult,
)
from hsr_battle_agent.battle_sandbox.revision import (
    RevisionAndTransactionSequence, StateRevision,
)
from hsr_battle_agent.battle_sandbox.rng import SandboxRng
from hsr_battle_agent.battle_sandbox.snapshot_v2 import SnapshotPolicyIdentity, TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.state_v2 import TerraBattleState
from hsr_battle_agent.battle_sandbox.transaction import (
    TransactionError, TransactionOperation, plan_transaction,
    transaction_plan_identity,
)


def make_state() -> TerraBattleState:
    return TerraBattleState(
        revision_sequence=RevisionAndTransactionSequence(
            StateRevision(7, "snapshot-7", "battle"), 11, 13
        ),
        allocator=IdentityAllocator(),
        rng_state=SandboxRng(90210),
    )


def make_policy() -> SnapshotPolicyIdentity:
    return SnapshotPolicyIdentity(
        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        evidence_vocabulary_version="1",
        profile_id="strict-profile", profile_version="1",
        profile_content_sha256="a" * 64,
        rule_set_id="strict-rules", rule_set_version="1",
        rule_set_content_sha256="b" * 64,
    )


def make_contract() -> ContractRef:
    return ContractRef(
        contract_id="transaction", namespace="tests.g01.transaction",
        schema_version="1", evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        content_sha256="c" * 64, source_refs=("fixture://transaction",),
    )


def make_certificate(state, operations, *, writes=(), reads=()):
    ref = make_contract()
    obligation = DependencyObligation(
        "TRANSACTION", ref, EvidenceMode.NATIVE_EVIDENCED,
        ObligationResolution.RESOLVED, reads=reads, writes=writes,
    )
    closure = DependencyGraph((obligation,)).close(
        (ChildObligationRef("TRANSACTION", ref),), expansion_budget=32
    )
    result = PreflightResult.from_closure(closure)
    return certify_closed_preflight(
        result,
        native_contract=certify_native_contract("transaction"),
        plan_identity=transaction_plan_identity(operations),
        evidence_mode=EvidenceMode.NATIVE_EVIDENCED,
        policy_identity=make_policy(), input_identity="input:1",
        input_revision="input-revision:1", state_revision=state.revision,
        contract_ref=ref, contract_revision="contract-revision:1",
    )


def make_plan(*, operations=None, writes=(), reads=()):
    state = make_state()
    ops = operations or (
        TransactionOperation("alpha", {"items": [1]}),
        TransactionOperation("alpha", {"items": [1]}),
    )
    cert = make_certificate(state, ops, writes=writes, reads=reads)
    return state, cert, plan_transaction(state, cert, ops)


class TestTransactionPlan(unittest.TestCase):
    def test_planning_is_pure_across_complete_semantic_state(self):
        state = make_state()
        operations = (TransactionOperation("noop", {"tuple": (1, 2)}),)
        cert = make_certificate(state, operations)
        before = state.to_dict()
        before_hash = semantic_hash_v2(
            TerraSnapshotV2(state=state, policy_identity=cert.policy_identity)
        )
        plan = plan_transaction(state, cert, operations)
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(
            semantic_hash_v2(
                TerraSnapshotV2(state=state, policy_identity=cert.policy_identity)
            ),
            before_hash,
        )
        self.assertEqual(plan.source_state_hash, before_hash)

    def test_order_duplicates_and_tuple_list_identity_are_preserved(self):
        tuple_ops = (TransactionOperation("x", (1, 2)), TransactionOperation("x", (1, 2)))
        list_ops = (TransactionOperation("x", [1, 2]), TransactionOperation("x", [1, 2]))
        self.assertNotEqual(transaction_plan_identity(tuple_ops), transaction_plan_identity(list_ops))
        state = make_state()
        plan = plan_transaction(state, make_certificate(state, tuple_ops), tuple_ops)
        self.assertEqual([x.operation_id for x in plan.operations], ["x", "x"])
        self.assertIsInstance(plan.operations[0].payload, tuple)

    def test_plan_cannot_broaden_certificate_permissions(self):
        write = ObligationAccess("store:resources:hp", PresenceValue.present(5))
        state, cert, plan = make_plan(writes=(write,))
        self.assertEqual(plan.allowed_writes, cert.allowed_writes)
        exported = plan.allowed_writes[0].extent.require_present()
        self.assertEqual(exported, 5)
        self.assertFalse(hasattr(plan, "add_permission"))

    def test_mismatched_operation_sequence_rejects(self):
        state = make_state()
        original = (TransactionOperation("a", {}),)
        cert = make_certificate(state, original)
        with self.assertRaises(TransactionError):
            plan_transaction(state, cert, (TransactionOperation("b", {}),))

    def test_stale_state_rejects(self):
        state = make_state()
        ops = (TransactionOperation("a", {}),)
        cert = make_certificate(state, ops)
        changed = TerraBattleState.from_dict(state.to_dict())
        document = changed.to_dict()
        document["revision_and_transaction_sequence"]["published_revision"]["counter"] = 8
        changed = TerraBattleState.from_dict(document)
        with self.assertRaises(TransactionError):
            plan_transaction(changed, cert, ops)

    def test_non_certificate_and_reference_cannot_plan(self):
        with self.assertRaises(TransactionError):
            plan_transaction(make_state(), True, ())

    def test_construction_and_read_aliases_are_detached(self):
        payload = {"items": []}
        op = TransactionOperation("x", payload)
        state = make_state()
        plan = plan_transaction(state, make_certificate(state, (op,)), (op,))
        before = plan.to_dict()
        payload["items"].append("input")
        plan.operations[0].payload["items"].append("output")
        self.assertEqual(plan.to_dict(), before)

    def test_plan_exposes_no_execution_or_mutation_surface(self):
        _, _, plan = make_plan()
        forbidden = {"execute", "apply", "commit", "draw_rng", "allocate", "stage"}
        self.assertTrue(forbidden.isdisjoint(dir(plan)))
        with self.assertRaises(TransactionError):
            bool(plan)


if __name__ == "__main__":
    unittest.main()
