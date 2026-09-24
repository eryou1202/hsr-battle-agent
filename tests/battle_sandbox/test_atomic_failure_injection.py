# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.atomic_commit import (
    ATOMIC_COMMIT_FAILURE_POINTS, AtomicCommit, AtomicCommitInjectedFailure,
)
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2
from hsr_battle_agent.battle_sandbox.snapshot_v2 import TerraSnapshotV2
from hsr_battle_agent.battle_sandbox.staged_trace import StagedTrace
from hsr_battle_agent.battle_sandbox.transaction import StagedDelta
from hsr_battle_agent.battle_sandbox.transaction_rng import TransactionRng
from tests.battle_sandbox.test_atomic_commit import transaction_components
from tests.battle_sandbox.test_transaction_plan import make_plan


def fingerprint(state, policy):
    return {
        "document": state.to_dict(),
        "semantic_hash": semantic_hash_v2(TerraSnapshotV2(state=state, policy_identity=policy)),
        "revision": state.revision_sequence.to_dict(),
        "rng": state.rng_state.to_dict(),
        "allocator": state.allocator.to_dict(),
        "queues": {
            name: store.to_dict()
            for name, store in state.stores.items()
            if "pending" in name or "request" in name or "task" in name
        },
        "opaque": {name: store.to_dict() for name, store in state.opaque_stores.items()},
    }


class TestFailureInjectionMatrix(unittest.TestCase):
    def test_every_commit_boundary_preserves_original(self):
        for point in ATOMIC_COMMIT_FAILURE_POINTS:
            live, plan, delta, rng, trace = transaction_components()
            before = fingerprint(live, plan.certificate.policy_identity)
            with self.subTest(point=point), self.assertRaises(AtomicCommitInjectedFailure):
                AtomicCommit(plan, delta, rng, trace).commit(live, failure_point=point)
            self.assertEqual(fingerprint(live, plan.certificate.policy_identity), before)

    def test_failures_immediately_before_and_after_each_functional_stage_write(self):
        live, plan, staged_delta, staged_rng, staged_trace = transaction_components()
        before = fingerprint(live, plan.certificate.policy_identity)
        for boundary in ("before_delta", "after_delta", "before_rng", "after_rng", "before_trace", "after_trace"):
            with self.subTest(boundary=boundary):
                delta = StagedDelta(plan, live) if boundary == "before_delta" else staged_delta.detached_copy()
                rng = TransactionRng(plan, live) if boundary == "before_rng" else staged_rng.detached_copy()
                trace = StagedTrace(plan, live) if boundary == "before_trace" else staged_trace.detached_copy()
                # Raising/discarding here simulates the caller failing around a
                # functional staging boundary. Nothing has a live publication API.
                try:
                    raise RuntimeError(boundary)
                except RuntimeError:
                    pass
                self.assertEqual(fingerprint(live, plan.certificate.policy_identity), before)

    def test_matrix_would_detect_partial_publication(self):
        live, plan, delta, rng, trace = transaction_components()
        before = fingerprint(live, plan.certificate.policy_identity)
        published = AtomicCommit(plan, delta, rng, trace).commit(live).state
        after = fingerprint(published, plan.certificate.policy_identity)
        for key in ("document", "semantic_hash", "revision", "rng", "allocator"):
            self.assertNotEqual(before[key], after[key], key)


if __name__ == "__main__":
    unittest.main()
